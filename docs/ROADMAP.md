# FreightLens Roadmap

## Phased Delivery Plan

**Version:** 1.0  
**Last Updated:** 2024-12-19

---

## Overview

FreightLens development follows a phased approach that prioritizes:
1. **Foundation first** — Solid data models and scoring before features
2. **Value early** — Each phase delivers usable functionality
3. **Risk reduction** — Hardest integrations tackled with stubs first
4. **Additive growth** — Never break existing functionality

---

## Phase Summary

| Phase | Name | Duration | Key Deliverables |
|-------|------|----------|------------------|
| **0** | Foundation | 2 weeks | Docs, types, directory structure, test scaffolding |
| **1** | Scoring Engine | 3 weeks | GreenLight score, explainability, config-driven weights |
| **2** | Enhanced Search | 2 weeks | Saved filters, lane search, improved API |
| **3** | Risk Intelligence | 3 weeks | Broker risk scores, facility dwell estimates |
| **4** | Terminal Workflows | 3 weeks | Watchlists, alerts, portfolio view |
| **5** | Data Ingestion | 4 weeks | Connector framework, normalization, provenance |
| **6** | Analytics & Trends | 3 weeks | Lane rate curves, heatmaps, forecasts |
| **7** | Production Hardening | 3 weeks | Auth, observability, security, performance |

**Total estimated timeline:** 23 weeks (~6 months)

---

## Phase 0: Foundation (Weeks 1–2)

### Goals
- Establish documentation as source of truth
- Define domain types and interfaces
- Create directory structure for future modules
- Set up testing infrastructure

### Deliverables

| Deliverable | Description | Status |
|-------------|-------------|--------|
| `/docs/` directory | PRD, Architecture, Data Model, Scoring, Roadmap, Testing | ✅ Complete |
| Domain types | Extended Pydantic models in `app/domain/` | Not started |
| Test scaffolding | pytest structure in `/tests/` | Not started |
| Synthetic data generator | Enhanced generator with all entity types | Not started |
| CI/CD skeleton | GitHub Actions for lint + test | Not started |

### Success Criteria
- [ ] All 7 core docs written and reviewed
- [ ] `pytest` runs with 0 errors (even if 0 tests)
- [ ] New directory structure created without breaking existing code
- [ ] Synthetic generator produces 1000+ loads with valid relationships

### Pain Points Addressed
None directly — this phase enables all future phases.

---

## Phase 1: Scoring Engine (Weeks 3–5)

### Goals
- Replace basic composite score with configurable GreenLight engine
- Provide explainable score breakdowns
- Enable user preference tuning

### Deliverables

| Deliverable | Description | Status |
|-------------|-------------|--------|
| `ScoringEngine` class | Factor-based scoring with weighted aggregation | Not started |
| Score factors | Profitability, feasibility, risk, preference match | Not started |
| Explainability | Top 5 reasons per load with contribution values | Not started |
| User preferences | Stored weights that adjust scoring | Not started |
| Deterministic mode | Fixed seed for reproducible test results | Not started |

### API Changes
```
GET /api/loads
  + score: float (0-100)
  + score_reasons: [{factor, value, contribution, direction}]
  
GET /api/preferences
POST /api/preferences
  {weight_rpm, weight_deadhead, weight_broker, ...}
```

### Success Criteria
- [ ] Every load returns a 0–100 score
- [ ] Score breakdown shows top 5 factors
- [ ] Changing preferences changes ranking order
- [ ] Same inputs produce same score (deterministic)
- [ ] Unit tests cover all factor calculations

### Pain Points Addressed
| Pain Point | How Addressed |
|------------|---------------|
| Rate opacity | Score contextualizes rate vs. market |
| Information overload | Ranking reduces decision fatigue |
| Bad load selection | Transparent factors educate users |

---

## Phase 2: Enhanced Search (Weeks 6–7)

### Goals
- Improve search performance and flexibility
- Add saved filter presets
- Support lane-based and radius searches

### Deliverables

| Deliverable | Description | Status |
|-------------|-------------|--------|
| Saved filters | Store and recall filter presets | Not started |
| Lane search | Origin→Destination pair queries | Not started |
| Radius search | "Within X miles of city" | Not started |
| Region groups | Named regions (Southeast, Midwest, etc.) | Not started |
| Search history | Recent searches for quick reuse | Not started |

### API Changes
```
GET /api/filters (list saved)
POST /api/filters (create)
DELETE /api/filters/{id}

GET /api/loads
  + origin_radius_miles: int
  + dest_radius_miles: int
  + lane: str (e.g., "ATL_GA:CHI_IL")
```

### Success Criteria
- [ ] Users can save and load filter presets
- [ ] Radius search works within 5% distance accuracy
- [ ] Lane queries return in <200ms for 10K loads
- [ ] UI exposes saved filters in dropdown

