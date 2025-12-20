# Product Requirements Document (PRD)

## FreightLens: The Bloomberg Terminal of Trucking

**Version:** 1.0  
**Status:** Draft  
**Last Updated:** 2024-12-19  
**Author:** Product Architecture Team

---

## 1. Executive Summary

FreightLens is a **decision-grade loadboard terminal** designed to give trucking professionals—owner-operators, dispatchers, and small fleet owners—the information asymmetry advantages that large carriers and 3PLs currently monopolize.

Unlike traditional loadboards that present "a pretty list" of available freight, FreightLens delivers **actionable decision support** across five critical dimensions:

1. **Profitability** — Net profit, $/mile, $/hour, fuel-adjusted margins
2. **Feasibility** — Deadhead, HOS compliance, appointments, equipment constraints
3. **Risk** — Broker credit, fraud signals, detention likelihood, cargo theft
4. **Forecasts** — Lane rate trends, volume proxies, seasonality, backhaul probability
5. **Workflows** — Watchlists, alerts, saved filters, portfolio management

---

## 2. Problem Statement

### The Information Asymmetry Crisis

Trucking remains one of the most fragmented and information-asymmetric industries:

- **300,000+ for-hire carriers** with 91% operating 6 trucks or fewer
- **17,000+ freight brokers** with varying reliability and payment practices
- **$900B+ US trucking market** with no single source of truth for rates

Small carriers operate at a structural disadvantage:

| Problem | Impact |
|---------|--------|
| Rate opacity | Accept loads 15–25% below market value |
| Empty miles | 35% of truck miles are unloaded (deadhead) |
| Detention unpredictability | 3+ hours average at shipper facilities |
| Payment risk | 5–8% of loads face slow-pay or chargebacks |
| Information overload | 50+ calls/texts per day to cover trucks |

### Why Existing Solutions Fail

| Solution | Limitation |
|----------|------------|
| DAT/Truckstop | "Dumb" lists; no profitability scoring; brokers pay for placement |
| TMS systems | Enterprise-focused; $500+/mo; not carrier-centric |
| Spreadsheets | Manual; error-prone; no real-time data |
| Broker relationships | Time-consuming; creates dependency; opaque |

---

## 3. Product Vision

> **"Every trucking professional deserves the same decision intelligence that hedge funds use to trade markets."**

FreightLens transforms raw freight data into **scored, ranked, and explainable recommendations** that answer the fundamental question:

> "Should I take this load?"

With follow-up intelligence:

- "What's my true net profit after fuel and deadhead?"
- "Will this broker pay me on time?"
- "Can I make my delivery and still be legal on HOS?"
- "What's my backhaul probability from the destination?"
- "Is this rate trending up or down?"

---

## 4. Target Users & Personas

### 4.1 Owner-Operator (1 truck)

**Name:** Marcus  
**Profile:** 47 years old, 12 years OTR, runs a 2019 Freightliner Cascadia with 53' dry van  
**Revenue:** $180K gross, $65K take-home after expenses

**Jobs-to-Be-Done:**
| Job | Current Pain | FreightLens Solution |
|-----|-------------|-------------------|
| Find profitable loads | Sorts 200+ postings manually; misses rate context | GreenLight score ranks by net profitability |
| Avoid bad brokers | Learns from experience (expensive lessons) | Broker risk score + payment history |
| Minimize deadhead | No visibility into destination opportunities | Backhaul probability + repositioning assistant |
| Get paid on time | 60+ day waits; surprise chargebacks | Days-to-pay estimates + fraud flags |
| Stay legal | Mental HOS math; appointment stress | Feasibility check: HOS + appointment windows |

**Quote:** *"I don't need more loads. I need to know which loads won't screw me."*

---

### 4.2 Dispatcher (5–50 trucks)

**Name:** Sandra  
**Profile:** 38 years old, manages 22 trucks for a family fleet in the Midwest  
**Workload:** Cover 22 trucks daily; 150+ calls/texts; 3 TMS screens open

**Jobs-to-Be-Done:**
| Job | Current Pain | FreightLens Solution |
|-----|-------------|-------------------|
| Cover trucks fast | 15 min+ per truck; information scattered | Portfolio view with recommended next loads |
| Predictable outcomes | Surprises: detention, rate changes, no-shows | Risk scoring + facility intelligence |
| Reduce overhead | Too many phone calls; manual data entry | Watchlists + alerts + one-click contact |
| Report to owner | Spreadsheet consolidation every Friday | Built-in P&L and utilization dashboards |

