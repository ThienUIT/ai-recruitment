"""Phase 1 domain transitions and transaction boundaries."""

import builtins
import re
from collections.abc import Iterable
from typing import cast

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from libs.datetime_utils import naive_utc_now
from models import Account

from ..audit.chain import AuditService, pseudonymize_candidate_id
from ..errors import ConflictError, NotFoundError, ValidationError
from ..models import Candidate, CandidateProcessingStatus, CandidateProfile, JobProfile, JobStatus, ScoringPolicy
from ..repositories import (
    CandidateProfileRepository,
    CandidateRepository,
    JobProfileRepository,
    ScoringPolicyRepository,
)
from ..schemas.domain import (
    CandidateCreatePayload,
    CandidateProfilePayload,
    CandidateUpdatePayload,
    JobCreatePayload,
    JobUpdatePayload,
    ScoringPolicyCreatePayload,
)

_EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?84|0)[ .-]?[1-9](?:[ .-]?\d){8,9}(?!\d)")


def _actor_role(account: Account) -> str | None:
    role = account.current_role
    return str(role) if role is not None else None


def _commit_or_conflict(session: Session, message: str) -> None:
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ConflictError(message) from error


def _validate_no_obvious_pii(value: object) -> None:
    if isinstance(value, str) and (_EMAIL_PATTERN.search(value) or _PHONE_PATTERN.search(value)):
        raise ValidationError("Candidate profile contains an obvious email or phone pattern.")
    if isinstance(value, dict):
        for nested_value in value.values():
            _validate_no_obvious_pii(nested_value)
    elif isinstance(value, list):
        for item in value:
            _validate_no_obvious_pii(item)


class CandidateService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repository = CandidateRepository(session)
        self._audit = AuditService(session)

    def create(
        self,
        tenant_id: str,
        account: Account,
        payload: CandidateCreatePayload,
        correlation_id: str,
    ) -> Candidate:
        candidate = Candidate(
            tenant_id=tenant_id,
            created_by=account.id,
            external_reference=payload.external_reference,
            consent_scope=payload.consent_scope.model_dump(mode="json"),
        )
        self._repository.add(candidate)
        with self._session.no_autoflush:
            self._audit.append_event(
                tenant_id,
                {
                    "event_type": "candidate.created",
                    "actor_id": account.id,
                    "actor_role": _actor_role(account),
                    "action": "candidate.created",
                    "result": "success",
                    "correlation_id": correlation_id,
                    "pseudonymous_candidate_id": pseudonymize_candidate_id(tenant_id, candidate.id),
                    "object_type": "candidate",
                    "object_id": candidate.id,
                    "metadata": {},
                },
            )
        _commit_or_conflict(self._session, "Candidate external reference already exists for this tenant.")
        return candidate

    def get(self, tenant_id: str, candidate_id: str) -> Candidate:
        candidate = self._repository.get_by_id_for_tenant(candidate_id, tenant_id)
        if candidate is None:
            raise NotFoundError("Candidate not found.")
        return candidate

    def list(self, tenant_id: str, *, page: int, limit: int) -> tuple[list[Candidate], int]:
        return self._repository.list_for_tenant(tenant_id, page=page, limit=limit)

    def update(
        self,
        tenant_id: str,
        account: Account,
        candidate_id: str,
        payload: CandidateUpdatePayload,
        correlation_id: str,
    ) -> Candidate:
        candidate = self.get(tenant_id, candidate_id)
        changes = payload.model_dump(exclude_unset=True)
        if not changes:
            raise ValidationError("At least one candidate field must be provided.")
        if "external_reference" in changes:
            candidate.external_reference = cast(str | None, changes["external_reference"])
        if payload.consent_scope is not None:
            candidate.consent_scope = payload.consent_scope.model_dump(mode="json")
        self._audit.append_event(
            tenant_id,
            {
                "event_type": "candidate.updated",
                "actor_id": account.id,
                "actor_role": _actor_role(account),
                "action": "candidate.updated",
                "result": "success",
                "correlation_id": correlation_id,
                "pseudonymous_candidate_id": pseudonymize_candidate_id(tenant_id, candidate.id),
                "object_type": "candidate",
                "object_id": candidate.id,
                "metadata": {"changed_fields": sorted(changes)},
            },
        )
        _commit_or_conflict(self._session, "Candidate external reference already exists for this tenant.")
        return candidate

    def request_deletion(self, tenant_id: str, account: Account, candidate_id: str, correlation_id: str) -> Candidate:
        candidate = self.get(tenant_id, candidate_id)
        if candidate.processing_status in {
            CandidateProcessingStatus.DELETION_REQUESTED,
            CandidateProcessingStatus.DELETED,
        }:
            raise ConflictError("Candidate deletion has already been requested or completed.")
        candidate.processing_status = CandidateProcessingStatus.DELETION_REQUESTED
        candidate.deletion_requested_at = naive_utc_now()
        self._audit.append_event(
            tenant_id,
            {
                "event_type": "candidate.deletion_requested",
                "actor_id": account.id,
                "actor_role": _actor_role(account),
                "action": "candidate.deletion_requested",
                "result": "success",
                "correlation_id": correlation_id,
                "pseudonymous_candidate_id": pseudonymize_candidate_id(tenant_id, candidate.id),
                "object_type": "candidate",
                "object_id": candidate.id,
                "metadata": {},
            },
        )
        self._session.commit()
        return candidate