### Pain Points Addressed
| Pain Point | How Addressed |
|------------|---------------|
| Repetitive searching | Saved filters eliminate re-entry |
| Geographic flexibility | Radius search expands options |
| Lane focus | Direct lane queries for dedicated routes |

---

## Phase 3: Risk Intelligence (Weeks 8–10)

### Goals
- Add broker payment risk indicators
- Add facility dwell/detention estimates
- Surface risk factors in scoring

### Deliverables

| Deliverable | Description | Status |
|-------------|-------------|--------|
| Broker entity | MC#, authority, risk profile | Not started |
| Broker risk score | Days-to-pay, dispute rate, fraud flags | Not started |
| Facility entity | Location, hours, dwell stats | Not started |
| Dwell estimates | Historical average/P90 dwell time | Not started |
| Risk factor integration | Risk scores feed into GreenLight | Not started |

### Dataset Categories Implemented
- **E) Compliance/Authority** — Broker authority status
- **F) Broker & Payment Risk** — Payment history signals
- **G) Facility Intelligence** — Dwell and detention data

### API Changes
```
GET /api/brokers/{mc_number}
GET /api/facilities/{id}

Load object additions:
  + broker.risk_score: float
  + broker.days_to_pay_avg: float
  + origin_facility.dwell_minutes_avg: float
  + dest_facility.detention_likelihood: enum
```

### Success Criteria
- [ ] Broker risk score available for 80%+ of loads
- [ ] Facility dwell estimates for top 100 facilities
- [ ] Risk factors visible in score explainability
- [ ] Users can filter by broker rating minimum

### Pain Points Addressed
| Pain Point | How Addressed |
|------------|---------------|
| Broker payment risk | Risk score flags slow-pay brokers |
| Detention uncertainty | Dwell estimates set expectations |
| Bad broker experiences | Historical data prevents repeat mistakes |

---

## Phase 4: Terminal Workflows (Weeks 11–13)

### Goals
- Enable "watch and wait" behavior with watchlists
- Proactive notifications via alerts
- Fleet/truck portfolio management

### Deliverables

| Deliverable | Description | Status |
|-------------|-------------|--------|
| Watchlists | Save loads for tracking | Not started |
| Lane alerts | Notify when loads match criteria | Not started |
| Price alerts | Notify when rate exceeds threshold | Not started |
| Truck registration | Add trucks with equipment/location | Not started |
| "Next load" recommendations | Suggested loads per truck | Not started |
| Notification stubs | Email/SMS hooks (not wired) | Not started |

### API Changes
```
GET/POST/DELETE /api/watchlists
GET/POST/DELETE /api/watchlists/{id}/loads

GET/POST/PUT/DELETE /api/alerts
GET /api/alerts/triggered

GET/POST/PUT/DELETE /api/trucks
GET /api/trucks/{id}/recommendations
```

### Success Criteria
- [ ] Users can add/remove loads from watchlists
- [ ] Alerts trigger when matching loads appear
- [ ] Truck recommendations based on location + preferences
- [ ] Portfolio view shows all trucks with status
- [ ] Notification events logged (actual delivery stubbed)

### Pain Points Addressed
| Pain Point | How Addressed |
|------------|---------------|
| Missing opportunities | Alerts notify proactively |
| Tracking multiple loads | Watchlists organize candidates |
| Fleet coordination | Portfolio shows all trucks at once |
| "What's next?" decisions | Recommendations per truck |

---

## Phase 5: Data Ingestion (Weeks 14–17)

### Goals
- Build pluggable connector framework
- Implement normalization pipeline
- Track data provenance and quality

### Deliverables

| Deliverable | Description | Status |
|-------------|-------------|--------|
| Connector base class | Abstract interface for data sources | Not started |
| CSV connector | Enhanced file import | Not started |
| JSON connector | Enhanced file import | Not started |
| API connector template | HTTP-based source adapter | Not started |
| Normalization pipeline | Transform → Validate → Dedupe → Store | Not started |
| Provenance tracking | Source, timestamp, confidence per record | Not started |
| Data quality scoring | Freshness, completeness, accuracy signals | Not started |

### Dataset Categories Implemented
- **A) Load Postings** — Primary connector
- **D) Fuel Prices** — Regional fuel data connector
- **I) Events/News Flags** — RSS/API news connector (extends existing)

### Success Criteria
- [ ] New connector can be added in <100 LOC
- [ ] All records have provenance metadata
- [ ] Duplicate loads detected and merged
- [ ] Data quality score visible per load
- [ ] Stale data flagged (>24h old)

### Pain Points Addressed
| Pain Point | How Addressed |
|------------|---------------|
| Data staleness | Freshness scoring flags old data |
| Duplicate loads | Deduplication prevents noise |
| Source reliability | Provenance tracks origin |

---

## Phase 6: Analytics & Trends (Weeks 18–20)

