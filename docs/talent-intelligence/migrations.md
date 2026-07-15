# Talent Intelligence migrations

Phase 2 revision `d7a9e2c4f681` follows `c3d7e9f1a462`. It creates `ti_candidate_documents` and adds restricted CandidatePII columns. Existing Phase 1 migrations are unchanged; downgrade removes Phase 2 objects only.

Migration `b8f4c2d9e731` follows the single Dify head `7a1c2d9e4b60` and creates only new `ti_` tables, indexes, constraints, and Candidate child foreign keys. It changes no existing Dify table.

Corrective migration `c3d7e9f1a462` follows `b8f4c2d9e731`. It adds `ti_audit_chain_heads`, backfills
`chain_sequence` without rewriting hashes, validates legacy chain links, installs append-only triggers, adds an
active-policy uniqueness invariant, and replaces ID-only relationships with tenant-aware composite foreign keys. It
fails with a diagnostic instead of silently repairing invalid chains, duplicate active policies, or cross-tenant rows.

From `docker/`, inspect and apply using the local-source Compose stack:

```powershell
docker compose -f docker-compose.yaml -f docker-compose.talent-intelligence.yaml exec -T api flask db heads
docker compose -f docker-compose.yaml -f docker-compose.talent-intelligence.yaml exec -T api flask db current
docker compose -f docker-compose.yaml -f docker-compose.talent-intelligence.yaml exec -T api flask db upgrade
```

The API entrypoint also runs Dify's normal `flask upgrade-db` startup migration path. Validate table/index presence using SQLAlchemy inspection inside the API container so no database password is printed.

The corrective downgrade removes its triggers, function, generated column, constraints, chain-head table, and
sequence column in dependency order while preserving AuditEvent rows. Downgrading the original `b8f4c2d9e731`
remains destructive to Talent Intelligence data and is only appropriate for a disposable database after backup.

PostgreSQL uses a PL/pgSQL rejection function and two triggers. MySQL uses equivalent `SIGNAL SQLSTATE '45000'`
triggers. Both use a stored generated active-policy key. PostgreSQL concurrency is covered in Phase 1 integration
tests; MySQL DDL compatibility must be rechecked whenever Dify's supported MySQL baseline changes.

## Explicit development seed

Seeding is never automatic. In an API `flask shell`, deliberately select an existing tenant and account, then run:

```python
from extensions.ext_database import db
from extensions.talent_intelligence.seeds import seed_development_data
from models import Account

account = db.session.get(Account, "EXISTING_ACCOUNT_ID")
result = seed_development_data(db.session, "EXISTING_TENANT_ID", account)
print(result)
```

The seed creates one default active policy, one synthetic job, one synthetic candidate, and one masked profile. Repeated execution is idempotent. It contains no real CV data, plaintext PII, or CandidatePII row.
