# Data Rights & Sourcing

## FreightLens Data Governance Policy v1

**Version:** 1.0  
**Status:** Active  
**Last Updated:** 2024-12-19  
**Policy Owner:** Engineering + Product  
**Review Cadence:** Quarterly or before major source additions

---

## A. Purpose & Scope

### Why This Document Exists

FreightLens ingests data from multiple external sources to provide carriers with load scoring, risk analysis, and decision support. This document establishes **enforceable rules** for:

1. **Classification** — Categorizing data sources by rights status and risk
2. **Ingestion** — What we can accept and how we tag it
3. **Storage** — Where data lives and for how long
4. **Access** — Who/what can see, transform, and export data
5. **Quarantine** — Enabling rapid prototyping without contaminating production

### What This Document Governs

| In Scope | Out of Scope |
|----------|--------------|
| All data ingested via connectors | User authentication data |
| User-uploaded/imported data | Application code |
| Derived/computed metrics | Infrastructure secrets |
| Cached external API responses | Billing/payment data |
| Model training datasets | HR/employee data |

### Guiding Principle

> **Default Deny**: If rights status is unknown, treat the source as QUARANTINED. Never expose uncertain data in production or allow export without explicit classification upgrade.

---

## B. Definitions

### Core Provenance Fields

| Field | Type | Description | Required |
|-------|------|-------------|----------|
| `provenance.source_type` | enum | Category of data source (see Section C) | YES |
| `provenance.source_name` | string | Specific source identifier (e.g., `partner:acme_feeds`, `upload:csv`) | YES |
| `provenance.source_record_id` | string | Original ID from source system | YES (if available) |
| `provenance.acquired_at` | datetime | When FreightLens first received this record (UTC) | YES |
| `provenance.license_class` | enum | Rights classification (see below) | YES |
| `provenance.rights_flags` | object | Granular permissions (see below) | YES |
| `provenance.quarantine` | boolean | Is this record in quarantine mode? | YES |
| `provenance.ttl_expires_at` | datetime | When record MUST be deleted (if set) | NO |
| `provenance.raw_payload_ref` | string | Reference to encrypted raw storage (if retained) | NO |
| `provenance.classification` | enum | COMPLIANT/RESTRICTED/QUARANTINED/BLOCKED | YES |

### License Classes

| Class | Definition | Example Sources |
|-------|------------|-----------------|
| `OPEN` | Explicitly public domain or permissive license (CC0, CC-BY, public government data) | FMCSA SAFER, EIA fuel data |
| `LICENSED` | Contractual agreement with data provider allowing specified uses | Paid API subscription with ToS |
| `USER_PROVIDED` | Data uploaded/entered by the user; user warrants they have rights | CSV import from user's TMS |
| `USER_CONNECTED` | User authorizes us to access their account elsewhere; we act as processor | OAuth-linked broker account |
| `UNKNOWN` | Rights not established; requires review before production use | Any source without contract |

### Rights Flags Object

```python
class RightsFlags:
    store_raw: bool          # Can we persist the original payload?
    store_derived: bool      # Can we persist computed/transformed data?
    display: bool            # Can we show this to the user who owns/provided it?
    display_aggregated: bool # Can we show aggregates (e.g., lane averages)?
    export: bool             # Can user download/export this data?
    redistribute: bool       # Can we share with other users/systems?
    commingle: bool          # Can we mix with other users' data?
    train_models: bool       # Can we use for ML training?
```

### Classification Levels

| Level | Definition | Typical Treatment |
|-------|------------|-------------------|
| **COMPLIANT** | Safe for all defined operations within license bounds | Normal pipeline, full features |
| **RESTRICTED** | Allowed with specific constraints | Display-only, no export, no commingling |
| **QUARANTINED** | Unknown/unclear rights; internal testing only | Isolated storage, TTL enforced, feature-flagged |
| **BLOCKED** | Explicitly prohibited; do not ingest | Reject at connector level |

### Additional Terms

| Term | Definition |
|------|------------|
| `quarantine_mode` | System-wide or per-record flag restricting data to non-production surfaces |
| `ttl` | Time-to-live; maximum duration data may be stored before mandatory deletion |
| `raw_payload` | Original, unmodified data as received from source |
| `derived_data` | Any data computed, aggregated, or transformed from raw data |
| `commingling` | Mixing data from different sources or users into shared datasets/views |
| `redistribution` | Exposing data to parties other than the original owner/provider |

---

## C. Source Taxonomy

### 1. Licensed Partner Feeds

**Definition:** Commercial APIs or data feeds with explicit contractual terms.

