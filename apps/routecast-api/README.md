# RouteCast API

FastAPI service that exposes routing, overlays, and scoring stubs for RouteCast.

## Run

```bash
cd apps/routecast-api
poetry install
poetry run uvicorn routecast_api.main:app --reload --port 8050
```

## Tests

```bash
cd apps/routecast-api
poetry run pytest
```

Or from the repo root:

```bash
scripts/run_routecast_tests.sh
```

## Endpoints
- `GET /health` — service heartbeat
- `POST /route` — returns a stub route with a simple polyline
- `POST /route/overlays` — returns an empty overlay collection
- `POST /route/score` — returns a deterministic stub score for the route
