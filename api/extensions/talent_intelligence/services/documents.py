"""Tenant-scoped CV ingestion, processing, retention, and privacy gates."""

import json
from collections import defaultdict
from collections.abc import Generator
from datetime import timedelta
from typing import Literal, Protocol, cast, overload

from sqlalchemy.orm import Session

from configs import dify_config
from extensions.ext_storage import storage
from libs.datetime_utils import naive_utc_now
from models import Account

from ..audit import AuditService, pseudonymize_candidate_id
from ..documents import (
    ClamAVScanner,
    FileValidationPolicy,
    LocalDocumentParser,
    LocalPIIRecognizer,
    PIIEncryptionProvider,
    PIIMasker,
    RequiresOCRError,
    detect_masked_leaks,
    validate_upload,
)
from ..documents.malware import MalwareScannerUnavailableError
from ..documents.parsers import ParsedDocument
from ..errors import ConflictError, NotFoundError
from ..models import CandidateDocument, CandidateDocumentStatus, CandidatePII, CandidateProcessingStatus
from ..repositories import (
    CandidateDocumentRepository,
    CandidatePIIRepository,
    CandidateProfileRepository,
    CandidateRepository,
)


class PrivateStorage(Protocol):
    def save(self, filename: str, data: bytes): ...
    @overload
    def load(self, filename: str, /, *, stream: Literal[False] = False) -> bytes: ...
    @overload
    def load(self, filename: str, /, *, stream: Literal[True]) -> Generator: ...
    def load(self, filename: str, /, *, stream: bool = False) -> bytes | Generator: ...
    def exists(self, filename: str) -> bool: ...
    def delete(self, filename: str): ...


_TERMINAL = {
    CandidateDocumentStatus.INFECTED,
    CandidateDocumentStatus.READY,
    CandidateDocumentStatus.PII_REVIEW_REQUIRED,
    CandidateDocumentStatus.REQUIRES_OCR,
    CandidateDocumentStatus.RAW_DELETED,
    CandidateDocumentStatus.DELETED,
}
_REPROCESSABLE = {
    CandidateDocumentStatus.PII_REVIEW_REQUIRED,
    CandidateDocumentStatus.REQUIRES_OCR,
    CandidateDocumentStatus.PROCESSING_FAILED,
}


def assert_document_safe_for_downstream(document: CandidateDocument) -> None:
    if (
        document.status not in {CandidateDocumentStatus.READY, CandidateDocumentStatus.RAW_DELETED}
        or document.manual_review_required
        or not document.masked_artifact_object_key
    ):
        raise ConflictError("Document has not passed the privacy gate.", code="privacy_gate_blocked")


def _audit(
    session: Session,
    document: CandidateDocument,
    event_type: str,
    correlation_id: str,
    *,
    result: str = "success",
    metadata: dict[str, object] | None = None,
) -> None:
    AuditService(session).append_event(
        document.tenant_id,
        {
            "event_type": event_type,
            "actor_id": document.uploaded_by,
            "actor_role": "system",
            "action": event_type,
            "result": result,
            "correlation_id": correlation_id,
            "pseudonymous_candidate_id": pseudonymize_candidate_id(document.tenant_id, document.candidate_id),
            "object_type": "candidate_document",
            "object_id": document.id,
            "metadata": metadata or {},
        },
    )


def _delete_object_verified(object_storage: PrivateStorage, key: str | None) -> None:
    if not key:
        return
    object_storage.delete(key)
    if object_storage.exists(key):
        raise RuntimeError("Object deletion could not be verified.")


def _delete_raw(object_storage: PrivateStorage, document: CandidateDocument) -> None:
    _delete_object_verified(object_storage, document.raw_object_key)
    document.raw_object_key = None
    document.raw_deleted_at = document.raw_deleted_at or naive_utc_now()


