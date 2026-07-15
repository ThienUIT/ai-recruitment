"""Append-only, tenant-scoped audit hash chain.

Phase 1 locks the latest tenant event while appending. This serializes updates
once a chain exists, but two simultaneous first events can still race. A
tenant-level advisory lock is reserved for the operational hardening phase.
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
        self._repository = AuditEventRepository(session)

    def append_event(self, tenant_id: str, payload: AuditAppendPayload) -> AuditEvent:
        metadata = payload.get("metadata", {})
        _validate_metadata(metadata)
        previous = self._repository.latest_for_tenant(tenant_id, lock=True)
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
            previous_event_hash=previous.event_hash if previous else None,
            event_hash="",
        )
        event.created_at = naive_utc_now()
        event.event_hash = calculate_event_hash(event)
        self._repository.append(event)
        return event

    def verify_chain(self, tenant_id: str) -> AuditChainVerification:
        events = self._repository.chain_for_tenant(tenant_id)
        previous_hash: str | None = None
        for event in events:
            if event.previous_event_hash != previous_hash or event.event_hash != calculate_event_hash(event):
                return AuditChainVerification(False, len(events), event.id)
            previous_hash = event.event_hash
        return AuditChainVerification(True, len(events))

    def list_events(self, tenant_id: str, *, page: int, limit: int) -> tuple[list[AuditEvent], int]:
        return self._repository.list_for_tenant(tenant_id, page=page, limit=limit)
