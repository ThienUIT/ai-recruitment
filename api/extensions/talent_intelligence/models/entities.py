"""SQLAlchemy models owned by the Talent Intelligence extension.

Every table is tenant-owned. Candidate PII is deliberately isolated and its
encrypted columns are excluded from dataclass repr output. No model stores raw
CV bytes or raw CV text.
"""

import enum
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from libs.datetime_utils import naive_utc_now
from libs.uuid_utils import uuidv7
from models.base import TypeBase
from models.types import AdjustedJSON, EnumText, LongText, StringUUID


def _uuid() -> str:
    return str(uuidv7())


class CandidateProcessingStatus(enum.StrEnum):
    CREATED = "created"
    PENDING_UPLOAD = "pending_upload"
    PROCESSING = "processing"
    PROCESSED = "processed"
    PROCESSING_FAILED = "processing_failed"
    DELETION_REQUESTED = "deletion_requested"
    DELETED = "deleted"


class JobStatus(enum.StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class Candidate(TypeBase):
    __tablename__ = "ti_candidates"
    __table_args__ = (
        sa.PrimaryKeyConstraint("id", name="ti_candidate_pkey"),
        sa.UniqueConstraint("tenant_id", "external_reference", name="ti_candidate_tenant_external_ref_uq"),
        sa.Index("ti_candidate_tenant_created_idx", "tenant_id", "created_at"),
        sa.Index("ti_candidate_tenant_status_idx", "tenant_id", "processing_status"),
    )

    id: Mapped[str] = mapped_column(StringUUID, default_factory=_uuid, init=False)
    tenant_id: Mapped[str] = mapped_column(StringUUID, nullable=False)
    created_by: Mapped[str] = mapped_column(StringUUID, nullable=False)
    external_reference: Mapped[str | None] = mapped_column(sa.String(255), nullable=True, default=None)
    processing_status: Mapped[CandidateProcessingStatus] = mapped_column(
        EnumText(CandidateProcessingStatus, length=32),
        nullable=False,
        default=CandidateProcessingStatus.CREATED,
        server_default=sa.text("'created'"),
    )
    consent_scope: Mapped[dict[str, object]] = mapped_column(AdjustedJSON, nullable=False, default_factory=dict)
    deletion_requested_at: Mapped[datetime | None] = mapped_column(sa.DateTime, nullable=True, default=None)
    deleted_at: Mapped[datetime | None] = mapped_column(sa.DateTime, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime,
        nullable=False,
        default_factory=naive_utc_now,
        server_default=sa.func.current_timestamp(),
        init=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime,
        nullable=False,
        default_factory=naive_utc_now,
        server_default=sa.func.current_timestamp(),
        onupdate=sa.func.current_timestamp(),
        init=False,
    )


class CandidatePII(TypeBase):
    """Restricted encrypted PII boundary; never serialize from normal APIs."""

    __tablename__ = "ti_candidate_pii"
    __table_args__ = (
        sa.PrimaryKeyConstraint("id", name="ti_candidate_pii_pkey"),
        sa.UniqueConstraint("candidate_id", name="ti_candidate_pii_candidate_uq"),
        sa.Index("ti_candidate_pii_tenant_candidate_idx", "tenant_id", "candidate_id"),
    )

    id: Mapped[str] = mapped_column(StringUUID, default_factory=_uuid, init=False)
    candidate_id: Mapped[str] = mapped_column(StringUUID, sa.ForeignKey("ti_candidates.id", ondelete="CASCADE"))
    tenant_id: Mapped[str] = mapped_column(StringUUID, nullable=False)
    encryption_key_version: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    encrypted_name: Mapped[str | None] = mapped_column(LongText, nullable=True, default=None, repr=False)
    encrypted_email: Mapped[str | None] = mapped_column(LongText, nullable=True, default=None, repr=False)
    encrypted_phone: Mapped[str | None] = mapped_column(LongText, nullable=True, default=None, repr=False)
    encrypted_address: Mapped[str | None] = mapped_column(LongText, nullable=True, default=None, repr=False)
    encrypted_personal_urls: Mapped[str | None] = mapped_column(LongText, nullable=True, default=None, repr=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime,
        nullable=False,
        default_factory=naive_utc_now,
        server_default=sa.func.current_timestamp(),
        init=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime,
        nullable=False,
        default_factory=naive_utc_now,
        server_default=sa.func.current_timestamp(),
        onupdate=sa.func.current_timestamp(),
        init=False,
    )


class CandidateProfile(TypeBase):
    __tablename__ = "ti_candidate_profiles"
    __table_args__ = (
        sa.PrimaryKeyConstraint("id", name="ti_candidate_profile_pkey"),
        sa.UniqueConstraint("candidate_id", name="ti_candidate_profile_candidate_uq"),
        sa.Index("ti_candidate_profile_tenant_candidate_idx", "tenant_id", "candidate_id"),
    )

    id: Mapped[str] = mapped_column(StringUUID, default_factory=_uuid, init=False)
    candidate_id: Mapped[str] = mapped_column(StringUUID, sa.ForeignKey("ti_candidates.id", ondelete="CASCADE"))
    tenant_id: Mapped[str] = mapped_column(StringUUID, nullable=False)
    headline: Mapped[str | None] = mapped_column(sa.String(512), nullable=True, default=None)
    total_experience_months: Mapped[int | None] = mapped_column(sa.Integer, nullable=True, default=None)
    current_location: Mapped[str | None] = mapped_column(sa.String(255), nullable=True, default=None)
    workplace_preferences: Mapped[list[object]] = mapped_column(AdjustedJSON, nullable=False, default_factory=list)
    willing_to_relocate: Mapped[bool | None] = mapped_column(sa.Boolean, nullable=True, default=None)
    notice_period_days: Mapped[int | None] = mapped_column(sa.Integer, nullable=True, default=None)
    experiences: Mapped[list[object]] = mapped_column(AdjustedJSON, nullable=False, default_factory=list)
    projects: Mapped[list[object]] = mapped_column(AdjustedJSON, nullable=False, default_factory=list)
    skills: Mapped[list[object]] = mapped_column(AdjustedJSON, nullable=False, default_factory=list)
    educations: Mapped[list[object]] = mapped_column(AdjustedJSON, nullable=False, default_factory=list)
    certifications: Mapped[list[object]] = mapped_column(AdjustedJSON, nullable=False, default_factory=list)
    languages: Mapped[list[object]] = mapped_column(AdjustedJSON, nullable=False, default_factory=list)
    extraction_confidence: Mapped[float | None] = mapped_column(sa.Float, nullable=True, default=None)
    parser_version: Mapped[str | None] = mapped_column(sa.String(128), nullable=True, default=None)
    normalization_model_version: Mapped[str | None] = mapped_column(sa.String(128), nullable=True, default=None)
    warnings: Mapped[list[object]] = mapped_column(AdjustedJSON, nullable=False, default_factory=list)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime,
        nullable=False,
        default_factory=naive_utc_now,
        server_default=sa.func.current_timestamp(),
        init=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime,
        nullable=False,
        default_factory=naive_utc_now,
        server_default=sa.func.current_timestamp(),
        onupdate=sa.func.current_timestamp(),
        init=False,
    )