class CandidateDocumentService:
    def __init__(self, session: Session, object_storage: PrivateStorage = storage) -> None:
        self._session = session
        self._storage = object_storage
        self._documents = CandidateDocumentRepository(session)
        self._candidates = CandidateRepository(session)

    def upload(
        self,
        tenant_id: str,
        account: Account,
        candidate_id: str,
        data: bytes,
        filename: str | None,
        content_type: str | None,
        correlation_id: str,
    ) -> CandidateDocument:
        candidate = self._candidates.get_by_id_for_tenant(candidate_id, tenant_id)
        if candidate is None:
            raise NotFoundError("Candidate not found.")
        validated = validate_upload(
            data,
            filename,
            content_type,
            FileValidationPolicy(
                max_size_bytes=dify_config.TI_MAX_CV_SIZE_MB * 1024 * 1024,
                max_docx_uncompressed_bytes=dify_config.TI_MAX_DOCX_UNCOMPRESSED_MB * 1024 * 1024,
            ),
        )
        document = CandidateDocument(
            tenant_id=tenant_id,
            candidate_id=candidate_id,
            mime_type=validated.mime_type,
            file_extension=validated.extension,
            size_bytes=validated.size_bytes,
            sha256=validated.sha256,
            uploaded_by=account.id,
            raw_delete_at=naive_utc_now() + timedelta(days=dify_config.TI_RAW_CV_RETENTION_DAYS),
        )
        self._documents.add(document)
        self._session.flush()
        key = f"talent-intelligence/quarantine/{tenant_id}/{document.id}/raw{validated.extension}"
        self._storage.save(key, validated.data)
        document.raw_object_key = key
        document.status = CandidateDocumentStatus.SCAN_PENDING
        candidate.processing_status = CandidateProcessingStatus.PROCESSING
        _audit(self._session, document, "candidate.document_uploaded", correlation_id)
        self._session.commit()
        return document

    def get(self, tenant_id: str, candidate_id: str, document_id: str) -> CandidateDocument:
        if self._candidates.get_by_id_for_tenant(candidate_id, tenant_id) is None:
            raise NotFoundError("Candidate not found.")
        document = self._documents.get_by_id_for_tenant(document_id, tenant_id)
        if document is None or document.candidate_id != candidate_id:
            raise NotFoundError("Candidate document not found.")
        return document

    def list(self, tenant_id: str, candidate_id: str) -> list[CandidateDocument]:
        if self._candidates.get_by_id_for_tenant(candidate_id, tenant_id) is None:
            raise NotFoundError("Candidate not found.")
        return self._documents.list_for_candidate_for_tenant(candidate_id, tenant_id)

    def reprocess(self, tenant_id: str, candidate_id: str, document_id: str, correlation_id: str) -> CandidateDocument:
        document = self.get(tenant_id, candidate_id, document_id)
        if document.status not in _REPROCESSABLE:
            raise ConflictError("Document is not reprocessable in its current state.", code="invalid_state")
        if document.raw_deleted_at or not document.raw_object_key:
            raise ConflictError("Raw document is no longer available.", code="raw_unavailable")
        document.status = CandidateDocumentStatus.SCAN_PENDING
        document.error_code = None
        document.safe_error_message = None
        _audit(self._session, document, "candidate.document_reprocess_requested", correlation_id)
        self._session.commit()
        return document

    def delete_raw(self, tenant_id: str, candidate_id: str, document_id: str, correlation_id: str) -> CandidateDocument:
        document = self.get(tenant_id, candidate_id, document_id)
        _delete_raw(self._storage, document)
        if document.status == CandidateDocumentStatus.READY:
            document.status = CandidateDocumentStatus.RAW_DELETED
        _audit(self._session, document, "candidate.document_raw_deleted", correlation_id)
        self._session.commit()
        return document


