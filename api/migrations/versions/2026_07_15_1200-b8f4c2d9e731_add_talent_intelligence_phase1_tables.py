"""add Talent Intelligence Phase 1 tables

Revision ID: b8f4c2d9e731
Revises: 7a1c2d9e4b60
Create Date: 2026-07-15 12:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

import models

revision = "b8f4c2d9e731"
down_revision = "7a1c2d9e4b60"
branch_labels = None
depends_on = None


def _id_column(name: str = "id") -> sa.Column:
    return sa.Column(name, models.types.StringUUID(), nullable=False)


def _tenant_column() -> sa.Column:
    return sa.Column("tenant_id", models.types.StringUUID(), nullable=False)


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )


def upgrade() -> None:
    op.create_table(
        "ti_candidates",
        _id_column(),
        _tenant_column(),
        sa.Column("created_by", models.types.StringUUID(), nullable=False),
        sa.Column("external_reference", sa.String(length=255), nullable=True),
        sa.Column("processing_status", sa.String(length=32), server_default=sa.text("'created'"), nullable=False),
        sa.Column("consent_scope", models.types.AdjustedJSON(), nullable=False),
        sa.Column("deletion_requested_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="ti_candidate_pkey"),
        sa.UniqueConstraint("tenant_id", "external_reference", name="ti_candidate_tenant_external_ref_uq"),
    )
    op.create_index("ti_candidate_tenant_created_idx", "ti_candidates", ["tenant_id", "created_at"])
    op.create_index("ti_candidate_tenant_status_idx", "ti_candidates", ["tenant_id", "processing_status"])

    op.create_table(
        "ti_candidate_pii",
        _id_column(),
        _id_column("candidate_id"),
        _tenant_column(),
        sa.Column("encryption_key_version", sa.String(length=64), nullable=False),
        sa.Column("encrypted_name", models.types.LongText(), nullable=True),
        sa.Column("encrypted_email", models.types.LongText(), nullable=True),
        sa.Column("encrypted_phone", models.types.LongText(), nullable=True),
        sa.Column("encrypted_address", models.types.LongText(), nullable=True),
        sa.Column("encrypted_personal_urls", models.types.LongText(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["candidate_id"], ["ti_candidates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="ti_candidate_pii_pkey"),
        sa.UniqueConstraint("candidate_id", name="ti_candidate_pii_candidate_uq"),
    )
    op.create_index("ti_candidate_pii_tenant_candidate_idx", "ti_candidate_pii", ["tenant_id", "candidate_id"])

    op.create_table(
        "ti_candidate_profiles",
        _id_column(),
        _id_column("candidate_id"),
        _tenant_column(),
        sa.Column("headline", sa.String(length=512), nullable=True),
        sa.Column("total_experience_months", sa.Integer(), nullable=True),
        sa.Column("current_location", sa.String(length=255), nullable=True),
        sa.Column("workplace_preferences", models.types.AdjustedJSON(), nullable=False),
        sa.Column("willing_to_relocate", sa.Boolean(), nullable=True),
        sa.Column("notice_period_days", sa.Integer(), nullable=True),
        sa.Column("experiences", models.types.AdjustedJSON(), nullable=False),
        sa.Column("projects", models.types.AdjustedJSON(), nullable=False),
        sa.Column("skills", models.types.AdjustedJSON(), nullable=False),
        sa.Column("educations", models.types.AdjustedJSON(), nullable=False),
        sa.Column("certifications", models.types.AdjustedJSON(), nullable=False),
        sa.Column("languages", models.types.AdjustedJSON(), nullable=False),
        sa.Column("extraction_confidence", sa.Float(), nullable=True),
        sa.Column("parser_version", sa.String(length=128), nullable=True),
        sa.Column("normalization_model_version", sa.String(length=128), nullable=True),
        sa.Column("warnings", models.types.AdjustedJSON(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["candidate_id"], ["ti_candidates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="ti_candidate_profile_pkey"),
        sa.UniqueConstraint("candidate_id", name="ti_candidate_profile_candidate_uq"),
    )
    op.create_index("ti_candidate_profile_tenant_candidate_idx", "ti_candidate_profiles", ["tenant_id", "candidate_id"])

    op.create_table(
        "ti_job_profiles",
        _id_column(),
        _tenant_column(),
        sa.Column("original_title", sa.String(length=255), nullable=False),
        sa.Column("created_by", models.types.StringUUID(), nullable=False),
        sa.Column("canonical_title", sa.String(length=255), nullable=True),
        sa.Column("job_family", sa.String(length=255), nullable=True),
        sa.Column("specialization", sa.String(length=255), nullable=True),
        sa.Column("seniority", sa.String(length=64), nullable=True),
        sa.Column("department", sa.String(length=255), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("workplace_mode", sa.String(length=64), nullable=True),
        sa.Column("employment_type", sa.String(length=64), nullable=True),
        sa.Column("business_objectives", models.types.AdjustedJSON(), nullable=False),
        sa.Column("responsibilities", models.types.AdjustedJSON(), nullable=False),
        sa.Column("must_have_skills", models.types.AdjustedJSON(), nullable=False),
        sa.Column("preferred_skills", models.types.AdjustedJSON(), nullable=False),
        sa.Column("experience_requirement", models.types.AdjustedJSON(), nullable=False),
        sa.Column("education_requirement", models.types.AdjustedJSON(), nullable=False),
        sa.Column("english_requirement", models.types.AdjustedJSON(), nullable=False),
        sa.Column("hard_requirements", models.types.AdjustedJSON(), nullable=False),
        sa.Column("scoring_policy_id", models.types.StringUUID(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'draft'"), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("approved_by", models.types.StringUUID(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="ti_job_profile_pkey"),
    )
    op.create_index("ti_job_profile_tenant_created_idx", "ti_job_profiles", ["tenant_id", "created_at"])
    op.create_index("ti_job_profile_tenant_status_idx", "ti_job_profiles", ["tenant_id", "status"])

    op.create_table(
        "ti_scoring_policies",
        _id_column(),
        _tenant_column(),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_by", models.types.StringUUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("criterion_weights", models.types.AdjustedJSON(), nullable=False),
        sa.Column("criterion_formulas", models.types.AdjustedJSON(), nullable=False),
        sa.Column("recommendation_thresholds", models.types.AdjustedJSON(), nullable=False),
        sa.Column("evidence_coverage_threshold", sa.Float(), nullable=False),
        sa.Column("confidence_rules", models.types.AdjustedJSON(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="ti_scoring_policy_pkey"),
        sa.UniqueConstraint("tenant_id", "name", "version", name="ti_scoring_policy_tenant_name_version_uq"),
    )
    op.create_index("ti_scoring_policy_tenant_active_idx", "ti_scoring_policies", ["tenant_id", "active"])

    op.create_foreign_key(
        "ti_job_profile_scoring_policy_fk",
        "ti_job_profiles",
        "ti_scoring_policies",
        ["scoring_policy_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ti_job_profile_tenant_policy_idx", "ti_job_profiles", ["tenant_id", "scoring_policy_id"])

    op.create_table(
        "ti_audit_events",
        _id_column(),
        _tenant_column(),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("actor_id", models.types.StringUUID(), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("result", sa.String(length=64), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("event_hash", sa.String(length=64), nullable=False),
        sa.Column("actor_role", sa.String(length=64), nullable=True),
        sa.Column("pseudonymous_candidate_id", sa.String(length=64), nullable=True),
        sa.Column("job_id", models.types.StringUUID(), nullable=True),
        sa.Column("object_type", sa.String(length=64), nullable=True),
        sa.Column("object_id", models.types.StringUUID(), nullable=True),
        sa.Column("policy_version", sa.String(length=64), nullable=True),
        sa.Column("model_versions", models.types.AdjustedJSON(), nullable=False),
        sa.Column("metadata", models.types.AdjustedJSON(), nullable=False),
        sa.Column("previous_event_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="ti_audit_event_pkey"),
        sa.UniqueConstraint("tenant_id", "event_hash", name="ti_audit_event_tenant_hash_uq"),
    )
    op.create_index("ti_audit_event_tenant_created_idx", "ti_audit_events", ["tenant_id", "created_at", "id"])
    op.create_index("ti_audit_event_tenant_object_idx", "ti_audit_events", ["tenant_id", "object_type", "object_id"])


def downgrade() -> None:
    op.drop_index("ti_audit_event_tenant_object_idx", table_name="ti_audit_events")
    op.drop_index("ti_audit_event_tenant_created_idx", table_name="ti_audit_events")
    op.drop_table("ti_audit_events")
    op.drop_index("ti_job_profile_tenant_policy_idx", table_name="ti_job_profiles")
    op.drop_index("ti_job_profile_tenant_status_idx", table_name="ti_job_profiles")
    op.drop_index("ti_job_profile_tenant_created_idx", table_name="ti_job_profiles")
    op.drop_table("ti_job_profiles")
    op.drop_index("ti_scoring_policy_tenant_active_idx", table_name="ti_scoring_policies")
    op.drop_table("ti_scoring_policies")
    op.drop_index("ti_candidate_profile_tenant_candidate_idx", table_name="ti_candidate_profiles")
    op.drop_table("ti_candidate_profiles")
    op.drop_index("ti_candidate_pii_tenant_candidate_idx", table_name="ti_candidate_pii")
    op.drop_table("ti_candidate_pii")
    op.drop_index("ti_candidate_tenant_status_idx", table_name="ti_candidates")
    op.drop_index("ti_candidate_tenant_created_idx", table_name="ti_candidates")
    op.drop_table("ti_candidates")