- **Examples:** Paid load board API, rate intelligence subscription, broker credit API
- **Contract Status:** UNKNOWN / NEEDS REVIEW (no contracts in repo)
- **Default Classification:** COMPLIANT (once contract verified)
- **Requirements:**
  - Contract must explicitly permit storage, display, derived works
  - Must specify retention limits and redistribution rights
  - Must include termination/deletion obligations

### 2. Public/Open Licensed Datasets

**Definition:** Data explicitly released under permissive licenses.

- **Examples:** FMCSA SAFER (public broker/carrier data), EIA fuel prices, Census geography
- **License Types:** Public domain, CC0, CC-BY, US Government works
- **Default Classification:** COMPLIANT
- **Requirements:**
  - Document license type per source
  - Comply with attribution requirements (CC-BY)
  - Periodically verify license hasn't changed

### 3. User-Provided Uploads

**Definition:** Data the user imports from their own files/systems.

- **Examples:** Rate con exports, TMS CSV dumps, manually entered loads
- **Ownership:** User warrants they have rights to the data
- **Default Classification:** COMPLIANT (for that user only)
- **Requirements:**
  - Clear ToS language: user represents they have rights
  - Isolate to user's tenant; never commingle without consent
  - Deletion on user request (data portability)

### 4. User-Connected Accounts (OAuth/API Keys)

**Definition:** User authorizes FreightLens to access their external account.

- **Examples:** User provides DAT API key, TMS OAuth connection
- **Role:** FreightLens acts as data processor, not owner
- **Default Classification:** RESTRICTED
- **Requirements:**
  - User explicitly grants access
  - Honor source ToS (UNKNOWN without source review)
  - Do not redistribute to other users
  - Revoke access on user request

### 5. Broker-Provided Data

**Definition:** Brokers share load/rate data directly with permission.

- **Examples:** Broker uploads their available loads via portal
- **Rights Holder:** The broker providing the data
- **Default Classification:** RESTRICTED (confirm redistribution rights)
- **Requirements:**
  - Written permission for display to carriers
  - Clarify if data can be shown to ALL carriers or only invited
  - Honor takedown requests

### 6. Public Web Sources / Forums

**Definition:** Publicly posted information accessible without authentication.

- **Examples:** Trucker forum posts, public Facebook groups, Reddit discussions
- **Default Classification:** RESTRICTED
- **Requirements:**
  - Only factual, non-personal data (no PII extraction)
  - Attribution where appropriate
  - No systematic scraping without ToS review
  - Respect robots.txt and rate limits

### 7. Scraped Sources

**Definition:** Data obtained via automated extraction from websites.

- **Examples:** Load board scraping, carrier directory crawling
- **Default Classification:** QUARANTINED or BLOCKED
- **Risk Level:** HIGH
- **Position:**
  - Commercial loadboards: **BLOCKED** unless explicitly licensed
  - Public carrier directories: **QUARANTINED** pending legal review
  - Any authenticated scraping: **BLOCKED**
- **Requirements:**
  - Explicit legal approval required before production use
  - Never ingest scraped loadboard data without license

### 8. Internal Telemetry

**Definition:** Usage data generated by FreightLens itself.

- **Examples:** Search patterns, click behavior, scoring feedback, API metrics
- **Default Classification:** COMPLIANT (with privacy controls)
- **Requirements:**
  - Anonymize user-identifying data for aggregate analysis
  - Respect user privacy preferences
  - Clear privacy policy disclosure

---

## D. Rights & Risk Matrix

| Source Type | Classification | Ingest | Store Raw | Store Derived | Display User | Export | Redistribute | Commingle | Train Models | Retention Default | Risk | Owner |
|-------------|---------------|--------|-----------|---------------|--------------|--------|--------------|-----------|--------------|-------------------|------|-------|
| Licensed Partner Feeds | COMPLIANT | Y | Y* | Y | Y | Y* | Y* | Y* | Y* | Per contract | Low | Eng |
| Public/Open Data | COMPLIANT | Y | Y | Y | Y | Y | Y | Y | Y** | Indefinite | Low | Eng |
| User-Provided Uploads | COMPLIANT | Y | Y | Y | Y | Y | N*** | N*** | N**** | User lifetime | Low | Product |
| User-Connected Accounts | RESTRICTED | Y | Conditional | Y | Y | Conditional | N | N | N | Session/7d | Med | Eng |
| Broker-Provided Data | RESTRICTED | Y | Y | Y | Y | Conditional | Conditional | N | N | 90d | Med | Product |
| Public Web/Forums | RESTRICTED | Conditional | N | Y | Y | N | N | Conditional | N | 30d | Med | Product |
| Scraped (Commercial) | **BLOCKED** | **N** | N | N | N | N | N | N | N | N/A | **High** | **Legal** |
| Scraped (Public Dir) | QUARANTINED | Conditional | N | Y | N | N | N | N | N | 24h | High | Legal |
| Internal Telemetry | COMPLIANT | Y | Y | Y | N/A | N/A | N | Y | Y | 1y | Low | Eng |

