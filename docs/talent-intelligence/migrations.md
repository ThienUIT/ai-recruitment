# Talent Intelligence migrations

Migration `b8f4c2d9e731` follows the single Dify head `7a1c2d9e4b60` and creates only new `ti_` tables, indexes, constraints, and Candidate child foreign keys. It changes no existing Dify table.

From `docker/`, inspect and apply using the local-source Compose stack:

```powershell
docker compose -f docker-compose.yaml -f docker-compose.talent-intelligence.yaml exec -T api flask db heads
docker compose -f docker-compose.yaml -f docker-compose.talent-intelligence.yaml exec -T api flask db current
docker compose -f docker-compose.yaml -f docker-compose.talent-intelligence.yaml exec -T api flask db upgrade
```

The API entrypoint also runs Dify's normal `flask upgrade-db` startup migration path. Validate table/index presence using SQLAlchemy inspection inside the API container so no database password is printed.

The migration includes a reverse-order downgrade. Downgrade is destructive to Talent Intelligence data and is only appropriate for a disposable development database after backup.

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
