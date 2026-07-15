"""SQLAlchemy repositories with mandatory tenant predicates.

Controllers never receive unscoped lookup methods. Audit events expose append
and read operations only; update and deletion are intentionally absent.
"""

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..models import AuditEvent, Candidate, CandidatePII, CandidateProfile, JobProfile, ScoringPolicy


class CandidateRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, candidate: Candidate) -> None:
        self._session.add(candidate)

    def get_by_id_for_tenant(self, candidate_id: str, tenant_id: str) -> Candidate | None:
        return self._session.scalar(
            select(Candidate).where(
                Candidate.id == candidate_id,
                Candidate.tenant_id == tenant_id,
                Candidate.deleted_at.is_(None),
            )
        )

    def get_by_external_reference_for_tenant(self, external_reference: str, tenant_id: str) -> Candidate | None:
        return self._session.scalar(
            select(Candidate).where(
                Candidate.external_reference == external_reference,
                Candidate.tenant_id == tenant_id,
                Candidate.deleted_at.is_(None),
            )
        )

    def list_for_tenant(self, tenant_id: str, *, page: int, limit: int) -> tuple[list[Candidate], int]:
        predicate = (Candidate.tenant_id == tenant_id, Candidate.deleted_at.is_(None))
        total = self._session.scalar(select(func.count()).select_from(Candidate).where(*predicate)) or 0
        rows = list(
            self._session.scalars(
                select(Candidate)
                .where(*predicate)
                .order_by(Candidate.created_at.desc(), Candidate.id.desc())
                .offset((page - 1) * limit)
                .limit(limit)
            ).all()
        )
        return rows, total


class CandidatePIIRepository:
    """Restricted storage repository; callers must never serialize returned rows."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, candidate_pii: CandidatePII) -> None:
        self._session.add(candidate_pii)

    def get_for_candidate_for_tenant(self, candidate_id: str, tenant_id: str) -> CandidatePII | None:
        return self._session.scalar(
            select(CandidatePII).where(
                CandidatePII.candidate_id == candidate_id,
                CandidatePII.tenant_id == tenant_id,
            )
        )


class CandidateProfileRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, profile: CandidateProfile) -> None:
        self._session.add(profile)

    def get_for_candidate_for_tenant(self, candidate_id: str, tenant_id: str) -> CandidateProfile | None:
        return self._session.scalar(
            select(CandidateProfile).where(
                CandidateProfile.candidate_id == candidate_id,
                CandidateProfile.tenant_id == tenant_id,
            )
        )


class JobProfileRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, job: JobProfile) -> None:
        self._session.add(job)

    def get_by_id_for_tenant(self, job_id: str, tenant_id: str) -> JobProfile | None:
        return self._session.scalar(
            select(JobProfile).where(
                JobProfile.id == job_id,
                JobProfile.tenant_id == tenant_id,
                JobProfile.deleted_at.is_(None),
            )
        )

    def get_by_original_title_for_tenant(self, original_title: str, tenant_id: str) -> JobProfile | None:
        return self._session.scalar(
            select(JobProfile).where(
                JobProfile.original_title == original_title,
                JobProfile.tenant_id == tenant_id,
                JobProfile.deleted_at.is_(None),
            )
        )

    def list_for_tenant(self, tenant_id: str, *, page: int, limit: int) -> tuple[list[JobProfile], int]:
        predicate = (JobProfile.tenant_id == tenant_id, JobProfile.deleted_at.is_(None))
        total = self._session.scalar(select(func.count()).select_from(JobProfile).where(*predicate)) or 0
        rows = list(
            self._session.scalars(
                select(JobProfile)
                .where(*predicate)
                .order_by(JobProfile.created_at.desc(), JobProfile.id.desc())
                .offset((page - 1) * limit)
                .limit(limit)
            ).all()
        )
        return rows, total


class ScoringPolicyRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, policy: ScoringPolicy) -> None:
        self._session.add(policy)

    def get_by_id_for_tenant(self, policy_id: str, tenant_id: str) -> ScoringPolicy | None:
        return self._session.scalar(
            select(ScoringPolicy).where(ScoringPolicy.id == policy_id, ScoringPolicy.tenant_id == tenant_id)
        )

    def list_for_tenant(self, tenant_id: str, *, page: int, limit: int) -> tuple[list[ScoringPolicy], int]:
        total = (
            self._session.scalar(
                select(func.count()).select_from(ScoringPolicy).where(ScoringPolicy.tenant_id == tenant_id)
            )
            or 0
        )
        rows = list(
            self._session.scalars(
                select(ScoringPolicy)
                .where(ScoringPolicy.tenant_id == tenant_id)
                .order_by(ScoringPolicy.name.asc(), ScoringPolicy.version.desc())
                .offset((page - 1) * limit)
                .limit(limit)
            ).all()
        )
        return rows, total

    def next_version(self, tenant_id: str, name: str) -> int:
        latest = self._session.scalar(
            select(func.max(ScoringPolicy.version)).where(
                ScoringPolicy.tenant_id == tenant_id,
                ScoringPolicy.name == name,
            )
        )
        return (latest or 0) + 1

    def latest_by_name_for_tenant(self, name: str, tenant_id: str) -> ScoringPolicy | None:
        return self._session.scalar(
            select(ScoringPolicy)
            .where(ScoringPolicy.tenant_id == tenant_id, ScoringPolicy.name == name)
            .order_by(ScoringPolicy.version.desc())
            .limit(1)
        )

    def deactivate_name(self, tenant_id: str, name: str) -> None:
        self._session.execute(
            update(ScoringPolicy)
            .where(
                ScoringPolicy.tenant_id == tenant_id,
                ScoringPolicy.name == name,
                ScoringPolicy.active.is_(True),
            )
            .values(active=False)
        )


class AuditEventRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def append(self, event: AuditEvent) -> None:
        self._session.add(event)

    def latest_for_tenant(self, tenant_id: str, *, lock: bool = False) -> AuditEvent | None:
        statement = (
            select(AuditEvent)
            .where(AuditEvent.tenant_id == tenant_id)
            .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
            .limit(1)
        )
        if lock:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def chain_for_tenant(self, tenant_id: str) -> list[AuditEvent]:
        return list(
            self._session.scalars(
                select(AuditEvent)
                .where(AuditEvent.tenant_id == tenant_id)
                .order_by(AuditEvent.created_at.asc(), AuditEvent.id.asc())
            ).all()
        )

    def list_for_tenant(self, tenant_id: str, *, page: int, limit: int) -> tuple[list[AuditEvent], int]:
        total = (
            self._session.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.tenant_id == tenant_id))
            or 0
        )
        rows = list(
            self._session.scalars(
                select(AuditEvent)
                .where(AuditEvent.tenant_id == tenant_id)
                .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
                .offset((page - 1) * limit)
                .limit(limit)
            ).all()
        )
        return rows, total
