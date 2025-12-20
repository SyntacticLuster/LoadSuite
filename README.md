# FreightLens MVP (UI-first)

This repository powers the **FreightLens MVP** bundle: a single FastAPI backend plus mobile-first UI that serves synthetic loads, accepts imports (CSV/JSON), and exposes the same filters/sorting as the CLI proof of concept.

## Getting started

1. Install Poetry globally (e.g., `python -m pip install --user poetry` or through your distro package manager).
2. From the repo root, target the required interpreter and install deps:
   ```bash
   poetry env use ~/.pyenv/versions/3.13.1/bin/python
   poetry install
   ```
3. Activate the virtualenv if you want to reuse `poetry run` implicitly (`poetry shell`) or prefix commands with `poetry run`.

## Run the server

```bash
poetry run python -m uvicorn app.main:app --reload --port 8035
```

- Visit http://127.0.0.1:8035 to load the UI.
- The FastAPI backend lives under `app/`, static assets under `static/`, and the UI HTML entrypoint is `static/index.html`.

## CLI utilities

The CLI reads any JSON/CSV following the schema in `sample_data/` and supports the same filters/sort options as the web UI.

```bash
poetry run python cli.py list --sort rpm_desc --limit 10
poetry run python cli.py list --equipment Reefer --rpm-min 2.5 --limit 10
poetry run python cli.py detail <load-id>  # print a single load in JSON
```

## Testing

Use the smoke test to ensure the API responds and the dataset loads:

```bash
poetry run python smoke_test.py
```

## Data

- `app/data.py` generates the synthetic dataset and knows how to parse imports.
- `sample_data/` holds the example CSV/JSON payloads (`sample_loads.csv`, `sample_loads.json`, `user_lane_rate_sample.json`). Importing replaces the in-memory dataset via `POST /api/import`.
- The API exposes full filter support for equipment, rpm, broker rating, hazmat, multistop/detention toggles, pickup/delivery windows, and composed sorting (see `app/filters.py`).

## Data Rights & Governance

See [docs/DATA_RIGHTS_AND_SOURCING.md](docs/DATA_RIGHTS_AND_SOURCING.md) for the data governance policy covering:
- Source classification (COMPLIANT/RESTRICTED/QUARANTINED/BLOCKED)
- Provenance tracking requirements
- Quarantine mode for rapid prototyping with unverified sources
- Rights enforcement rules for ingestion, storage, display, and export

## Notes

- Poetry already bundles FastAPI (0.125) and Uvicorn (0.38); the package metadata lives in `pyproject.toml`.
- The CLI and web server share the same core models in `app/models.py`, so validation stays consistent across both interfaces.
