# API Reference

## FreightLens REST API Specification

**Version:** 1.0  
**Base URL:** `http://localhost:8035/api`  
**Last Updated:** 2024-12-19

---

## Overview

FreightLens exposes a RESTful JSON API built on **FastAPI**. All endpoints return JSON responses and accept JSON request bodies where applicable.

### Base Configuration

| Property | Value |
|----------|-------|
| Framework | FastAPI 0.125+ |
| Server | Uvicorn 0.38+ |
| Serialization | Pydantic v2 |
| Documentation | Auto-generated at `/docs` (Swagger) and `/redoc` |

### Response Format

All successful responses follow this structure:

```json
{
  "data": { ... },      // or array for list endpoints
  "meta": {             // optional metadata
    "total": 100,
    "page": 1,
    "per_page": 20
  }
}
```

Error responses:

```json
{
  "detail": "Error message",
  "code": "ERROR_CODE",      // optional
  "fields": { ... }          // optional, for validation errors
}
```

---

## Current Endpoints

### Meta & Health

#### GET /api/meta

Returns server metadata and dataset information.

**Response:**

```json
{
  "source": "synthetic",
  "count": 250,
  "server_time": "2024-12-19T15:30:00Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `source` | string | Data source identifier (`synthetic`, `import:json`, `import:csv`) |
| `count` | integer | Total loads in current dataset |
| `server_time` | string | Current server time (ISO 8601 UTC) |

**Status Codes:**

| Code | Description |
|------|-------------|
| 200 | Success |

---

### Loads

#### GET /api/loads

List and search loads with filtering and sorting.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `q` | string | — | Free-text search (origin, destination, commodity) |
| `equipment` | string | — | Equipment type filter (`Dry Van`, `Reefer`, `Flatbed`, `Power Only`) |
| `weight_min` | integer | — | Minimum weight in lbs |
| `weight_max` | integer | — | Maximum weight in lbs |
| `hazmat` | boolean | — | Filter by hazmat requirement |
| `pickup_start` | datetime | — | Pickup window start (ISO 8601) |
| `pickup_end` | datetime | — | Pickup window end (ISO 8601) |
| `delivery_start` | datetime | — | Delivery window start (ISO 8601) |
| `delivery_end` | datetime | — | Delivery window end (ISO 8601) |
| `deadhead_max` | float | — | Maximum deadhead miles |
| `rpm_min` | float | — | Minimum rate per mile |
| `broker_rating_min` | float | — | Minimum broker rating (0-5) |
| `detention` | boolean | — | Filter by detention pay availability |
| `multi_stop` | boolean | — | Filter by multi-stop loads |
| `lane_history` | boolean | — | Filter by lane history availability |
| `sort` | string | `composite` | Sort order (see below) |

**Sort Options:**

| Value | Description |
|-------|-------------|
| `composite` | GreenLight composite score (default) |
| `rpm_desc` | Rate per mile, highest first |
| `pickup_soonest` | Earliest pickup first |
| `deadhead_asc` | Lowest deadhead first |
| `broker_desc` | Highest broker rating first |

**Response:**

```json
{
  "total": 150,
  "loads": [
    {
      "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "origin": {
        "city": "Atlanta",
        "state": "GA"
      },
      "destination": {
        "city": "Chicago",
        "state": "IL"
      },
      "pickup_start": "2024-12-20T08:00:00Z",
      "pickup_end": "2024-12-20T16:00:00Z",
      "delivery_start": "2024-12-21T08:00:00Z",
      "delivery_end": "2024-12-21T18:00:00Z",
      "equipment": "Dry Van",
      "weight_lbs": 42000,
      "hazmat": false,
      "distance_miles": 716.5,
      "deadhead_miles": 45.0,
      "rate_total_usd": 1850.00,
      "rpm": 2.58,
      "broker": {
        "name": "Acme Logistics",
        "rating": 4.2
      },
      "detention": true,
      "multi_stop": false,
      "lane_history": true,
      "commodity": "General Freight",
      "posted_at": "2024-12-19T10:30:00Z",
      "updated_at": "2024-12-19T14:15:00Z"
    }
  ]
}
```

**Status Codes:**

| Code | Description |
|------|-------------|
| 200 | Success |
| 422 | Validation error (invalid parameters) |

---

#### GET /api/loads/{load_id}

Get detailed information for a single load.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `load_id` | string | Load UUID |

**Response:**

```json
{
  "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "origin": {
    "city": "Atlanta",
    "state": "GA"
  },
  "destination": {
    "city": "Chicago",
    "state": "IL"
  },
  // ... all load fields
}
```

**Status Codes:**

| Code | Description |
|------|-------------|
| 200 | Success |
| 404 | Load not found |

---

### Data Management

#### POST /api/refresh

Regenerate the synthetic dataset.

**Request Body:**

```json
{
  "count": 200
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `count` | integer | 200 | Number of loads to generate (1-5000) |

**Response:**

```json
{
  "ok": true,
  "source": "synthetic",
  "count": 200
}
```

**Status Codes:**

| Code | Description |
|------|-------------|
| 200 | Success |
| 422 | Invalid count parameter |

---

#### POST /api/import

Import loads from a JSON or CSV file.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `filename` | string | Yes | Original filename (used to detect format) |

**Request Body:**

Raw file content as `application/octet-stream` or `application/json`.

**Response:**

```json
{
  "ok": true,
  "source": "import:json",
  "count": 50
}
```

**Status Codes:**

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Import failed (parse error, invalid format) |

---

### News

#### GET /api/news

Get trucking news headlines for the ticker.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 20 | Maximum items to return |

**Response:**

```json
{
  "items": [
    {
      "title": "Spot rates rise 3% in Southeast",
      "link": "https://example.com/article",
      "source": "FreightWaves",
      "published": "2024-12-19T12:00:00Z"
    }
  ]
}
```

**Status Codes:**

| Code | Description |
|------|-------------|
| 200 | Success |

---

## Planned Endpoints (Future Phases)

### Phase 1: Scoring

#### GET /api/loads (Enhanced)

**Additional Response Fields:**

```json
{
  "loads": [
    {
      // ... existing fields
      "score": 78.5,
      "score_reasons": [
        {
          "factor": "rpm",
          "category": "profitability",
          "direction": "positive",
          "contribution_pct": 22.3,
          "explanation": "Rate of $2.58/mi is 12% above market average"
        }
      ],
      "confidence": 0.85
    }
  ]
}
```

---

### Phase 2: Preferences

#### GET /api/preferences

Get current user scoring preferences.

**Response:**

```json
{
  "user_id": "default",
  "preferences": {
    "equipment_types": ["Dry Van", "Reefer"],
    "max_deadhead_miles": 200,
    "max_weight_lbs": 45000,
    "min_weight_lbs": 12000,
    "cost_per_mile": 1.5,
    "preferred_lanes": ["ATL_GA:CHI_IL", "DAL_TX:DEN_CO"],
    "home_base": "ATL_GA",
    "hazmat_endorsed": false,
    "detention": null,
    "watchlisted": null,
    "hazmat": null,
    "multi_stop": null,
    "min_broker_rating": 3.5,
    "min_rpm": 2.5,
    "greenlight_threshold": 70
  },
  "updated_at": "2024-12-19T12:00:00Z"
}
```

---

#### PUT /api/preferences

Update user scoring preferences.

**Request Body:**

```json
{
  "min_rpm": 2.75,
  "max_deadhead_miles": 150,
  "equipment_types": ["Dry Van"],
  "watchlisted": true,
  "detention": false,
  "hazmat": false,
  "multi_stop": null
}
```

**Response:**

```json
{
  "user_id": "default",
  "preferences": { /* updated preferences */ },
  "updated_at": "2024-12-19T12:05:00Z"
}
```

---

### Phase 2: Saved Filters

#### GET /api/filters

List saved filter presets.

**Response:**

```json
{
  "filters": [
    {
      "id": "flt_abc123",
      "name": "High RPM Dry Van",
      "criteria": {
        "equipment": "Dry Van",
        "rpm_min": 2.5,
        "deadhead_max": 150
      },
      "is_default": true,
      "created_at": "2024-12-01T10:00:00Z"
    }
  ]
}
```

---

#### POST /api/filters

Create a new saved filter.

**Request Body:**

```json
{
  "name": "Southeast Reefer",
  "criteria": {
    "q": "GA FL SC NC",
    "equipment": "Reefer",
    "rpm_min": 2.8
  },
  "is_default": false
}
```

**Response:**

```json
{
  "id": "flt_def456",
  "name": "Southeast Reefer",
  // ... full filter object
}
```

---

#### DELETE /api/filters/{filter_id}

Delete a saved filter.

**Status Codes:**

| Code | Description |
|------|-------------|
| 204 | Deleted successfully |
| 404 | Filter not found |

---

### Phase 3: Brokers

#### GET /api/brokers/{mc_number}

Get broker details and risk profile.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `mc_number` | string | Broker MC number (e.g., `MC-123456`) |

**Response:**

```json
{
  "mc_number": "MC-123456",
  "dot_number": "DOT-789012",
  "name": "Acme Logistics Inc",
  "authority_status": "active",
  "authority_granted": "2018-05-15",
  "insurance_on_file": true,
  "bond_on_file": true,
  "risk_score": 72.5,
  "days_to_pay_avg": 32.5,
  "days_to_pay_p90": 45.0,
  "dispute_rate": 0.02,
  "chargeback_rate": 0.005,
  "rating": 4.2,
  "rating_count": 156,
  "updated_at": "2024-12-15T00:00:00Z"
}
```

---

#### GET /api/brokers

Search brokers.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `q` | string | Search by name or MC number |
| `risk_score_min` | float | Minimum risk score (0-100) |
| `rating_min` | float | Minimum rating (0-5) |

---

### Phase 3: Facilities

#### GET /api/facilities/{facility_id}

Get facility intelligence.

**Response:**

```json
{
  "id": "fac_abc123",
  "name": "Amazon Fulfillment Center",
  "location": {
    "city": "Atlanta",
    "state": "GA",
    "address": "123 Warehouse Blvd"
  },
  "facility_type": "receiver",
  "operating_hours": {
    "monday": {"open": "06:00", "close": "22:00"},
    "tuesday": {"open": "06:00", "close": "22:00"}
    // ...
  },
  "appointment_required": true,
  "drop_trailer_allowed": false,
  "avg_dwell_minutes": 145,
  "p90_dwell_minutes": 240,
  "detention_likelihood": "medium",
  "lumper_required": true,
  "lumper_avg_cost_usd": 75.00,
  "rating": 3.8,
  "rating_count": 89,
  "updated_at": "2024-12-10T00:00:00Z"
}
```

---

### Phase 4: Watchlists

#### GET /api/watchlists

List user's watchlists.

**Response:**

```json
{
  "watchlists": [
    {
      "id": "wl_abc123",
      "name": "Hot Loads",
      "load_count": 5,
      "is_default": true,
      "created_at": "2024-12-01T10:00:00Z",
      "updated_at": "2024-12-19T14:30:00Z"
    }
  ]
}
```

---

#### POST /api/watchlists

Create a new watchlist.

**Request Body:**

```json
{
  "name": "West Coast Opportunities"
}
```

---

#### GET /api/watchlists/{watchlist_id}

Get watchlist with loads.

**Response:**

```json
{
  "id": "wl_abc123",
  "name": "Hot Loads",
  "loads": [
    { /* full load objects */ }
  ],
  "created_at": "2024-12-01T10:00:00Z"
}
```

---

#### POST /api/watchlists/{watchlist_id}/loads

Add a load to watchlist.

**Request Body:**

```json
{
  "load_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479"
}
```

---

#### DELETE /api/watchlists/{watchlist_id}/loads/{load_id}

Remove a load from watchlist.

---

### Phase 4: Alerts

#### GET /api/alerts

List user's alerts.

**Response:**

```json
{
  "alerts": [
    {
      "id": "alt_abc123",
      "name": "Chicago Dry Van Alert",
      "alert_type": "lane",
      "criteria": {
        "q": "Chicago",
        "equipment": "Dry Van",
        "rpm_min": 2.5
      },
      "channels": ["email", "push"],
      "enabled": true,
      "last_triggered": "2024-12-19T10:00:00Z",
      "trigger_count": 15,
      "created_at": "2024-12-01T00:00:00Z"
    }
  ]
}
```

---

#### POST /api/alerts

Create a new alert.

**Request Body:**

```json
{
  "name": "High-paying Reefer",
  "alert_type": "price",
  "criteria": {
    "equipment": "Reefer"
  },
  "threshold_value": 3.0,
  "threshold_operator": "gte",
  "channels": ["email"]
}
```

---

#### PUT /api/alerts/{alert_id}

Update an alert.

---

#### DELETE /api/alerts/{alert_id}

Delete an alert.

---

#### GET /api/alerts/triggered

Get recently triggered alerts with matching loads.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `since` | datetime | 24h ago | Only alerts triggered after this time |

**Response:**

```json
{
  "triggered": [
    {
      "alert_id": "alt_abc123",
      "alert_name": "Chicago Dry Van Alert",
      "triggered_at": "2024-12-19T14:30:00Z",
      "matching_loads": [
        { /* load objects */ }
      ]
    }
  ]
}
```

---

### Phase 4: Portfolio (Fleet Management)

#### GET /api/trucks

List user's registered trucks.

**Response:**

```json
{
  "trucks": [
    {
      "id": "trk_abc123",
      "equipment_type": "Dry Van",
      "current_location": {
        "city": "Nashville",
        "state": "TN"
      },
      "available_at": "2024-12-19T18:00:00Z",
      "status": "en_route",
      "driver_name": "John Smith"
    }
  ]
}
```

---

#### POST /api/trucks

Register a new truck.

**Request Body:**

```json
{
  "equipment_type": "Dry Van",
  "current_location": {
    "city": "Atlanta",
    "state": "GA"
  },
  "max_weight_lbs": 45000,
  "hazmat_endorsed": false,
  "driver_name": "Jane Doe"
}
```

---

#### PUT /api/trucks/{truck_id}

Update truck information.

---

#### GET /api/trucks/{truck_id}/recommendations

Get recommended loads for a specific truck.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 10 | Number of recommendations |

**Response:**

```json
{
  "truck_id": "trk_abc123",
  "recommendations": [
    {
      "load": { /* load object */ },
      "score": 85.2,
      "match_reasons": [
        "Equipment match: Dry Van",
        "Low deadhead: 23 miles",
        "High RPM: $2.95/mi"
      ],
      "deadhead_from_truck": 23.5
    }
  ]
}
```

---

### Phase 6: Analytics

#### GET /api/lanes

List lane statistics.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `origin` | string | Origin market filter |
| `destination` | string | Destination market filter |
| `equipment` | string | Equipment type filter |

**Response:**

```json
{
  "lanes": [
    {
      "id": "ATL_GA:CHI_IL",
      "origin_region": "ATL_GA",
      "destination_region": "CHI_IL",
      "load_count_7d": 245,
      "load_count_30d": 1050,
      "rate_avg_usd": 1820.00,
      "rate_p25_usd": 1650.00,
      "rate_p50_usd": 1800.00,
      "rate_p75_usd": 1950.00,
      "rpm_avg": 2.54,
      "rate_change_7d_pct": 3.2,
      "rate_change_30d_pct": -1.5,
      "backhaul_probability": 0.72,
      "market_pressure": "balanced",
      "updated_at": "2024-12-19T00:00:00Z"
    }
  ]
}
```

---

#### GET /api/lanes/{lane_id}

Get detailed lane information.

---

#### GET /api/lanes/{lane_id}/history

Get historical rate data for a lane.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | integer | 30 | Days of history |
| `granularity` | string | `daily` | `daily` or `weekly` |

**Response:**

```json
{
  "lane_id": "ATL_GA:CHI_IL",
  "history": [
    {
      "date": "2024-12-18",
      "rate_avg": 1810.00,
      "rate_low": 1650.00,
      "rate_high": 2100.00,
      "load_count": 35
    }
  ]
}
```

---

#### GET /api/analytics/heatmap

Get market heatmap data.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `metric` | string | `volume` | `volume`, `rate_change`, `pressure` |
| `equipment` | string | — | Equipment type filter |

**Response:**

```json
{
  "metric": "volume",
  "regions": [
    {
      "region": "ATL_GA",
      "value": 0.85,
      "label": "High"
    }
  ]
}
```

---

## Authentication (Phase 7)

### POST /api/auth/login

Authenticate and receive tokens.

**Request Body:**

```json
{
  "email": "user@example.com",
  "password": "secretpassword"
}
```

**Response:**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

---

### POST /api/auth/refresh

Refresh access token.

**Request Body:**

```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

---

### POST /api/auth/logout

Invalidate refresh token.

**Headers:**

```
Authorization: Bearer <access_token>
```

---

## Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 422 | Request validation failed |
| `NOT_FOUND` | 404 | Resource not found |
| `UNAUTHORIZED` | 401 | Authentication required |
| `FORBIDDEN` | 403 | Insufficient permissions |
| `RATE_LIMITED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Server error |
| `IMPORT_FAILED` | 400 | Data import failed |
| `INVALID_FILTER` | 400 | Invalid filter criteria |

---

## Rate Limiting (Phase 7)

| Tier | Requests/Minute | Burst |
|------|-----------------|-------|
| Anonymous | 30 | 10 |
| Authenticated | 300 | 50 |
| Premium | 1000 | 100 |

Rate limit headers:

```
X-RateLimit-Limit: 300
X-RateLimit-Remaining: 295
X-RateLimit-Reset: 1703001600
```

---

## Versioning

The API uses URL-based versioning (future):

- Current: `/api/...` (v1 implicit)
- Future: `/api/v2/...`

Breaking changes will increment the major version. Non-breaking additions are allowed within a version.

---

## OpenAPI Specification

Auto-generated documentation available at:

- **Swagger UI:** `http://localhost:8035/docs`
- **ReDoc:** `http://localhost:8035/redoc`
- **OpenAPI JSON:** `http://localhost:8035/openapi.json`

---

## SDK Examples

### Python (httpx)

```python
import httpx

client = httpx.Client(base_url="http://localhost:8035")

# List loads with filters
response = client.get("/api/loads", params={
    "equipment": "Dry Van",
    "rpm_min": 2.5,
    "sort": "composite"
})
loads = response.json()["loads"]

# Get single load
load = client.get(f"/api/loads/{loads[0]['id']}").json()
```

### JavaScript (fetch)

```javascript
const API_BASE = "http://localhost:8035/api";

// List loads
const response = await fetch(`${API_BASE}/loads?equipment=Dry+Van&rpm_min=2.5`);
const { loads, total } = await response.json();

// Get single load
const load = await fetch(`${API_BASE}/loads/${loads[0].id}`).then(r => r.json());
```

### cURL

```bash
# List loads
curl "http://localhost:8035/api/loads?equipment=Dry%20Van&rpm_min=2.5"

# Import JSON file
curl -X POST "http://localhost:8035/api/import?filename=loads.json" \
  -H "Content-Type: application/octet-stream" \
  --data-binary @loads.json

# Refresh synthetic data
curl -X POST "http://localhost:8035/api/refresh" \
  -H "Content-Type: application/json" \
  -d '{"count": 500}'
```

---

## Trust Metadata in Responses

All load responses include trust metadata for UI confidence/provenance display. See [TRUST_UI_SPEC.md](TRUST_UI_SPEC.md) for full specification.

### Trust Fields (Required)

Every load object includes a `trust` property:

```json
{
  "id": "abc-123",
  "rate_total_usd": 1850.00,
  "score": 92,
  "trust": {
    "confidence_score": 88,
    "confidence_bucket": "high",
    "confidence_reasons": [
      {"factor": "core_fields_present", "contribution": 40},
      {"factor": "broker_reviews_count", "contribution": 20},
      {"factor": "data_freshness", "contribution": 15},
      {"factor": "source_verified", "contribution": 15},
      {"factor": "facility_data_missing", "contribution": -2}
    ],
    "missing_fields": ["facility_id", "dwell_estimate"],
    "provenance": {
      "source_type": "partner",
      "source_name": "Acme Logistics API",
      "acquired_at": "2024-12-19T15:15:00Z"
    },
    "freshness_seconds": 900,
    "freshness_bucket": "fresh",
    "rights_state": "compliant",
    "rights_restrictions": []
  }
}
```

### Confidence Breakdown Endpoint

#### GET /api/loads/{load_id}/confidence

Get detailed confidence score breakdown for a load.

**Response:**

```json
{
  "load_id": "abc-123",
  "confidence_score": 88,
  "confidence_bucket": "high",
  "breakdown": [
    {
      "factor": "core_fields_present",
      "label": "Core fields verified",
      "contribution": 40,
      "details": "Rate, distance, equipment, pickup, delivery all present"
    },
    {
      "factor": "broker_reviews_count",
      "label": "Broker reputation depth",
      "contribution": 20,
      "details": "156 verified reviews"
    }
  ],
  "penalties": [
    {
      "factor": "facility_data_missing",
      "label": "Facility not in database",
      "contribution": -2,
      "details": "No dwell or detention estimates available"
    }
  ]
}
```

### Trust Endpoint (Confidence Summary)

#### GET /api/loads/{load_id}/trust

Returns the trust/confidence summary for a specific load with a deterministic score and a stable ordering of reasons. This is the supported contract that powers the UI trust badge; the legacy `/api/loads/{load_id}/confidence` breakdown above is a richer prototype and may diverge.

**Response shape (exactly as implemented):**

```json
{
  "load_id": "abc-123",
  "confidence_score": 88,
  "confidence_bucket": "high",
  "confidence_reasons": [
    {
      "factor": "core_fields_present",
      "label": "Core fields verified",
      "contribution": 20,
      "details": {
        "message": "Distance, rate, and RPM present"
      }
    }
  ]
}
```

**Semantics and degradation rules:**
- Deterministic scoring; the reason list is emitted in a stable order.
- Degrades when RPM must be derived (`rpm_derived`), distance is clamped (`distance_clamped`), provenance timestamps are stale/expired, or provenance identifiers are missing.
- Sensitive provenance fields (record IDs, raw source payloads) are never returned in this response; only derived factors/reasons are exposed.

**Buckets:** `high` (score ≥ 80), `medium` (score ≥ 50), `low` (otherwise).

### Restricted Data Redaction

Loads with `rights_state: "restricted"` have certain fields redacted:

```json
{
  "broker": {
    "name": "Beta Freight",
    "mc_number": "[RESTRICTED]",
    "phone": "[RESTRICTED]",
    "rating": 3.8
  },
  "trust": {
    "rights_state": "restricted",
    "rights_restrictions": [
      {"field": "broker.mc_number", "reason": "source_terms"},
      {"field": "broker.phone", "reason": "source_terms"}
    ]
  }
}
```

**Redaction Rules:**
- Restricted fields display `[RESTRICTED]` placeholder
- `rights_restrictions` array lists each redacted field with reason
- Export endpoints exclude restricted data entirely
