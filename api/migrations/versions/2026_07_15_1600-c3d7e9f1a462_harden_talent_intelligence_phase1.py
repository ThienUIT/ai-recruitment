"""harden Talent Intelligence Phase 1 integrity

Revision ID: c3d7e9f1a462
Revises: b8f4c2d9e731
Create Date: 2026-07-15 16:00:00.000000

Existing audit hashes are not rewritten. Records are deterministically ordered
by their legacy verifier order (created_at, id), validated as one linked chain,
and assigned sequence numbers before append-only triggers are installed.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import models

revision = "c3d7e9f1a462"
down_revision = "b8f4c2d9e731"
branch_labels = None
depends_on = None


def _audit_events() -> sa.Table:
    return sa.table(
        "ti_audit_events",
        sa.column("id", models.types.StringUUID()),
        sa.column("tenant_id", models.types.StringUUID()),
        sa.column("event_hash", sa.String(64)),
        sa.column("previous_event_hash", sa.String(64)),
        sa.column("chain_sequence", sa.BigInteger()),
        sa.column("created_at", sa.DateTime()),
    )


def _audit_chain_heads() -> sa.Table:
    return sa.table(
        "ti_audit_chain_heads",
        sa.column("tenant_id", models.types.StringUUID()),
        sa.column("last_event_id", models.types.StringUUID()),
        sa.column("last_event_hash", sa.String(64)),
        sa.column("last_sequence", sa.BigInteger()),
    )


def _invalid_relationship_count(connection: sa.Connection, sql: str) -> int:
    return int(connection.scalar(sa.text(sql)) or 0)


def _validate_tenant_relationships(connection: sa.Connection) -> None:
    checks = {
        "ti_candidate_pii": """
            SELECT COUNT(*) FROM ti_candidate_pii child
            JOIN ti_candidates parent ON parent.id = child.candidate_id
            WHERE child.tenant_id <> parent.tenant_id
        """,
        "ti_candidate_profiles": """
            SELECT COUNT(*) FROM ti_candidate_profiles child
            JOIN ti_candidates parent ON parent.id = child.candidate_id
            WHERE child.tenant_id <> parent.tenant_id
        """,
        "ti_job_profiles": """
            SELECT COUNT(*) FROM ti_job_profiles child
            JOIN ti_scoring_policies parent ON parent.id = child.scoring_policy_id
            WHERE child.scoring_policy_id IS NOT NULL AND child.tenant_id <> parent.tenant_id
        """,
    }
    invalid = {table: _invalid_relationship_count(connection, sql) for table, sql in checks.items()}
    invalid = {table: count for table, count in invalid.items() if count}
    if invalid:
        details = ", ".join(f"{table}={count}" for table, count in sorted(invalid.items()))
        raise RuntimeError(f"Talent Intelligence tenant-integrity migration blocked by invalid rows: {details}")


def _validate_active_policies(connection: sa.Connection) -> None:
    duplicate = connection.execute(
        sa.text(
            """
            SELECT tenant_id, name, COUNT(*) AS active_count
            FROM ti_scoring_policies
            WHERE active IS TRUE
            GROUP BY tenant_id, name
            HAVING COUNT(*) > 1
            """
        )
    ).first()
    if duplicate is not None:
        raise RuntimeError(
            "Talent Intelligence policy-integrity migration blocked: "
            f"tenant={duplicate.tenant_id}, name={duplicate.name!r}, active_count={duplicate.active_count}"
        )


def _backfill_audit_sequences(connection: sa.Connection) -> None:
    events = _audit_events()
    heads = _audit_chain_heads()
    rows = connection.execute(
        sa.select(
            events.c.id,
            events.c.tenant_id,
            events.c.event_hash,
            events.c.previous_event_hash,
        ).order_by(events.c.tenant_id, events.c.created_at, events.c.id)
    ).mappings()
    tenant_state: dict[object, tuple[int, str | None, object]] = {}
    for row in rows:
        sequence, previous_hash, _ = tenant_state.get(row["tenant_id"], (0, None, row["id"]))
        if row["previous_event_hash"] != previous_hash:
            raise RuntimeError(
                "Talent Intelligence audit migration blocked by an invalid legacy chain: "
                f"tenant={row['tenant_id']}, event={row['id']}"
            )
        sequence += 1
        connection.execute(events.update().where(events.c.id == row["id"]).values(chain_sequence=sequence))
        tenant_state[row["tenant_id"]] = (sequence, row["event_hash"], row["id"])

    for tenant_id, (sequence, event_hash, event_id) in tenant_state.items():
        connection.execute(
            heads.insert().values(
                tenant_id=tenant_id,
                last_event_id=event_id,
                last_event_hash=event_hash,
                last_sequence=sequence,
            )
        )


def _foreign_key_name(connection: sa.Connection, table_name: str, columns: Sequence[str]) -> str:
    expected = list(columns)
    for foreign_key in sa.inspect(connection).get_foreign_keys(table_name):
        if foreign_key["constrained_columns"] == expected and foreign_key["name"]:
            return str(foreign_key["name"])
    raise RuntimeError(f"Expected foreign key not found: {table_name}({', '.join(columns)})")


def _create_append_only_triggers(connection: sa.Connection) -> None:
    if connection.dialect.name == "postgresql":
        op.execute(
            """
            CREATE FUNCTION ti_reject_audit_event_mutation() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
                RAISE EXCEPTION 'ti_audit_events is append-only';
            END;
            $$
            """
        )
        op.execute(
            """
            CREATE TRIGGER ti_audit_events_no_update
            BEFORE UPDATE ON ti_audit_events
            FOR EACH ROW EXECUTE FUNCTION ti_reject_audit_event_mutation()
            """
        )
        op.execute(
            """
            CREATE TRIGGER ti_audit_events_no_delete
            BEFORE DELETE ON ti_audit_events
            FOR EACH ROW EXECUTE FUNCTION ti_reject_audit_event_mutation()
            """
        )
    elif connection.dialect.name == "mysql":
        op.execute(
            """
            CREATE TRIGGER ti_audit_events_no_update
            BEFORE UPDATE ON ti_audit_events FOR EACH ROW
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'ti_audit_events is append-only'
            """
        )
        op.execute(
            """
            CREATE TRIGGER ti_audit_events_no_delete
            BEFORE DELETE ON ti_audit_events FOR EACH ROW
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'ti_audit_events is append-only'
            """
        )
    else:
        raise RuntimeError(f"Unsupported database for audit append-only triggers: {connection.dialect.name}")


def _drop_append_only_triggers(connection: sa.Connection) -> None:
    if connection.dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS ti_audit_events_no_update ON ti_audit_events")
        op.execute("DROP TRIGGER IF EXISTS ti_audit_events_no_delete ON ti_audit_events")
        op.execute("DROP FUNCTION IF EXISTS ti_reject_audit_event_mutation()")
    else:
        op.execute("DROP TRIGGER IF EXISTS ti_audit_events_no_update")
        op.execute("DROP TRIGGER IF EXISTS ti_audit_events_no_delete")


def upgrade() -> None:
    connection = op.get_bind()
    _validate_tenant_relationships(connection)
    _validate_active_policies(connection)

    op.add_column("ti_audit_events", sa.Column("chain_sequence", sa.BigInteger(), nullable=True))
    op.create_table(
        "ti_audit_chain_heads",
        sa.Column("tenant_id", models.types.StringUUID(), nullable=False),
        sa.Column("last_event_id", models.types.StringUUID(), nullable=True),
        sa.Column("last_event_hash", sa.String(64), nullable=True),
        sa.Column("last_sequence", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.PrimaryKeyConstraint("tenant_id", name="ti_audit_chain_head_pkey"),
    )
    _backfill_audit_sequences(connection)
    op.alter_column("ti_audit_events", "chain_sequence", nullable=False)
    op.create_unique_constraint("ti_audit_event_tenant_sequence_uq", "ti_audit_events", ["tenant_id", "chain_sequence"])

    op.create_unique_constraint("ti_candidate_tenant_id_id_uq", "ti_candidates", ["tenant_id", "id"])
    op.create_unique_constraint("ti_scoring_policy_tenant_id_id_uq", "ti_scoring_policies", ["tenant_id", "id"])
    pii_fk = _foreign_key_name(connection, "ti_candidate_pii", ["candidate_id"])
    profile_fk = _foreign_key_name(connection, "ti_candidate_profiles", ["candidate_id"])
    policy_fk = _foreign_key_name(connection, "ti_job_profiles", ["scoring_policy_id"])
    op.drop_constraint(pii_fk, "ti_candidate_pii", type_="foreignkey")
    op.drop_constraint(profile_fk, "ti_candidate_profiles", type_="foreignkey")
    op.drop_constraint(policy_fk, "ti_job_profiles", type_="foreignkey")
    op.create_foreign_key(
        "ti_candidate_pii_tenant_candidate_fk",
        "ti_candidate_pii",
        "ti_candidates",
        ["tenant_id", "candidate_id"],
        ["tenant_id", "id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "ti_candidate_profile_tenant_candidate_fk",
        "ti_candidate_profiles",
        "ti_candidates",
        ["tenant_id", "candidate_id"],
        ["tenant_id", "id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "ti_job_profile_tenant_policy_fk",
        "ti_job_profiles",
        "ti_scoring_policies",
        ["tenant_id", "scoring_policy_id"],
        ["tenant_id", "id"],
    )

    op.add_column(
        "ti_scoring_policies",
        sa.Column(
            "active_policy_name",
            sa.String(255),
            sa.Computed("CASE WHEN active THEN name ELSE NULL END", persisted=True),
            nullable=True,
        ),
    )
    op.create_unique_constraint(
        "ti_scoring_policy_tenant_active_name_uq",
        "ti_scoring_policies",
        ["tenant_id", "active_policy_name"],
    )
    _create_append_only_triggers(connection)


def downgrade() -> None:
    connection = op.get_bind()
    _drop_append_only_triggers(connection)
    op.drop_constraint("ti_scoring_policy_tenant_active_name_uq", "ti_scoring_policies", type_="unique")
    op.drop_column("ti_scoring_policies", "active_policy_name")

    op.drop_constraint("ti_job_profile_tenant_policy_fk", "ti_job_profiles", type_="foreignkey")
    op.drop_constraint("ti_candidate_profile_tenant_candidate_fk", "ti_candidate_profiles", type_="foreignkey")
    op.drop_constraint("ti_candidate_pii_tenant_candidate_fk", "ti_candidate_pii", type_="foreignkey")
    op.create_foreign_key(
        "ti_candidate_pii_candidate_id_fkey",
        "ti_candidate_pii",
        "ti_candidates",
        ["candidate_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "ti_candidate_profiles_candidate_id_fkey",
        "ti_candidate_profiles",
        "ti_candidates",
        ["candidate_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "ti_job_profile_scoring_policy_fk",
        "ti_job_profiles",
        "ti_scoring_policies",
        ["scoring_policy_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_constraint("ti_scoring_policy_tenant_id_id_uq", "ti_scoring_policies", type_="unique")
    op.drop_constraint("ti_candidate_tenant_id_id_uq", "ti_candidates", type_="unique")

    op.drop_constraint("ti_audit_event_tenant_sequence_uq", "ti_audit_events", type_="unique")
    op.drop_table("ti_audit_chain_heads")
    op.drop_column("ti_audit_events", "chain_sequence")
