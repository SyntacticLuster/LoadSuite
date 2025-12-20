# Trust UI Specification

## Inline Confidence, Provenance & Data Rights Display

**Version:** 1.0  
**Status:** Draft  
**Last Updated:** 2024-12-19  
**Owner:** Product + Design + Engineering

---

## Purpose

FreightLens surfaces data from multiple sources with varying reliability. Users deserve to know:
1. **How confident** are we in this information?
2. **Where** did it come from?
3. **How fresh** is it?
4. **Can I share/export** it?

This spec defines how trust signals appear throughout the UI—inline, not hidden.

---

## A. Trust Primitives

Every data element that feeds into decision-making carries trust metadata.

### A.1 Core Trust Fields

| Field | Type | Description | Required |
|-------|------|-------------|----------|
| `confidence_score` | int (0-100) | Numeric confidence in data accuracy | Yes |
| `confidence_bucket` | enum | Human-readable bucket: `high`, `medium`, `low` | Yes |
| `provenance.source_type` | enum | Category of source (see below) | Yes |
| `provenance.source_name` | string | Specific source identifier | Yes |
| `provenance.acquired_at` | datetime | When FreightLens received this data | Yes |
| `freshness_seconds` | int | Age since acquisition (computed) | Yes |
| `freshness_bucket` | enum | `fresh`, `recent`, `stale`, `expired` | Yes |
| `rights_state` | enum | `compliant`, `restricted`, `quarantined` | Yes |

### A.2 Confidence Buckets

| Bucket | Score Range | Visual | Meaning |
|--------|-------------|--------|---------|
| `high` | 80-100 | 🟢 Green dot | Strong data; multiple verified sources or user-provided |
| `medium` | 50-79 | 🟡 Yellow dot | Partial data; some fields estimated or single source |
| `low` | 0-49 | 🔴 Red dot | Weak data; critical fields missing or stale |

### A.3 Provenance Types

| Type | Badge Text | Icon | Example |
|------|------------|------|---------|
| `partner` | "Partner" | 🤝 | Licensed API feed |
| `public` | "Public" | 📊 | FMCSA SAFER, EIA |
| `user_provided` | "Your data" | 👤 | User CSV import |
| `user_connected` | "Connected" | 🔗 | OAuth-linked account |
| `community` | "Community" | 👥 | Aggregated user ratings |
| `estimated` | "Estimated" | 📐 | Computed/modeled value |
| `unknown` | "Unverified" | ❓ | Source not classified |

### A.4 Freshness Buckets

| Bucket | Age | Badge | Color |
|--------|-----|-------|-------|
| `fresh` | < 1 hour | None (default) | — |
| `recent` | 1-4 hours | "1h ago", "3h ago" | text-secondary |
| `stale` | 4-12 hours | "Stale" | yellow |
| `expired` | > 12 hours | "Expired" | red |

### A.5 Rights States

| State | Meaning | UI Treatment |
|-------|---------|--------------|
| `compliant` | Full rights for display, export, sharing | Normal |
| `restricted` | Display allowed; export/share limited | Export disabled; tooltip explains |
| `quarantined` | Internal/test only; should not appear in production | Hidden or red warning banner |

---

## B. Placement

### B.1 Load List (Terminal Table)

Each row shows minimal trust indicators:

```
┌────────────────────────────────────────────────────────────────────────────┐
│ SCORE │ O→D              │ RATE    │ RPM   │ BROKER        │ CONF │ AGE   │
├────────────────────────────────────────────────────────────────────────────┤
│ 🟢 92 │ ATL,GA → CHI,IL  │ $1,850  │ $2.58 │ Acme 4.2★     │ 🟢   │       │
│ 🟡 78 │ DAL,TX → DEN,CO  │ $2,100  │ $2.72 │ Beta 3.8★     │ 🟡   │ 2h    │
│ 🔴 54 │ MIA,FL → ATL,GA  │ $1,200  │ $2.45 │ Unknown       │ 🔴   │ 6h ⚠️ │
└────────────────────────────────────────────────────────────────────────────┘
```

