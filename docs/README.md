# FreightLens Documentation

> **"The Bloomberg Terminal of Trucking"**

Welcome to the FreightLens technical documentation. This directory contains all architectural decisions, product requirements, and implementation guides for building a decision-grade loadboard terminal for trucking professionals.

---

## 📚 Documentation Index

| Document | Purpose |
|----------|---------|
| [PRD.md](PRD.md) | Master Product Requirements Document: goals, personas, JTBD, scope, success metrics |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design, component diagram, data flow, module boundaries |
| [DATA_MODEL.md](DATA_MODEL.md) | Domain schemas, entity relationships, dataset categories (A–I) |
| [INGESTION.md](INGESTION.md) | Data connectors, normalization pipeline, provenance, deduplication |
| [SCORING_ENGINE.md](SCORING_ENGINE.md) | GreenLight composite score: factors, weights, explainability, tuning |
| [API.md](API.md) | REST endpoints, request/response contracts, versioning |
| [UI_UX.md](UI_UX.md) | Terminal workflows: search, watchlists, alerts, portfolio, keyboard shortcuts |
| [SECURITY_COMPLIANCE.md](SECURITY_COMPLIANCE.md) | Auth, RBAC, audit logging, PII handling, data licensing |
| [OBSERVABILITY.md](OBSERVABILITY.md) | Structured logging, metrics, tracing, alerting |
| [ROADMAP.md](ROADMAP.md) | Phased delivery with milestones (Phase 0–5+) |
| [TESTING.md](TESTING.md) | Testing strategy, fixtures, synthetic data, CI/CD |
| [DATA_RIGHTS_AND_SOURCING.md](DATA_RIGHTS_AND_SOURCING.md) | Data provenance, licensing, quarantine rules |
| [MONETIZATION.md](MONETIZATION.md) | Outcome-based pricing tiers, value proof, KPIs |
| [SCORING_CALIBRATION.md](SCORING_CALIBRATION.md) | Ground truth, validation, weight governance, anti-score-theater |
| [TRUST_UI_SPEC.md](TRUST_UI_SPEC.md) | Confidence, provenance, freshness UI; acceptance criteria |

---

## 🎯 Quick Start for Contributors

1. **Read the PRD first** — understand the problem space and user jobs-to-be-done.
2. **Review ARCHITECTURE.md** — grasp the module boundaries before touching code.
3. **Check ROADMAP.md** — find the current phase and open work items.
4. **Follow TESTING.md** — every new module must include test scaffolding.

---

## 🏗️ Repository Structure

```
LoadSuite/
├── app/                    # FastAPI application (existing)
│   ├── main.py             # API entrypoints
│   ├── models.py           # Pydantic domain models
│   ├── data.py             # Synthetic generator + import parsers
│   ├── filters.py          # Query filtering + composite scoring
│   └── news.py             # RSS news ticker
├── static/                 # Frontend assets (existing)
│   ├── index.html          # SPA shell
│   └── app.js              # Vanilla JS UI
├── sample_data/            # Example datasets (existing)
├── docs/                   # ← YOU ARE HERE
├── scripts/                # Utility scripts (generators, migrations)
├── tests/                  # Test suite
│   ├── unit/               # Pure function tests
│   ├── integration/        # API + service tests
│   └── fixtures/           # Shared test data
├── cli.py                  # CLI tool
├── smoke_test.py           # Quick sanity check
├── pyproject.toml          # Poetry config
└── README.md               # Repo readme
```

---

## 📖 Conventions

- **Additive changes only** — do not delete or rename existing files without explicit approval.
- **Logging required** — every new module must use structured logging (`structlog` or stdlib with JSON formatter).
- **Tests required** — every new module must include at least unit test scaffolding.
- **Type hints** — all function signatures must have type annotations.
- **Docstrings** — public functions must have docstrings (Google style preferred).

---

## 🔗 Related Resources

- [Main README](../README.md) — Getting started, running the server
- [RUNBOOK.md](../RUNBOOK.md) — Operational runbook (if exists)
- [pyproject.toml](../pyproject.toml) — Dependencies and metadata
