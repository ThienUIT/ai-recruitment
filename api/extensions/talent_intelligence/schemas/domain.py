"""Strict request and response contracts for Phase 1 resources."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from fields.base import ResponseModel

from ..models import CandidateProcessingStatus, JobStatus


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PaginationQuery(StrictModel):
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)


class ConsentScope(StrictModel):
    current_application: bool = True
    talent_pool: bool = False


class CandidateCreatePayload(StrictModel):
    external_reference: str | None = Field(default=None, max_length=255)
    consent_scope: ConsentScope = Field(default_factory=ConsentScope)


class CandidateUpdatePayload(StrictModel):
    external_reference: str | None = Field(default=None, max_length=255)
    consent_scope: ConsentScope | None = None


class CandidateResponse(ResponseModel):
    id: str
    tenant_id: str
    external_reference: str | None
    processing_status: CandidateProcessingStatus
    consent_scope: dict[str, object]
    created_by: str
    created_at: datetime
    updated_at: datetime
    deletion_requested_at: datetime | None
    deleted_at: datetime | None


class CandidateListResponse(ResponseModel):
    data: list[CandidateResponse]
    page: int
    limit: int
    total: int


class CandidateProfilePayload(StrictModel):
    headline: str | None = Field(default=None, max_length=512)
    total_experience_months: int | None = Field(default=None, ge=0)
    current_location: str | None = Field(default=None, max_length=255)
    workplace_preferences: list[object] = Field(default_factory=list)
    willing_to_relocate: bool | None = None
    notice_period_days: int | None = Field(default=None, ge=0)
    experiences: list[object] = Field(default_factory=list)
    projects: list[object] = Field(default_factory=list)
    skills: list[object] = Field(default_factory=list)
    educations: list[object] = Field(default_factory=list)
    certifications: list[object] = Field(default_factory=list)
    languages: list[object] = Field(default_factory=list)
    extraction_confidence: float | None = Field(default=None, ge=0, le=1)
    parser_version: str | None = Field(default=None, max_length=128)
    normalization_model_version: str | None = Field(default=None, max_length=128)
    warnings: list[object] = Field(default_factory=list)


class CandidateProfileResponse(ResponseModel):
    id: str
    candidate_id: str
    tenant_id: str
    headline: str | None
    total_experience_months: int | None
    current_location: str | None
    workplace_preferences: list[object]
    willing_to_relocate: bool | None
    notice_period_days: int | None
    experiences: list[object]
    projects: list[object]
    skills: list[object]
    educations: list[object]
    certifications: list[object]
    languages: list[object]
    extraction_confidence: float | None
    parser_version: str | None
    normalization_model_version: str | None
    warnings: list[object]
    created_at: datetime
    updated_at: datetime


class JobCreatePayload(StrictModel):
    original_title: str = Field(min_length=1, max_length=255)
    canonical_title: str | None = Field(default=None, max_length=255)
    job_family: str | None = Field(default=None, max_length=255)
    specialization: str | None = Field(default=None, max_length=255)
    seniority: str | None = Field(default=None, max_length=64)
    department: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    workplace_mode: str | None = Field(default=None, max_length=64)
    employment_type: str | None = Field(default=None, max_length=64)
    business_objectives: list[object] = Field(default_factory=list)
    responsibilities: list[object] = Field(default_factory=list)
    must_have_skills: list[object] = Field(default_factory=list)
    preferred_skills: list[object] = Field(default_factory=list)
    experience_requirement: dict[str, object] = Field(default_factory=dict)
    education_requirement: dict[str, object] = Field(default_factory=dict)
    english_requirement: dict[str, object] = Field(default_factory=dict)
    hard_requirements: list[object] = Field(default_factory=list)
    scoring_policy_id: str | None = None


class JobUpdatePayload(StrictModel):
    original_title: str | None = Field(default=None, min_length=1, max_length=255)
    canonical_title: str | None = Field(default=None, max_length=255)
    job_family: str | None = Field(default=None, max_length=255)
    specialization: str | None = Field(default=None, max_length=255)
    seniority: str | None = Field(default=None, max_length=64)
    department: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    workplace_mode: str | None = Field(default=None, max_length=64)
    employment_type: str | None = Field(default=None, max_length=64)
    business_objectives: list[object] | None = None
    responsibilities: list[object] | None = None
    must_have_skills: list[object] | None = None
    preferred_skills: list[object] | None = None
    experience_requirement: dict[str, object] | None = None
    education_requirement: dict[str, object] | None = None
    english_requirement: dict[str, object] | None = None
    hard_requirements: list[object] | None = None
    scoring_policy_id: str | None = None


class JobResponse(ResponseModel):
    id: str
    tenant_id: str
    original_title: str
    canonical_title: str | None
    job_family: str | None
    specialization: str | None
    seniority: str | None
    department: str | None
    location: str | None
    workplace_mode: str | None
    employment_type: str | None
    business_objectives: list[object]
    responsibilities: list[object]
    must_have_skills: list[object]
    preferred_skills: list[object]
    experience_requirement: dict[str, object]
    education_requirement: dict[str, object]
    english_requirement: dict[str, object]
    hard_requirements: list[object]
    scoring_policy_id: str | None
    status: JobStatus
    version: int
    created_by: str
    approved_by: str | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class JobListResponse(ResponseModel):
    data: list[JobResponse]
    page: int
    limit: int
    total: int


DEFAULT_CRITERION_WEIGHTS: dict[str, float] = {
    "skills": 40.0,
    "relevant_experience": 25.0,
    "english": 15.0,
    "location": 10.0,
    "education": 10.0,
}


class ScoringPolicyCreatePayload(StrictModel):
    name: str = Field(min_length=1, max_length=255)
    criterion_weights: dict[str, float] = Field(default_factory=lambda: dict(DEFAULT_CRITERION_WEIGHTS))
    criterion_formulas: dict[str, object] = Field(default_factory=dict)
    recommendation_thresholds: dict[str, object] = Field(default_factory=dict)
    evidence_coverage_threshold: float = Field(default=0.7, ge=0, le=1)
    confidence_rules: dict[str, object] = Field(default_factory=dict)

    @field_validator("criterion_weights")
    @classmethod
    def validate_weights(cls, value: dict[str, float]) -> dict[str, float]:
        if any(weight < 0 for weight in value.values()):
            raise ValueError("criterion weights must be non-negative")
        if abs(sum(value.values()) - 100) > 1e-9:
            raise ValueError("criterion weights must total 100")
        return value


class ScoringPolicyResponse(ResponseModel):
    id: str
    tenant_id: str
    name: str
    version: int
    criterion_weights: dict[str, object]
    criterion_formulas: dict[str, object]
    recommendation_thresholds: dict[str, object]
    evidence_coverage_threshold: float
    confidence_rules: dict[str, object]
    active: bool
    created_by: str
    created_at: datetime
    updated_at: datetime


class ScoringPolicyListResponse(ResponseModel):
    data: list[ScoringPolicyResponse]
    page: int
    limit: int
    total: int


class AuditEventResponse(ResponseModel):
    id: str
    tenant_id: str
    event_type: str
    actor_id: str
    actor_role: str | None
    pseudonymous_candidate_id: str | None
    job_id: str | None
    object_type: str | None
    object_id: str | None
    action: str
    result: str
    policy_version: str | None
    model_versions: dict[str, object]
    correlation_id: str
    metadata: dict[str, object] = Field(validation_alias="metadata_")
    previous_event_hash: str | None
    event_hash: str
    chain_sequence: int
    created_at: datetime


class AuditEventListResponse(ResponseModel):
    data: list[AuditEventResponse]
    page: int
    limit: int
    total: int


class AuditVerificationResponse(ResponseModel):
    valid: bool
    event_count: int
    first_invalid_event_id: str | None = None
    failure_reason: str | None = None