**Column definitions:**
- **CONF** (Confidence): Colored dot indicating `confidence_bucket`
- **AGE**: Time since load posted; shows warning icon if `stale` or `expired`

**Keyboard:** `c` toggles confidence column visibility.

### B.2 Load Detail Panel

Full trust breakdown in dedicated section:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ LOAD DETAIL: ATL,GA → CHI,IL                                    [×] [⭐]   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│ GreenLight Score: ████████████████░░░░ 92/100                              │
│                                                                             │
│ DATA QUALITY                                                                │
│ ┌─────────────────────────────────────────────────────────────────────────┐│
│ │ 🟢 High Confidence (88/100)                                             ││
│ │                                                                          ││
│ │ Source: Partner feed (Acme Logistics API)                               ││
│ │ Updated: 15 minutes ago                                                  ││
│ │ Rights: ✓ Display  ✓ Export  ✓ Share                                    ││
│ │                                                                          ││
│ │ Field Coverage:                                                          ││
│ │   ✓ Rate        ✓ Distance    ✓ Equipment    ✓ Broker                   ││
│ │   ✓ Pickup      ✓ Delivery    ⚠ Facility     ✗ Dwell estimate          ││
│ │                                                                          ││
│ │ [?] Why this confidence                                                  ││
│ └─────────────────────────────────────────────────────────────────────────┘│
│                                                                             │
│ WHY THIS SCORE: (click any factor for details)                             │
│   ✓ +22% RPM above market     ✓ Broker 4.2★ (156 reviews)                 │
│   ✓ Lane history: 12 runs     ⚠ Pickup in 18 hours                        │
│   ✓ Low deadhead: 45 mi       ⚠ Unknown facility (no dwell data)          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Field coverage legend:**
- ✓ = Present and verified
- ⚠ = Present but incomplete/estimated
- ✗ = Missing

### B.3 Broker Profile

Broker cards show source of reputation data:

```
┌───────────────────────────────────────────────────────────────┐
│ BROKER: Acme Logistics (MC-123456)                            │
├───────────────────────────────────────────────────────────────┤
│ Rating: ★★★★☆ 4.2 (156 reviews)                              │
│ Source: 🟢 Community ratings                                  │
│                                                                │
│ Days to Pay: 28 avg (22–38 range)                             │
│ Source: 🟡 Estimated from 23 user reports                     │
│                                                                │
│ Authority: Active since 2018                                  │
│ Source: 🟢 FMCSA SAFER (verified Dec 15, 2024)               │
│                                                                │
│ Dispute Rate: 2.1%                                            │
│ Source: 🟡 Community reports (limited sample)                 │
└───────────────────────────────────────────────────────────────┘
```

### B.4 Alerts

Alert cards include confidence of matched loads:

```
┌─────────────────────────────────────────────────────────────────┐
│ 🔔 ALERT: "High RPM Southeast"                                  │
│    3 new loads match your criteria                              │
├─────────────────────────────────────────────────────────────────┤
│ 🟢 92 │ ATL→CHI │ $2.58/mi │ High confidence                   │
│ 🟡 78 │ MIA→ATL │ $2.45/mi │ Medium confidence (broker unknown)│
│ 🔴 61 │ JAX→SAV │ $2.80/mi │ Low confidence (stale, 8h old)    │
└─────────────────────────────────────────────────────────────────┘
```

### B.5 Exports

Export dialogs warn about restricted data:

```
┌─────────────────────────────────────────────────────────────────┐
│ EXPORT: Selected Loads (12)                                     │
├─────────────────────────────────────────────────────────────────┤
│ Format: [CSV ▾]  [Download]                                     │
│                                                                  │
│ ⚠️ 2 loads have restricted data:                                │
│    • Load #4: Broker contact info (source limitation)           │
│    • Load #9: Rate details (connected account terms)            │
│                                                                  │
│ These fields will be excluded from export.                      │
│ [Learn more]                                                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## C. Interaction Rules

### C.1 Hover/Click: "Why This Confidence"

**Trigger:** Click `[?]` or hover over confidence indicator (500ms delay).

**Content:**
```
┌─────────────────────────────────────────────────────────────────┐
│ WHY THIS CONFIDENCE: 88/100 (High)                              │
├─────────────────────────────────────────────────────────────────┤
│ ✓ Core fields present (rate, distance, equipment)      +40     │
│ ✓ Broker has 150+ ratings                               +20     │
│ ✓ Data is fresh (15 min old)                            +15     │
│ ✓ Source is verified partner                            +15     │
│ ⚠ Facility dwell data missing                           -2     │
│                                                                  │
│ Confidence = sum of quality signals (capped at 100)             │
└─────────────────────────────────────────────────────────────────┘
```

**Dismiss:** Click outside, press `Esc`, or after 5 seconds of mouse-out.

### C.2 Hover/Click: "Why This Score"

**Trigger:** Click factor row in score breakdown.

**Content:**
```
┌─────────────────────────────────────────────────────────────────┐
│ FACTOR: Rate Per Mile (RPM)                                     │
├─────────────────────────────────────────────────────────────────┤
│ This load: $2.58/mi                                             │
│ Lane average: $2.12/mi (last 30 days)                           │
│ Your preference weight: 1.5× (you prioritize RPM)               │
│                                                                  │
│ Contribution: +22% above market → +18.2 points                  │
│                                                                  │
│ Source: Lane average from Partner feed                          │
│ Confidence: 🟢 High (450 loads in sample)                       │
│                                                                  │
│ [Adjust weight in Settings]                                     │
└─────────────────────────────────────────────────────────────────┘
```

### C.3 Restricted State Behavior

| Element | Normal | Restricted |
|---------|--------|------------|
| View load in list | ✓ | ✓ |
| View load detail | ✓ | ✓ |
| Export to CSV | ✓ | ✗ (grayed, tooltip: "Limited sharing: source terms prevent export") |
| Share via link | ✓ | ✗ (grayed, tooltip: "Limited sharing: source terms prevent sharing") |
| Copy to clipboard | ✓ | Partial (excludes restricted fields) |
| API access | ✓ | Fields redacted or omitted |

### C.4 Quarantined State (Should Not Appear in Production)

If a quarantined record appears (bug or test data leak):

```
┌─────────────────────────────────────────────────────────────────┐
│ ⚠️ INTERNAL DATA — NOT FOR DECISIONS                            │
├─────────────────────────────────────────────────────────────────┤
│ This load is from an unverified source and may be inaccurate.  │
│ It is shown for testing purposes only.                          │
│                                                                  │
│ [Hide this load]  [Report issue]                                │
└─────────────────────────────────────────────────────────────────┘
```

**Feature flag:** `SHOW_QUARANTINED_DATA` must be enabled (dev/staging only).

---

## D. Copy Guidelines

### D.1 Principles

- **Non-legal:** No "terms of service" language in UI copy
- **Non-scary:** Explain limitations helpfully, not ominously
- **Actionable:** Tell users what they CAN do, not just what they can't

### D.2 Standard Phrases

| Situation | Copy |
|-----------|------|
| High confidence | "Strong data quality" |
| Medium confidence | "Some details estimated" |
| Low confidence | "Limited data available" |
| Missing field | "Not available" or "—" |
| Stale data | "Updated 6 hours ago" |
| Expired data | "This info may be outdated" |
| Restricted export | "Limited sharing: this source can't be exported" |
| Restricted share | "Limited sharing: link sharing not available" |
| Unknown broker | "Broker not yet rated" |
| Low sample size | "Based on limited reports" |

### D.3 Tooltip Templates

**Confidence tooltip:**
> "Confidence reflects data completeness and source reliability. Higher confidence = more fields verified from trusted sources."

**Provenance tooltip:**
> "{Source name} provides this data. Last updated {time ago}."

**Restricted tooltip:**
> "This data source has sharing limits. You can view it here, but export and link sharing are disabled."

### D.4 Empty States

**No confidence data:**
> "We couldn't verify this data. Proceed with caution."

**No provenance:**
> "Source unknown. This information hasn't been verified."

---

## E. Accessibility & Performance

### E.1 Keyboard Navigation

| Key | Action |
|-----|--------|
| `Tab` | Move between interactive trust elements |
| `Enter` / `Space` | Open tooltip or detail panel |
| `Escape` | Close any open tooltip |
| `c` | Toggle confidence column in list view |
| `?` | Open "Why this score" for focused load |

### E.2 Screen Reader Support

- Confidence indicators include `aria-label`: "High confidence", "Medium confidence", etc.
- Provenance badges include `aria-label`: "Data from {source name}"
- Tooltips are `role="tooltip"` with `aria-describedby` linkage
- Stale/expired badges announce: "Warning: data is {N} hours old"

### E.3 Color Independence

- Confidence dots use color + shape: 🟢 (circle), 🟡 (triangle), 🔴 (square)
- Alternative: Text labels available via accessibility setting
- Badge text always accompanies icons

### E.4 Performance Requirements

| Constraint | Target |
|------------|--------|
| Tooltip render time | < 50ms |
| List row confidence indicators | No additional API call (bundled with load) |
| Detail panel trust section | Lazy-loaded, but < 100ms |
| No modals for trust info | Inline popovers only |
| Confidence computation | Happens server-side, cached |

---

## F. API Contract Updates

### F.1 Load Response: Trust Fields

Every load in API responses must include:

```json
{
  "id": "abc-123",
  "origin": { ... },
  "destination": { ... },
  "rate_total_usd": 1850.00,
  "score": 92,
  "score_reasons": [ ... ],
  
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

### F.2 Restricted Data Redaction

For restricted loads, certain fields are redacted:

```json
{
  "id": "def-456",
  "rate_total_usd": 2100.00,
  "broker": {
    "name": "Beta Freight",
    "mc_number": "[RESTRICTED]",
    "phone": "[RESTRICTED]",
    "rating": 3.8
  },
  "trust": {
    "confidence_bucket": "medium",
    "rights_state": "restricted",
    "rights_restrictions": [
      {"field": "broker.mc_number", "reason": "source_terms"},
      {"field": "broker.phone", "reason": "source_terms"}
    ]
  }
}
```

### F.3 Required Fields in All Responses

| Endpoint | Required Trust Fields |
|----------|----------------------|
| `GET /api/loads` | `trust.confidence_bucket`, `trust.freshness_bucket`, `trust.rights_state` |
| `GET /api/loads/{id}` | Full `trust` object |
| `GET /api/brokers/{id}` | `trust` per data section (rating, payment, authority) |
| `GET /api/alerts` | `trust.confidence_bucket` per matched load |

### F.4 New Endpoint: Confidence Breakdown

```
GET /api/loads/{id}/confidence
```

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

---

## G. Acceptance Criteria

### G.1 List View

- [ ] AC-1: Loads display `confidence_bucket` as colored indicator (dot or icon)
- [ ] AC-2: Loads display age badge if `freshness_bucket` is `stale` or `expired`
- [ ] AC-3: Hovering confidence indicator shows tooltip within 500ms
- [ ] AC-4: Keyboard `c` toggles confidence column visibility
- [ ] AC-5: Screen readers announce confidence level for each row

### G.2 Detail Panel

- [ ] AC-6: Detail panel includes "DATA QUALITY" section
- [ ] AC-7: Confidence score shown as numeric (X/100) and bucket (High/Med/Low)
- [ ] AC-8: Provenance shows source type, source name, and age
- [ ] AC-9: Field coverage checklist shows ✓/⚠/✗ for key fields
- [ ] AC-10: Clicking "[?] Why this confidence" opens breakdown popover
- [ ] AC-11: Each score factor row is clickable and shows contribution detail

### G.3 Data Quality Rules

- [ ] AC-12: Loads with missing `rate_total_usd` display confidence_bucket = "low"
- [ ] AC-13: Loads with missing `distance_miles` display confidence_bucket = "low"
- [ ] AC-14: Loads older than 12 hours display `freshness_bucket` = "expired"
- [ ] AC-15: Loads with `rights_state` = "restricted" have export button disabled
- [ ] AC-16: Disabled export button shows tooltip explaining restriction
- [ ] AC-17: Loads with missing broker rating show "Broker not yet rated"

### G.4 API Contract

- [ ] AC-18: `GET /api/loads` includes `trust.confidence_bucket` for every load
- [ ] AC-19: `GET /api/loads/{id}` includes full `trust` object
- [ ] AC-20: Restricted fields are redacted with `[RESTRICTED]` placeholder
- [ ] AC-21: `rights_restrictions` array lists each redacted field and reason
- [ ] AC-22: `GET /api/loads/{id}/confidence` returns breakdown within 100ms

### G.5 Accessibility

- [ ] AC-23: All trust indicators have `aria-label` attributes
- [ ] AC-24: Tooltips are keyboard-accessible (Tab + Enter to open)
- [ ] AC-25: Color is not the only indicator (shape or text accompanies)
- [ ] AC-26: Focus trap in popovers; Escape closes

### G.6 Performance

- [ ] AC-27: Confidence indicators add < 5ms to list render time
- [ ] AC-28: Tooltips render in < 50ms
- [ ] AC-29: No blocking modals for trust information
- [ ] AC-30: Trust data is bundled with load response (no extra round-trip)

---

## H. Implementation Notes

### H.1 Confidence Score Computation

Server-side computation (see SCORING_CALIBRATION.md for weights):

```python
def compute_confidence(load: Load) -> int:
    score = 0
    
    # Core fields present (+40 max)
    core_fields = ["rate_total_usd", "distance_miles", "equipment", 
                   "pickup_start", "delivery_start"]
    present = sum(1 for f in core_fields if getattr(load, f) is not None)
    score += (present / len(core_fields)) * 40
    
    # Broker data quality (+25 max)
    if load.broker and load.broker.rating_count:
        if load.broker.rating_count >= 100:
            score += 25
        elif load.broker.rating_count >= 20:
            score += 15
        elif load.broker.rating_count >= 5:
            score += 8
    
    # Data freshness (+20 max)
    age_hours = (now() - load.provenance.acquired_at).total_seconds() / 3600
    if age_hours < 1:
        score += 20
    elif age_hours < 4:
        score += 15
    elif age_hours < 12:
        score += 5
    # else: 0
    
    # Source verification (+15 max)
    if load.provenance.source_type in ("partner", "public"):
        score += 15
    elif load.provenance.source_type == "user_provided":
        score += 10
    
    # Penalties
    if not load.facility_id:
        score -= 2
    if load.provenance.license_class == "UNKNOWN":
        score -= 10
    
    return max(0, min(100, int(score)))
```

### H.2 Freshness Bucket Logic

```python
def get_freshness_bucket(acquired_at: datetime) -> str:
    age_hours = (now() - acquired_at).total_seconds() / 3600
    if age_hours < 1:
        return "fresh"
    elif age_hours < 4:
        return "recent"
    elif age_hours < 12:
        return "stale"
    else:
        return "expired"
```

### H.3 UI Component Hierarchy

```
<LoadRow>
  <ConfidenceIndicator bucket={trust.confidence_bucket} />
  <FreshnessBadge bucket={trust.freshness_bucket} />
  <RestrictedIcon visible={trust.rights_state !== "compliant"} />
</LoadRow>

<LoadDetail>
  <DataQualitySection trust={load.trust}>
    <ConfidenceScore score={trust.confidence_score} bucket={trust.confidence_bucket} />
    <ProvenanceBadge source={trust.provenance} />
    <FieldCoverage fields={load} missing={trust.missing_fields} />
    <WhyConfidencePopover reasons={trust.confidence_reasons} />
  </DataQualitySection>
</LoadDetail>
```

---

## Assumptions

1. **Server-side confidence:** Confidence is computed on the server, not client, for consistency.
2. **Bundled trust data:** Trust fields are included in all load responses by default (no lazy loading for list view).
3. **No legal review required:** Copy is non-legal by design; this is UX language, not terms.
4. **Feature-flagged quarantine:** Quarantined data never appears in production without explicit flag.
