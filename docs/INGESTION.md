# Data Ingestion

## Connectors, Normalization, Provenance & Deduplication

**Version:** 1.0  
**Last Updated:** 2024-12-19

---

## Overview

FreightLens's ingestion layer transforms raw external data into normalized, deduplicated records with full provenance tracking. The system is designed to be **vendor-agnostic**, supporting multiple data sources through a pluggable connector architecture.

### Design Goals

| Goal | Description |
|------|-------------|
| **Pluggable** | Add new data sources without modifying core code |
| **Traceable** | Every record knows where it came from and when |
| **Resilient** | Graceful handling of malformed, duplicate, or stale data |
| **Auditable** | Full history of data changes for compliance |
| **Performant** | Process 10,000+ records/minute with minimal latency |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           INGESTION PIPELINE                                     │
│                                                                                  │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐         │
│  │  External   │   │  Connector  │   │   Parser    │   │ Normalizer  │         │
│  │   Source    │──►│   Adapter   │──►│             │──►│             │         │
│  │  (API/File) │   │             │   │             │   │             │         │
│  └─────────────┘   └─────────────┘   └─────────────┘   └──────┬──────┘         │
│                                                                │                │
│                                                                ▼                │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐         │
│  │   Store     │◄──│  Provenance │◄──│   Dedupe    │◄──│  Validator  │         │
│  │             │   │   Tracker   │   │   Engine    │   │             │         │
│  └─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘         │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Pipeline Stages

| Stage | Input | Output | Responsibility |
|-------|-------|--------|----------------|
| **Connector** | External source | Raw bytes/JSON | Authentication, fetching, error handling |
| **Parser** | Raw data | Source-specific objects | Format detection, deserialization |
| **Normalizer** | Source objects | Canonical models | Field mapping, type conversion |
| **Validator** | Canonical models | Valid records | Schema validation, business rules |
| **Deduplicator** | Valid records | Unique records | Duplicate detection, merge strategy |
| **Provenance** | Unique records | Tracked records | Lineage metadata, timestamps |
| **Store** | Tracked records | Persisted data | Write to storage layer |

---

## Connector Framework

### Base Connector Interface

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import AsyncIterator, Generic, TypeVar

T = TypeVar("T")

@dataclass
class ConnectorConfig:
    """Base configuration for all connectors."""
    name: str                          # Unique connector identifier
    enabled: bool = True               # Toggle without removing
    poll_interval_seconds: int = 300   # For polling connectors
    timeout_seconds: int = 30          # Request timeout
    retry_attempts: int = 3            # Retries on failure
    retry_backoff_seconds: int = 5     # Backoff between retries


@dataclass
class FetchResult(Generic[T]):
    """Result of a connector fetch operation."""
    records: list[T]                   # Fetched records
    source: str                        # Source identifier
    fetched_at: datetime               # When fetch completed
    cursor: str | None = None          # Pagination cursor for next fetch
    has_more: bool = False             # More data available
    errors: list[str] | None = None    # Non-fatal errors encountered


class BaseConnector(ABC, Generic[T]):
    """
    Abstract base class for all data connectors.
    
    Subclasses implement source-specific fetching logic while
    the framework handles retries, logging, and metrics.
    """
    
    def __init__(self, config: ConnectorConfig):
        self.config = config
        self._last_fetch: datetime | None = None
        self._fetch_count: int = 0
        self._error_count: int = 0
    
    @property
    @abstractmethod
    def source_type(self) -> str:
        """Return the source type identifier (e.g., 'api', 'file', 'webhook')."""
        ...
    
    @property
    @abstractmethod
    def dataset_category(self) -> str:
        """Return the dataset category (e.g., 'loads', 'rates', 'brokers')."""
        ...
    
    @abstractmethod
    async def fetch(self, cursor: str | None = None) -> FetchResult[T]:
        """
        Fetch records from the external source.
        
        Args:
            cursor: Pagination cursor from previous fetch
            
        Returns:
            FetchResult containing records and metadata
        """
        ...
    
    @abstractmethod
    async def healthcheck(self) -> bool:
        """
        Check if the connector can reach its data source.
        
        Returns:
            True if healthy, False otherwise
        """
        ...
    
    async def fetch_all(self) -> AsyncIterator[FetchResult[T]]:
        """
        Fetch all available records, handling pagination.
        
        Yields:
            FetchResult for each page of data
        """
        cursor = None
        while True:
            result = await self.fetch(cursor)
            yield result
            if not result.has_more:
                break
            cursor = result.cursor