**Legend:**
- `Y*` — Yes, within contract bounds
- `Y**` — Yes, respecting license (attribution for CC-BY)
- `N***` — Not across users without explicit consent
- `N****` — Not without user opt-in and anonymization
- `Conditional` — Depends on specific source/contract terms

### Required Provenance Fields by Source Type

| Source Type | source_record_id | acquired_at | license_class | rights_flags | classification | ttl_expires_at |
|-------------|------------------|-------------|---------------|--------------|----------------|----------------|
| Licensed Partner | Required | Required | Required | Required | Required | Optional |
| Public/Open Data | If available | Required | Required | Required | Required | Optional |
| User-Provided | Optional | Required | `USER_PROVIDED` | Required | Required | Optional |
| User-Connected | Required | Required | `USER_CONNECTED` | Required | Required | Recommended |
| Broker-Provided | Required | Required | `LICENSED` | Required | Required | Recommended |
| Public Web | Optional | Required | `UNKNOWN` | Required | Required | Required |
| Scraped | N/A | N/A | N/A | N/A | BLOCKED | N/A |
| Telemetry | Auto-generated | Required | `OPEN` | Auto-set | COMPLIANT | Required |

---

## E. Quarantine Mode

### Intended Use

Quarantine Mode enables **rapid prototyping and internal experimentation** with data sources that lack clear rights status. It provides a "sandbox" for validating data quality and integration feasibility before committing to formal licensing.

**Use Cases:**
- Evaluating a potential data partner before signing contract
- Testing connector implementation with real-world data shapes
- Internal dogfooding of new features
- Research and development of scoring algorithms

**NOT For:**
- Production user access
- External demos without disclosure
- Any form of monetization
- Retention beyond TTL

### Enforcement Rules

#### MUST (Hard Requirements)

| Rule | Implementation |
|------|----------------|
| **TTL Enforced** | Default 24h; max 7d with justification. Background job deletes expired records. |
| **No Export** | API must reject export requests for quarantined data. UI hides export buttons. |
| **No Redistribution** | Quarantined data never leaves the user context that triggered ingestion. |
| **No Cross-User Commingling** | Quarantined data isolated per user. No aggregation across users. |
| **Record Labeling** | Every record: `quarantine: true`, `classification: QUARANTINED`, `license_class: UNKNOWN` |
| **Environment Gating** | Quarantine surfaces only enabled in `dev` and `staging` by default. |
| **Feature Flagged** | Quarantine features behind flags: `ENABLE_QUARANTINE_MODE`, `QUARANTINE_SOURCE_<name>` |
| **Audit Log** | All ingestion, access, and deletion of quarantined data logged with user/timestamp. |

#### SHOULD (Strong Recommendations)

| Rule | Implementation |
|------|----------------|
| **Avoid Raw Storage** | Prefer storing only derived/normalized data. If raw needed, encrypt at rest. |
| **Separate Namespace** | Store quarantined data in separate tables/schemas: `quarantine_loads`, etc. |
| **Explicit Acknowledgment** | Require user/developer to acknowledge quarantine status when accessing. |
| **Limited Retention** | Even if TTL is 7d, prefer 24h unless actively testing. |

#### MAY (Optional Allowances)

| Rule | Implementation |
|------|----------------|
| **Aggregated Display** | May show aggregate stats (e.g., "15 loads available") if useful for testing |
| **Admin Override** | Admin role may extend TTL with logged justification |
| **Production Preview** | May show quarantined data in production with explicit `[QUARANTINED]` badge and disabled actions, for internal users only |

### UI Behavior

| Element | Quarantined Behavior |
|---------|---------------------|
| Load card | Display `🔒 QUARANTINED` badge prominently |
| Export button | Hidden or disabled with tooltip: "Export unavailable for restricted data" |
| Share button | Hidden |
| Watchlist add | Disabled with tooltip: "Cannot save restricted loads" |
| Detail panel | Banner: "This load is from a restricted source and may be removed" |
| Search results | Filter toggle: "Include quarantined (internal only)" - default OFF |

### API Behavior

| Endpoint | Quarantined Behavior |
|----------|---------------------|
| `GET /api/loads` | Exclude quarantined by default. Require `?include_quarantine=true` + valid feature flag |
| `GET /api/loads/{id}` | Return 403 if quarantined and flag not enabled |
| `POST /api/exports/*` | Reject with 403: `{"error": "QUARANTINE_EXPORT_BLOCKED", "detail": "Cannot export quarantined data"}` |
| `GET /api/loads/{id}/raw` | Reject for ALL quarantined data |
| Aggregation endpoints | May include quarantined in counts only if explicitly documented |

