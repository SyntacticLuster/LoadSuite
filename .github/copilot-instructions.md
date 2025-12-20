# Copilot instructions (LoadSuite / FreightLens MVP)

## Architecture (prefer the newer flow)
- This is a **modular monolith** FastAPI app with a **vanilla JS SPA**.
- Prefer the **service + repository** architecture for new backend work:
  - Repository interfaces + in-memory stubs: `app/services/repositories.py`
  - Application-layer orchestration: `app/services/scoring_service.py`
  - Postgres-backed repositories (when `Settings.use_database=true`): `app/services/postgres.py` + pool in `app/database.py`
- Keep the scoring engine **pure/deterministic/explainable**:
  - Core algorithm and factor explanations: `app/scoring/engine.py`
  - Factor weights/thresholds: `app/scoring/config.py`

## Current vs target flows (design for seamless migration)
- Current API entrypoint is `app/main.py` (also serves `static/`). Some endpoints still read from module-level in-memory state (`_dataset`, `preferences_store`, etc.).
- When adding/changing endpoints, structure code so swapping storage is trivial:
  - Put orchestration in a service (e.g., `ScoringService`) and call it from `app/main.py`.
  - Access data via `LoadRepository` / `PreferencesRepository` / `MarketDataRepository` (not global lists) when feasible.
  - Keep `app/scoring/*` free of I/O (no DB/network/file reads).

## Frontend
- UI entrypoint: `static/index.html` + `static/app.js`.
- UI is a simple full re-render SPA: mutate global `state`, then call `render()`.
- Use the existing helpers: `el()`, `apiGet`, `apiPostJson`, `apiPut`, `apiDelete`, `apiPostFileBytes`.

## Data & persistence
- In-memory by default: synthetic load generation + CSV/JSON import parsing lives in `app/data.py`.
- Feature flag: `Settings.use_database` in `app/config.py`. When enabled, `lifespan()` in `app/main.py` initializes the asyncpg pool (`app/database.py`).
- Postgres schema reference: `scripts/schema.sql`.

## Commands (day-to-day)
- Install: `poetry install`
- Dev server: `poetry run python -m uvicorn app.main:app --reload --port 8035`
- Tests: `poetry run pytest`
- Smoke test: `poetry run python smoke_test.py`
- CLI (shares filters/import parsing): `poetry run python cli.py list --sort rpm_desc --limit 10`

## Agent vs. Long-form manifesto
- The short `Sage` agent in `.github/agents/Sage.agent.md` distills the behavior Copilot should follow when you select it.
- The longer manifesto you wrote lives in `.github/Sage_chatmode.md`; treat it as the canonical spec (ingestion, scoring, observability, UI guardrails) and sync the agent with it whenever that doc changes.
- When you update the long doc, copy any new bullet points into this instructions file so the summary stays aligned and we avoid drift.

## Agents
- “Sage” agent is defined in `.github/agents/Sage.agent.md` (blunt, skeptical, practical). Use it when you want an architecture-first review or a no-fluff implementation plan.

## Quick “where do I change X?”
- Add API endpoints / wire services: `app/main.py`
- Add orchestration / storage abstraction: `app/services/*`
- Change explainable GreenLight scoring: `app/scoring/*`
- Change simple list filtering/sorting: `app/filters.py`
- Change UI workflows/labels: `static/app.js`
