# Talent Intelligence local operations

## Enable the extension

Do not commit `docker/.env`. Add this line to the local file:

```dotenv
TALENT_INTELLIGENCE_ENABLED=true
```

The feature defaults to `false` when the variable is absent. When false, the console health route is not registered.

## Build and start local API source

From `docker/`, run:

```powershell
docker compose -f docker-compose.yaml -f docker-compose.talent-intelligence.yaml up -d --build
docker compose -f docker-compose.yaml -f docker-compose.talent-intelligence.yaml restart nginx
```

The second command refreshes Nginx's upstream address after the API container is replaced. The override builds one local API image and assigns it to `api`, `api_websocket`, `worker`, and `worker_beat`. It does not replace the web, database, Redis, plugin daemon, sandbox, or vector-store images.

Validate the merged configuration without starting services:

```powershell
docker compose -f docker-compose.yaml -f docker-compose.talent-intelligence.yaml config --quiet
```

## Runtime checks

Confirm the image and service state:

```powershell
docker compose -f docker-compose.yaml -f docker-compose.talent-intelligence.yaml ps api api_websocket worker worker_beat
```

Confirm the module and flag inside the API container:

```powershell
docker compose -f docker-compose.yaml -f docker-compose.talent-intelligence.yaml exec -T api python -c "from configs import dify_config; import extensions.talent_intelligence as ti; print(ti.EXTENSION_NAME, ti.EXTENSION_VERSION, dify_config.TALENT_INTELLIGENCE_ENABLED)"
```

With the feature enabled, an authenticated Dify console request to:

```text
GET http://localhost/console/api/talent-intelligence/health
```

returns:

```json
{
  "status": "ok",
  "module": "talent_intelligence",
  "enabled": true,
  "version": "0.1.0"
}
```

The endpoint uses normal Dify console authentication and CSRF protection. An unauthenticated request returns HTTP 401.

## Phase 1 migration and seed

Apply the extension migration explicitly after building the local image:

```powershell
docker compose -f docker-compose.yaml -f docker-compose.talent-intelligence.yaml exec -T api flask db upgrade
```

The API startup path also runs normal Dify migrations. See `migrations.md` for head inspection, schema verification, downgrade guidance, and the explicit idempotent development seed. The seed is never run automatically.

After migration, recreate or restart `api`, `api_websocket`, `worker`, and `worker_beat`, then restart Nginx. Verify `/console/api/setup`, Talent Intelligence health, a candidate create/list, a job create/publish, and `/talent-intelligence/audit/verify` with an authenticated admin console session.

## Disable and verify baseline behavior

Set `TALENT_INTELLIGENCE_ENABLED=false` in the local environment and recreate the four services. The health path must return HTTP 404. Verify baseline Dify with:

```powershell
curl.exe -I http://localhost/
curl.exe http://localhost/console/api/setup
```