```

---

### Connector Implementations

#### JSON File Connector

```python
import json
from pathlib import Path

@dataclass
class JsonFileConfig(ConnectorConfig):
    """Configuration for JSON file connector."""
    file_path: Path
    watch_for_changes: bool = False


class JsonFileConnector(BaseConnector[dict]):
    """
    Connector for local JSON files.
    
    Supports single files and directories of JSON files.
    """
    
    def __init__(self, config: JsonFileConfig):
        super().__init__(config)
        self.file_config = config
    
    @property
    def source_type(self) -> str:
        return "file"
    
    @property
    def dataset_category(self) -> str:
        return "loads"  # Override per instance
    
    async def fetch(self, cursor: str | None = None) -> FetchResult[dict]:
        path = self.file_config.file_path
        
        if path.is_file():
            records = self._parse_file(path)
        elif path.is_dir():
            records = []
            for file in path.glob("*.json"):
                records.extend(self._parse_file(file))
        else:
            raise FileNotFoundError(f"Path not found: {path}")
        
        return FetchResult(
            records=records,
            source=f"file:{path}",
            fetched_at=datetime.now(timezone.utc),
            has_more=False,
        )
    
    def _parse_file(self, path: Path) -> list[dict]:
        with open(path, "r") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        return [data]
    
    async def healthcheck(self) -> bool:
        return self.file_config.file_path.exists()
```

#### CSV File Connector

```python
import csv
from io import StringIO

@dataclass
class CsvFileConfig(ConnectorConfig):
    """Configuration for CSV file connector."""
    file_path: Path
    delimiter: str = ","
    has_header: bool = True
    encoding: str = "utf-8"


class CsvFileConnector(BaseConnector[dict]):
    """
    Connector for CSV files.
    
    Converts rows to dictionaries using header row as keys.
    """
    
    @property
    def source_type(self) -> str:
        return "file"
    
    @property
    def dataset_category(self) -> str:
        return "loads"
    
    async def fetch(self, cursor: str | None = None) -> FetchResult[dict]:
        path = self.csv_config.file_path
        
        with open(path, "r", encoding=self.csv_config.encoding) as f:
            if self.csv_config.has_header:
                reader = csv.DictReader(f, delimiter=self.csv_config.delimiter)
                records = list(reader)
            else:
                reader = csv.reader(f, delimiter=self.csv_config.delimiter)
                records = [{"col_" + str(i): v for i, v in enumerate(row)} for row in reader]
        
        return FetchResult(
            records=records,
            source=f"csv:{path}",
            fetched_at=datetime.now(timezone.utc),
            has_more=False,
        )
    
    async def healthcheck(self) -> bool:
        return self.csv_config.file_path.exists()
```

#### API Connector (Template)

```python
import httpx
from typing import Any

@dataclass
class ApiConnectorConfig(ConnectorConfig):
    """Configuration for HTTP API connectors."""
    base_url: str
    api_key: str | None = None
    api_key_header: str = "X-API-Key"
    auth_type: str = "api_key"  # "api_key", "bearer", "basic", "oauth2"
    rate_limit_rps: float = 10.0
    page_size: int = 100


class ApiConnector(BaseConnector[dict]):
    """
    Generic HTTP API connector.
    
    Subclass to implement source-specific request/response handling.
    """
    
    def __init__(self, config: ApiConnectorConfig):
        super().__init__(config)
        self.api_config = config
        self._client: httpx.AsyncClient | None = None
    
    @property
    def source_type(self) -> str:
        return "api"
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {}
            if self.api_config.api_key:
                if self.api_config.auth_type == "api_key":
                    headers[self.api_config.api_key_header] = self.api_config.api_key
                elif self.api_config.auth_type == "bearer":
                    headers["Authorization"] = f"Bearer {self.api_config.api_key}"
            
            self._client = httpx.AsyncClient(
                base_url=self.api_config.base_url,
                headers=headers,
                timeout=self.api_config.timeout_seconds,
            )
        return self._client
    
    @abstractmethod
    def _build_request(self, cursor: str | None) -> tuple[str, dict[str, Any]]:
        """
        Build the request path and parameters.
        
        Returns:
            Tuple of (path, query_params)
        """
        ...
    
    @abstractmethod
    def _parse_response(self, data: dict) -> tuple[list[dict], str | None, bool]:
        """
        Parse the API response.
        
        Returns:
            Tuple of (records, next_cursor, has_more)
        """
        ...
    
    async def fetch(self, cursor: str | None = None) -> FetchResult[dict]:
        client = await self._get_client()
        path, params = self._build_request(cursor)
        
        response = await client.get(path, params=params)
        response.raise_for_status()
        data = response.json()
        
        records, next_cursor, has_more = self._parse_response(data)
        
        return FetchResult(
            records=records,
            source=f"api:{self.api_config.base_url}",
            fetched_at=datetime.now(timezone.utc),
            cursor=next_cursor,
            has_more=has_more,
        )
    
    async def healthcheck(self) -> bool:
        try:
            client = await self._get_client()
            response = await client.get("/health")  # Adjust per API
            return response.status_code < 500
        except Exception:
            return False