### Quarantine Promotion

To move data from QUARANTINED → COMPLIANT or RESTRICTED:

1. **Legal/Product Review** — Document rights status in this file
2. **Update Source Config** — Change `default_classification` and `rights_flags`
3. **Re-ingest or Re-tag** — Either re-fetch data or batch-update existing records
4. **Audit Trail** — Log promotion decision with justification and approver

---

## F. Policy Rules

### Ingestion Policies

| Rule | Level | Description |
|------|-------|-------------|
| **Provenance Required** | MUST | Reject ingestion if `source_type`, `source_name`, `acquired_at` are missing |
| **Classification Required** | MUST | Every record must have `classification` set at ingestion time |
| **Rights Flags Required** | MUST | Every record must have `rights_flags` object populated |
| **Default to Quarantine** | MUST | If source not in approved list, set `classification: QUARANTINED` |
| **Block Scraped Sources** | MUST | Reject any record with `source_type: scraped` unless override approved |
| **External ID Preservation** | SHOULD | Store `source_record_id` for deduplication and audit |
| **Raw Payload Encryption** | SHOULD | If storing raw payloads, encrypt at rest with per-source keys |

### Storage Policies

| Rule | Level | Description |
|------|-------|-------------|
| **Quarantine Isolation** | MUST | Quarantined data in separate tables/namespace from production |
| **TTL Enforcement** | MUST | Background job must delete records past `ttl_expires_at` |
| **Soft Delete First** | SHOULD | Mark deleted, then hard delete after 7d grace period |
| **Encryption at Rest** | SHOULD | All data encrypted; quarantine data with separate key |
| **Backup Exclusion** | MAY | Exclude quarantine namespace from long-term backups |

### Access Policies

| Rule | Level | Description |
|------|-------|-------------|
| **User Tenant Isolation** | MUST | User-provided data only visible to that user unless explicitly shared |
| **Rights Flag Check** | MUST | API must check `rights_flags.display` before returning data |
| **Export Check** | MUST | API must check `rights_flags.export` before allowing download |
| **Quarantine Gating** | MUST | Quarantined data requires feature flag + environment check |
| **Aggregate Permission** | SHOULD | Check `rights_flags.display_aggregated` for aggregate views |

### Audit Requirements

| Event | Required Fields | Retention |
|-------|-----------------|-----------|
| Ingestion Decision | source_type, source_name, classification, record_count, decision (accept/reject), reason | 1 year |
| Rights Change | record_id, old_classification, new_classification, changed_by, reason | Indefinite |
| Export Attempt | user_id, record_ids, export_type, allowed (bool), reason_if_denied | 1 year |
| Quarantine Access | user_id, record_id, access_type, timestamp | 90 days |
| TTL Deletion | source_type, record_count, deletion_timestamp | 90 days |
| Takedown Request | source, requester, record_ids, completed_at | Indefinite |

### Takedown & Deletion Workflow

1. **Request Received** — Log request with source, requester, scope
2. **Identify Records** — Query by `source_name` or `source_record_id`
3. **Soft Delete** — Set `deleted_at`, exclude from all queries
4. **Notify Downstream** — Invalidate caches, derived datasets
5. **Hard Delete** — After 24h grace period, permanently remove
6. **Audit Log** — Record completion with record count and timestamp
7. **Confirmation** — Notify requester of completion

### PII Handling

| Data Type | Detection | Handling |
|-----------|-----------|----------|
| Phone Numbers | Regex pattern match | Store only if `rights_flags.store_raw`; mask in logs |
| Email Addresses | Regex pattern match | Store only if `rights_flags.store_raw`; mask in display |
| Driver Names | Named entity recognition (future) | Do not aggregate; isolate to user context |
| MC/DOT Numbers | Regex pattern match | Treated as business identifiers, not PII |
| Location (precise) | Lat/long with high precision | Round to 2 decimals for aggregation |

**Default PII Rule:** If rights status is UNKNOWN or QUARANTINED, mask PII in all displays and never include in exports.

---

## G. Implementation Mapping

### DATA_MODEL.md Changes

Add to `Load` and all ingestible entities:

```python
class Provenance:
    source_type: SourceType          # Enum from Section C
    source_name: str                 # Specific source identifier
    source_record_id: str | None     # External ID for dedup/audit
    acquired_at: datetime            # When FreightLens received (UTC)
    license_class: LicenseClass      # OPEN, LICENSED, USER_PROVIDED, USER_CONNECTED, UNKNOWN
    rights_flags: RightsFlags        # See Section B
    classification: Classification   # COMPLIANT, RESTRICTED, QUARANTINED, BLOCKED
    quarantine: bool                 # Is record in quarantine?
    ttl_expires_at: datetime | None  # Mandatory deletion time
    raw_payload_ref: str | None      # Reference to encrypted raw storage

class RightsFlags:
    store_raw: bool = False
    store_derived: bool = True
    display: bool = True
    display_aggregated: bool = True
    export: bool = False             # Default deny
    redistribute: bool = False       # Default deny
    commingle: bool = False          # Default deny
    train_models: bool = False       # Default deny

class SourceType(str, Enum):
    LICENSED_PARTNER = "licensed_partner"
    PUBLIC_OPEN = "public_open"
    USER_PROVIDED = "user_provided"
    USER_CONNECTED = "user_connected"
    BROKER_PROVIDED = "broker_provided"
    PUBLIC_WEB = "public_web"
    SCRAPED = "scraped"              # Should always → BLOCKED
    INTERNAL_TELEMETRY = "internal_telemetry"

class LicenseClass(str, Enum):
    OPEN = "open"
    LICENSED = "licensed"
    USER_PROVIDED = "user_provided"
    USER_CONNECTED = "user_connected"
    UNKNOWN = "unknown"

class Classification(str, Enum):
    COMPLIANT = "compliant"
    RESTRICTED = "restricted"
    QUARANTINED = "quarantined"
    BLOCKED = "blocked"
```

### INGESTION.md Changes

#### Connector Config Extension

```python
@dataclass
class ConnectorConfig:
    name: str
    enabled: bool = True
    # ... existing fields ...
    
    # NEW: Rights configuration
    source_type: SourceType
    default_license_class: LicenseClass = LicenseClass.UNKNOWN
    default_classification: Classification = Classification.QUARANTINED
    default_rights_flags: RightsFlags = RightsFlags()  # Deny-by-default
    default_ttl_hours: int | None = 24  # For quarantine
    allow_raw_storage: bool = False
```

#### Pipeline Stage: Rights Validation

Insert after Normalizer, before Deduplicator:

```
[Connector] → [Parser] → [Normalizer] → [RightsValidator] → [Deduplicator] → [Store]
```

```python
class RightsValidator:
    """Validates and enriches records with provenance and rights metadata."""
    
    def validate(self, record: Load, config: ConnectorConfig) -> Load | None:
        # 1. Reject BLOCKED sources
        if config.default_classification == Classification.BLOCKED:
            log_rejection(record, reason="blocked_source")
            return None
        
        # 2. Enrich provenance
        record.provenance = Provenance(
            source_type=config.source_type,
            source_name=config.name,
            source_record_id=record.external_id,
            acquired_at=datetime.now(UTC),
            license_class=config.default_license_class,
            rights_flags=config.default_rights_flags,
            classification=config.default_classification,
            quarantine=config.default_classification == Classification.QUARANTINED,
            ttl_expires_at=self._compute_ttl(config),
        )
        
        # 3. Log ingestion decision
        audit_log("ingestion_accepted", record=record.id, source=config.name)
        
        return record
```

#### Deduplication with Rights Awareness

```python
class RightsAwareDeduplicator:
    """Deduplicator that respects commingling restrictions."""
    
    def dedupe(self, record: Load, existing: Load | None) -> Load:
        if existing is None:
            return record
        
        # Never merge across users if commingling disallowed
        if not record.provenance.rights_flags.commingle:
            if record.user_id != existing.user_id:
                return record  # Keep separate
        
        # Never merge quarantined into compliant
        if existing.provenance.classification == Classification.COMPLIANT:
            if record.provenance.classification == Classification.QUARANTINED:
                return record  # Keep quarantine separate
        
        return self._merge(record, existing)
```

### API.md Changes

#### Middleware: Rights Enforcement

```python
@app.middleware("http")
async def rights_enforcement(request: Request, call_next):
    response = await call_next(request)
    
    # Check if response contains loads
    if hasattr(response, 'loads'):
        response.loads = [
            load for load in response.loads
            if check_display_rights(load, request.user)
        ]
    
    return response

def check_display_rights(load: Load, user: User) -> bool:
    """Return True if user can see this load."""
    prov = load.provenance
    
    # Quarantine requires feature flag
    if prov.quarantine:
        if not feature_flag_enabled("ENABLE_QUARANTINE_MODE", user):
            return False
        if settings.environment == "production":
            if not user.is_internal:
                return False
    
    # Check display permission
    if not prov.rights_flags.display:
        return False
    
    # User-provided: only owner sees
    if prov.source_type == SourceType.USER_PROVIDED:
        if load.user_id != user.id:
            return False
    
    return True
```

