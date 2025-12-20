# Data Model

## FreightLens Entity Schemas & Dataset Categories

**Version:** 1.0  
**Last Updated:** 2024-12-19

---

## 1. Overview

FreightLens's data model serves two purposes:

1. **Domain Entities** — Internal representations of loads, brokers, facilities, etc.
2. **Dataset Categories** — External data sources that feed the system (vendor-agnostic)

This document defines schemas for both, with clear separation between:
- **Core fields** — Required for basic functionality
- **Extended fields** — Enhanced features and decision support
- **Computed fields** — Derived at query time or via scoring engine

---

## 2. Core Domain Entities

### 2.1 Load

A **Load** represents a single freight movement opportunity.

```python
class Load:
    # Identity
    id: str                      # UUID, internal primary key
    external_id: str | None      # Source system ID (for deduplication)
    source: str                  # Data source identifier ("dat", "truckstop", "import")

    # Geography
    origin: Location             # Pickup location
    destination: Location        # Delivery location

    # Timing
    pickup_start: datetime       # Earliest pickup (UTC)
    pickup_end: datetime         # Latest pickup (UTC)
    delivery_start: datetime     # Earliest delivery (UTC)
    delivery_end: datetime       # Latest delivery (UTC)
    posted_at: datetime          # When load was posted (UTC)
    updated_at: datetime         # Last update timestamp (UTC)
    expires_at: datetime | None  # When load expires (UTC)

    # Requirements
    equipment: EquipmentType     # Dry Van, Reefer, Flatbed, etc.
    weight_lbs: int              # Cargo weight in pounds
    length_ft: float | None      # Required trailer length
    hazmat: bool                 # Hazmat endorsement required
    team_required: bool          # Team driver requirement
    commodity: str               # Cargo type description

    # Financials
    rate_total_usd: float        # Posted rate in USD
    rate_type: RateType          # "flat", "per_mile", "negotiable"
    fuel_surcharge_included: bool

    # Route
    distance_miles: float        # Loaded miles (origin to destination)
    deadhead_miles: float        # Empty miles to pickup (user-relative)
    
    # Stops
    stops: list[Stop]            # Multi-stop details
    multi_stop: bool             # Convenience flag

    # Broker
    broker: BrokerRef            # Reference to broker entity

    # Computed (at query time)
    rpm: float                   # Rate per mile (rate / distance)
    score: float | None          # GreenLight composite score
    score_reasons: list[str]     # Top factors driving score

    # Metadata
    provenance: Provenance       # Data lineage info
```

### 2.2 Location

```python
class Location:
    city: str
    state: str                   # 2-letter code (US) or province
    postal_code: str | None
    country: str = "US"
    latitude: float | None
    longitude: float | None
    region: str | None           # "Southeast", "Pacific Northwest", etc.
```

### 2.3 Stop (Multi-Stop Loads)

```python
class Stop:
    sequence: int                # Order in route (1, 2, 3...)
    location: Location
    stop_type: StopType          # "pickup", "delivery", "both"
    earliest: datetime
    latest: datetime
    facility_id: str | None      # Reference to Facility entity
    instructions: str | None
```

### 2.4 Broker

```python
class Broker:
    id: str                      # UUID, internal
    mc_number: str               # Motor Carrier number
    dot_number: str | None       # DOT number
    name: str                    # Company name
    
    # Authority
    authority_status: AuthorityStatus  # "active", "inactive", "revoked"
    authority_granted: date | None
    insurance_on_file: bool
    bond_on_file: bool

    # Risk Profile (aggregated)
    risk_score: float | None     # 0-100, lower is riskier
    days_to_pay_avg: float | None
    days_to_pay_p90: float | None
    dispute_rate: float | None   # % of loads with disputes
    chargeback_rate: float | None
    
    # Ratings (aggregated)
    rating: float | None         # 0-5 average rating
    rating_count: int

    # Contact
    phone: str | None
    email: str | None
    website: str | None

    # Metadata
    updated_at: datetime
```

### 2.5 Facility

A **Facility** is a shipper or receiver location with operational intelligence.

```python
class Facility:
    id: str                      # UUID, internal
    name: str                    # Facility name
    location: Location

    # Type
    facility_type: FacilityType  # "shipper", "receiver", "both", "warehouse"
    
    # Operations
    operating_hours: OperatingHours | None
    appointment_required: bool
    drop_trailer_allowed: bool
    
    # Dwell Intelligence
    avg_dwell_minutes: float | None
    p90_dwell_minutes: float | None
    detention_likelihood: DetentionRisk  # "low", "medium", "high"
    
    # Accessorials
    lumper_required: bool
    lumper_avg_cost_usd: float | None
    driver_assist_required: bool
    
    # Ratings
    rating: float | None         # 0-5 average
    rating_count: int

    # Metadata
    updated_at: datetime
    source: str
```

