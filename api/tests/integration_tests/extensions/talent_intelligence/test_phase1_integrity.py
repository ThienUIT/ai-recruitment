"""PostgreSQL regression tests for Talent Intelligence Phase 1 integrity.

Set ``TALENT_INTELLIGENCE_TEST_DATABASE_URL`` to a migrated disposable
PostgreSQL database. Audit rows are intentionally not deleted because the
production triggers under test prohibit mutation.
"""

import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from typing import cast
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from extensions.talent_intelligence.audit import AuditService
from extensions.talent_intelligence.models import Candidate, CandidatePII, CandidateProfile, JobProfile, ScoringPolicy
from extensions.talent_intelligence.schemas.domain import ScoringPolicyCreatePayload
from extensions.talent_intelligence.services import ScoringPolicyService
from models import Account

_DATABASE_URL = os.environ.get("TALENT_INTELLIGENCE_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not _DATABASE_URL, reason="PostgreSQL integrity database is not configured")


@pytest.fixture(scope="module")
def engine() -> Iterator[sa.Engine]:
    assert _DATABASE_URL is not None
    database_engine = sa.create_engine(_DATABASE_URL, pool_size=12, max_overflow=4)
    if database_engine.dialect.name != "postgresql":
        pytest.skip("Phase 1 integrity integration tests require PostgreSQL")
    yield database_engine
    database_engine.dispose()


def _id() -> str:
    return str(uuid4())


def _account() -> Account:
    account = MagicMock(spec=Account)
    account.id = _id()
    account.current_role = "admin"
    account.has_edit_permission = True
    account.is_admin_or_owner = True
    return cast(Account, account)


def _append(engine: sa.Engine, tenant_id: str, correlation_id: str) -> str:
    with Session(engine, expire_on_commit=False) as session:
        event = AuditService(session).append_event(
            tenant_id,
            {
                "event_type": "integration.appended",
                "actor_id": _id(),
                "action": "integration.appended",
                "result": "success",
                "correlation_id": correlation_id,
                "metadata": {"test": True},
            },
        )
        session.commit()
        return event.id


def test_audit_triggers_reject_mutation_and_preserve_transaction_recovery(engine: sa.Engine) -> None:
    tenant_id = _id()
    event_id = _append(engine, tenant_id, "trigger-1")

    with Session(engine) as session:
        with pytest.raises(DBAPIError, match="append-only"):
            session.execute(sa.text("UPDATE ti_audit_events SET action = 'tampered' WHERE id = :id"), {"id": event_id})
        session.rollback()

        with pytest.raises(DBAPIError, match="append-only"):
            session.execute(sa.text("DELETE FROM ti_audit_events WHERE id = :id"), {"id": event_id})
        session.rollback()

    _append(engine, tenant_id, "trigger-2")
    with Session(engine) as session:
        verification = AuditService(session).verify_chain(tenant_id)
        assert verification.valid is True
        assert verification.event_count == 2


def test_concurrent_audit_appends_are_gapless_and_tenant_scoped(engine: sa.Engine) -> None:
    first_tenant = _id()
    second_tenant = _id()
    work = [(first_tenant, f"first-{index}") for index in range(8)]
    work.extend((second_tenant, f"second-{index}") for index in range(5))

    with ThreadPoolExecutor(max_workers=13) as executor:
        event_ids = list(executor.map(lambda item: _append(engine, *item), work))

    assert len(set(event_ids)) == 13
    with Session(engine) as session:
        for tenant_id, expected_count in ((first_tenant, 8), (second_tenant, 5)):
            verification = AuditService(session).verify_chain(tenant_id)
            sequences = list(
                session.scalars(
                    sa.text(
                        "SELECT chain_sequence FROM ti_audit_events "
                        "WHERE tenant_id = :tenant_id ORDER BY chain_sequence"
                    ),
                    {"tenant_id": tenant_id},
                )
            )
            assert verification.valid is True
            assert verification.event_count == expected_count
            assert sequences == list(range(1, expected_count + 1))


def test_policy_activation_is_serialized_and_database_enforced(engine: sa.Engine) -> None:
    tenant_id = _id()
    account = _account()
    with Session(engine, expire_on_commit=False) as session:
        service = ScoringPolicyService(session)
        first = service.create(tenant_id, account, ScoringPolicyCreatePayload(name="default"), "policy-create-1")
        second = service.create(tenant_id, account, ScoringPolicyCreatePayload(name="default"), "policy-create-2")
        first_id, second_id = first.id, second.id

    def activate(policy_id: str) -> None:
        with Session(engine) as session:
            ScoringPolicyService(session).activate(tenant_id, account, policy_id, f"activate-{policy_id}")

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(activate, [first_id, second_id]))

    with Session(engine) as session:
        active_count = session.scalar(
            sa.select(sa.func.count())
            .select_from(ScoringPolicy)
            .where(
                ScoringPolicy.tenant_id == tenant_id, ScoringPolicy.name == "default", ScoringPolicy.active.is_(True)
            )
        )
        assert active_count == 1
        assert AuditService(session).verify_chain(tenant_id).valid is True
        inactive_policy_id = session.scalar(
            sa.select(ScoringPolicy.id).where(
                ScoringPolicy.tenant_id == tenant_id,
                ScoringPolicy.name == "default",
                ScoringPolicy.active.is_(False),
            )
        )
        with pytest.raises(IntegrityError):
            session.execute(sa.update(ScoringPolicy).where(ScoringPolicy.id == inactive_policy_id).values(active=True))
        session.rollback()

    with Session(engine) as session:
        other_name = ScoringPolicy(
            tenant_id=tenant_id,
            name="alternative",
            created_by=account.id,
            version=1,
            active=True,
        )
        other_tenant = ScoringPolicy(
            tenant_id=_id(),
            name="default",
            created_by=account.id,
            version=1,
            active=True,
        )
        session.add_all([other_name, other_tenant])
        session.commit()


def test_composite_foreign_keys_enforce_tenant_ownership(engine: sa.Engine) -> None:
    tenant_a, tenant_b = _id(), _id()
    candidate = Candidate(tenant_id=tenant_a, created_by=_id())
    policy = ScoringPolicy(tenant_id=tenant_a, name="tenant-fk", created_by=_id(), version=1)
    with Session(engine, expire_on_commit=False) as session:
        session.add_all([candidate, policy])
        session.commit()

        valid_rows = [
            CandidatePII(tenant_id=tenant_a, candidate_id=candidate.id, encryption_key_version="test-only"),
            CandidateProfile(tenant_id=tenant_a, candidate_id=candidate.id),
            JobProfile(
                tenant_id=tenant_a,
                created_by=_id(),
                original_title="Valid job",
                scoring_policy_id=policy.id,
            ),
        ]
        session.add_all(valid_rows)
        session.commit()

    invalid_rows = [
        CandidatePII(tenant_id=tenant_b, candidate_id=candidate.id, encryption_key_version="test-only"),
        CandidateProfile(tenant_id=tenant_b, candidate_id=candidate.id),
        JobProfile(
            tenant_id=tenant_b,
            created_by=_id(),
            original_title="Invalid job",
            scoring_policy_id=policy.id,
        ),
    ]
    for invalid_row in invalid_rows:
        with Session(engine) as session:
            session.add(invalid_row)
            with pytest.raises(IntegrityError):
                session.commit()
