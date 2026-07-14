# ADR 0001: Modular extension inside one Dify fork

- Status: accepted
- Date: 2026-07-15

## Context

Talent Intelligence needs recruitment records, privacy enforcement, deterministic scoring, salary calculations, human decisions, and auditability while retaining Dify's workflow and model platform. A second service would duplicate authentication, tenancy, storage, deployment, and operational concerns and would create another privacy boundary.

## Decision

Maintain one Dify fork and isolate recruitment behavior in `api/extensions/talent_intelligence` plus corresponding feature-owned frontend, plugin, workflow, migration, and documentation paths as they are implemented.

Dify remains responsible for Flask application hosting, authentication, accounts and tenants, SQLAlchemy connectivity, Alembic migrations, object storage, Celery/Redis, model providers, knowledge bases, workflows, plugins, logging, and the Next.js shell. Talent Intelligence owns all recruitment records and rules. Dify workflow state is never the source of truth for candidates, jobs, salary observations, matches, or HR decisions.

All integration points are guarded by `TALENT_INTELLIGENCE_ENABLED`, which defaults to false. Disabled deployments retain existing Dify behavior and expose no Talent Intelligence UI or API surface.

## Core modifications

Phase 0 modifies only:

- `api/configs/feature/__init__.py` to compose the extension flag into `DifyConfig`;
- `docker/.env.example` to document the disabled default; and
- `api/tests/unit_tests/configs/test_dify_config.py` to lock down flag parsing.

Later core hooks must remain small, feature-gated, delegate immediately to the extension, and be recorded in `docs/talent-intelligence/core-modifications.md`.

## Consequences

The single deployment and shared tenant model reduce operational and authorization drift. The module boundary keeps domain logic reviewable and limits upstream conflicts. Sharing the Dify process means privacy-sensitive code must be especially strict about tenant predicates, logs, prompts, task payloads, and storage keys.

## Upstream merge strategy

The private fork should use `origin`; official Dify should use `upstream`. Upgrade branches will merge or rebase an upstream release, review the core-modification register, run migration and feature-disabled smoke tests first, then execute Talent Intelligence unit, tenant-isolation, privacy, workflow-contract, and end-to-end tests. Generated Compose files will be regenerated from their source template rather than hand-edited.
