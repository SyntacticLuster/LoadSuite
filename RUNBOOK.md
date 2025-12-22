# Runbook — FreightLens MVP (UI-first)

## Start server

```bash
cd output/bundles/freightlens_mvp_ui
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8035
```

- Same-machine: http://127.0.0.1:8035
- Other device on your LAN: `http://<your-lan-ip>:8035`

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

## Verification gates

1. `python smoke_test.py`
2. `GET /api/loads` returns non-empty
3. UI loads at `/` and renders rows
