# Dify core modifications

This register tracks changes outside feature-owned Talent Intelligence paths.

| File | Reason and delegation | Conflict risk | Retest |
| --- | --- | --- | --- |
| `api/configs/feature/__init__.py` | Composes the feature-owned configuration into `DifyConfig`; contains no domain behavior. | Low: the mix-in list changes upstream. | Talent Intelligence config unit test and API configuration import. |
| `api/controllers/console/__init__.py` | Calls the feature-owned console registrar. The registrar owns the flag check and route implementation. | Medium: the upstream controller import/registration list changes frequently. | Enabled/disabled health registration tests and authenticated HTTP smoke test. |
| `api/tests/unit_tests/configs/test_dify_config.py` | Verifies disabled default and environment opt-in. | Low. | Run the focused pytest test. |
| `docker/.env.example` | Documents the disabled deployment default. | Low: environment template changes frequently. | Render Compose config with the example copied to `.env`. |
| `api/migrations/versions/2026_07_15_1200-b8f4c2d9e731_add_talent_intelligence_phase1_tables.py` | Uses Dify's shared Alembic chain to create extension-owned tables. Migration placement is required by the single upstream migration runner; domain models remain in the extension. | Medium: future upstream migration heads can require a merge revision during rebase. | Inspect heads, upgrade, schema inspection, and downgrade on a disposable database. |
| `api/migrations/versions/2026_07_15_1600-c3d7e9f1a462_harden_talent_intelligence_phase1.py` | Adds chain-head serialization, append-only triggers, policy uniqueness, and tenant-aware foreign keys without rewriting the applied Phase 1 migration. | Medium: trigger and generated-column DDL must remain PostgreSQL/MySQL compatible. | Clean and existing-data upgrade, PostgreSQL concurrency, trigger, index, FK, and downgrade checks. |

No generic service, model, workflow, authentication, or frontend file is modified through Phase 1. The generic console change remains a two-line import and delegation hook; all route, domain, permission, persistence, seed, and audit behavior remains in `api/extensions/talent_intelligence`.