class CandidateDocumentProcessor:
    def __init__(self, session: Session, object_storage: PrivateStorage = storage) -> None:
        self._session = session
        self._storage = object_storage
        self._documents = CandidateDocumentRepository(session)
        self._candidates = CandidateRepository(session)
        self._pii = CandidatePIIRepository(session)

    def process(self, tenant_id: str, document_id: str, correlation_id: str) -> CandidateDocument:
        document = self._documents.get_by_id_for_tenant(document_id, tenant_id, lock=True)
        if document is None:
            raise NotFoundError("Candidate document not found.")
        if document.status in _TERMINAL:
            return document
        document.processing_attempts += 1
        document.processing_started_at = naive_utc_now()
        try:
            self._process(document, correlation_id)
        except RequiresOCRError:
            document.status = CandidateDocumentStatus.REQUIRES_OCR
            document.requires_ocr = True
            _audit(self._session, document, "candidate.document_ocr_required", correlation_id)
        # The security boundary persists only a safe code and never the source exception.
        except Exception:
            document.status = CandidateDocumentStatus.PROCESSING_FAILED
            document.error_code = "secure_processing_failed"
            document.safe_error_message = "Document could not be processed securely."
            _audit(
                self._session,
                document,
                "candidate.document_processing_failed",
                correlation_id,
                result="failed",
                metadata={"error_code": document.error_code},
            )
        document.processing_completed_at = naive_utc_now()
        self._session.commit()
        return document

    def _process(self, document: CandidateDocument, correlation_id: str) -> None:
        if not document.raw_object_key or not self._storage.exists(document.raw_object_key):
            raise RuntimeError("Raw document is unavailable.")
        raw = self._storage.load(document.raw_object_key)
        if dify_config.TI_MALWARE_SCAN_ENABLED:
            scan = ClamAVScanner(dify_config.TI_CLAMAV_HOST, dify_config.TI_CLAMAV_PORT).scan(raw)
        elif dify_config.TI_ALLOW_UNSCANNED_UPLOADS_IN_DEVELOPMENT:
            scan = None
        else:
            raise MalwareScannerUnavailableError("Malware scanning is required.")
        if scan is not None and not scan.clean:
            document.malware_scan_status = "infected"
            document.malware_scanner_version = scan.scanner_version
            document.status = CandidateDocumentStatus.INFECTED
            _delete_raw(self._storage, document)
            _audit(
                self._session,
                document,
                "candidate.document_malware_detected",
                correlation_id,
                metadata={"scanner": scan.scanner_version},
            )
            return
        document.malware_scan_status = "clean" if scan else "development_bypass"
        document.malware_scanner_version = scan.scanner_version if scan else "explicit-development-bypass"
        document.status = CandidateDocumentStatus.PARSING
        parsed = LocalDocumentParser(
            max_pdf_pages=dify_config.TI_MAX_PDF_PAGES,
            max_text_chars=dify_config.TI_MAX_EXTRACTED_TEXT_CHARS,
        ).parse(raw, document.file_extension)
        document.parser_name = parsed.parser_name
        document.parser_version = parsed.parser_version
        document.status = CandidateDocumentStatus.MASKING
        masked = PIIMasker().mask(parsed.text, LocalPIIRecognizer().recognize(parsed.text))
        leak = detect_masked_leaks(masked.text)
        document.pii_entity_counts = cast(dict[str, object], masked.entity_counts)
        document.pii_risk_score = masked.risk_score
        if not leak.safe:
            document.status = CandidateDocumentStatus.PII_REVIEW_REQUIRED
            document.manual_review_required = True
            document.error_code = "pii_leak_detected"
            document.safe_error_message = "Document requires privacy review."
            _audit(
                self._session,
                document,
                "candidate.document_privacy_gate_blocked",
                correlation_id,
                result="blocked",
                metadata={"remaining_entity_counts": leak.entity_counts},
            )
            return
        self._persist_masked(
            document,
            parsed,
            masked.text,
            masked.placeholder_map,
            masked.entity_counts,
            masked.risk_score,
        )
        document.status = CandidateDocumentStatus.READY
        candidate = self._candidates.get_by_id_for_tenant(document.candidate_id, document.tenant_id)
        if candidate is not None:
            candidate.processing_status = CandidateProcessingStatus.PROCESSED
        _audit(self._session, document, "candidate.document_processing_completed", correlation_id)
        if dify_config.TI_DELETE_RAW_CV_AFTER_EXTRACTION:
            _delete_raw(self._storage, document)
            document.status = CandidateDocumentStatus.RAW_DELETED

    def _persist_masked(
        self,
        document: CandidateDocument,
        parsed: ParsedDocument,
        masked_text: str,
        placeholder_map: dict[str, str],
        entity_counts: dict[str, int],
        risk_score: float,
    ) -> None:
        provider = PIIEncryptionProvider.from_json(
            dify_config.TI_PII_ENCRYPTION_KEYS_JSON,
            dify_config.TI_PII_ACTIVE_KEY_VERSION,
        )
        grouped: dict[str, list[str]] = defaultdict(list)
        for placeholder, value in placeholder_map.items():
            grouped[placeholder[1:].split("_", 1)[0]].append(value)
        pii = self._pii.get_for_candidate_for_tenant(document.candidate_id, document.tenant_id)
        if pii is None:
            pii = CandidatePII(
                candidate_id=document.candidate_id,
                tenant_id=document.tenant_id,
                encryption_key_version=provider.active_version,
            )
            self._pii.add(pii)
        pii.encryption_key_version = provider.active_version
        pii.updated_from_document_id = document.id
        pii.pii_detection_metadata = {"entity_counts": entity_counts, "risk_score": risk_score}
        fields = {
            "encrypted_name": grouped.get("PERSON", []),
            "encrypted_email": grouped.get("EMAIL", []),
            "encrypted_phone": grouped.get("PHONE", []),
            "encrypted_address": grouped.get("ADDRESS", []),
            "encrypted_personal_urls": grouped.get("PERSONAL", [])
            + grouped.get("LINKEDIN", [])
            + grouped.get("GITHUB", []),
        }
        for field_name, values in fields.items():
            aad = provider.aad(document.tenant_id, document.candidate_id, field_name)
            setattr(pii, field_name, provider.encrypt(json.dumps(values, ensure_ascii=False), aad=aad))
        pii.encrypted_placeholder_map = provider.encrypt(
            json.dumps(placeholder_map, ensure_ascii=False, sort_keys=True),
            aad=provider.aad(document.tenant_id, document.candidate_id, "placeholder_map"),
        )
        artifact = json.dumps(
            {
                "blocks": [{"index": index, "text": text} for index, text in enumerate(masked_text.splitlines())],
                "document_id": document.id,
                "parser": {"name": parsed.parser_name, "version": parsed.parser_version},
                "schema_version": "v1",
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
        key = f"talent-intelligence/masked/{document.tenant_id}/{document.id}/document.json"
        self._storage.save(key, artifact)
        document.masked_artifact_object_key = key


class RawRetentionService:
    def __init__(self, session: Session, object_storage: PrivateStorage = storage) -> None:
        self._session = session
        self._storage = object_storage
        self._documents = CandidateDocumentRepository(session)

    def delete_expired(self, correlation_id: str, *, limit: int = 100) -> int:
        documents = self._documents.expired_raw(naive_utc_now(), limit=limit)
        for document in documents:
            _delete_raw(self._storage, document)
            if document.status == CandidateDocumentStatus.READY:
                document.status = CandidateDocumentStatus.RAW_DELETED
            _audit(self._session, document, "candidate.document_raw_expired", correlation_id)
        self._session.commit()
        return len(documents)


class CandidateDeletionService:
    def __init__(self, session: Session, object_storage: PrivateStorage = storage) -> None:
        self._session = session
        self._storage = object_storage
        self._candidates = CandidateRepository(session)
        self._documents = CandidateDocumentRepository(session)
        self._pii = CandidatePIIRepository(session)
        self._profiles = CandidateProfileRepository(session)

    def ensure_exists(self, tenant_id: str, candidate_id: str) -> None:
        if self._candidates.get_including_deleted_for_tenant(candidate_id, tenant_id) is None:
            raise NotFoundError("Candidate not found.")

    def execute(self, tenant_id: str, candidate_id: str, correlation_id: str) -> bool:
        candidate = self._candidates.get_including_deleted_for_tenant(candidate_id, tenant_id)
        if candidate is None:
            raise NotFoundError("Candidate not found.")
        if candidate.processing_status == CandidateProcessingStatus.DELETED:
            return False
        if candidate.processing_status != CandidateProcessingStatus.DELETION_REQUESTED:
            raise ConflictError("Candidate deletion has not been requested.", code="deletion_not_requested")
        documents = self._documents.list_for_candidate_for_tenant(candidate_id, tenant_id)
        for document in documents:
            _delete_object_verified(self._storage, document.raw_object_key)
            _delete_object_verified(self._storage, document.masked_artifact_object_key)
        self._pii.delete_for_candidate_for_tenant(candidate_id, tenant_id)
        self._profiles.delete_for_candidate_for_tenant(candidate_id, tenant_id)
        self._session.flush()
        self._documents.delete_for_candidate_for_tenant(candidate_id, tenant_id)
        candidate.external_reference = None
        candidate.consent_scope = {}
        candidate.processing_status = CandidateProcessingStatus.DELETED
        candidate.deleted_at = naive_utc_now()
        AuditService(self._session).append_event(
            tenant_id,
            {
                "event_type": "candidate.deletion_completed",
                "actor_id": candidate.created_by,
                "actor_role": "system",
                "action": "candidate.deletion_completed",
                "result": "success",
                "correlation_id": correlation_id,
                "pseudonymous_candidate_id": pseudonymize_candidate_id(tenant_id, candidate_id),
                "object_type": "candidate",
                "object_id": candidate_id,
                "metadata": {"documents_deleted": len(documents)},
            },
        )
        self._session.commit()
        return True
