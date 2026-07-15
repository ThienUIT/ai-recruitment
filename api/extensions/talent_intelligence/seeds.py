"""Explicit, idempotent development seed data for Phase 1.

Nothing calls this module during application startup. Operators must invoke
``seed_development_data`` deliberately for a selected tenant and actor.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from models import Account

from .repositories import CandidateProfileRepository, CandidateRepository, JobProfileRepository, ScoringPolicyRepository
from .schemas.domain import (
    CandidateCreatePayload,
    CandidateProfilePayload,
    JobCreatePayload,
    ScoringPolicyCreatePayload,
)
from .services import CandidateProfileService, CandidateService, JobService, ScoringPolicyService

_SEED_CANDIDATE_REFERENCE = "TI-SYNTHETIC-001"
_SEED_JOB_TITLE = "[Synthetic] Backend Engineer"
_SEED_POLICY_NAME = "default"


@dataclass(frozen=True)
class SeedResult:
    candidates_created: int
    profiles_created: int
    jobs_created: int
    policies_created: int


def seed_development_data(session: Session, tenant_id: str, account: Account) -> SeedResult:
    """Create only missing synthetic fixtures for one explicitly selected tenant."""

    candidate_repository = CandidateRepository(session)
    profile_repository = CandidateProfileRepository(session)
    job_repository = JobProfileRepository(session)
    policy_repository = ScoringPolicyRepository(session)
    candidates_created = profiles_created = jobs_created = policies_created = 0

    policy = policy_repository.latest_by_name_for_tenant(_SEED_POLICY_NAME, tenant_id)
    if policy is None:
        policy = ScoringPolicyService(session).create(
            tenant_id,
            account,
            ScoringPolicyCreatePayload(name=_SEED_POLICY_NAME),
            "ti-development-seed",
        )
        ScoringPolicyService(session).activate(tenant_id, account, policy.id, "ti-development-seed")
        policies_created = 1

    job = job_repository.get_by_original_title_for_tenant(_SEED_JOB_TITLE, tenant_id)
    if job is None:
        JobService(session).create(
            tenant_id,
            account,
            JobCreatePayload(
                original_title=_SEED_JOB_TITLE,
                canonical_title="Software Engineer",
                department="Synthetic Engineering",
                location="Ho Chi Minh City",
                workplace_mode="hybrid",
                employment_type="full_time",
                responsibilities=["Build synthetic test services"],
                must_have_skills=["Python"],
                scoring_policy_id=policy.id,
            ),
            "ti-development-seed",
        )
        jobs_created = 1

    candidate = candidate_repository.get_by_external_reference_for_tenant(_SEED_CANDIDATE_REFERENCE, tenant_id)
    if candidate is None:
        candidate = CandidateService(session).create(
            tenant_id,
            account,
            CandidateCreatePayload(external_reference=_SEED_CANDIDATE_REFERENCE),
            "ti-development-seed",
        )
        candidates_created = 1

    if profile_repository.get_for_candidate_for_tenant(candidate.id, tenant_id) is None:
        CandidateProfileService(session).put(
            tenant_id,
            candidate.id,
            CandidateProfilePayload(
                headline="Masked synthetic backend engineer",
                total_experience_months=60,
                current_location="Ho Chi Minh City",
                workplace_preferences=["hybrid"],
                skills=["Python", "SQLAlchemy"],
                parser_version="synthetic-fixture-v1",
            ),
        )
        profiles_created = 1

    return SeedResult(candidates_created, profiles_created, jobs_created, policies_created)