#### Export Endpoint Protection

```python
@router.get("/api/exports/loads")
async def export_loads(load_ids: list[str], user: User):
    loads = await load_repo.get_many(load_ids)
    
    for load in loads:
        if not load.provenance.rights_flags.export:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "EXPORT_BLOCKED",
                    "message": f"Load {load.id} cannot be exported",
                    "reason": "restricted_source"
                }
            )
        if load.provenance.quarantine:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "QUARANTINE_EXPORT_BLOCKED",
                    "message": "Cannot export quarantined data"
                }
            )
    
    return generate_export(loads)
```

#### Endpoints Requiring Rights Checks

| Endpoint | Check |
|----------|-------|
| `GET /api/loads` | `rights_flags.display`, quarantine gating |
| `GET /api/loads/{id}` | `rights_flags.display`, quarantine gating |
| `GET /api/loads/{id}/raw` | `rights_flags.store_raw` + never for quarantine |
| `GET /api/exports/*` | `rights_flags.export` + never for quarantine |
| `POST /api/loads/share` | `rights_flags.redistribute` |
| `GET /api/lanes/stats` | `rights_flags.display_aggregated` |
| `POST /api/watchlist/add` | Block quarantine adds |

### UI_UX.md Changes

#### Trust Cues & Badges

```
┌─────────────────────────────────────────────────────────────┐
│  LOAD CARD BADGES                                           │
├─────────────────────────────────────────────────────────────┤
│  ✓ Normal load          │ (no badge)                        │
│  🔒 RESTRICTED          │ Yellow badge, muted card          │
│  ⚠️ QUARANTINED         │ Red badge, striped background     │
│  📤 User Import         │ Blue badge (user's own data)      │
└─────────────────────────────────────────────────────────────┘
```

#### Disabled Actions Pattern

```javascript
// Export button for restricted load
<Button 
  disabled={!load.provenance.rights_flags.export}
  title={!load.provenance.rights_flags.export 
    ? "Export unavailable: This load is from a restricted source" 
    : "Export load details"}
>
  Export
</Button>

// Watchlist button for quarantined load
<Button
  disabled={load.provenance.quarantine}
  title={load.provenance.quarantine
    ? "Cannot save: Quarantined loads are temporary"
    : "Add to watchlist"}
>
  Save
</Button>
```

#### "Why Restricted" Explanation Modal

```
┌─────────────────────────────────────────────────────────────┐
│  ℹ️ Why is this load restricted?                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  This load comes from a data source with usage limitations. │
│                                                             │
│  Source: Broker Feed (pending license)                      │
│  Status: RESTRICTED                                         │
│                                                             │
│  What you CAN do:                                           │
│    ✓ View load details                                      │
│    ✓ Contact broker                                         │
│                                                             │
│  What you CANNOT do:                                        │
│    ✗ Export to file                                         │
│    ✗ Share with others                                      │
│    ✗ Add to watchlist                                       │
│                                                             │
│  [Learn More]                              [Dismiss]        │
└─────────────────────────────────────────────────────────────┘
```

### OBSERVABILITY.md Changes

#### New Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `freightlens_ingest_total` | Counter | source_type, classification, decision | Ingestion decisions |
| `freightlens_quarantine_records` | Gauge | source_type | Current quarantine record count |
| `freightlens_quarantine_ttl_expirations` | Counter | source_type | TTL-triggered deletions |
| `freightlens_export_blocked` | Counter | source_type, reason | Blocked export attempts |
| `freightlens_rights_check_failures` | Counter | endpoint, reason | Rights check failures |

#### New Alerts

```yaml
alerts:
  - name: QuarantineVolumeHigh
    expr: freightlens_quarantine_records > 10000
    for: 5m
    severity: warning
    summary: "High volume of quarantined data"
    
  - name: ExportBlockSpike
    expr: rate(freightlens_export_blocked[5m]) > 10
    for: 5m
    severity: warning
    summary: "Spike in blocked export attempts"
    
  - name: UnknownSourceIngestion
    expr: increase(freightlens_ingest_total{classification="quarantined"}[1h]) > 1000
    for: 0m
    severity: info
    summary: "Large ingestion from unclassified source"
```

#### Audit Dashboard Panels

1. **Ingestion by Classification** — Pie chart of COMPLIANT/RESTRICTED/QUARANTINED/BLOCKED
2. **Quarantine TTL Countdown** — Records expiring in next 1h, 6h, 24h
3. **Export Block Events** — Timeline of blocked exports with source
4. **Rights Change Log** — Table of classification changes

