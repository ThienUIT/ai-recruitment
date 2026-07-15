"""Focused Phase 1 persistence, isolation, and transition tests."""

from collections.abc import Iterator
from typing import cast
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
import sqlalchemy as sa
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from extensions.talent_intelligence.audit import AuditService
from extensions.talent_intelligence.errors import ConflictError, NotFoundError, ValidationError
from extensions.talent_intelligence.models import (
    AuditChainHead,
    AuditEvent,
    Candidate,
    CandidatePII,
    CandidateProcessingStatus,
    CandidateProfile,
    JobProfile,
    JobStatus,
    ScoringPolicy,
)
from extensions.talent_intelligence.permissions import TalentAction, require_permission
from extensions.talent_intelligence.repositories import AuditEventRepository, CandidateRepository
from extensions.talent_intelligence.schemas.domain import (
    CandidateCreatePayload,
    CandidateProfilePayload,
    CandidateResponse,
    CandidateUpdatePayload,
    JobCreatePayload,
    JobUpdatePayload,
    ScoringPolicyCreatePayload,
)
from extensions.talent_intelligence.seeds import seed_development_data
from extensions.talent_intelligence.services import (
    CandidateProfileService,
    CandidateService,
    JobService,
    ScoringPolicyService,
)
from models import Account


@pytest.fixture
def session() -> Iterator[Session]:
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record) -> None:
        connection.execute("PRAGMA foreign_keys=ON")

    tables: list[sa.Table] = [
        cast(sa.Table, Candidate.__table__),
        cast(sa.Table, CandidatePII.__table__),
        cast(sa.Table, CandidateProfile.__table__),
        cast(sa.Table, JobProfile.__table__),
        cast(sa.Table, ScoringPolicy.__table__),
        cast(sa.Table, AuditChainHead.__table__),
        cast(sa.Table, AuditEvent.__table__),
    ]
    Candidate.metadata.create_all(engine, tables=tables)
    with Session(engine, expire_on_commit=False) as database_session:
        yield database_session
    Candidate.metadata.drop_all(engine, tables=list(reversed(tables)))
    engine.dispose()


def _id() -> str:
    return str(uuid4())


def _account(*, can_edit: bool = True, is_admin: bool = True) -> Account:
    account = MagicMock(spec=Account)
    account.id = _id()
    account.current_role = "admin" if is_admin else "normal"
    account.has_edit_permission = can_edit
    account.is_admin_or_owner = is_admin
    return cast(Account, account)


def _candidate_payload(reference: str = "ATS-001") -> CandidateCreatePayload:
    return CandidateCreatePayload(external_reference=reference)


def _publishable_job() -> JobCreatePayload:
    return JobCreatePayload(
        original_title="Backend Engineer",
        canonical_title="Software Engineer",
        location="Ho Chi Minh City",
        workplace_mode="hybrid",
        employment_type="full_time",
        responsibilities=["Build reliable APIs"],
        must_have_skills=["Python"],
    )


def test_candidate_is_tenant_scoped_paginated_and_soft_deleted(session: Session) -> None:
    tenant_a, tenant_b = _id(), _id()
    account = _account()
    service = CandidateService(session)
    first = service.create(tenant_a, account, _candidate_payload("A-1"), "corr-a1")
    service.create(tenant_a, account, _candidate_payload("A-2"), "corr-a2")
    service.create(tenant_b, account, _candidate_payload("B-1"), "corr-b1")

    rows, total = service.list(tenant_a, page=1, limit=1)

    assert len(rows) == 1
    assert total == 2
    with pytest.raises(NotFoundError):
        service.get(tenant_b, first.id)

    first.deleted_at = first.created_at
    session.commit()
    assert CandidateRepository(session).get_by_id_for_tenant(first.id, tenant_a) is None


def test_candidate_mutations_emit_audits_and_duplicate_reference_conflicts(session: Session) -> None:
    tenant_id = _id()
    account = _account()
    service = CandidateService(session)
    candidate = service.create(tenant_id, account, _candidate_payload(), "corr-create")
    service.update(
        tenant_id,
        account,
        candidate.id,
        CandidateUpdatePayload(consent_scope={"current_application": True, "talent_pool": True}),
        "corr-update",
    )
    service.request_deletion(tenant_id, account, candidate.id, "corr-delete")

    events, total = AuditService(session).list_events(tenant_id, page=1, limit=20)

    assert candidate.processing_status == CandidateProcessingStatus.DELETION_REQUESTED
    assert [event.event_type for event in reversed(events)] == [
        "candidate.created",
        "candidate.updated",
        "candidate.deletion_requested",
    ]
    assert total == 3
    with pytest.raises(ConflictError):
        service.create(tenant_id, account, _candidate_payload(), "corr-duplicate")