### 2.6 Lane

A **Lane** is an origin-destination pair with aggregate market data.

```python
class Lane:
    id: str                      # Computed: f"{origin_region}:{dest_region}"
    origin_region: str           # City+State or market region
    destination_region: str
    
    # Volume
    load_count_7d: int           # Loads posted last 7 days
    load_count_30d: int          # Loads posted last 30 days
    
    # Rate Statistics
    rate_avg_usd: float          # Average rate
    rate_p25_usd: float          # 25th percentile
    rate_p50_usd: float          # Median
    rate_p75_usd: float          # 75th percentile
    rpm_avg: float               # Average rate per mile
    
    # Trends
    rate_change_7d_pct: float    # % change from 7 days ago
    rate_change_30d_pct: float   # % change from 30 days ago
    
    # Seasonality
    seasonal_index: float        # 1.0 = normal, >1.0 = above average
    
    # Backhaul
    backhaul_probability: float  # Likelihood of return load (0-1)
    backhaul_rate_discount_pct: float  # Expected discount from headhaul
    
    # Market Pressure
    market_pressure: MarketPressure  # "shipper", "carrier", "balanced"
    
    # Metadata
    updated_at: datetime
```

### 2.7 Truck (Fleet Management)

```python
class Truck:
    id: str                      # UUID, internal
    user_id: str                 # Owner user
    
    # Equipment
    equipment_type: EquipmentType
    year: int | None
    make: str | None
    model: str | None
    
    # Capacity
    max_weight_lbs: int
    max_length_ft: float | None
    
    # Endorsements
    hazmat_endorsed: bool
    tanker_endorsed: bool
    doubles_triples: bool
    
    # Current State
    current_location: Location | None
    available_at: datetime | None
    status: TruckStatus          # "available", "en_route", "loading", "idle"
    
    # Preferences (link to driver)
    driver_id: str | None
    home_base: Location | None
    max_deadhead_miles: float | None
    preferred_lanes: list[str]   # Lane IDs
    avoid_regions: list[str]
    
    # Metadata
    created_at: datetime
    updated_at: datetime
```

### 2.8 Alert

```python
class Alert:
    id: str
    user_id: str
    name: str
    
    # Trigger Type
    alert_type: AlertType        # "lane", "price", "broker", "watchlist"
    
    # Conditions
    criteria: LoadsQuery         # Reuse filter structure
    threshold_value: float | None  # For price alerts
    threshold_operator: str | None  # "gte", "lte"
    
    # Notification
    channels: list[NotificationChannel]  # "email", "sms", "push"
    
    # State
    enabled: bool
    last_triggered: datetime | None
    trigger_count: int
    
    # Metadata
    created_at: datetime
    updated_at: datetime
```

### 2.9 Watchlist

```python
class Watchlist:
    id: str
    user_id: str
    name: str
    
    # Items
    load_ids: list[str]          # Saved load references
    
    # State
    is_default: bool
    
    # Metadata
    created_at: datetime
    updated_at: datetime
```

### 2.10 Preference (User Scoring Weights)

```python
class Preference:
    id: str
    user_id: str
    
    # Scoring Weights (0.0 to 2.0, 1.0 = default)
    weight_profitability: float = 1.0
    weight_feasibility: float = 1.0
    weight_risk: float = 1.0
    weight_preference_match: float = 1.0
    
    # Sub-weights
    weight_rpm: float = 1.0
    weight_deadhead: float = 1.0
    weight_broker_rating: float = 1.0
    weight_dwell_risk: float = 1.0
    weight_backhaul: float = 1.0
    
    # Default Filters
    default_equipment: EquipmentType | None
    default_weight_max: int | None
    default_hazmat: bool | None
    default_rpm_min: float | None
    default_deadhead_max: float | None
    default_broker_rating_min: float | None
    
    # Cost Inputs (for profitability)
    cost_per_mile_usd: float = 1.50
    fixed_cost_per_day_usd: float = 0.0
    fuel_efficiency_mpg: float = 6.5
    
    # Metadata
    updated_at: datetime
```

---

## 3. Enumeration Types