---

## H. Example Artifacts

### Example Load Record with Provenance

```json
{
  "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "origin": {"city": "Atlanta", "state": "GA"},
  "destination": {"city": "Chicago", "state": "IL"},
  "equipment": "dry_van",
  "rate_total_usd": 1850.00,
  "distance_miles": 716.5,
  "rpm": 2.58,
  "broker": {
    "name": "Acme Logistics",
    "mc_number": "MC-123456"
  },
  "provenance": {
    "source_type": "licensed_partner",
    "source_name": "partner:acme_feeds",
    "source_record_id": "ACME-2024-87654",
    "acquired_at": "2024-12-19T10:30:00Z",
    "license_class": "licensed",
    "rights_flags": {
      "store_raw": true,
      "store_derived": true,
      "display": true,
      "display_aggregated": true,
      "export": true,
      "redistribute": false,
      "commingle": true,
      "train_models": false
    },
    "classification": "compliant",
    "quarantine": false,
    "ttl_expires_at": null,
    "raw_payload_ref": "s3://freightlens-raw/acme/2024-12-19/87654.json.enc"
  },
  "posted_at": "2024-12-19T10:00:00Z",
  "updated_at": "2024-12-19T10:30:00Z"
}
```

### Example Quarantined Record

```json
{
  "id": "a1b2c3d4-5678-90ab-cdef-1234567890ab",
  "origin": {"city": "Dallas", "state": "TX"},
  "destination": {"city": "Denver", "state": "CO"},
  "equipment": "reefer",
  "rate_total_usd": 2100.00,
  "provenance": {
    "source_type": "user_connected",
    "source_name": "oauth:external_tms",
    "source_record_id": "TMS-99887766",
    "acquired_at": "2024-12-19T14:00:00Z",
    "license_class": "unknown",
    "rights_flags": {
      "store_raw": false,
      "store_derived": true,
      "display": true,
      "display_aggregated": false,
      "export": false,
      "redistribute": false,
      "commingle": false,
      "train_models": false
    },
    "classification": "quarantined",
    "quarantine": true,
    "ttl_expires_at": "2024-12-20T14:00:00Z",
    "raw_payload_ref": null
  }
}
```

### Example Source Configuration

```yaml
# config/sources.yaml - Readable policy config (NOT executable code)

sources:
  - name: partner:acme_feeds
    source_type: licensed_partner
    enabled: true
    default_classification: compliant
    default_license_class: licensed
    rights_flags:
      store_raw: true
      store_derived: true
      display: true
      display_aggregated: true
      export: true
      redistribute: false  # Contract restricts
      commingle: true
      train_models: false  # Not in contract
    retention_days: null  # Per contract: indefinite
    notes: "Contract signed 2024-11-01. Annual review 2025-11-01."

  - name: public:fmcsa_safer
    source_type: public_open
    enabled: true
    default_classification: compliant
    default_license_class: open
    rights_flags:
      store_raw: true
      store_derived: true
      display: true
      display_aggregated: true
      export: true
      redistribute: true
      commingle: true
      train_models: true
    retention_days: null
    notes: "US Government public data. No restrictions."

  - name: user_import:csv
    source_type: user_provided
    enabled: true
    default_classification: compliant
    default_license_class: user_provided
    rights_flags:
      store_raw: true
      store_derived: true
      display: true  # To owner only
      display_aggregated: false
      export: true   # To owner only
      redistribute: false
      commingle: false
      train_models: false
    retention_days: null  # User lifetime
    notes: "User uploads. Isolated per user tenant."

  - name: test:experimental_scrape
    source_type: scraped
    enabled: false  # BLOCKED
    default_classification: blocked
    notes: "DO NOT ENABLE. Requires legal approval."

  - name: staging:unverified_partner
    source_type: licensed_partner
    enabled: true
    environment: [dev, staging]  # Not production
    default_classification: quarantined
    default_license_class: unknown
    rights_flags:
      store_raw: false
      store_derived: true
      display: true
      display_aggregated: true
      export: false
      redistribute: false
      commingle: false
      train_models: false
    retention_days: 1  # 24h TTL
    notes: "Evaluating partner. Contract pending."
```

---

## I. Before We Ingest a New Source (2-Minute Checklist)

Use this checklist before adding ANY new data source:

### Quick Classification