class JobProfile(TypeBase):
    __tablename__ = "ti_job_profiles"
    __table_args__ = (
        sa.PrimaryKeyConstraint("id", name="ti_job_profile_pkey"),
        sa.Index("ti_job_profile_tenant_created_idx", "tenant_id", "created_at"),
        sa.Index("ti_job_profile_tenant_status_idx", "tenant_id", "status"),
        sa.Index("ti_job_profile_tenant_policy_idx", "tenant_id", "scoring_policy_id"),
    )

    id: Mapped[str] = mapped_column(StringUUID, default_factory=_uuid, init=False)
    tenant_id: Mapped[str] = mapped_column(StringUUID, nullable=False)
    original_title: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    created_by: Mapped[str] = mapped_column(StringUUID, nullable=False)
    canonical_title: Mapped[str | None] = mapped_column(sa.String(255), nullable=True, default=None)
    job_family: Mapped[str | None] = mapped_column(sa.String(255), nullable=True, default=None)
    specialization: Mapped[str | None] = mapped_column(sa.String(255), nullable=True, default=None)
    seniority: Mapped[str | None] = mapped_column(sa.String(64), nullable=True, default=None)
    department: Mapped[str | None] = mapped_column(sa.String(255), nullable=True, default=None)
    location: Mapped[str | None] = mapped_column(sa.String(255), nullable=True, default=None)
    workplace_mode: Mapped[str | None] = mapped_column(sa.String(64), nullable=True, default=None)
    employment_type: Mapped[str | None] = mapped_column(sa.String(64), nullable=True, default=None)
    business_objectives: Mapped[list[object]] = mapped_column(AdjustedJSON, nullable=False, default_factory=list)
    responsibilities: Mapped[list[object]] = mapped_column(AdjustedJSON, nullable=False, default_factory=list)
    must_have_skills: Mapped[list[object]] = mapped_column(AdjustedJSON, nullable=False, default_factory=list)
    preferred_skills: Mapped[list[object]] = mapped_column(AdjustedJSON, nullable=False, default_factory=list)
    experience_requirement: Mapped[dict[str, object]] = mapped_column(
        AdjustedJSON, nullable=False, default_factory=dict
    )
    education_requirement: Mapped[dict[str, object]] = mapped_column(AdjustedJSON, nullable=False, default_factory=dict)
    english_requirement: Mapped[dict[str, object]] = mapped_column(AdjustedJSON, nullable=False, default_factory=dict)
    hard_requirements: Mapped[list[object]] = mapped_column(AdjustedJSON, nullable=False, default_factory=list)
    scoring_policy_id: Mapped[str | None] = mapped_column(
        StringUUID,
        sa.ForeignKey("ti_scoring_policies.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
    )
    status: Mapped[JobStatus] = mapped_column(
        EnumText(JobStatus, length=32), nullable=False, default=JobStatus.DRAFT, server_default=sa.text("'draft'")
    )
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=1, server_default=sa.text("1"))
    approved_by: Mapped[str | None] = mapped_column(StringUUID, nullable=True, default=None)
    published_at: Mapped[datetime | None] = mapped_column(sa.DateTime, nullable=True, default=None)
    deleted_at: Mapped[datetime | None] = mapped_column(sa.DateTime, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime,
        nullable=False,
        default_factory=naive_utc_now,
        server_default=sa.func.current_timestamp(),
        init=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime,
        nullable=False,
        default_factory=naive_utc_now,
        server_default=sa.func.current_timestamp(),
        onupdate=sa.func.current_timestamp(),
        init=False,
    )