```python
class EquipmentType(str, Enum):
    DRY_VAN = "dry_van"
    REEFER = "reefer"
    FLATBED = "flatbed"
    STEP_DECK = "step_deck"
    LOWBOY = "lowboy"
    POWER_ONLY = "power_only"
    TANKER = "tanker"
    HOPPER = "hopper"
    CONESTOGA = "conestoga"
    OTHER = "other"

class RateType(str, Enum):
    FLAT = "flat"
    PER_MILE = "per_mile"
    NEGOTIABLE = "negotiable"

class StopType(str, Enum):
    PICKUP = "pickup"
    DELIVERY = "delivery"
    BOTH = "both"

class AuthorityStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    REVOKED = "revoked"
    PENDING = "pending"

class FacilityType(str, Enum):
    SHIPPER = "shipper"
    RECEIVER = "receiver"
    BOTH = "both"
    WAREHOUSE = "warehouse"
    PORT = "port"
    RAIL = "rail"

class DetentionRisk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"

class MarketPressure(str, Enum):
    SHIPPER = "shipper"      # Excess capacity, rates down
    CARRIER = "carrier"      # Tight capacity, rates up
    BALANCED = "balanced"

class TruckStatus(str, Enum):
    AVAILABLE = "available"
    EN_ROUTE = "en_route"
    LOADING = "loading"
    UNLOADING = "unloading"
    IDLE = "idle"
    MAINTENANCE = "maintenance"

class AlertType(str, Enum):
    LANE = "lane"            # Loads matching lane criteria
    PRICE = "price"          # Rate exceeds threshold
    BROKER = "broker"        # Specific broker posts
    WATCHLIST = "watchlist"  # Changes to watched loads

class NotificationChannel(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    WEBHOOK = "webhook"
```

---

## 4. Dataset Categories (External Sources)

These categories represent the types of external data FreightLens ingests. Schemas are **vendor-agnostic** — actual sources will have different field names that map to these canonical schemas.

### 4.A Load Postings (Core)

**Purpose:** Primary inventory of available freight.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| external_id | string | Y | Source system's load ID |
| origin_city | string | Y | Pickup city |
| origin_state | string | Y | Pickup state (2-letter) |
| origin_zip | string | N | Pickup postal code |
| dest_city | string | Y | Delivery city |
| dest_state | string | Y | Delivery state |
| dest_zip | string | N | Delivery postal code |
| pickup_date | date | Y | Pickup date |
| pickup_time_earliest | time | N | Earliest pickup window |
| pickup_time_latest | time | N | Latest pickup window |
| delivery_date | date | N | Delivery date |
| equipment_type | enum | Y | Equipment required |
| weight_lbs | int | N | Cargo weight |
| length_ft | float | N | Required length |
| hazmat | bool | N | Hazmat required |
| rate | float | N | Posted rate (USD) |
| rate_type | enum | N | Flat/per-mile/negotiable |
| commodity | string | N | Cargo description |
| stops | int | N | Number of stops |
| broker_name | string | N | Broker company name |
| broker_mc | string | N | Broker MC number |
| broker_phone | string | N | Contact phone |
| posted_at | datetime | Y | When posted |
| expires_at | datetime | N | Expiration time |

**Update Cadence:** Real-time or every 5-15 minutes  
**Confidence Scoring:** Age of posting, source reliability  
**Ingestion:** API (primary), file import (secondary)

---

### 4.B Rate Intelligence

**Purpose:** Market rate context for evaluating load value.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| origin_region | string | Y | Origin market (city+state or region) |
| dest_region | string | Y | Destination market |
| equipment_type | enum | Y | Equipment type |
| date | date | Y | Rate observation date |
| rate_low | float | Y | Low end of range |
| rate_avg | float | Y | Average rate |
| rate_high | float | Y | High end of range |
| rpm_avg | float | N | Average rate per mile |
| sample_size | int | N | Number of data points |
| confidence | float | N | Confidence score (0-1) |
| trend_7d_pct | float | N | 7-day trend % |
| trend_30d_pct | float | N | 30-day trend % |

**Update Cadence:** Daily or weekly  
**Confidence Scoring:** Sample size, recency, source diversity  
**Ingestion:** API, bulk file

---

### 4.C Distance/Route/ETA

