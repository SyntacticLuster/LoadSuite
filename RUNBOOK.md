# Runbook — FreightLens MVP (UI-first)

## Start server

```bash
cd output/bundles/freightlens_mvp_ui
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8035
```

- Same-machine: http://127.0.0.1:8035
- Other device on your LAN: `http://<your-lan-ip>:8035`

## Use MySQL persistence (optional)

By default, the app runs in-memory. If you set `USE_DATABASE=true`, user workflow state
(preferences, watchlist, alerts, filter presets) persists to MySQL.

### Local dev using your server DB (recommended: SSH tunnel)

1. Start an SSH tunnel to your cPanel host so MySQL is not exposed publicly:

```bash
ssh -p 21098 -L 3307:127.0.0.1:3306 <cpanel_user>@orbitsuite.cloud
```

2. In your local `.env` (do not commit), set:

```bash
USE_DATABASE=true
DATABASE_URL=mysql://<db_user>:<db_pass>@127.0.0.1:3307/orbiizny_loadsuite?charset=utf8mb4
```

3. Initialize the schema once (safe to re-run):

```bash
DATABASE_URL="$DATABASE_URL" poetry run python scripts/init_db.py
```

## Deploy (cPanel / Passenger)

This repo includes an opinionated helper script for the cPanel + Passenger setup described in `docs/CPANEL_DEPLOYMENT.md`.

Requirements:

- Your server must be able to `git clone` / `git fetch` the repo (SSH deploy key recommended; HTTPS remote requires a PAT/non-interactive auth).
- Passenger restart is triggered by touching `tmp/restart.txt` inside the app directory.

Run:

```bash
DEPLOY_SSH_HOST=orbitsuite.cloud \
DEPLOY_SSH_USER=<your_cpanel_username> \
./scripts/deploy_cpanel.sh
```

If you have an SSH config host alias (and optionally a `User`) set up, you can use it directly:

```bash
DEPLOY_SSH_TARGET=loadsuite-prod ./scripts/deploy_cpanel.sh
```

Example `~/.ssh/config` entry for the orbitsuite.cloud host (note the non-standard SSH port):

```
Host loadsuite-prod
  HostName orbitsuite.cloud
  Port 21098
  User <your_cpanel_username>
  IdentityFile ~/.ssh/loadsuite_prod
  IdentitiesOnly yes
  BatchMode yes
  StrictHostKeyChecking accept-new
```

Common overrides:

```bash
# Where the repo lives on the server (relative to $HOME by default)
DEPLOY_REMOTE_DIR=apps/LoadSuite

# Use an SSH URL so the server can auth via SSH keys
DEPLOY_REPO_URL=git@github.com:SyntacticLuster/LoadSuite.git
```

If the app doesn’t come back up, use the cPanel “Setup Python App” Restart button and check `~/apps/LoadSuite/*.log`.

## Smoke checks

Manual smoke against a running server (human-readable PASS/FAIL, non-zero exit code on failure):

```bash
# If you started uvicorn on 8035
poetry run python scripts/smoke_manual.py --base-url http://127.0.0.1:8035
```

Auth-enabled example:

```bash
# Terminal 1: run server with auth enabled
AUTH_ENABLED=true ADMIN_API_KEY=secret poetry run python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8035

# Terminal 2: run smoke (it will assert 401s without key and 200s with key)
AUTH_ENABLED=true ADMIN_API_KEY=secret poetry run python scripts/smoke_manual.py --base-url http://127.0.0.1:8035 --auth
```

## CLI (POC-first)

Run without starting the server:

```bash
cd output/bundles/freightlens_mvp_ui
poetry run python cli.py list --sort rpm_desc --limit 10
```

Filter examples:

```bash
poetry run python cli.py list --q Dallas --sort broker_desc --limit 10
poetry run python cli.py list --equipment Reefer --rpm-min 2.5 --limit 10
poetry run python cli.py list --hazmat true --limit 10
```

## Use UI

- Loads list: `/`
- Load detail: click a row
- Settings: `/#/settings`

## API

- `GET /api/loads` — query params:
  - `q` (text: origin/destination/commodity)
  - `equipment`
  - `weight_min`, `weight_max`
  - `hazmat` (`true|false`)
  - `pickup_start`, `pickup_end` (ISO datetime)
  - `delivery_start`, `delivery_end` (ISO datetime)
  - `deadhead_max`
  - `rpm_min`
  - `broker_rating_min`
  - `detention` (`true|false`)
  - `multi_stop` (`true|false`)
  - `lane_history` (`true|false`)
  - `sort` (`composite|rpm_desc|pickup_soonest|deadhead_asc|broker_desc`)

- `GET /api/loads/{id}`
- `POST /api/refresh` — JSON body: `{ "count": 200 }` (optional)
- `POST /api/import` — multipart file upload (CSV or JSON)

## RouteCast (optional)

- Start RouteCast API locally:

```bash
cd apps/routecast-api
poetry install
poetry run uvicorn routecast_api.main:app --reload --host 0.0.0.0 --port 8050
```

- Enable FreightLens to call RouteCast (feature flag + env):

```bash
ROUTECAST_ENABLED=true \
ROUTECAST_BASE_URL=http://localhost:8050 \
ROUTECAST_PROVIDER=osrm \
ROUTECAST_TIMEOUT_SECONDS=0.75 \
ROUTECAST_CACHE_TTL_SECONDS=900 \
ROUTECAST_NEGATIVE_CACHE_TTL_SECONDS=60 \
poetry run python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8035
```

- Example curl against FreightLens:

```bash
curl -X POST http://127.0.0.1:8035/api/routecast/score \
  -H "Content-Type: application/json" \
  -d '{"origin":{"lat":33.749,"lon":-84.388},"destination":{"lat":41.8781,"lon":-87.6298},"via":[],"equipment_type":"Dry Van","weight_lbs":40000,"departure_time":"2024-12-19T10:00:00Z"}'
```

## Ops notes

- **Auth (optional):** when `AUTH_ENABLED=true`, include `Authorization: Bearer <ADMIN_API_KEY>` or `X-API-Key: <ADMIN_API_KEY>` for:
  - `POST /api/import`
  - `POST /api/ingestion/run`
  - `GET /api/ingestion/sources`
- **In-memory state scope:** imports, ingestion state, and stores are per-process. Multi-worker deployments (`--workers` / `WEB_CONCURRENCY`) will diverge unless you use DB-backed persistence or an external shared store (e.g., Redis).

## Verification gates

1. `python smoke_test.py`
2. `GET /api/loads` returns non-empty
3. UI loads at `/` and renders rows