class CandidateProfileService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._candidate_repository = CandidateRepository(session)
        self._repository = CandidateProfileRepository(session)

    def get(self, tenant_id: str, candidate_id: str) -> CandidateProfile:
        if self._candidate_repository.get_by_id_for_tenant(candidate_id, tenant_id) is None:
            raise NotFoundError("Candidate not found.")
        profile = self._repository.get_for_candidate_for_tenant(candidate_id, tenant_id)
        if profile is None:
            raise NotFoundError("Candidate profile not found.")
        return profile

    def put(self, tenant_id: str, candidate_id: str, payload: CandidateProfilePayload) -> CandidateProfile:
        if self._candidate_repository.get_by_id_for_tenant(candidate_id, tenant_id) is None:
            raise NotFoundError("Candidate not found.")
        values = payload.model_dump(mode="json")
        _validate_no_obvious_pii(values)
        profile = self._repository.get_for_candidate_for_tenant(candidate_id, tenant_id)
        if profile is None:
            profile = CandidateProfile(candidate_id=candidate_id, tenant_id=tenant_id, **values)
            self._repository.add(profile)
        else:
            for field_name, value in values.items():
                setattr(profile, field_name, value)
        self._session.commit()
        return profile


class JobService:
    _UPDATABLE_FIELDS = frozenset(JobUpdatePayload.model_fields)

    def __init__(self, session: Session) -> None:
        self._session = session
        self._repository = JobProfileRepository(session)
        self._policy_repository = ScoringPolicyRepository(session)
        self._audit = AuditService(session)

    def create(self, tenant_id: str, account: Account, payload: JobCreatePayload, correlation_id: str) -> JobProfile:
        self._validate_policy(tenant_id, payload.scoring_policy_id)
        job = JobProfile(tenant_id=tenant_id, created_by=account.id, **payload.model_dump(mode="json"))
        self._repository.add(job)
        with self._session.no_autoflush:
            self._audit_job(job, account, "job.created", correlation_id)
        self._session.commit()
        return job

    def get(self, tenant_id: str, job_id: str) -> JobProfile:
        job = self._repository.get_by_id_for_tenant(job_id, tenant_id)
        if job is None:
            raise NotFoundError("Job not found.")
        return job

    def list(self, tenant_id: str, *, page: int, limit: int) -> tuple[list[JobProfile], int]:
        return self._repository.list_for_tenant(tenant_id, page=page, limit=limit)

    def update(
        self,
        tenant_id: str,
        account: Account,
        job_id: str,
        payload: JobUpdatePayload,
        correlation_id: str,
    ) -> JobProfile:
        job = self.get(tenant_id, job_id)
        if job.status == JobStatus.PUBLISHED:
            raise ConflictError("Published jobs are immutable; create a new draft version.")
        changes = payload.model_dump(exclude_unset=True, mode="json")
        if not changes:
            raise ValidationError("At least one job field must be provided.")
        if "scoring_policy_id" in changes:
            self._validate_policy(tenant_id, cast(str | None, changes["scoring_policy_id"]))
        for field_name, value in changes.items():
            if field_name in self._UPDATABLE_FIELDS:
                setattr(job, field_name, value)
        self._audit_job(job, account, "job.updated", correlation_id, changed_fields=changes)
        self._session.commit()
        return job

    def publish(self, tenant_id: str, account: Account, job_id: str, correlation_id: str) -> JobProfile:
        job = self.get(tenant_id, job_id)
        if job.status == JobStatus.PUBLISHED:
            raise ConflictError("Job is already published.")
        missing = self._missing_publish_fields(job)
        if missing:
            raise ValidationError(f"Job is not publishable; missing: {', '.join(missing)}.")
        job.status = JobStatus.PUBLISHED
        job.approved_by = account.id
        job.published_at = naive_utc_now()
        self._audit_job(job, account, "job.published", correlation_id)
        self._session.commit()
        return job

    @staticmethod
    def _missing_publish_fields(job: JobProfile) -> builtins.list[str]:
        values: dict[str, object] = {
            "original_title": job.original_title,
            "canonical_title": job.canonical_title,
            "location": job.location,
            "workplace_mode": job.workplace_mode,
            "employment_type": job.employment_type,
            "responsibilities": job.responsibilities,
            "must_have_skills": job.must_have_skills,
        }
        return [name for name, value in values.items() if not value]

    def _validate_policy(self, tenant_id: str, policy_id: str | None) -> None:
        if policy_id is not None and self._policy_repository.get_by_id_for_tenant(policy_id, tenant_id) is None:
            raise NotFoundError("Scoring policy not found.")

    def _audit_job(
        self,
        job: JobProfile,
        account: Account,
        event_type: str,
        correlation_id: str,
        *,
        changed_fields: dict[str, object] | None = None,
    ) -> None:
        metadata: dict[str, object] = {}
        if changed_fields is not None:
            metadata["changed_fields"] = sorted(changed_fields)
        self._audit.append_event(
            job.tenant_id,
            {
                "event_type": event_type,
                "actor_id": account.id,
                "actor_role": _actor_role(account),
                "action": event_type,
                "result": "success",
                "correlation_id": correlation_id,
                "job_id": job.id,
                "object_type": "job",
                "object_id": job.id,
                "metadata": metadata,
            },
        )