**Quote:** *"I spend more time on the phone than actually dispatching."*

---

### 4.3 Small Fleet Owner (5–50 trucks)

**Name:** David  
**Profile:** 52 years old, built a 35-truck dry van fleet over 20 years  
**Focus:** Strategic decisions; cash flow; growth vs. consolidation

**Jobs-to-Be-Done:**
| Job | Current Pain | FreightLens Solution |
|-----|-------------|-------------------|
| Maximize utilization | 78% utilization; 22% wasted capacity | Fleet portfolio + lane analytics + gap detection |
| Reduce financial surprises | Bad debt, chargebacks, insurance claims | Broker risk aggregation + early warning |
| Benchmark performance | No idea if rates are competitive | Lane rate benchmarks + distribution curves |
| Plan strategically | Gut feel on lanes; reactive positioning | Trend forecasts + seasonality + volume proxies |

**Quote:** *"I need to run this like a business, not a hustle."*

---

## 5. Pain Points → Features Mapping

| # | Pain Point | Feature Category | Priority |
|---|-----------|------------------|----------|
| P1 | Rate opacity / information asymmetry | Rate Intelligence Module | P0 |
| P2 | Empty miles / bad repositioning | Backhaul Probability + Lane Heatmaps | P0 |
| P3 | Detention/dwell uncertainty | Facility Intelligence + Dwell Scoring | P0 |
| P4 | Broker payment risk | Broker Risk Score + Days-to-Pay | P0 |
| P5 | Appointment constraints | Feasibility Engine (HOS + Appointments) | P1 |
| P6 | Equipment/commodity constraints | Equipment Matching + Constraint Filters | P1 |
| P7 | Market volatility | Lane Trend Forecasts + Seasonality | P1 |
| P8 | Operational overhead | Watchlists + Alerts + Quick Actions | P1 |
| P9 | HOS compliance | HOS Calculator Integration | P2 |
| P10 | Fraud and cargo theft | Fraud Signals + Theft Risk Zones | P2 |

---

## 6. Functional Requirements

### 6.1 Core Search & Filtering

**FR-1.1** Users can search loads by origin/destination (city, state, radius, region)  
**FR-1.2** Users can filter by equipment type (dry van, reefer, flatbed, power only, step deck, etc.)  
**FR-1.3** Users can filter by weight, hazmat, multi-stop, team required  
**FR-1.4** Users can filter by pickup/delivery date windows  
**FR-1.5** Users can filter by minimum RPM, minimum rate, maximum deadhead  
**FR-1.6** Users can save filter presets for quick reuse  
**FR-1.7** Search results return in <500ms for 10,000 loads

### 6.2 Scoring & Ranking

**FR-2.1** Every load displays a **GreenLight Score** (0–100) based on configurable factors  
**FR-2.2** Each score includes **Top 5 Reasons** explaining the primary drivers  
**FR-2.3** Users can adjust scoring weights via a preferences panel  
**FR-2.4** Scoring factors include: rate, deadhead, broker risk, dwell risk, backhaul probability, time-to-pickup, equipment match, HOS feasibility  
**FR-2.5** Scoring is deterministic (same inputs → same output) for testability

### 6.3 Profitability Analysis

**FR-3.1** Display estimated **net profit** after fuel, tolls, and fixed costs  
**FR-3.2** Display **$/mile (loaded)** and **$/mile (all miles)** including deadhead  
**FR-3.3** Display estimated **$/hour** based on transit time estimates  
**FR-3.4** Allow users to input their cost-per-mile for personalized calculations  
**FR-3.5** Support fuel price lookups by region for fuel-adjusted margins

### 6.4 Risk Assessment

**FR-4.1** Display **Broker Risk Score** (0–100) based on payment history, disputes, authority age  
**FR-4.2** Display **Days-to-Pay** estimate with confidence interval  
**FR-4.3** Display **Detention Likelihood** (Low/Medium/High) based on facility data  
**FR-4.4** Flag loads with elevated fraud or cargo theft risk  
**FR-4.5** Provide drill-down to underlying risk factors

### 6.5 Facility Intelligence

**FR-5.1** Display shipper/receiver operating hours and appointment requirements  
**FR-5.2** Display historical average dwell time at facility  
**FR-5.3** Display lumper likelihood and estimated lumper cost  
**FR-5.4** Allow users to contribute facility ratings and notes (future)

### 6.6 Watchlists & Alerts

