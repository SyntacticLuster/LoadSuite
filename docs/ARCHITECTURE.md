# System Architecture

## FreightLens: Component Design & Data Flow

**Version:** 1.0  
**Last Updated:** 2024-12-19

---

## 1. Architecture Overview

FreightLens follows a **modular monolith** architecture, organized around domain-driven components that can evolve toward microservices if scaling demands. The current implementation uses **FastAPI** as the API layer with an in-memory data store, designed for incremental enhancement.

### High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                   CLIENTS                                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Web SPA    │  │   CLI Tool   │  │  Mobile App  │  │  3rd Party   │         │
│  │ (static/*)   │  │  (cli.py)    │  │   (future)   │  │ Integrations │         │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘         │
└─────────┼─────────────────┼─────────────────┼─────────────────┼─────────────────┘
          │                 │                 │                 │
          └─────────────────┴────────┬────────┴─────────────────┘
                                     │ HTTPS/REST
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              API GATEWAY LAYER                                   │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                         FastAPI Application                              │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │    │
│  │  │   /loads    │  │   /brokers  │  │   /alerts   │  │  /portfolio │     │    │
│  │  │   Router    │  │   Router    │  │   Router    │  │   Router    │     │    │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘     │    │
│  │         └────────────────┴────────────────┴────────────────┘             │    │
│  │                                    │                                      │    │
│  │  ┌─────────────────────────────────┴─────────────────────────────────┐   │    │
│  │  │                      Middleware Stack                              │   │    │
│  │  │  [Auth] → [RateLimit] → [RequestID] → [Logging] → [Metrics]       │   │    │
│  │  └───────────────────────────────────────────────────────────────────┘   │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              SERVICE LAYER                                       │
│                                                                                  │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐ │
│  │  Load Service  │  │ Scoring Engine │  │ Broker Service │  │ Alert Service  │ │
│  │                │  │                │  │                │  │                │ │
│  │ • Search       │  │ • GreenLight   │  │ • Risk Score   │  │ • Lane Alerts  │ │
│  │ • Filter       │  │ • Factors      │  │ • Days-to-Pay  │  │ • Price Alerts │ │
│  │ • CRUD         │  │ • Explain      │  │ • Disputes     │  │ • Delivery     │ │
│  └───────┬────────┘  └───────┬────────┘  └───────┬────────┘  └───────┬────────┘ │
│          │                   │                   │                   │          │
│  ┌───────┴───────────────────┴───────────────────┴───────────────────┴────────┐ │
│  │                        Domain Model Layer                                   │ │
│  │  Load • Lane • Broker • Facility • Truck • Preference • Watchlist • Alert  │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                          │
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │                           Repository Pattern                                │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │ │
│  │  │ LoadRepo     │  │ BrokerRepo   │  │ FacilityRepo │  │ UserRepo     │    │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                     │                                            │
│          ┌──────────────────────────┼──────────────────────────┐                │
│          ▼                          ▼                          ▼                │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐          │
│  │   In-Memory      │    │    PostgreSQL    │    │      Redis       │          │
│  │   (Current)      │    │    (Future)      │    │   (Cache/Queue)  │          │
│  └──────────────────┘    └──────────────────┘    └──────────────────┘          │
└─────────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           INGESTION LAYER                                        │
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │                         Connector Framework                                 │ │
│  │                                                                             │ │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  │ │
│  │  │  Loads  │ │  Rates  │ │  Fuel   │ │ Brokers │ │Facility │ │ Market  │  │ │
│  │  │Connector│ │Connector│ │Connector│ │Connector│ │Connector│ │Connector│  │ │
│  │  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘  │ │
│  │       └───────────┴──────────┬┴───────────┴──────────┴───────────┘        │ │
│  │                              ▼                                             │ │
│  │  ┌───────────────────────────────────────────────────────────────────────┐│ │
│  │  │              Normalization + Deduplication Pipeline                   ││ │
│  │  │  [Raw] → [Validate] → [Normalize] → [Dedupe] → [Provenance] → [Store] ││ │
│  │  └───────────────────────────────────────────────────────────────────────┘│ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         EXTERNAL DATA SOURCES                                    │
│                                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │   Load      │  │    Rate     │  │    Fuel     │  │   FMCSA     │            │
│  │  Postings   │  │Intelligence │  │   Prices    │  │  Authority  │            │
│  │   (APIs)    │  │   (APIs)    │  │   (APIs)    │  │   (APIs)    │            │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘            │
│                                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │   Broker    │  │  Facility   │  │   Weather   │  │    News     │            │
│  │ Credit/Risk │  │Intelligence │  │  & Traffic  │  │    Feeds    │            │
│  │   (APIs)    │  │   (APIs)    │  │   (APIs)    │  │    (RSS)    │            │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘            │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Component Descriptions

### 2.1 API Gateway Layer

The API layer is the single entry point for all clients. Built on **FastAPI**, it provides:

| Component | Responsibility |
|-----------|---------------|
| **Routers** | Path-based routing for each domain (loads, brokers, alerts, portfolio) |
| **Auth Middleware** | JWT/API key validation; user context injection |
| **Rate Limiter** | Per-user/IP request throttling |
| **Request ID** | UUID correlation for distributed tracing |
| **Logging** | Structured request/response logging |
| **Metrics** | Prometheus-compatible endpoint metrics |

**Current Implementation:** [app/main.py](../app/main.py)

### 2.2 Service Layer

Services encapsulate business logic and orchestrate data access:

| Service | Responsibility | Current Status |
|---------|---------------|----------------|
| **LoadService** | Search, filter, CRUD for loads | Exists in `main.py`, `filters.py` |
| **ScoringEngine** | Compute GreenLight scores | Basic in `filters.py` |
| **BrokerService** | Broker risk and payment data | Not implemented |
| **FacilityService** | Shipper/receiver intelligence | Not implemented |
| **AlertService** | Lane/price alert management | Not implemented |
| **PreferenceService** | User preferences and filters | Client-side only |
| **PortfolioService** | Fleet/truck management | Not implemented |

### 2.3 Domain Model Layer

Core entities that represent the trucking domain:

| Entity | Description |
|--------|-------------|
| **Load** | A freight movement opportunity with origin, destination, rate, constraints |
| **Lane** | Origin-destination pair with aggregate statistics |
| **Broker** | Freight broker entity with risk profile |
| **Facility** | Shipper or receiver location with dwell/appointment data |
| **Truck** | Carrier equipment with type, location, availability |
| **Preference** | User-defined scoring weights and filter defaults |
| **Watchlist** | Saved loads for tracking |
| **Alert** | Trigger conditions for notifications |

**Current Implementation:** [app/models.py](../app/models.py)

### 2.4 Data Layer

Data access abstraction using the repository pattern:

| Component | Purpose |
|-----------|---------|
| **Repositories** | Abstract storage operations (CRUD) per entity |
| **In-Memory Store** | Current: `Dataset` class holds `list[Load]` |
| **PostgreSQL** | Future: Persistent storage for production |
| **Redis** | Future: Caching layer and job queue |

**Current Implementation:** [app/data.py](../app/data.py)

### 2.5 Ingestion Layer

Data pipeline for external sources:

| Component | Purpose |
|-----------|---------|
| **Connectors** | Source-specific adapters (API, file, webhook) |
| **Normalizers** | Transform source schemas to internal models |
| **Deduplicator** | Identify and merge duplicate loads |
| **Provenance Tracker** | Record data lineage and timestamps |

**Current Implementation:** Partial in `data.py` (CSV/JSON import)

---

## 3. Data Flow Diagrams

### 3.1 Load Search Flow

```
┌──────────┐     GET /api/loads?q=Chicago&rpm_min=2.5     ┌──────────────┐
│  Client  │ ──────────────────────────────────────────► │  FastAPI     │
└──────────┘                                              │  Router      │
                                                          └──────┬───────┘
                                                                 │
                                                                 ▼
                                                          ┌──────────────┐
                                                          │ LoadService  │
                                                          │              │
                                                          │ 1. Validate  │
                                                          │ 2. Filter    │
                                                          │ 3. Score     │
                                                          │ 4. Sort      │
                                                          └──────┬───────┘
                                                                 │
                         ┌───────────────────────────────────────┼───────────────────┐
                         │                                       │                   │
                         ▼                                       ▼                   ▼
                  ┌──────────────┐                       ┌──────────────┐    ┌──────────────┐
                  │  LoadRepo    │                       │ScoringEngine │    │ PreferenceRepo│
                  │              │                       │              │    │              │
                  │ Get loads    │                       │ Compute score│    │ Get weights  │
                  │ matching     │                       │ for each load│    │ for user     │
                  │ criteria     │                       │              │    │              │
                  └──────────────┘                       └──────────────┘    └──────────────┘
                         │                                       │                   │
                         └───────────────────────────────────────┴───────────────────┘
                                                                 │
                                                                 ▼
                                                          ┌──────────────┐
                                                          │   Response   │
                                                          │              │
                                                          │ { loads: [   │
                                                          │   { score,   │
                                                          │     reasons, │
                                                          │     ... }    │
                                                          │ ]}           │
                                                          └──────────────┘
```

### 3.2 Scoring Flow

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                           Scoring Engine Pipeline                              │
│                                                                                │
│  ┌─────────┐    ┌─────────────────────────────────────────────────────────┐   │
│  │  Load   │    │                    Factor Calculators                    │   │
│  │         │    │                                                          │   │
│  │ • rate  │───►│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │   │
│  │ • miles │    │  │Profit   │ │Feasibility│ │  Risk  │ │Preference│       │   │
│  │ • broker│    │  │Factor   │ │ Factor   │ │ Factor │ │ Factor  │        │   │
│  │ • etc   │    │  │         │ │          │ │        │ │         │        │   │
│  └─────────┘    │  │ • RPM   │ │ •Deadhead│ │•Broker │ │•User wt │        │   │
│                 │  │ • Net$  │ │ • HOS    │ │•Dwell  │ │•Equip   │        │   │
│                 │  │ • $/hr  │ │ • Appt   │ │•Fraud  │ │•Lanes   │        │   │
│                 │  └────┬────┘ └────┬─────┘ └───┬────┘ └────┬────┘        │   │
│                 │       │           │           │           │              │   │
│                 │       └───────────┴─────┬─────┴───────────┘              │   │
│                 │                         ▼                                │   │
│                 │                 ┌───────────────┐                        │   │
│  ┌─────────┐    │                 │   Weighted    │     ┌─────────────┐   │   │
│  │ Weights │───►│                 │   Aggregator  │────►│   Score     │   │   │
│  │ Config  │    │                 │               │     │   0-100     │   │   │
│  └─────────┘    │                 │ Σ(factor×wt)  │     │   + Top 5   │   │   │
│                 │                 └───────────────┘     │   Reasons   │   │   │
│                 │                                       └─────────────┘   │   │
│                 └──────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Module Boundaries

### 4.1 Current Structure

```
app/
├── __init__.py
├── main.py          # FastAPI app + all routes (monolithic)
├── models.py        # Pydantic models
├── data.py          # Synthetic generation + import parsing
├── filters.py       # Filtering + basic scoring
└── news.py          # RSS feed fetcher
```

### 4.2 Target Structure (Incremental)

```
app/
├── __init__.py
├── main.py              # FastAPI app setup + router mounting
├── config.py            # Configuration management (NEW)
├── dependencies.py      # FastAPI dependency injection (NEW)
│
├── api/                 # API layer (NEW)
│   ├── __init__.py
│   ├── loads.py         # /api/loads routes
│   ├── brokers.py       # /api/brokers routes (NEW)
│   ├── alerts.py        # /api/alerts routes (NEW)
│   ├── portfolio.py     # /api/portfolio routes (NEW)
│   └── preferences.py   # /api/preferences routes (NEW)
│
├── services/            # Business logic (NEW)
│   ├── __init__.py
│   ├── load_service.py
│   ├── scoring_engine.py
│   ├── broker_service.py
│   ├── facility_service.py
│   ├── alert_service.py
│   └── preference_service.py
│
├── domain/              # Domain models (NEW)
│   ├── __init__.py
│   ├── load.py
│   ├── lane.py
│   ├── broker.py
│   ├── facility.py
│   ├── truck.py
│   └── alert.py
│
├── repositories/        # Data access (NEW)
│   ├── __init__.py
│   ├── base.py
│   ├── load_repository.py
│   ├── broker_repository.py
│   └── memory_store.py
│
├── ingestion/           # Data pipeline (NEW)
│   ├── __init__.py
│   ├── base_connector.py
│   ├── normalizers.py
│   └── connectors/
│       ├── csv_connector.py
│       ├── json_connector.py
│       └── api_connector.py
│
├── models.py            # Keep for backward compat
├── data.py              # Keep for backward compat
├── filters.py           # Keep for backward compat
└── news.py              # Keep for backward compat
```

---

## 5. Technology Stack

| Layer | Current | Future Consideration |
|-------|---------|---------------------|
| **Language** | Python 3.13 | — |
| **API Framework** | FastAPI 0.125 | — |
| **Server** | Uvicorn 0.38 | Gunicorn + Uvicorn workers |
| **Data Validation** | Pydantic v2 | — |
| **Storage** | In-memory | PostgreSQL 16 |
| **Cache** | None | Redis 7 |
| **Queue** | None | Redis Streams / Celery |
| **Search** | Linear scan | PostgreSQL FTS / Meilisearch |
| **Auth** | None | JWT + OAuth2 |
| **Frontend** | Vanilla JS | Optional: React/Vue |
| **Testing** | pytest | pytest-asyncio, httpx |
| **Observability** | Basic logging | structlog, Prometheus, OpenTelemetry |

---

## 6. Security Architecture

### 6.1 Authentication Flow (Future)

```
┌──────────┐     POST /auth/login     ┌──────────────┐     ┌──────────────┐
│  Client  │ ────────────────────────►│  Auth Router │────►│  Auth Service│
└──────────┘     {email, password}    └──────────────┘     └──────┬───────┘
                                                                   │
                                                                   ▼
                                                           ┌──────────────┐
                                                           │  User Repo   │
                                                           │  (verify)    │
                                                           └──────┬───────┘
                                                                   │
     ◄─────────────────────────────────────────────────────────────┘
     {access_token, refresh_token, expires_in}
```

### 6.2 Authorization Model

| Role | Permissions |
|------|-------------|
| **Anonymous** | Read public loads (rate-limited) |
| **User** | Full read; watchlists; alerts; preferences |
| **Dispatcher** | User + fleet management; portfolio |
| **Admin** | All + user management; system config |

---

## 7. Deployment Architecture (Future)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Load Balancer                                   │
│                         (nginx / AWS ALB / CloudFlare)                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
          ┌───────────────────────────┼───────────────────────────┐
          ▼                           ▼                           ▼
   ┌──────────────┐           ┌──────────────┐           ┌──────────────┐
   │  API Node 1  │           │  API Node 2  │           │  API Node N  │
   │  (Uvicorn)   │           │  (Uvicorn)   │           │  (Uvicorn)   │
   └──────┬───────┘           └──────┬───────┘           └──────┬───────┘
          │                          │                          │
          └──────────────────────────┼──────────────────────────┘
                                     │
                                     ▼
                          ┌──────────────────┐
                          │   PostgreSQL     │
                          │   (Primary)      │
                          └────────┬─────────┘
                                   │
                          ┌────────┴─────────┐
                          ▼                  ▼
                   ┌──────────────┐  ┌──────────────┐
                   │    Redis     │  │   PG Replica │
                   │ (Cache/Queue)│  │   (Read)     │
                   └──────────────┘  └──────────────┘
```

---

## 8. Observability Architecture

See [OBSERVABILITY.md](OBSERVABILITY.md) for detailed specifications.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           Observability Stack                                 │
│                                                                               │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐          │
│  │    Metrics      │    │     Logs        │    │    Traces       │          │
│  │  (Prometheus)   │    │   (structlog)   │    │ (OpenTelemetry) │          │
│  └────────┬────────┘    └────────┬────────┘    └────────┬────────┘          │
│           │                      │                      │                    │
│           └──────────────────────┼──────────────────────┘                    │
│                                  ▼                                           │
│                        ┌─────────────────┐                                   │
│                        │   Aggregation   │                                   │
│                        │   (Grafana)     │                                   │
│                        └────────┬────────┘                                   │
│                                 │                                            │
│                                 ▼                                            │
│                        ┌─────────────────┐                                   │
│                        │    Alerting     │                                   │
│                        │  (PagerDuty)    │                                   │
│                        └─────────────────┘                                   │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. Integration Points

| Integration | Protocol | Purpose | Priority |
|-------------|----------|---------|----------|
| Load posting APIs | REST/JSON | Real load data | P0 |
| Rate intelligence | REST/JSON | Market rate context | P0 |
| Fuel price APIs | REST/JSON | Profitability calc | P1 |
| FMCSA SAFER | REST/XML | Broker authority | P1 |
| Distance/routing | REST/JSON | Mileage + ETA | P1 |
| Weather APIs | REST/JSON | Disruption flags | P2 |
| SMS gateway | REST/JSON | Alert delivery | P2 |
| Email service | SMTP/API | Alert delivery | P2 |

---

## 10. Decision Log

| Decision | Rationale | Date |
|----------|-----------|------|
| FastAPI over Flask/Django | Async support, Pydantic integration, OpenAPI auto-docs | Existing |
| Modular monolith over microservices | Team size, deployment simplicity, avoid premature optimization | 2024-12 |
| Repository pattern | Swap storage backends without service changes | 2024-12 |
| Config-driven scoring | User tunability, A/B testing, explainability | 2024-12 |
| Vendor-agnostic connectors | Avoid lock-in, support multiple data sources | 2024-12 |
