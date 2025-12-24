# AGENTS.md — LoadSuite / FreightLens (repo-specific overrides)
This file adds project-specific constraints and acceptance criteria on top of ~/.codex/AGENTS.md.

## Scope & Discipline
- Prefer minimal diffs. Do not refactor, rename, or reformat unless explicitly requested.
- Preserve existing behavior and features. Fix inline; add guards rather than removing code.
- When asked for UI work: change layout only unless explicitly asked to change styles/logic.

## Deterministic Synthetic Data (Hard Rule)
- The committed static dataset (e.g., `sample_data/synthetic_loads_6769.json`) is the default data source.
- The server must **never** regenerate synthetic data automatically:
  - no regen on startup
  - no regen “if missing”
  - no regen “if empty”
  - no timers/background tasks
- Any regeneration must be explicit and gated:
  - `/api/refresh` must return **403 by default**
  - it may only work when `ALLOW_SYNTH_REFRESH=1`
  - when allowed, regeneration must be deterministic given a seed and must run only on explicit POST

## Persistence & DB Mode
- If DB mode is enabled, the source of truth must be explicit for each entity:
  - loads, watchlist, alerts, presets, ingestion state
- Avoid split-brain behavior where APIs read from in-memory while DB mode is enabled.
- Fail loudly on misconfiguration rather than silently falling back.

## Time & Date Handling
- Use timezone-aware UTC datetimes end-to-end.
- Never compare naive and aware datetimes.
- Parse external timestamps defensively (support `Z` suffix / offset ISO8601).

## Caching
- Cache keys must include all parameters that affect results (weight, equipment, time windows, etc.).
- Caches must have bounds (TTL and/or max size). No unbounded dict caches.
- Avoid per-process caches for critical shared data when DB mode is enabled.

## API Contract & Security
- Do not change API response shapes without updating tests and API.md.
- Do not leak sensitive provenance data in payloads.
- Metrics endpoints should be treated as internal-only unless explicitly designed otherwise.

## Testing Requirements
- After backend changes: run `poetry run pytest`.
- Add/update tests for:
  - dataset count == 6769 (when static fixture exists)
  - refresh endpoint gated by default (403)
  - determinism (stable IDs/ordering on reload)
  - API contract shape for touched endpoints

## Output Requirements
When you make changes, always include:
- Files changed (list)
- Commands run + results (tests)
- Any behavior/contract changes (explicitly called out)