**FR-6.1** Users can save loads to a watchlist for tracking  
**FR-6.2** Users can create **lane alerts** (notify when loads match criteria)  
**FR-6.3** Users can set **price alerts** (notify when rate exceeds threshold)  
**FR-6.4** Alerts support email, SMS, and in-app delivery (stubbed initially)

### 6.7 Portfolio Management (Dispatcher/Fleet)

**FR-7.1** Users can register their trucks with location, equipment, and availability  
**FR-7.2** System recommends "next load" for each truck based on location and preferences  
**FR-7.3** Portfolio view shows fleet utilization and idle trucks  
**FR-7.4** Support driver-specific preferences and restrictions

---

## 7. Non-Functional Requirements

| Category | Requirement |
|----------|-------------|
| **Performance** | API response <500ms p95 for 10K loads; UI render <100ms |
| **Availability** | 99.5% uptime target; graceful degradation on data source outages |
| **Scalability** | Support 100K concurrent loads; 10K daily active users |
| **Security** | Auth required for write operations; rate limiting; audit logging |
| **Observability** | Structured logs; request tracing; Prometheus metrics |
| **Extensibility** | Plugin architecture for new data sources |
| **Testability** | Deterministic scoring; synthetic data generator; >80% coverage |

---

## 8. Success Metrics

| Metric | Definition | Target |
|--------|-----------|--------|
| **Time-to-Decision** | Median time from search to load selection | <3 minutes |
| **Deadhead Reduction** | Average deadhead miles per loaded mile | -15% vs. baseline |
| **Profitability Accuracy** | Predicted net profit vs. actual | ±10% |
| **Bad Broker Avoidance** | % of slow-pay/dispute loads flagged pre-booking | >80% |
| **User Retention** | Weekly active users / Monthly active users | >60% |
| **Score Trust** | % of users who book top-3 scored loads | >40% |

---

## 9. Scope & Non-Goals

### In Scope (Phase 1)
- Load search with advanced filtering
- GreenLight composite scoring with explainability
- Basic profitability calculations
- Broker risk indicators (stubbed data initially)
- Facility dwell estimates (stubbed data initially)
- Watchlists and saved filters
- Single-user authentication

### Out of Scope (Future Phases)
- Direct booking / load tendering
- Integrated TMS functionality
- Driver mobile app
- Carrier/broker marketplace
- Financial services (factoring, fuel cards)
- Autonomous dispatch / AI recommendations
- Real-time GPS tracking

---

## 10. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Data source licensing | High | Vendor-agnostic schemas; pluggable connectors |
| Scoring accuracy skepticism | Medium | Transparent weights; user-tunable; explainability |
| Broker data sensitivity | High | Aggregate signals; no individual defamation |
| User adoption friction | Medium | Familiar UI patterns; minimal onboarding |
| Rate data staleness | High | Confidence scoring; freshness indicators |

---

## 11. Dependencies

| Dependency | Owner | Status |
|-----------|-------|--------|
| Rate intelligence data source | TBD vendor | Not started |
| Fuel price API | TBD vendor | Not started |
| Facility database | Crowdsourced / TBD | Not started |
| Auth provider | Internal / OAuth | Not started |
| SMS/Email delivery | Twilio / SendGrid | Not started |

---

## 12. Appendix: Competitive Landscape

| Competitor | Strengths | Weaknesses |
|-----------|-----------|------------|
| DAT | Market leader; extensive network | Pay-to-play; no scoring; broker-biased |
| Truckstop | Good rate data; integrations | Similar limitations to DAT |
| Convoy | End-to-end; predictable | Disintermediates carriers; limited control |
| Uber Freight | Scale; tech-forward | Commodity rates; no customization |
| Trucker Path | Driver community | Limited decision support |

**FreightLens Differentiation:** Carrier-first scoring, transparent analytics, configurable decision engine, no broker bias.

---

## 13. Related Documentation

| Document | Relevance |
|----------|----------|
| [MONETIZATION.md](MONETIZATION.md) | Outcome-based pricing tiers tied to measurable user value |
| [SCORING_CALIBRATION.md](SCORING_CALIBRATION.md) | How we validate GreenLight scores against real outcomes |
| [TRUST_UI_SPEC.md](TRUST_UI_SPEC.md) | Inline confidence and provenance display specification |
| [DATA_RIGHTS_AND_SOURCING.md](DATA_RIGHTS_AND_SOURCING.md) | Data governance and licensing policy |