### Goals
- Aggregate lane-level statistics
- Visualize rate trends and market conditions
- Provide forecasting signals

### Deliverables

| Deliverable | Description | Status |
|-------------|-------------|--------|
| Lane aggregation | Compute stats per origin-dest pair | Not started |
| Rate curves | Historical rate distribution by lane | Not started |
| Lane heatmaps | Visual capacity tightness map | Not started |
| Trend indicators | 7-day, 30-day rate direction | Not started |
| Backhaul probability | Likelihood of return load | Not started |
| Seasonality index | Historical seasonal patterns | Not started |

### Dataset Categories Implemented
- **B) Rate Intelligence** — Lane rate statistics
- **H) Market Demand Proxies** — Volume and capacity signals

### API Changes
```
GET /api/lanes
GET /api/lanes/{id}
GET /api/lanes/{id}/history
GET /api/analytics/heatmap
```

### Success Criteria
- [ ] Lane stats computed for top 500 lanes
- [ ] Rate trends show 7d and 30d direction
- [ ] Heatmap renders in UI
- [ ] Backhaul probability shown on load detail
- [ ] Historical data queryable for 90 days

### Pain Points Addressed
| Pain Point | How Addressed |
|------------|---------------|
| Rate opacity | Lane benchmarks contextualize offers |
| Market timing | Trend indicators suggest wait/act |
| Empty miles | Backhaul probability guides positioning |
| Seasonal surprises | Seasonality index sets expectations |

---

## Phase 7: Production Hardening (Weeks 21–23)

### Goals
- Secure the application for production use
- Implement comprehensive observability
- Optimize performance for scale

### Deliverables

| Deliverable | Description | Status |
|-------------|-------------|--------|
| Authentication | JWT-based auth with refresh tokens | Not started |
| Authorization | Role-based access (user, dispatcher, admin) | Not started |
| Rate limiting | Per-user request throttling | Not started |
| Audit logging | Security-relevant event log | Not started |
| Structured logging | JSON logs with correlation IDs | Not started |
| Metrics endpoint | Prometheus-compatible `/metrics` | Not started |
| Tracing hooks | OpenTelemetry instrumentation | Not started |
| Performance tuning | Query optimization, caching | Not started |

### Success Criteria
- [ ] All write endpoints require authentication
- [ ] Failed auth attempts logged with context
- [ ] Request latency p95 <500ms at 100 RPS
- [ ] Metrics dashboard shows key indicators
- [ ] Traces span full request lifecycle
- [ ] Rate limiting blocks abuse (100 req/min default)

### Pain Points Addressed
| Pain Point | How Addressed |
|------------|---------------|
| Data security | Auth prevents unauthorized access |
| System reliability | Observability enables fast debugging |
| Abuse prevention | Rate limiting protects resources |

---

## Future Phases (Post-MVP)

### Phase 8: Mobile App
- Native iOS/Android apps
- Push notifications
- Offline mode for poor connectivity

### Phase 9: Integrations
- TMS integrations
- ELD data for HOS calculations
- Factoring company connections

### Phase 10: AI/ML Enhancements
- Predictive load matching
- Anomaly detection (fraud, unusual rates)
- Natural language search ("loads from Atlanta to Chicago next week")

### Phase 11: Marketplace Features
- Direct load booking
- Rate negotiation
- Carrier-shipper matching

---

## Milestone Summary

| Milestone | Phase | Target Date | Key Metric |
|-----------|-------|-------------|------------|
| **M1: Docs Complete** | 0 | Week 2 | 7 docs published |
| **M2: Scoring Live** | 1 | Week 5 | Score on all loads |
| **M3: Saved Filters** | 2 | Week 7 | Filters persist |
| **M4: Risk Scores** | 3 | Week 10 | Broker risk visible |
| **M5: Watchlists** | 4 | Week 13 | Watchlist CRUD works |
| **M6: Connectors** | 5 | Week 17 | 3 connector types |
| **M7: Analytics** | 6 | Week 20 | Lane stats available |
| **M8: Production Ready** | 7 | Week 23 | Auth + Observability |

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Data source licensing | Medium | High | Vendor-agnostic design; multiple source support |
| Scoring accuracy skepticism | Medium | Medium | Transparent weights; user tuning; A/B testing |
| Performance at scale | Low | High | Early load testing; caching strategy |
| Scope creep | High | Medium | Strict phase boundaries; MVP focus |
| Team availability | Medium | Medium | Modular design enables parallel work |

---

## Dependencies

| Dependency | Required By Phase | Status |
|------------|-------------------|--------|
| pytest + pytest-asyncio | 0 | Available (pyproject.toml) |
| structlog (logging) | 7 | Not installed |
| Redis (caching) | 7 | Not installed |
| PostgreSQL (persistence) | 5+ | Not installed |
| Auth library (JWT) | 7 | Not installed |

---

## Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2024-12-19 | 1.0 | Initial roadmap |