class ScoringPolicyService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repository = ScoringPolicyRepository(session)
        self._audit = AuditService(session)

    @staticmethod
    def validate_weights(weights: Iterable[float]) -> None:
        values = list(weights)
        if any(weight < 0 for weight in values) or abs(sum(values) - 100) > 1e-9:
            raise ValidationError("Scoring policy weights must be non-negative and total 100.")

    def create(
        self,
        tenant_id: str,
        account: Account,
        payload: ScoringPolicyCreatePayload,
        correlation_id: str,
    ) -> ScoringPolicy:
        self.validate_weights(payload.criterion_weights.values())
        policy = ScoringPolicy(
            tenant_id=tenant_id,
            name=payload.name,
            created_by=account.id,
            version=self._repository.next_version(tenant_id, payload.name),
            criterion_weights=cast(dict[str, object], payload.criterion_weights),
            criterion_formulas=payload.criterion_formulas,
            recommendation_thresholds=payload.recommendation_thresholds,
            evidence_coverage_threshold=payload.evidence_coverage_threshold,
            confidence_rules=payload.confidence_rules,
        )
        self._repository.add(policy)
        with self._session.no_autoflush:
            self._audit_policy(policy, account, "scoring_policy.created", correlation_id)
        _commit_or_conflict(self._session, "Scoring policy version already exists.")
        return policy

    def get(self, tenant_id: str, policy_id: str) -> ScoringPolicy:
        policy = self._repository.get_by_id_for_tenant(policy_id, tenant_id)
        if policy is None:
            raise NotFoundError("Scoring policy not found.")
        return policy

    def list(self, tenant_id: str, *, page: int, limit: int) -> tuple[list[ScoringPolicy], int]:
        return self._repository.list_for_tenant(tenant_id, page=page, limit=limit)

    def activate(self, tenant_id: str, account: Account, policy_id: str, correlation_id: str) -> ScoringPolicy:
        policy = self.get(tenant_id, policy_id)
        group = self._repository.lock_group_for_tenant(tenant_id, policy.name)
        locked_policy = next((candidate for candidate in group if candidate.id == policy_id), None)
        if locked_policy is None:
            raise NotFoundError("Scoring policy not found.")
        for candidate in group:
            candidate.active = candidate.id == locked_policy.id
        self._audit_policy(locked_policy, account, "scoring_policy.activated", correlation_id)
        self._session.commit()
        return locked_policy

    def _audit_policy(self, policy: ScoringPolicy, account: Account, event_type: str, correlation_id: str) -> None:
        self._audit.append_event(
            policy.tenant_id,
            {
                "event_type": event_type,
                "actor_id": account.id,
                "actor_role": _actor_role(account),
                "action": event_type,
                "result": "success",
                "correlation_id": correlation_id,
                "object_type": "scoring_policy",
                "object_id": policy.id,
                "policy_version": str(policy.version),
                "metadata": {},
            },
        )