```

---

## Dataset Category Connectors

### A) Load Postings Connector

```python
@dataclass
class LoadPostingsConfig(ApiConnectorConfig):
    """Configuration for load posting API connector."""
    include_expired: bool = False
    equipment_filter: list[str] | None = None
    min_rate: float | None = None


class LoadPostingsConnector(ApiConnector):
    """
    Connector for load posting data sources.
    
    Normalizes different load APIs to canonical Load schema.
    """
    
    @property
    def dataset_category(self) -> str:
        return "load_postings"
    
    def _build_request(self, cursor: str | None) -> tuple[str, dict]:
        params = {"page_size": self.api_config.page_size}
        if cursor:
            params["cursor"] = cursor
        if self.load_config.equipment_filter:
            params["equipment"] = ",".join(self.load_config.equipment_filter)
        if self.load_config.min_rate:
            params["min_rate"] = self.load_config.min_rate
        return "/loads", params
    
    def _parse_response(self, data: dict) -> tuple[list[dict], str | None, bool]:
        records = data.get("loads", [])
        cursor = data.get("next_cursor")
        has_more = cursor is not None
        return records, cursor, has_more
```

### B) Rate Intelligence Connector

```python
@dataclass
class RateIntelConfig(ApiConnectorConfig):
    """Configuration for rate intelligence connector."""
    lookback_days: int = 30
    include_contract_rates: bool = False


class RateIntelConnector(ApiConnector):
    """
    Connector for lane rate intelligence data.
    """
    
    @property
    def dataset_category(self) -> str:
        return "rate_intelligence"
    
    # ... implementation
```

### C–I) Additional Category Connectors

| Category | Connector Class | Primary Source Types |
|----------|----------------|---------------------|
| **C) Distance/Route** | `RoutingConnector` | API (mapping services) |
| **D) Fuel Prices** | `FuelPriceConnector` | API (EIA, retail APIs) |
| **E) Compliance** | `ComplianceConnector` | API (FMCSA SAFER) |
| **F) Broker Risk** | `BrokerRiskConnector` | API, File (aggregated data) |
| **G) Facility Intel** | `FacilityConnector` | API, Crowdsourced |
| **H) Market Demand** | `MarketDemandConnector` | API (proprietary indices) |
| **I) Events/News** | `NewsConnector` | RSS, Webhook |

---

## Normalization

### Purpose

Transform source-specific schemas into canonical FreightLens models, ensuring:
- Consistent field names across all sources
- Proper data types and validation
- Unit conversions (miles ↔ km, lbs ↔ kg)
- Timezone normalization to UTC

### Normalizer Interface

```python
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

SourceT = TypeVar("SourceT")
TargetT = TypeVar("TargetT")


class BaseNormalizer(ABC, Generic[SourceT, TargetT]):
    """
    Abstract normalizer that transforms source records to canonical models.
    """
    
    @property
    @abstractmethod
    def source_name(self) -> str:
        """Identifier for the source being normalized."""
        ...
    
    @abstractmethod
    def normalize(self, record: SourceT) -> TargetT | None:
        """
        Transform a source record to canonical form.
        
        Returns:
            Normalized record, or None if record should be skipped
        """
        ...
    
    def normalize_batch(self, records: list[SourceT]) -> list[TargetT]:
        """
        Normalize a batch of records, filtering out failures.
        """
        results = []
        for record in records:
            try:
                normalized = self.normalize(record)
                if normalized is not None:
                    results.append(normalized)
            except Exception as e:
                self._log_normalization_error(record, e)
        return results
    
    def _log_normalization_error(self, record: SourceT, error: Exception) -> None:
        """Log normalization failures for debugging."""
        logger.warning(
            "Normalization failed",
            source=self.source_name,
            error=str(error),
            record_preview=str(record)[:200],
        )