**Purpose:** Accurate mileage for profitability and HOS calculations.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| origin_lat | float | Y | Origin latitude |
| origin_lng | float | Y | Origin longitude |
| dest_lat | float | Y | Destination latitude |
| dest_lng | float | Y | Destination longitude |
| practical_miles | float | Y | Truck-routable distance |
| hub_miles | float | N | Hub-to-hub distance |
| tolls_est_usd | float | N | Estimated toll cost |
| drive_time_hours | float | N | Estimated drive time |
| stops | list | N | Waypoint coordinates |
| hazmat_route | bool | N | Hazmat-compliant route |
| oversize_route | bool | N | Oversize-compliant route |

**Update Cadence:** Static (geocode-based) + real-time for ETA  
**Confidence Scoring:** Source accuracy, route complexity  
**Ingestion:** API (on-demand), cached lookups

---

### 4.D Fuel Prices

**Purpose:** Fuel-adjusted profitability calculations.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| region | string | Y | Geographic region (state or PADD) |
| fuel_type | enum | Y | Diesel, DEF, gasoline |
| date | date | Y | Price observation date |
| price_per_gallon | float | Y | Retail price (USD) |
| week_over_week_pct | float | N | Weekly change % |

**Update Cadence:** Daily (EIA) or real-time (station-level)  
**Confidence Scoring:** Recency, regional granularity  
**Ingestion:** API (EIA, GasBuddy), file import

---

### 4.E Compliance/Authority

**Purpose:** Verify broker/carrier legitimacy and safety.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| mc_number | string | Y | Motor Carrier number |
| dot_number | string | N | DOT number |
| legal_name | string | Y | Legal entity name |
| dba_name | string | N | Doing-business-as name |
| entity_type | enum | Y | Broker, carrier, both |
| authority_status | enum | Y | Active, inactive, revoked |
| authority_granted | date | N | Date authority granted |
| insurance_on_file | bool | N | Insurance current |
| bond_on_file | bool | N | Surety bond current |
| safety_rating | enum | N | Satisfactory, conditional, unsatisfactory |
| out_of_service_pct | float | N | OOS rate (vehicles) |
| driver_oos_pct | float | N | OOS rate (drivers) |

**Update Cadence:** Weekly (FMCSA snapshot)  
**Confidence Scoring:** Recency of SAFER data  
**Ingestion:** API (FMCSA SAFER), file (MCMIS snapshots)  
**Licensing:** Public domain (FMCSA data is public)

---

### 4.F Broker & Payment Risk

**Purpose:** Assess likelihood of on-time payment and disputes.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| broker_mc | string | Y | Broker MC number |
| days_to_pay_avg | float | N | Average days to payment |
| days_to_pay_p50 | float | N | Median days to payment |
| days_to_pay_p90 | float | N | 90th percentile |
| on_time_rate | float | N | % paid within terms |
| dispute_rate | float | N | % of loads disputed |
| chargeback_rate | float | N | % with chargebacks |
| fraud_flags | int | N | Number of fraud reports |
| rating_avg | float | N | Carrier ratings (0-5) |
| rating_count | int | N | Number of ratings |
| sample_size | int | N | Data points for stats |

**Update Cadence:** Weekly or monthly  
**Confidence Scoring:** Sample size, recency  
**Ingestion:** API, carrier-contributed data  
**Licensing:** Aggregated/anonymized to avoid defamation risk

---

### 4.G Facility Intelligence

**Purpose:** Predict detention, lumper costs, and scheduling.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| facility_id | string | Y | Internal or external ID |
| name | string | Y | Facility name |
| address | string | Y | Street address |
| city | string | Y | City |
| state | string | Y | State |
| zip | string | N | Postal code |
| facility_type | enum | Y | Shipper, receiver, warehouse |
| hours_open | time | N | Opening time |
| hours_close | time | N | Closing time |
| days_of_week | list | N | Operating days |
| appointment_required | bool | N | Appointment needed |
| avg_dwell_minutes | float | N | Average dwell time |
| dwell_p90_minutes | float | N | 90th percentile dwell |
| lumper_required | bool | N | Lumper typically needed |
| lumper_avg_cost | float | N | Average lumper cost |
| driver_assist | bool | N | Driver assist required |
| rating_avg | float | N | Carrier ratings |
| rating_count | int | N | Number of ratings |

**Update Cadence:** Crowdsourced (continuous), vendor (weekly)  
**Confidence Scoring:** Sample size, recency of reports  
**Ingestion:** API, carrier-contributed, import

---

### 4.H Market Demand Proxies