| # | Question | If YES | If NO |
|---|----------|--------|-------|
| 1 | Is this a publicly licensed dataset (CC0, public govt)? | → `COMPLIANT` | Continue |
| 2 | Do we have a signed contract/license with the provider? | → `COMPLIANT` | Continue |
| 3 | Is this data the user is uploading/importing themselves? | → `COMPLIANT` (user-scoped) | Continue |
| 4 | Is the user authorizing access to their own external account? | → `RESTRICTED` | Continue |
| 5 | Did a broker explicitly send us this data for display? | → `RESTRICTED` | Continue |
| 6 | Are we scraping a commercial website/app? | → **BLOCKED** | Continue |
| 7 | None of the above? | → `QUARANTINED` | N/A |

### Minimum Required Actions

- [ ] **Document source** in this file (Section C or as appendix)
- [ ] **Set connector config** with correct `source_type`, `classification`, `rights_flags`
- [ ] **Set TTL** if QUARANTINED (default 24h)
- [ ] **Add to source registry** (`config/sources.yaml` or equivalent)
- [ ] **Test ingestion** in dev environment
- [ ] **Verify isolation** — quarantine data separate from production
- [ ] **Log decision** in audit trail

### When to Escalate

Escalate to Legal/Product review if:
- Source involves scraping of any kind
- Contract terms are ambiguous about storage/display/redistribution
- Source contains significant PII (driver names, personal phones)
- We want to use data for ML model training
- We want to share data across users or externally

---

## J. Open Questions / TODO

| ID | Question | Owner | Priority | Status |
|----|----------|-------|----------|--------|
| Q1 | What specific partner APIs will we integrate? Need contracts reviewed. | Product | P0 | OPEN |
| Q2 | Do DAT/Truckstop have data licensing programs? What are terms? | Product | P0 | OPEN |
| Q3 | Legal review of user ToS language for data ownership/warranty | Legal | P1 | OPEN |
| Q4 | Privacy policy update to reflect data sourcing categories | Legal | P1 | OPEN |
| Q5 | Is FMCSA SAFER data truly unrestricted for commercial use? | Eng | P2 | NEEDS VERIFY |
| Q6 | ML training: need separate user opt-in flow for training data usage? | Product | P2 | OPEN |
| Q7 | What is our position on using publicly posted forum/social content? | Product/Legal | P2 | OPEN |
| Q8 | PII detection: implement automated masking or defer? | Eng | P2 | OPEN |
| Q9 | Encryption key management for raw payload storage | Eng | P1 | OPEN |
| Q10 | Multi-tenant isolation: shared DB with row-level security or separate schemas? | Eng | P1 | OPEN |

---

## Patch Plan: Adopting This Document

### Required Changes (Priority Order)

| # | File | Change | Effort | Dependency |
|---|------|--------|--------|------------|
| 1 | `app/models.py` | Add `Provenance`, `RightsFlags`, `SourceType`, `LicenseClass`, `Classification` classes | S | None |
| 2 | `docs/DATA_MODEL.md` | Document new provenance fields and enums | S | #1 |
| 3 | `app/services/repositories.py` | Add `provenance` field handling to load repository | M | #1 |
| 4 | `docs/INGESTION.md` | Add Rights Validator stage, update connector config schema | M | #1 |
| 5 | `app/data.py` | Implement TTL expiration background job | M | #1, #3 |
| 6 | `config/sources.yaml` (new) | Create source registry with default configurations | S | #1 |
| 7 | `app/main.py` | Add rights enforcement middleware, export blocking | M | #1, #3 |
| 8 | `docs/API.md` | Document rights-related query params and error responses | S | #7 |
| 9 | `static/app.js` + `static/index.html` | Add quarantine badges, disabled action states | M | #7 |
| 10 | `docs/UI_UX.md` | Document trust cues and restriction patterns | S | #9 |
| 11 | `app/logging.py` | Add audit log events for rights decisions | S | #7 |
| 12 | `docs/OBSERVABILITY.md` | Add metrics, alerts, dashboard specs | S | #11 |

### Quick Wins (Can Ship Immediately)

1. **Add this document** to `/docs/` ✓
2. **Update README.md** to reference this policy
3. **Add `classification` field stub** to models (default: `COMPLIANT`)
4. **Add `--quarantine` flag** to CLI import commands

### Future Enhancements (Post-v1)

- Automated PII detection and masking pipeline
- Self-service source registration for partners
- User-facing data provenance transparency ("Where does this data come from?")
- Differential privacy for aggregate statistics
- Formal contract document storage and linking

---

## Document Changelog

| Date | Version | Author | Changes |
|------|---------|--------|---------|
| 2024-12-19 | 1.0 | Engineering | Initial version |

---

**Disclaimer:** This document provides engineering guidance and policy, not legal advice. Consult legal counsel before finalizing data agreements or when rights status is unclear. Source classifications marked "UNKNOWN / NEEDS REVIEW" require human verification before production use.
