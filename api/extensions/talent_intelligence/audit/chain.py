"""Database-enforced append-only, tenant-scoped audit hash chain.

Every append locks a dedicated tenant chain-head row. The event insert and head
advance share the caller's transaction, so API and worker processes serialize
without process-local locks. Sequence numbers, not timestamps, define order.
"""

import hashlib
import json
import re
from dataclasses import dataclass
from typing import TypedDict

from sqlalchemy.orm import Session

from libs.datetime_utils import naive_utc_now

from ..errors import ValidationError
from ..models import AuditEvent
from ..repositories import AuditEventRepository

_EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?84|0)[ .-]?[1-9](?:[ .-]?\d){8,9}(?!\d)")
_BANNED_METADATA_KEYS = {
    "address",
    "email",
    "encrypted_address",
    "encrypted_email",
    "encrypted_name",
    "encrypted_personal_urls",
    "encrypted_phone",
    "full_name",
    "name",
    "phone",
    "raw_cv",
    "raw_cv_text",
}


class AuditAppendPayload(TypedDict, total=False):
    event_type: str
    actor_id: str
    actor_role: str | None
    action: str
    result: str
    correlation_id: str
    pseudonymous_candidate_id: str | None
    job_id: str | None
    object_type: str | None
    object_id: str | None
    policy_version: str | None
    model_versions: dict[str, object]
    metadata: dict[str, object]


@dataclass(frozen=True)
class AuditChainVerification:
    valid: bool
    event_count: int
    first_invalid_event_id: str | None = None
    failure_reason: str | None = None


def _canonical_event_payload(event: AuditEvent) -> dict[str, object]:
    return {
        "tenant_id": event.tenant_id,
        "event_type": event.event_type,
        "actor_id": event.actor_id,
        "actor_role": event.actor_role,
        "pseudonymous_candidate_id": event.pseudonymous_candidate_id,
        "job_id": event.job_id,
        "object_type": event.object_type,
        "object_id": event.object_id,
        "action": event.action,
        "result": event.result,
        "policy_version": event.policy_version,
        "model_versions": event.model_versions,
        "correlation_id": event.correlation_id,
        "metadata": event.metadata_,
        "previous_event_hash": event.previous_event_hash,
        "created_at": event.created_at.isoformat(timespec="microseconds"),
    }


def calculate_event_hash(event: AuditEvent) -> str:
    canonical = json.dumps(_canonical_event_payload(event), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def pseudonymize_candidate_id(tenant_id: str, candidate_id: str) -> str:
    return hashlib.sha256(f"{tenant_id}:{candidate_id}".encode()).hexdigest()


def _validate_metadata(value: object, *, key: str | None = None) -> None:
    if key is not None and key.lower() in _BANNED_METADATA_KEYS:
        raise ValidationError(f"Audit metadata key '{key}' is not allowed.")
    if isinstance(value, str) and (_EMAIL_PATTERN.search(value) or _PHONE_PATTERN.search(value)):
        raise ValidationError("Audit metadata contains an obvious PII pattern.")
    if isinstance(value, dict):
        for nested_key, nested_value in value.items():
            _validate_metadata(nested_value, key=str(nested_key))
    elif isinstance(value, list):
        for item in value:
            _validate_metadata(item)


class AuditService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repository = AuditEventRepository(session)

    def append_event(self, tenant_id: str, payload: AuditAppendPayload) -> AuditEvent:
        metadata = payload.get("metadata", {})
        _validate_metadata(metadata)
        head = self._repository.lock_chain_head(tenant_id)
        event = AuditEvent(
            tenant_id=tenant_id,
            event_type=payload["event_type"],
            actor_id=payload["actor_id"],
            actor_role=payload.get("actor_role"),
            action=payload["action"],
            result=payload["result"],
            correlation_id=payload["correlation_id"],
            pseudonymous_candidate_id=payload.get("pseudonymous_candidate_id"),
            job_id=payload.get("job_id"),
            object_type=payload.get("object_type"),
            object_id=payload.get("object_id"),
            policy_version=payload.get("policy_version"),
            model_versions=payload.get("model_versions", {}),
            metadata_=metadata,
            previous_event_hash=head.last_event_hash,
            event_hash="",
        )
        event.chain_sequence = head.last_sequence + 1
        event.created_at = naive_utc_now()
        event.event_hash = calculate_event_hash(event)
        self._repository.append(event)
        # Flush only the audit row. Other pending domain writes may intentionally
        # defer their own constraint handling until the service commit boundary.
        self._session.flush([event])
        head.last_event_id = event.id
        head.last_event_hash = event.event_hash
        head.last_sequence = event.chain_sequence
        return event

    def verify_chain(self, tenant_id: str) -> AuditChainVerification:
        events = self._repository.chain_for_tenant(tenant_id)
        head = self._repository.head_for_tenant(tenant_id)
        if not events:
            empty_head = (
                head is not None
                and head.last_event_id is None
                and head.last_event_hash is None
                and head.last_sequence == 0
            )
            if head is None or empty_head:
                return AuditChainVerification(True, 0)
            return AuditChainVerification(False, 0, failure_reason="chain_head_not_empty")
        if head is None:
            return AuditChainVerification(False, len(events), events[-1].id, "chain_head_missing")
        previous_hash: str | None = None
        for expected_sequence, event in enumerate(events, start=1):
            if event.chain_sequence != expected_sequence:
                return AuditChainVerification(False, len(events), event.id, "invalid_chain_sequence")
            if event.previous_event_hash != previous_hash:
                return AuditChainVerification(False, len(events), event.id, "previous_hash_mismatch")
            if event.event_hash != calculate_event_hash(event):
                return AuditChainVerification(False, len(events), event.id, "event_hash_mismatch")
            previous_hash = event.event_hash
        last_event = events[-1]
        if (
            head.last_event_id != last_event.id
            or head.last_event_hash != last_event.event_hash
            or head.last_sequence != last_event.chain_sequence
        ):
            return AuditChainVerification(False, len(events), last_event.id, "chain_head_mismatch")
        return AuditChainVerification(True, len(events))

    def list_events(self, tenant_id: str, *, page: int, limit: int) -> tuple[list[AuditEvent], int]:
        return self._repository.list_for_tenant(tenant_id, page=page, limit=limit)