**Purpose:** Gauge capacity tightness and volume trends.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| region | string | Y | Geographic market |
| date | date | Y | Observation date |
| load_volume_index | float | N | Relative load volume |
| truck_volume_index | float | N | Relative truck posts |
| load_to_truck_ratio | float | N | L/T ratio |
| tender_rejection_rate | float | N | Contract rejection % |
| outbound_pressure | enum | N | Tight, normal, loose |
| inbound_pressure | enum | N | Tight, normal, loose |
| port_congestion | bool | N | Major port delays |
| rail_disruption | bool | N | Rail service issues |

**Update Cadence:** Daily or weekly  
**Confidence Scoring:** Source reliability, sample size  
**Ingestion:** API, proprietary indices

---

### 4.I Events/News Flags

**Purpose:** Surface disruptions affecting freight movement.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| event_id | string | Y | Unique event identifier |
| event_type | enum | Y | Weather, closure, strike, holiday |
| headline | string | Y | Event summary |
| description | string | N | Detailed description |
| affected_regions | list | N | Impacted regions |
| start_date | date | Y | Event start |
| end_date | date | N | Event end (if known) |
| severity | enum | N | Low, medium, high |
| source | string | Y | Data source |
| url | string | N | Link to details |

**Update Cadence:** Real-time or hourly  
**Confidence Scoring:** Source reliability  
**Ingestion:** RSS feeds, API, manual curation

---

## 5. Entity Relationships

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           Entity Relationship Diagram                           │
│                                                                                  │
│                                                                                  │
│    ┌──────────┐         ┌──────────┐         ┌──────────┐                       │
│    │   User   │────────<│Preference│         │  Alert   │                       │
│    └────┬─────┘    1:1  └──────────┘         └────┬─────┘                       │
│         │                                         │                              │
│         │ 1:N                                     │ N:1                          │
│         ▼                                         ▼                              │
│    ┌──────────┐                             ┌──────────┐                        │
│    │  Truck   │                             │   User   │                        │
│    └────┬─────┘                             └──────────┘                        │
│         │                                                                        │
│         │ N:1 (current location)                                                │
│         ▼                                                                        │
│    ┌──────────┐         ┌──────────┐         ┌──────────┐                       │
│    │ Location │<───────>│   Load   │───────>│  Broker  │                       │
│    └──────────┘   N:1   └────┬─────┘   N:1  └──────────┘                        │
│         ▲                    │                                                   │
│         │                    │ N:M (via stops)                                  │
│         │                    ▼                                                   │
│         │              ┌──────────┐                                             │
│         └──────────────│ Facility │                                             │
│               N:1      └──────────┘                                             │
│                                                                                  │
│                                                                                  │
│    ┌──────────┐         ┌──────────┐                                            │
│    │   Lane   │◄────────│   Load   │  (computed aggregation)                    │
│    └──────────┘   N:1   └──────────┘                                            │
│                                                                                  │
│                                                                                  │
│    ┌──────────┐         ┌──────────┐                                            │
│    │Watchlist │────────<│   Load   │  (N:M via load_ids)                        │
│    └──────────┘         └──────────┘                                            │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. ID Schemes

| Entity | ID Format | Example |
|--------|-----------|---------|
| Load | UUIDv4 | `f47ac10b-58cc-4372-a567-0e02b2c3d479` |
| Broker | UUIDv4 (internal) + MC# (external) | `MC-123456` |
| Facility | UUIDv4 or hash of address | `fac_abc123` |
| Lane | `{origin}:{destination}` | `ATL_GA:CHI_IL` |
| User | UUIDv4 | `usr_f47ac10b` |
| Truck | UUIDv4 | `trk_58cc4372` |
| Alert | UUIDv4 | `alt_a567e02b` |
| Watchlist | UUIDv4 | `wl_2c3d4790` |

---

## 7. Provenance Tracking

Every ingested record includes provenance metadata:

```python
class Provenance:
    source_system: str           # "dat", "truckstop", "import", "synthetic"
    source_record_id: str | None # Original ID from source
    ingested_at: datetime        # When we received it
    source_updated_at: datetime | None  # When source last updated
    confidence_score: float      # 0.0 - 1.0 based on freshness/reliability
    dedup_key: str | None        # Hash for deduplication
    version: int                 # Increment on updates
```

---

## 8. Schema Evolution

All schemas follow these principles:

1. **Additive only** — New fields are optional with defaults
2. **Versioned** — Major changes increment API version
3. **Documented** — All fields have descriptions
4. **Validated** — Pydantic enforces constraints

Current schema version: **1.0.0**
