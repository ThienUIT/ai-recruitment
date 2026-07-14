# Talent Intelligence architecture discovery

## Repository identity

- Discovery date: 2026-07-15 (Asia/Saigon).
- Git commit: `40df83de660d19b17d9674821e82aa2bd4b61a49`.
- Git description: `1.16.0-rc1-108-g40df83de66` before Phase 0 changes.
- Package and Docker image version: `1.16.0-rc1`.
- Branch: `main`, tracking `origin/main`.
- Remote: `origin` points to `https://github.com/langgenius/dify.git` for fetch and push.
- Classification: clean upstream Dify checkout, not yet a private recruitment fork. There is no separate `upstream` remote.
- Initial working tree: clean. Existing user customizations were therefore not present to preserve.

Before customization, a private fork should become `origin` and the official Dify repository should become `upstream`.
Changing remotes is intentionally not part of Phase 0 because no private remote URL was supplied.

## Detected architecture

| Concern | Detected implementation |
| --- | --- |
| Backend | Python 3.12, Flask 3.1, Flask-RESTX |
| ORM | SQLAlchemy 2-style models using shared metadata and `models.base.TypeBase` |
| Migrations | Flask-Migrate and Alembic under `api/migrations` |
| Task queue | Celery 5.6 with the existing Redis deployment |
| Frontend | Next.js, React, TypeScript, pnpm workspace |
| Backend tests | pytest |
| Frontend tests | Vitest and React Testing Library |
| Object storage | `extensions.ext_storage.storage` over Dify storage providers |
| Plugins | Dify plugin daemon image `0.6.3-local` |
| Workflow DSL | Export fixture version `0.3.1`; workflow node versions remain node-specific |
| Deployment | `docker/docker-compose.yaml`, generated from `docker/docker-compose-template.yaml` |

The root package requires Node `^22.22.1` and pnpm `11.10.0`. The API and web manifests both report Dify `1.16.0-rc1`.

## Deployment state

- Docker Compose `v5.3.0` is installed.
- `docker compose ps` at the repository root fails because the Compose file lives under `docker/`.
- `docker compose -f docker/docker-compose.yaml ps` succeeds and reports no running services.
- `docker compose -f docker/docker-compose.yaml config --quiet` succeeds.
- An ignored local `docker/.env` exists. It was not read into documentation, printed, or modified; it does not currently declare `TALENT_INTELLIGENCE_ENABLED`.
- No containers were started during discovery.

During final Phase 0 verification, the pre-existing Compose project was running (it was started outside this work). The API, PostgreSQL, Redis, local sandbox, and sandbox containers reported healthy; the web, workers, plugin daemon, agent backend, Nginx, and Weaviate containers reported running. `http://localhost/` returned HTTP 307 and `http://localhost/console/api/setup` returned HTTP 200. These containers use upstream `1.16.0-rc1` images, so this verifies the baseline deployment, not the unbuilt source-tree extension.

## Local-source runtime integration

The upstream Compose file has four services that import and execute `/app/api` Python code from the Dify API image:

| Service | Runtime mode | Local-source requirement |
| --- | --- | --- |
| `api` | Gunicorn Flask API | Serves the Talent Intelligence console route. |
| `api_websocket` | Gunicorn collaboration API | Imports the same application factory and controller graph. |
| `worker` | Celery worker | Imports Dify configuration and the application task graph. |
| `worker_beat` | Celery beat | Imports the Dify Celery application and configuration. |

`docker/docker-compose.talent-intelligence.yaml` replaces the image for all four with a build from `api/Dockerfile` and the repository root context. Other services continue to use upstream images.

Phase 0.5 runtime verification built `dify-api-local:talent-intelligence` and recreated all four services. Inside the API container, `extensions.talent_intelligence` imported from `/app/api`, reported version `0.1.0`, and the health-controller SHA-256 matched the working tree. With the flag enabled, an authenticated request returned HTTP 200 and the expected module metadata. With the flag disabled, the route returned HTTP 404 while the API remained healthy and `/console/api/setup` returned HTTP 200. The final verified container state is feature-disabled.

## Extension points selected

1. Domain code lives in `api/extensions/talent_intelligence`. It may use Dify services, but generic Dify code must not contain recruitment rules.
2. Configuration uses a dedicated `TalentIntelligenceConfig` mixed into the existing `DifyConfig` composition.
3. Future console APIs will use the existing `/console/api` Flask blueprint, login/session decorators, tenant context, and Pydantic/Flask-RESTX schema conventions.
4. Future models will use Dify SQLAlchemy metadata and Alembic migrations. Prefixed `ti_` tables are the conservative fallback because Dify supports PostgreSQL and MySQL deployments; a PostgreSQL-only schema would break that portability.
5. Future files will use `extensions.ext_storage.storage`; tasks will use the existing Celery application and Redis.
6. Future UI will use Next.js routing, existing workspace context, generated console contracts, Dify UI primitives, and locale resources.
7. Plugin tools may target plugin daemon `0.6.3-local`, but only after a compatible manifest is built and exercised.
8. Workflow files must be derived from exported DSL `0.3.1` examples and cannot be marked compatible until imported successfully.

## Phase 0 boundary

Phase 0 adds a disabled-by-default flag and an importable package boundary. It deliberately adds no controllers, models, migrations, background tasks, navigation, plugins, or workflow DSL. This preserves normal Dify behavior while later phases add tested vertical slices.

Phase 0.5 adds only an authenticated, tenant-resolving runtime health controller and the local-source Compose override. Candidate, job, salary, matching, and scoring persistence remain outside this gate.