def test_candidate_pii_repr_and_normal_response_do_not_expose_encrypted_fields() -> None:
    encrypted_value = "ciphertext-secret"
    pii = CandidatePII(
        candidate_id=_id(),
        tenant_id=_id(),
        encryption_key_version="v1",
        encrypted_email=encrypted_value,
    )
    candidate = Candidate(tenant_id=pii.tenant_id, created_by=_id())

    serialized = CandidateResponse.model_validate(candidate).model_dump()

    assert encrypted_value not in repr(pii)
    assert not any(key.startswith("encrypted_") for key in serialized)


@pytest.mark.parametrize(
    "profile",
    [
        CandidateProfilePayload(headline="Contact person@example.com"),
        CandidateProfilePayload(experiences=[{"summary": "Call +84 912 345 678"}]),
    ],
)
def test_candidate_profile_rejects_obvious_plaintext_pii(session: Session, profile: CandidateProfilePayload) -> None:
    tenant_id = _id()
    account = _account()
    candidate = CandidateService(session).create(tenant_id, account, _candidate_payload(), "corr")

    with pytest.raises(ValidationError):
        CandidateProfileService(session).put(tenant_id, candidate.id, profile)


def test_candidate_profile_upsert_is_tenant_scoped(session: Session) -> None:
    tenant_id = _id()
    candidate = CandidateService(session).create(tenant_id, _account(), _candidate_payload(), "corr")
    service = CandidateProfileService(session)

    profile = service.put(
        tenant_id,
        candidate.id,
        CandidateProfilePayload(headline="Masked engineer", skills=["Python"]),
    )
    updated = service.put(tenant_id, candidate.id, CandidateProfilePayload(headline="Senior engineer"))

    assert updated.id == profile.id
    assert updated.headline == "Senior engineer"
    with pytest.raises(NotFoundError):
        service.get(_id(), candidate.id)


def test_job_publish_transition_is_validated_and_published_jobs_are_immutable(session: Session) -> None:
    tenant_id = _id()
    account = _account()
    service = JobService(session)
    incomplete = service.create(tenant_id, account, JobCreatePayload(original_title="Engineer"), "corr-1")
    with pytest.raises(ValidationError):
        service.publish(tenant_id, account, incomplete.id, "corr-2")

    job = service.create(tenant_id, account, _publishable_job(), "corr-3")
    service.update(tenant_id, account, job.id, JobUpdatePayload(seniority="senior"), "corr-4")
    published = service.publish(tenant_id, account, job.id, "corr-5")

    assert published.status == JobStatus.PUBLISHED
    assert published.version == 1
    assert published.published_at is not None
    with pytest.raises(ConflictError):
        service.update(tenant_id, account, job.id, JobUpdatePayload(department="Platform"), "corr-6")
    with pytest.raises(NotFoundError):
        service.get(_id(), job.id)


def test_scoring_policy_validation_versioning_activation_and_audit(session: Session) -> None:
    tenant_id = _id()
    account = _account()
    service = ScoringPolicyService(session)
    first = service.create(tenant_id, account, ScoringPolicyCreatePayload(name="default"), "corr-1")
    second = service.create(tenant_id, account, ScoringPolicyCreatePayload(name="default"), "corr-2")
    service.activate(tenant_id, account, first.id, "corr-3")
    service.activate(tenant_id, account, second.id, "corr-4")
    session.refresh(first)

    assert (first.version, second.version) == (1, 2)
    assert first.active is False
    assert second.active is True
    assert AuditService(session).verify_chain(tenant_id).valid is True
    with pytest.raises(PydanticValidationError):
        ScoringPolicyCreatePayload(name="bad", criterion_weights={"skills": 99})