```

### Load Normalizer Example

```python
from app.models import Load, Location, Broker

class LoadNormalizer(BaseNormalizer[dict, Load]):
    """
    Normalizes load records from various sources to canonical Load model.
    """
    
    # Field mappings from common source schemas
    FIELD_MAPS = {
        "source_a": {
            "origin_city": "pickup_city",
            "origin_state": "pickup_state",
            "dest_city": "delivery_city",
            "dest_state": "delivery_state",
            "rate": "total_rate",
            "mileage": "distance",
        },
        "source_b": {
            "origin_city": "orig.city",
            "origin_state": "orig.state",
            "dest_city": "dest.city",
            "dest_state": "dest.state",
            "rate": "linehaul_rate",
            "mileage": "miles",
        },
    }
    
    def __init__(self, source_name: str):
        self._source_name = source_name
        self._field_map = self.FIELD_MAPS.get(source_name, {})
    
    @property
    def source_name(self) -> str:
        return self._source_name
    
    def normalize(self, record: dict) -> Load | None:
        """
        Transform a source load record to canonical Load.
        """
        # Extract with field mapping
        origin_city = self._get_field(record, "origin_city")
        origin_state = self._get_field(record, "origin_state")
        dest_city = self._get_field(record, "dest_city")
        dest_state = self._get_field(record, "dest_state")
        
        if not all([origin_city, origin_state, dest_city, dest_state]):
            return None  # Skip incomplete records
        
        # Normalize rate (handle different formats)
        rate = self._normalize_rate(record)
        distance = self._normalize_distance(record)
        
        # Normalize dates to UTC
        pickup_start = self._normalize_datetime(record, "pickup_start", "pickup_date")
        pickup_end = self._normalize_datetime(record, "pickup_end", "pickup_date_end")
        
        # Normalize equipment type
        equipment = self._normalize_equipment(record)
        
        return Load(
            id=str(uuid.uuid4()),
            external_id=record.get("id") or record.get("load_id"),
            origin=Location(city=origin_city, state=origin_state),
            destination=Location(city=dest_city, state=dest_state),
            pickup_start=pickup_start,
            pickup_end=pickup_end or pickup_start + timedelta(hours=4),
            delivery_start=self._normalize_datetime(record, "delivery_start", "delivery_date"),
            delivery_end=self._normalize_datetime(record, "delivery_end", "delivery_date_end"),
            equipment=equipment,
            weight_lbs=self._normalize_weight(record),
            hazmat=self._normalize_bool(record, "hazmat"),
            distance_miles=distance,
            deadhead_miles=0.0,  # Computed later based on user location
            rate_total_usd=rate,
            rpm=round(rate / max(distance, 1), 3),
            broker=self._normalize_broker(record),
            detention=self._normalize_bool(record, "detention", "detention_pay"),
            multi_stop=self._normalize_bool(record, "multi_stop", "stops") or self._get_field(record, "stops", 1) > 1,
            lane_history=False,  # Enriched later
            commodity=record.get("commodity", "General Freight"),
            posted_at=self._normalize_datetime(record, "posted_at", "post_date") or datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    
    def _get_field(self, record: dict, canonical_name: str, default=None):
        """Get field using source-specific mapping."""
        source_name = self._field_map.get(canonical_name, canonical_name)
        
        # Handle nested paths (e.g., "orig.city")
        if "." in source_name:
            parts = source_name.split(".")
            value = record
            for part in parts:
                value = value.get(part, {}) if isinstance(value, dict) else default
            return value if value != {} else default
        
        return record.get(source_name, default)
    
    def _normalize_rate(self, record: dict) -> float:
        """Normalize rate to USD float."""
        rate = self._get_field(record, "rate", 0)
        
        # Handle string formats like "$1,500.00"
        if isinstance(rate, str):
            rate = rate.replace("$", "").replace(",", "")
            rate = float(rate)
        
        return float(rate)
    
    def _normalize_distance(self, record: dict) -> float:
        """Normalize distance to miles."""
        distance = self._get_field(record, "mileage", 0)
        
        # Check if kilometers (some APIs use km)
        if record.get("distance_unit") == "km":
            distance = distance * 0.621371
        
        return float(distance)
    
    def _normalize_weight(self, record: dict) -> int:
        """Normalize weight to pounds."""
        weight = record.get("weight") or record.get("weight_lbs") or record.get("weight_kg", 0)
        
        # Convert kg to lbs if needed
        if "weight_kg" in record and "weight_lbs" not in record:
            weight = weight * 2.20462
        
        return int(weight)
    
    def _normalize_equipment(self, record: dict) -> str:
        """Normalize equipment type to canonical values."""
        raw = record.get("equipment") or record.get("equipment_type") or record.get("trailer_type")
        
        EQUIPMENT_MAP = {
            # Dry Van variants
            "V": "Dry Van", "VAN": "Dry Van", "DRY VAN": "Dry Van", "DV": "Dry Van",
            "53V": "Dry Van", "48V": "Dry Van",
            # Reefer variants
            "R": "Reefer", "REEFER": "Reefer", "REFRIGERATED": "Reefer", "RF": "Reefer",
            # Flatbed variants
            "F": "Flatbed", "FLATBED": "Flatbed", "FB": "Flatbed", "FLAT": "Flatbed",
            # Step deck
            "SD": "Step Deck", "STEP DECK": "Step Deck", "STEPDECK": "Step Deck",
            # Power only
            "PO": "Power Only", "POWER ONLY": "Power Only", "POWERONLY": "Power Only",
        }
        
        if raw:
            normalized = EQUIPMENT_MAP.get(raw.upper().strip(), raw)
            return normalized
        return "Dry Van"  # Default
    
    def _normalize_datetime(self, record: dict, *field_names) -> datetime | None:
        """Normalize datetime fields to UTC."""
        for name in field_names:
            value = record.get(name)
            if value:
                if isinstance(value, datetime):
                    dt = value
                elif isinstance(value, str):
                    # Try common formats
                    for fmt in [
                        "%Y-%m-%dT%H:%M:%SZ",
                        "%Y-%m-%dT%H:%M:%S",
                        "%Y-%m-%d %H:%M:%S",
                        "%Y-%m-%d",
                        "%m/%d/%Y",
                    ]:
                        try:
                            dt = datetime.strptime(value, fmt)
                            break
                        except ValueError:
                            continue
                    else:
                        continue
                else:
                    continue
                
                # Ensure UTC
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
        return None
    
    def _normalize_bool(self, record: dict, *field_names) -> bool:
        """Normalize boolean fields."""
        for name in field_names:
            value = record.get(name)
            if value is not None:
                if isinstance(value, bool):
                    return value
                if isinstance(value, str):
                    return value.lower() in ("true", "yes", "1", "y")
                if isinstance(value, (int, float)):
                    return value > 0
        return False
    
    def _normalize_broker(self, record: dict) -> Broker:
        """Normalize broker information."""
        return Broker(
            name=record.get("broker_name") or record.get("broker") or "Unknown",
            rating=float(record.get("broker_rating") or record.get("rating") or 3.0),
        )
```

---

## Validation

### Validation Rules

```python
from pydantic import ValidationError
from typing import TypeVar, Generic

T = TypeVar("T")

@dataclass
class ValidationResult(Generic[T]):
    """Result of validation with errors."""
    valid_records: list[T]
    invalid_records: list[tuple[dict, list[str]]]  # (record, errors)
    total_input: int
    valid_count: int
    invalid_count: int


class RecordValidator(Generic[T]):
    """
    Validates normalized records against business rules.
    """
    
    def validate_batch(self, records: list[T]) -> ValidationResult[T]:
        valid = []
        invalid = []
        
        for record in records:
            errors = self._validate_record(record)
            if errors:
                invalid.append((record, errors))
            else:
                valid.append(record)
        
        return ValidationResult(
            valid_records=valid,
            invalid_records=invalid,
            total_input=len(records),
            valid_count=len(valid),
            invalid_count=len(invalid),
        )
    
    def _validate_record(self, record: T) -> list[str]:
        """Return list of validation errors, empty if valid."""
        errors = []
        
        # Pydantic validation happens during normalization
        # Additional business rules:
        
        if hasattr(record, "rate_total_usd"):
            if record.rate_total_usd <= 0:
                errors.append("Rate must be positive")
            if record.rate_total_usd > 50000:
                errors.append("Rate exceeds maximum ($50,000)")
        
        if hasattr(record, "distance_miles"):
            if record.distance_miles <= 0:
                errors.append("Distance must be positive")
            if record.distance_miles > 5000:
                errors.append("Distance exceeds maximum (5,000 miles)")
        
        if hasattr(record, "weight_lbs"):
            if record.weight_lbs < 0:
                errors.append("Weight cannot be negative")
            if record.weight_lbs > 80000:
                errors.append("Weight exceeds legal limit (80,000 lbs)")
        
        if hasattr(record, "pickup_start") and hasattr(record, "delivery_start"):
            if record.delivery_start < record.pickup_start:
                errors.append("Delivery cannot be before pickup")
        
        if hasattr(record, "rpm"):
            if record.rpm > 20:
                errors.append("Rate per mile exceeds reasonable maximum ($20/mi)")
        
        return errors
```

---

## Deduplication

### Strategy

FreightLens uses a **composite key** strategy for deduplication:

1. **Primary Key**: `external_id` from source (if available)
2. **Composite Key**: Hash of identifying fields when no external ID

### Dedup Key Generation

```python
import hashlib
from typing import Any

def generate_dedup_key(record: Load) -> str:
    """
    Generate a deduplication key for a load record.
    
    The key is based on immutable identifying characteristics
    that should be unique across sources.
    """
    # If we have an external ID from a known source, use it
    if record.external_id:
        return f"ext:{record.source}:{record.external_id}"
    
    # Otherwise, create composite key from identifying fields
    components = [
        record.origin.city,
        record.origin.state,
        record.destination.city,
        record.destination.state,
        record.pickup_start.strftime("%Y-%m-%d"),
        record.equipment,
        str(int(record.rate_total_usd)),
        str(int(record.distance_miles)),
        record.broker.name,
    ]
    
    composite = "|".join(components)
    hash_value = hashlib.sha256(composite.encode()).hexdigest()[:16]
    
    return f"comp:{hash_value}"
```

### Deduplication Engine

```python
from dataclasses import dataclass
from typing import Callable

@dataclass
class DedupeResult:
    """Result of deduplication operation."""
    unique_records: list[Load]
    duplicates_found: int
    merge_operations: int


class DeduplicationEngine:
    """
    Handles duplicate detection and merging.
    """
    
    def __init__(
        self,
        key_generator: Callable[[Load], str] = generate_dedup_key,
        merge_strategy: str = "prefer_newest",
    ):
        self.key_generator = key_generator
        self.merge_strategy = merge_strategy
        self._seen_keys: dict[str, Load] = {}
    
    def process_batch(self, records: list[Load]) -> DedupeResult:
        """
        Process a batch of records, detecting and handling duplicates.
        """
        unique = []
        duplicates = 0
        merges = 0
        
        for record in records:
            key = self.key_generator(record)
            
            if key in self._seen_keys:
                duplicates += 1
                existing = self._seen_keys[key]
                merged = self._merge(existing, record)
                if merged != existing:
                    self._seen_keys[key] = merged
                    merges += 1
            else:
                self._seen_keys[key] = record
                unique.append(record)
        
        return DedupeResult(
            unique_records=unique,
            duplicates_found=duplicates,
            merge_operations=merges,
        )
    
    def _merge(self, existing: Load, new: Load) -> Load:
        """
        Merge duplicate records based on strategy.
        """
        if self.merge_strategy == "prefer_newest":
            # Keep record with most recent update
            if new.updated_at > existing.updated_at:
                return new
            return existing
        
        elif self.merge_strategy == "prefer_complete":
            # Keep record with more non-null fields
            existing_score = self._completeness_score(existing)
            new_score = self._completeness_score(new)
            return new if new_score > existing_score else existing
        
        elif self.merge_strategy == "merge_fields":
            # Combine best of both (more complex)
            return self._merge_fields(existing, new)
        
        return existing
    
    def _completeness_score(self, record: Load) -> int:
        """Count non-null optional fields."""
        score = 0
        if record.external_id:
            score += 1
        if record.commodity != "General Freight":
            score += 1
        if record.broker.rating > 0:
            score += 1
        # ... more fields
        return score
    
    def _merge_fields(self, existing: Load, new: Load) -> Load:
        """
        Merge fields from both records, preferring non-default values.
        """
        # Create copy of existing
        merged_data = existing.model_dump()
        new_data = new.model_dump()
        
        # Update with new non-default values
        for key, new_value in new_data.items():
            if new_value is not None and new_value != merged_data.get(key):
                # Prefer newer timestamp
                merged_data[key] = new_value
        
        # Always use latest update time
        merged_data["updated_at"] = max(existing.updated_at, new.updated_at)
        
        return Load.model_validate(merged_data)
    
    def reset(self) -> None:
        """Clear seen keys for fresh deduplication run."""
        self._seen_keys.clear()
```

---

## Provenance Tracking

### Provenance Model

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Any

@dataclass
class Provenance:
    """
    Tracks the origin and history of a data record.
    """
    # Source identification
    source_system: str           # "dat_api", "truckstop_file", "manual_import"
    source_record_id: str | None # Original ID from source
    connector_name: str          # Connector that fetched this data
    
    # Timestamps
    source_timestamp: datetime | None  # When source said it was updated
    ingested_at: datetime              # When we received it
    normalized_at: datetime            # When we normalized it
    
    # Quality signals
    confidence_score: float      # 0.0 - 1.0 based on data quality
    freshness_hours: float       # Hours since source update
    completeness_pct: float      # % of optional fields populated
    
    # Lineage
    dedup_key: str               # Key used for deduplication
    version: int                 # Increment on updates
    previous_version_id: str | None  # Link to previous version
    
    # Debugging
    raw_hash: str                # SHA256 of raw input for verification
    transform_log: list[str]    # List of transformations applied


def create_provenance(
    record: Any,
    source_system: str,
    connector_name: str,
    raw_data: bytes,
) -> Provenance:
    """
    Create provenance metadata for a record.
    """
    now = datetime.now(timezone.utc)
    
    # Calculate freshness
    source_ts = getattr(record, "updated_at", None) or getattr(record, "posted_at", None)
    if source_ts:
        freshness = (now - source_ts).total_seconds() / 3600.0
    else:
        freshness = 0.0
    
    # Calculate completeness
    completeness = calculate_completeness(record)
    
    # Calculate confidence
    confidence = calculate_confidence(freshness, completeness, source_system)
    
    return Provenance(
        source_system=source_system,
        source_record_id=getattr(record, "external_id", None),
        connector_name=connector_name,
        source_timestamp=source_ts,
        ingested_at=now,
        normalized_at=now,
        confidence_score=confidence,
        freshness_hours=freshness,
        completeness_pct=completeness,
        dedup_key=generate_dedup_key(record),
        version=1,
        previous_version_id=None,
        raw_hash=hashlib.sha256(raw_data).hexdigest(),
        transform_log=["normalized", "validated"],
    )


def calculate_completeness(record: Any) -> float:
    """
    Calculate what percentage of optional fields are populated.
    """
    optional_fields = [
        "external_id", "commodity", "weight_lbs", "hazmat",
        "detention", "multi_stop", "broker.rating",
    ]
    
    populated = 0
    for field in optional_fields:
        value = record
        for part in field.split("."):
            value = getattr(value, part, None)
            if value is None:
                break
        if value is not None:
            populated += 1
    
    return populated / len(optional_fields) * 100


def calculate_confidence(
    freshness_hours: float,
    completeness_pct: float,
    source_system: str,
) -> float:
    """
    Calculate overall confidence score for a record.
    
    Factors:
    - Freshness (newer = higher confidence)
    - Completeness (more fields = higher confidence)
    - Source reliability (known sources = higher confidence)
    """
    # Freshness score (exponential decay)
    if freshness_hours <= 1:
        freshness_score = 1.0
    elif freshness_hours <= 6:
        freshness_score = 0.9
    elif freshness_hours <= 24:
        freshness_score = 0.7
    elif freshness_hours <= 72:
        freshness_score = 0.5
    else:
        freshness_score = max(0.2, 1.0 - freshness_hours / 168)
    
    # Completeness score (linear)
    completeness_score = completeness_pct / 100
    
    # Source reliability (configurable)
    SOURCE_RELIABILITY = {
        "synthetic": 0.5,
        "manual_import": 0.7,
        "api_tier1": 1.0,
        "api_tier2": 0.85,
    }
    source_score = SOURCE_RELIABILITY.get(source_system, 0.6)
    
    # Weighted average
    confidence = (
        freshness_score * 0.4 +
        completeness_score * 0.3 +
        source_score * 0.3
    )
    
    return round(confidence, 3)
```

---

## Pipeline Orchestration

### Complete Pipeline

```python
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")

@dataclass
class PipelineResult:
    """Result of a complete ingestion pipeline run."""
    source: str
    started_at: datetime
    completed_at: datetime
    records_fetched: int
    records_normalized: int
    records_validated: int
    records_deduplicated: int
    records_stored: int
    errors: list[str]
    duration_seconds: float


class IngestionPipeline:
    """
    Orchestrates the complete ingestion pipeline.
    """
    
    def __init__(
        self,
        connector: BaseConnector,
        normalizer: BaseNormalizer,
        validator: RecordValidator,
        deduplicator: DeduplicationEngine,
        store: DataStore,
    ):
        self.connector = connector
        self.normalizer = normalizer
        self.validator = validator
        self.deduplicator = deduplicator
        self.store = store
    
    async def run(self) -> PipelineResult:
        """
        Execute the complete ingestion pipeline.
        """
        started_at = datetime.now(timezone.utc)
        errors = []
        
        records_fetched = 0
        records_normalized = 0
        records_validated = 0
        records_deduplicated = 0
        records_stored = 0
        
        try:
            # 1. Fetch from source
            async for fetch_result in self.connector.fetch_all():
                records_fetched += len(fetch_result.records)
                
                if fetch_result.errors:
                    errors.extend(fetch_result.errors)
                
                # 2. Normalize
                normalized = self.normalizer.normalize_batch(fetch_result.records)
                records_normalized += len(normalized)
                
                # 3. Validate
                validation_result = self.validator.validate_batch(normalized)
                records_validated += validation_result.valid_count
                
                for record, errs in validation_result.invalid_records:
                    errors.append(f"Validation failed: {errs}")
                
                # 4. Deduplicate
                dedup_result = self.deduplicator.process_batch(validation_result.valid_records)
                records_deduplicated += len(dedup_result.unique_records)
                
                # 5. Add provenance and store
                for record in dedup_result.unique_records:
                    record.provenance = create_provenance(
                        record=record,
                        source_system=self.connector.config.name,
                        connector_name=self.connector.__class__.__name__,
                        raw_data=b"",  # Would be actual raw data
                    )
                    await self.store.upsert(record)
                    records_stored += 1
        
        except Exception as e:
            errors.append(f"Pipeline error: {str(e)}")
            logger.exception("Ingestion pipeline failed")
        
        completed_at = datetime.now(timezone.utc)
        
        return PipelineResult(
            source=self.connector.config.name,
            started_at=started_at,
            completed_at=completed_at,
            records_fetched=records_fetched,
            records_normalized=records_normalized,
            records_validated=records_validated,
            records_deduplicated=records_deduplicated,
            records_stored=records_stored,
            errors=errors,
            duration_seconds=(completed_at - started_at).total_seconds(),
        )
```

---

## Current Implementation

The existing implementation in [app/data.py](../app/data.py) provides basic import functionality:

```python
# Current: detect_and_parse_import()
# Handles: JSON and CSV file imports
# Normalizes: Basic field mapping for sample data formats
# Missing: Provenance, deduplication, validation rules
```

### Migration Path

1. **Phase 5.1**: Extract current import logic to `JsonFileConnector` and `CsvFileConnector`
2. **Phase 5.2**: Add `LoadNormalizer` with current field mappings
3. **Phase 5.3**: Implement `RecordValidator` with business rules
4. **Phase 5.4**: Add `DeduplicationEngine` with composite keys
5. **Phase 5.5**: Add provenance tracking to all records
6. **Phase 5.6**: Create `IngestionPipeline` orchestrator

---

## Monitoring & Alerting

### Ingestion Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `ingestion_records_total` | Counter | Total records processed by source |
| `ingestion_errors_total` | Counter | Total errors by source and type |
| `ingestion_duration_seconds` | Histogram | Pipeline run duration |
| `ingestion_freshness_hours` | Gauge | Average data freshness |
| `ingestion_dedup_rate` | Gauge | % of records that were duplicates |
| `ingestion_validation_failures` | Counter | Validation failures by rule |

### Alerts

| Alert | Condition | Severity |
|-------|-----------|----------|
| `IngestionStaleness` | No new records in 1 hour | Warning |
| `IngestionHighErrorRate` | >10% error rate | Critical |
| `IngestionSourceDown` | Healthcheck failing | Critical |
| `IngestionHighDupeRate` | >50% duplicates | Warning |

---

## Appendix: Dataset Category Schemas

See [DATA_MODEL.md](DATA_MODEL.md) for complete schema definitions for all 9 dataset categories (A–I).
