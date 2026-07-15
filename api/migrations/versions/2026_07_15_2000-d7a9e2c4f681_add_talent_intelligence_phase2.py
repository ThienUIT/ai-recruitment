"""add secure Talent Intelligence CV ingestion

Revision ID: d7a9e2c4f681
Revises: c3d7e9f1a462
Create Date: 2026-07-15 20:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

import models

revision = "d7a9e2c4f681"
down_revision = "c3d7e9f1a462"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ti_candidate_documents",
        sa.Column("id", models.types.StringUUID(), nullable=False),
        sa.Column("tenant_id", models.types.StringUUID(), nullable=False),
        sa.Column("candidate_id", models.types.StringUUID(), nullable=False),
        sa.Column("status", sa.String(32), server_default=sa.text("'uploaded'"), nullable=False),
        sa.Column("mime_type", sa.String(128), nullable=False),
        sa.Column("file_extension", sa.String(16), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("raw_object_key", sa.String(512), nullable=True),
        sa.Column("masked_artifact_object_key", sa.String(512), nullable=True),
        sa.Column("malware_scan_status", sa.String(32), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("malware_scanner_version", sa.String(128), nullable=True),
        sa.Column("parser_name", sa.String(64), nullable=True),
        sa.Column("parser_version", sa.String(64), nullable=True),
        sa.Column("requires_ocr", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("pii_entity_counts", models.types.AdjustedJSON(), nullable=False),
        sa.Column("pii_risk_score", sa.Float(), nullable=True),
        sa.Column("manual_review_required", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("processing_attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("safe_error_message", sa.String(255), nullable=True),
        sa.Column("uploaded_by", models.types.StringUUID(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("processing_started_at", sa.DateTime(), nullable=True),
        sa.Column("processing_completed_at", sa.DateTime(), nullable=True),
        sa.Column("raw_delete_at", sa.DateTime(), nullable=True),
        sa.Column("raw_deleted_at", sa.DateTime(), nullable=True),
        sa.Column("masked_deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "candidate_id"],
            ["ti_candidates.tenant_id", "ti_candidates.id"],
            name="ti_candidate_document_tenant_candidate_fk",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="ti_candidate_document_pkey"),
        sa.UniqueConstraint("tenant_id", "id", name="ti_candidate_document_tenant_id_id_uq"),
    )
    op.create_index(
        "ti_candidate_document_tenant_candidate_idx",
        "ti_candidate_documents",
        ["tenant_id", "candidate_id"],
    )
    op.create_index("ti_candidate_document_tenant_status_idx", "ti_candidate_documents", ["tenant_id", "status"])
    op.create_index("ti_candidate_document_raw_delete_idx", "ti_candidate_documents", ["raw_delete_at"])
    op.create_index("ti_candidate_document_tenant_sha256_idx", "ti_candidate_documents", ["tenant_id", "sha256"])
    op.add_column("ti_candidate_pii", sa.Column("encrypted_placeholder_map", models.types.LongText(), nullable=True))
    op.add_column(
        "ti_candidate_pii",
        sa.Column("pii_schema_version", sa.String(32), server_default=sa.text("'v1'"), nullable=False),
    )
    op.add_column("ti_candidate_pii", sa.Column("pii_detection_metadata", models.types.AdjustedJSON(), nullable=True))
    op.execute("UPDATE ti_candidate_pii SET pii_detection_metadata = '{}' WHERE pii_detection_metadata IS NULL")
    op.alter_column("ti_candidate_pii", "pii_detection_metadata", nullable=False)
    op.add_column("ti_candidate_pii", sa.Column("updated_from_document_id", models.types.StringUUID(), nullable=True))


def downgrade() -> None:
    op.drop_column("ti_candidate_pii", "updated_from_document_id")
    op.drop_column("ti_candidate_pii", "pii_detection_metadata")
    op.drop_column("ti_candidate_pii", "pii_schema_version")
    op.drop_column("ti_candidate_pii", "encrypted_placeholder_map")
    op.drop_index("ti_candidate_document_tenant_sha256_idx", table_name="ti_candidate_documents")
    op.drop_index("ti_candidate_document_raw_delete_idx", table_name="ti_candidate_documents")
    op.drop_index("ti_candidate_document_tenant_status_idx", table_name="ti_candidate_documents")
    op.drop_index("ti_candidate_document_tenant_candidate_idx", table_name="ti_candidate_documents")
    op.drop_table("ti_candidate_documents")