def test_active_policy_database_invariant_and_failed_activation_are_safe(session: Session) -> None:
    tenant_id = _id()
    account = _account()
    service = ScoringPolicyService(session)
    first = service.create(tenant_id, account, ScoringPolicyCreatePayload(name="default"), "corr-1")
    second = service.create(tenant_id, account, ScoringPolicyCreatePayload(name="default"), "corr-2")
    service.activate(tenant_id, account, first.id, "corr-3")
    _, audit_count_before = AuditService(session).list_events(tenant_id, page=1, limit=20)

    with pytest.raises(NotFoundError):
        service.activate(tenant_id, account, _id(), "corr-missing")
    session.refresh(first)
    _, audit_count_after = AuditService(session).list_events(tenant_id, page=1, limit=20)
    assert first.active is True
    assert audit_count_after == audit_count_before

    second.active = True
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_audit_chain_detects_a_directly_inserted_malformed_test_event(session: Session) -> None:
    tenant_id = _id()
    event = AuditService(session).append_event(
        tenant_id,
        {
            "event_type": "test.created",
            "actor_id": _id(),
            "action": "test.created",
            "result": "success",
            "correlation_id": "corr",
            "metadata": {"safe": True},
        },
    )
    session.commit()

    assert AuditService(session).verify_chain(tenant_id).valid is True
    malformed = AuditEvent(
        tenant_id=tenant_id,
        event_type="synthetic.malformed",
        actor_id=_id(),
        action="synthetic.malformed",
        result="test-only",
        correlation_id="corr-malformed",
        event_hash="0" * 64,
        previous_event_hash=event.event_hash,
    )
    malformed.chain_sequence = 3
    AuditEventRepository(session).append(malformed)
    session.commit()
    verification = AuditService(session).verify_chain(tenant_id)

    assert verification.valid is False
    assert verification.first_invalid_event_id == malformed.id
    assert verification.failure_reason == "invalid_chain_sequence"
    assert not hasattr(AuditEventRepository(session), "update")
    assert not hasattr(AuditEventRepository(session), "delete")


def test_tenant_composite_foreign_keys_reject_cross_tenant_rows(session: Session) -> None:
    tenant_a, tenant_b = _id(), _id()
    account = _account()
    candidate = CandidateService(session).create(tenant_a, account, _candidate_payload(), "corr-candidate")
    policy = ScoringPolicyService(session).create(
        tenant_a, account, ScoringPolicyCreatePayload(name="default"), "corr-policy"
    )

    invalid_rows = [
        CandidatePII(
            tenant_id=tenant_b,
            candidate_id=candidate.id,
            encryption_key_version="test-only",
        ),
        CandidateProfile(tenant_id=tenant_b, candidate_id=candidate.id),
        JobProfile(
            tenant_id=tenant_b,
            created_by=account.id,
            original_title="Cross-tenant job",
            scoring_policy_id=policy.id,
        ),
    ]
    for invalid_row in invalid_rows:
        session.add(invalid_row)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_tenant_composite_foreign_keys_allow_same_tenant_rows(session: Session) -> None:
    tenant_id = _id()
    account = _account()
    candidate = CandidateService(session).create(tenant_id, account, _candidate_payload(), "corr-candidate")
    policy = ScoringPolicyService(session).create(
        tenant_id, account, ScoringPolicyCreatePayload(name="default"), "corr-policy"
    )
    session.add_all(
        [
            CandidatePII(
                tenant_id=tenant_id,
                candidate_id=candidate.id,
                encryption_key_version="test-only",
            ),
            CandidateProfile(tenant_id=tenant_id, candidate_id=candidate.id),
            JobProfile(
                tenant_id=tenant_id,
                created_by=account.id,
                original_title="Same-tenant job",
                scoring_policy_id=policy.id,
            ),
        ]
    )
    session.commit()


def test_permission_mapping_restricts_admin_actions() -> None:
    normal_member = _account(can_edit=False, is_admin=False)

    require_permission(normal_member, TalentAction.READ_CANDIDATE)
    with pytest.raises(Exception, match="not permitted"):
        require_permission(normal_member, TalentAction.READ_AUDIT)


def test_development_seed_is_explicit_idempotent_and_synthetic(session: Session) -> None:
    tenant_id = _id()
    account = _account()

    first = seed_development_data(session, tenant_id, account)
    second = seed_development_data(session, tenant_id, account)

    assert first.candidates_created == first.profiles_created == first.jobs_created == first.policies_created == 1
    assert second.candidates_created == second.profiles_created == second.jobs_created == second.policies_created == 0