class ScoringPolicy(TypeBase):
    __tablename__ = "ti_scoring_policies"
    __table_args__ = (
        sa.PrimaryKeyConstraint("id", name="ti_scoring_policy_pkey"),
        sa.UniqueConstraint("tenant_id", "name", "version", name="ti_scoring_policy_tenant_name_version_uq"),
        sa.Index("ti_scoring_policy_tenant_active_idx", "tenant_id", "active"),
    )

    id: Mapped[str] = mapped_column(StringUUID, default_factory=_uuid, init=False)
    tenant_id: Mapped[str] = mapped_column(StringUUID, nullable=False)
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    created_by: Mapped[str] = mapped_column(StringUUID, nullable=False)
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=1)
    criterion_weights: Mapped[dict[str, object]] = mapped_column(AdjustedJSON, nullable=False, default_factory=dict)
    criterion_formulas: Mapped[dict[str, object]] = mapped_column(AdjustedJSON, nullable=False, default_factory=dict)
    recommendation_thresholds: Mapped[dict[str, object]] = mapped_column(
        AdjustedJSON, nullable=False, default_factory=dict
    )
    evidence_coverage_threshold: Mapped[float] = mapped_column(sa.Float, nullable=False, default=0.7)
    confidence_rules: Mapped[dict[str, object]] = mapped_column(AdjustedJSON, nullable=False, default_factory=dict)
    active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False, server_default=sa.text("false"))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime,
        nullable=False,
        default_factory=naive_utc_now,
        server_default=sa.func.current_timestamp(),
        init=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime,
        nullable=False,
        default_factory=naive_utc_now,
        server_default=sa.func.current_timestamp(),
        onupdate=sa.func.current_timestamp(),
        init=False,
    )


class AuditEvent(TypeBase):
    """Append-only event. Mutation methods are intentionally absent from its repository."""

    __tablename__ = "ti_audit_events"
    __table_args__ = (
        sa.PrimaryKeyConstraint("id", name="ti_audit_event_pkey"),
        sa.UniqueConstraint("tenant_id", "event_hash", name="ti_audit_event_tenant_hash_uq"),
        sa.Index("ti_audit_event_tenant_created_idx", "tenant_id", "created_at", "id"),
        sa.Index("ti_audit_event_tenant_object_idx", "tenant_id", "object_type", "object_id"),
    )

    id: Mapped[str] = mapped_column(StringUUID, default_factory=_uuid, init=False)
    tenant_id: Mapped[str] = mapped_column(StringUUID, nullable=False)
    event_type: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    actor_id: Mapped[str] = mapped_column(StringUUID, nullable=False)
    action: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    result: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    correlation_id: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    event_hash: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    actor_role: Mapped[str | None] = mapped_column(sa.String(64), nullable=True, default=None)
    pseudonymous_candidate_id: Mapped[str | None] = mapped_column(sa.String(64), nullable=True, default=None)
    job_id: Mapped[str | None] = mapped_column(StringUUID, nullable=True, default=None)
    object_type: Mapped[str | None] = mapped_column(sa.String(64), nullable=True, default=None)
    object_id: Mapped[str | None] = mapped_column(StringUUID, nullable=True, default=None)
    policy_version: Mapped[str | None] = mapped_column(sa.String(64), nullable=True, default=None)
    model_versions: Mapped[dict[str, object]] = mapped_column(AdjustedJSON, nullable=False, default_factory=dict)
    metadata_: Mapped[dict[str, object]] = mapped_column("metadata", AdjustedJSON, nullable=False, default_factory=dict)
    previous_event_hash: Mapped[str | None] = mapped_column(sa.String(64), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime,
        nullable=False,
        default_factory=naive_utc_now,
        server_default=sa.func.current_timestamp(),
        init=False,
    )
