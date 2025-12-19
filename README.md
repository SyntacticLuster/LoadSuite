# Loadboard MVP (UI-first) — Output Bundle

This bundle is intentionally **self-contained** and lives under `output/` only. It provides a small FastAPI server that serves a mobile-first web UI and a JSON/CSV import pipeline.

## What it does

- **Loads list** (mobile-first)
- **Inline collapsible Filters/Sort** section
- **Load detail** screen
- **Settings** screen with:
  - mock/fixture indicator
  - refresh (regenerate synthetic loads)
  - import JSON/CSV (replaces dataset)

## Quick start

From the repo root (with your Poetry venv activated):

```bash
cd output/bundles/loadboard_mvp_ui
python -m uvicorn app.main:app --reload --port 8035
```

Open:

- http://127.0.0.1:8035

## Smoke test

```bash
cd output/bundles/loadboard_mvp_ui
python smoke_test.py
```

## Data formats

- JSON: array of objects (see `sample_data/sample_loads.json`)
- CSV: header row (see `sample_data/sample_loads.csv`)
