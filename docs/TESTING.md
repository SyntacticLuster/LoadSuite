# Testing Strategy

## FreightLens Test Plan & Guidelines

**Version:** 1.0  
**Last Updated:** 2024-12-19

---

## Overview

FreightLens uses a multi-layered testing strategy aligned with the existing Python/FastAPI stack:

| Layer | Purpose | Tools | Coverage Target |
|-------|---------|-------|-----------------|
| **Unit** | Pure function logic | pytest | 90%+ |
| **Integration** | API + service interactions | pytest + TestClient | 80%+ |
| **Contract** | API schema validation | pydantic + OpenAPI | 100% endpoints |
| **E2E** | Full user workflows | pytest + httpx | Critical paths |
| **Performance** | Load and latency | locust (future) | P95 targets |

---

## Current State

### Existing Test Infrastructure

| Component | Location | Status |
|-----------|----------|--------|
| Smoke test | [smoke_test.py](../smoke_test.py) | ✅ Working |
| pytest | pyproject.toml | ✅ Installed |
| Test fixtures | — | ❌ Not created |
| Unit tests | — | ❌ Not created |
| Integration tests | — | ❌ Not created |

### Existing Smoke Test Coverage

The current `smoke_test.py` validates:
- `GET /api/meta` returns count > 0
- `GET /api/loads` returns loads
- `GET /api/loads/{id}` returns correct load
- `GET /api/loads?hazmat=true` filters correctly
- `POST /api/import` accepts JSON file

---

## Proposed Directory Structure

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── unit/
│   ├── __init__.py
│   ├── test_scoring.py      # Scoring engine tests
│   ├── test_filters.py      # Filter logic tests
│   ├── test_models.py       # Pydantic validation tests
│   └── test_data.py         # Synthetic generator tests
├── integration/
│   ├── __init__.py
│   ├── test_loads_api.py    # /api/loads endpoints
│   ├── test_brokers_api.py  # /api/brokers endpoints (future)
│   ├── test_alerts_api.py   # /api/alerts endpoints (future)
│   └── test_import_api.py   # /api/import endpoints
├── fixtures/
│   ├── __init__.py
│   ├── loads.py             # Sample load factories
│   ├── brokers.py           # Sample broker factories
│   └── users.py             # Sample user factories
└── performance/
    ├── __init__.py
    └── locustfile.py        # Load testing (future)
```

---

## Unit Testing

### Principles

1. **Pure functions only** — No I/O, no database, no network
2. **Fast execution** — All unit tests complete in <5 seconds
3. **Deterministic** — Same inputs always produce same outputs
4. **Isolated** — No shared state between tests

### Key Modules to Test

#### 1. Scoring Engine (`test_scoring.py`)

```python
# Test each factor independently
def test_rpm_factor_high_rate():
    """High RPM should produce high factor score."""
    load = make_load(rate_total_usd=3000, distance_miles=1000)  # $3/mi
    factor = calculate_rpm_factor(load)
    assert factor >= 0.8  # High score

def test_rpm_factor_low_rate():
    """Low RPM should produce low factor score."""
    load = make_load(rate_total_usd=1000, distance_miles=1000)  # $1/mi
    factor = calculate_rpm_factor(load)
    assert factor <= 0.4  # Low score

def test_deadhead_penalty():
    """High deadhead should reduce score."""
    load = make_load(deadhead_miles=200)
    penalty = calculate_deadhead_penalty(load)
    assert penalty > 0  # Penalty applied

def test_composite_score_deterministic():
    """Same load should always produce same score."""
    load = make_load(seed=42)
    score1 = calculate_composite_score(load, weights=DEFAULT_WEIGHTS)
    score2 = calculate_composite_score(load, weights=DEFAULT_WEIGHTS)
    assert score1 == score2

def test_composite_score_range():
    """Score must be between 0 and 100."""
    for _ in range(100):
        load = make_random_load()
        score = calculate_composite_score(load)
        assert 0 <= score <= 100

def test_score_explainability():
    """Score must include top 5 reasons."""
    load = make_load()
    result = calculate_score_with_reasons(load)
    assert len(result.reasons) == 5
    assert all(r.factor for r in result.reasons)
    assert all(r.contribution for r in result.reasons)
```

#### 2. Filters (`test_filters.py`)

```python
def test_filter_by_equipment():
    """Filter should return only matching equipment."""
    loads = [make_load(equipment="Dry Van"), make_load(equipment="Reefer")]
    query = LoadsQuery(equipment="Reefer")
    result = apply_filters(loads, query)
    assert len(result) == 1
    assert result[0].equipment == "Reefer"

def test_filter_by_rpm_min():
    """Filter should exclude loads below RPM threshold."""
    loads = [make_load(rpm=2.0), make_load(rpm=3.0)]
    query = LoadsQuery(rpm_min=2.5)
    result = apply_filters(loads, query)
    assert len(result) == 1
    assert result[0].rpm >= 2.5

def test_filter_by_date_range():
    """Filter should include loads within pickup window."""
    now = datetime.now(timezone.utc)
    loads = [
        make_load(pickup_start=now + timedelta(hours=1)),
        make_load(pickup_start=now + timedelta(hours=48)),
    ]
    query = LoadsQuery(pickup_end=now + timedelta(hours=24))
    result = apply_filters(loads, query)
    assert len(result) == 1

def test_filter_compound():
    """Multiple filters should AND together."""
    loads = generate_synthetic_loads(100)
    query = LoadsQuery(equipment="Dry Van", rpm_min=2.0, hazmat=False)
    result = apply_filters(loads, query)
    for load in result:
        assert load.equipment == "Dry Van"
        assert load.rpm >= 2.0
        assert load.hazmat is False
```

#### 3. Models (`test_models.py`)

```python
def test_load_validation_positive_values():
    """Load should reject negative distances."""
    with pytest.raises(ValidationError):
        Load(distance_miles=-100, ...)

def test_load_validation_rpm_computed():
    """RPM should be computed correctly."""
    load = Load(rate_total_usd=2500, distance_miles=1000, ...)
    assert load.rpm == 2.5

def test_broker_rating_range():
    """Broker rating must be 0-5."""
    with pytest.raises(ValidationError):
        Broker(rating=6.0, ...)

def test_location_serialization():
    """Location should serialize to JSON correctly."""
    loc = Location(city="Atlanta", state="GA")
    data = loc.model_dump()
    assert data == {"city": "Atlanta", "state": "GA"}
```

---

## Integration Testing

### Principles

1. **Use TestClient** — FastAPI's test client for HTTP simulation
2. **Fresh state** — Reset data before each test
3. **Real validation** — Full request/response cycle
4. **Contract verification** — Check response schemas

### API Test Patterns

#### Setup Fixture (`conftest.py`)

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.data import generate_synthetic_loads, Dataset

@pytest.fixture
def client():
    """Provide a test client with fresh synthetic data."""
    # Reset to known state
    from app import main
    main._dataset = generate_synthetic_loads(100)
    return TestClient(app)

@pytest.fixture
def client_with_loads(client):
    """Client with pre-loaded test data."""
    # Import specific test dataset
    test_loads = load_fixture("sample_loads.json")
    response = client.post(
        "/api/import",
        params={"filename": "test.json"},
        content=test_loads,
    )
    assert response.status_code == 200
    return client
```

#### Loads API Tests (`test_loads_api.py`)

```python
def test_list_loads_returns_results(client):
    """GET /api/loads should return non-empty list."""
    response = client.get("/api/loads")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "loads" in data
    assert data["total"] > 0

def test_list_loads_with_filters(client):
    """GET /api/loads with filters should narrow results."""
    # Get unfiltered count
    all_response = client.get("/api/loads")
    all_count = all_response.json()["total"]
    
    # Get filtered count
    filtered_response = client.get("/api/loads", params={"rpm_min": 2.5})
    filtered_count = filtered_response.json()["total"]
    
    assert filtered_count <= all_count

def test_list_loads_sorting(client):
    """GET /api/loads should respect sort parameter."""
    response = client.get("/api/loads", params={"sort": "rpm_desc"})
    loads = response.json()["loads"]
    
    rpms = [load["rpm"] for load in loads]
    assert rpms == sorted(rpms, reverse=True)

def test_get_single_load(client):
    """GET /api/loads/{id} should return correct load."""
    # First get a valid ID
    list_response = client.get("/api/loads")
    load_id = list_response.json()["loads"][0]["id"]
    
    # Then fetch by ID
    detail_response = client.get(f"/api/loads/{load_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == load_id

def test_get_nonexistent_load(client):
    """GET /api/loads/{id} should 404 for invalid ID."""
    response = client.get("/api/loads/nonexistent-id")
    assert response.status_code == 404

def test_refresh_regenerates_data(client):
    """POST /api/refresh should create new dataset."""
    # Get original load IDs
    original = client.get("/api/loads").json()["loads"]
    original_ids = {load["id"] for load in original}
    
    # Refresh
    refresh_response = client.post("/api/refresh", json={"count": 50})
    assert refresh_response.status_code == 200
    
    # Get new load IDs
    new = client.get("/api/loads").json()["loads"]
    new_ids = {load["id"] for load in new}
    
    # Should be different (UUIDs regenerated)
    assert original_ids != new_ids
```

#### Import API Tests (`test_import_api.py`)

```python
def test_import_json(client):
    """POST /api/import should accept valid JSON."""
    json_data = json.dumps([{
        "id": "test-1",
        "origin": {"city": "Atlanta", "state": "GA"},
        "destination": {"city": "Chicago", "state": "IL"},
        # ... minimal required fields
    }])
    
    response = client.post(
        "/api/import",
        params={"filename": "test.json"},
        content=json_data.encode(),
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True

def test_import_csv(client):
    """POST /api/import should accept valid CSV."""
    csv_data = """id,origin_city,origin_state,dest_city,dest_state,...
test-1,Atlanta,GA,Chicago,IL,..."""
    
    response = client.post(
        "/api/import",
        params={"filename": "test.csv"},
        content=csv_data.encode(),
    )
    assert response.status_code == 200

def test_import_invalid_format(client):
    """POST /api/import should reject invalid data."""
    response = client.post(
        "/api/import",
        params={"filename": "test.json"},
        content=b"not valid json",
    )
    assert response.status_code == 400
```

---

## Contract Testing

### OpenAPI Schema Validation

```python
def test_openapi_schema_valid(client):
    """OpenAPI schema should be valid and complete."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    
    # Check required endpoints exist
    assert "/api/loads" in schema["paths"]
    assert "/api/loads/{load_id}" in schema["paths"]
    assert "/api/meta" in schema["paths"]

def test_load_response_schema(client):
    """Load response should match Pydantic model."""
    response = client.get("/api/loads")
    loads = response.json()["loads"]
    
    for load_data in loads[:10]:
        # Validate against model
        load = Load.model_validate(load_data)
        assert load.id == load_data["id"]
```

---

## Test Fixtures

### Load Factory (`fixtures/loads.py`)

```python
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from app.models import Load, Location, Broker

def make_load(
    *,
    id: str | None = None,
    origin_city: str = "Atlanta",
    origin_state: str = "GA",
    dest_city: str = "Chicago",
    dest_state: str = "IL",
    equipment: str = "Dry Van",
    weight_lbs: int = 40000,
    hazmat: bool = False,
    distance_miles: float = 700,
    deadhead_miles: float = 50,
    rate_total_usd: float = 1750,
    broker_name: str = "Test Broker",
    broker_rating: float = 4.0,
    detention: bool = False,
    multi_stop: bool = False,
    seed: int | None = None,
) -> Load:
    """Create a test load with sensible defaults."""
    now = datetime.now(timezone.utc)
    
    return Load(
        id=id or str(uuid4()),
        origin=Location(city=origin_city, state=origin_state),
        destination=Location(city=dest_city, state=dest_state),
        pickup_start=now + timedelta(hours=24),
        pickup_end=now + timedelta(hours=36),
        delivery_start=now + timedelta(hours=48),
        delivery_end=now + timedelta(hours=60),
        equipment=equipment,
        weight_lbs=weight_lbs,
        hazmat=hazmat,
        distance_miles=distance_miles,
        deadhead_miles=deadhead_miles,
        rate_total_usd=rate_total_usd,
        rpm=round(rate_total_usd / distance_miles, 3),
        broker=Broker(name=broker_name, rating=broker_rating),
        detention=detention,
        multi_stop=multi_stop,
        lane_history=False,
        commodity="General Freight",
        posted_at=now - timedelta(hours=2),
        updated_at=now,
    )

def make_random_load() -> Load:
    """Create a randomized test load."""
    from app.data import generate_synthetic_loads
    dataset = generate_synthetic_loads(1)
    return dataset.loads[0]
```

### Broker Factory (`fixtures/brokers.py`)

```python
def make_broker(
    *,
    mc_number: str = "MC-123456",
    name: str = "Test Broker Inc",
    rating: float = 4.0,
    risk_score: float = 75.0,
    days_to_pay_avg: float = 35.0,
) -> Broker:
    """Create a test broker with sensible defaults."""
    return Broker(
        id=str(uuid4()),
        mc_number=mc_number,
        name=name,
        rating=rating,
        rating_count=50,
        risk_score=risk_score,
        days_to_pay_avg=days_to_pay_avg,
        authority_status="active",
    )
```

---

## Synthetic Data Generator

### Enhanced Generator Requirements

The existing `generate_synthetic_loads()` in `data.py` should be enhanced:

```python
def generate_synthetic_dataset(
    *,
    load_count: int = 1000,
    broker_count: int = 50,
    facility_count: int = 200,
    seed: int | None = None,
) -> SyntheticDataset:
    """
    Generate a complete synthetic dataset with relationships.
    
    Args:
        load_count: Number of loads to generate
        broker_count: Number of unique brokers
        facility_count: Number of unique facilities
        seed: Random seed for reproducibility
    
    Returns:
        SyntheticDataset with loads, brokers, facilities, and lanes
    """
    if seed is not None:
        random.seed(seed)
    
    brokers = [generate_broker(i) for i in range(broker_count)]
    facilities = [generate_facility(i) for i in range(facility_count)]
    loads = [
        generate_load(
            brokers=brokers,
            facilities=facilities,
        )
        for _ in range(load_count)
    ]
    lanes = aggregate_lanes(loads)
    
    return SyntheticDataset(
        loads=loads,
        brokers=brokers,
        facilities=facilities,
        lanes=lanes,
    )
```

---

## Running Tests

### Commands

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=app --cov-report=html

# Run only unit tests
poetry run pytest tests/unit/

# Run only integration tests
poetry run pytest tests/integration/

# Run specific test file
poetry run pytest tests/unit/test_scoring.py

# Run specific test function
poetry run pytest tests/unit/test_scoring.py::test_rpm_factor_high_rate

# Run with verbose output
poetry run pytest -v

# Run and stop on first failure
poetry run pytest -x

# Run tests matching pattern
poetry run pytest -k "scoring"

# Run smoke test (existing)
poetry run python smoke_test.py
```

### Configuration (`pyproject.toml`)

Add to existing `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
asyncio_mode = "auto"
addopts = "-ra -q"

[tool.coverage.run]
source = ["app"]
omit = ["app/__pycache__/*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise NotImplementedError",
]
```

---

## CI/CD Integration

### GitHub Actions Workflow (`.github/workflows/test.yml`)

```yaml
name: Tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      
      - name: Install Poetry
        run: pip install poetry
      
      - name: Install dependencies
        run: poetry install
      
      - name: Run tests
        run: poetry run pytest --cov=app --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: coverage.xml
```

---

## Performance Testing (Future)

### Locust Load Test (`tests/performance/locustfile.py`)

```python
from locust import HttpUser, task, between

class FreightLensUser(HttpUser):
    wait_time = between(1, 3)
    
    @task(10)
    def list_loads(self):
        self.client.get("/api/loads")
    
    @task(5)
    def list_loads_filtered(self):
        self.client.get("/api/loads", params={
            "equipment": "Dry Van",
            "rpm_min": 2.0,
        })
    
    @task(3)
    def get_load_detail(self):
        # First get a valid ID
        response = self.client.get("/api/loads")
        if response.status_code == 200:
            loads = response.json().get("loads", [])
            if loads:
                load_id = loads[0]["id"]
                self.client.get(f"/api/loads/{load_id}")
    
    @task(1)
    def get_meta(self):
        self.client.get("/api/meta")
```

### Performance Targets

| Endpoint | P50 | P95 | P99 | Max RPS |
|----------|-----|-----|-----|---------|
| GET /api/loads | 50ms | 200ms | 500ms | 500 |
| GET /api/loads (filtered) | 75ms | 250ms | 600ms | 300 |
| GET /api/loads/{id} | 20ms | 50ms | 100ms | 1000 |
| GET /api/meta | 10ms | 25ms | 50ms | 1000 |
| POST /api/refresh | 500ms | 1000ms | 2000ms | 10 |

---

## Test Data Management

### Principles

1. **Never use production data** — Synthetic only
2. **Deterministic seeds** — Reproducible test runs
3. **Realistic distributions** — Match real-world patterns
4. **Edge cases included** — Boundary values, nulls, extremes

### Sample Data Files

Location: `sample_data/` (existing) + `tests/fixtures/`

| File | Purpose | Records |
|------|---------|---------|
| `sample_loads.json` | Basic load import testing | 10 |
| `sample_loads.csv` | CSV import testing | 10 |
| `edge_case_loads.json` | Boundary conditions | 20 |
| `large_dataset.json` | Performance testing | 10,000 |

---

## Coverage Requirements

### By Module

| Module | Target | Rationale |
|--------|--------|-----------|
| `scoring.py` | 95% | Core business logic, must be reliable |
| `filters.py` | 90% | User-facing queries, high impact |
| `models.py` | 85% | Validation logic |
| `data.py` | 80% | Generator + parsers |
| `main.py` | 70% | Routing, tested via integration |
| `news.py` | 60% | External dependency, harder to test |

### Overall Target

- **Unit tests:** 90% line coverage
- **Integration tests:** All endpoints covered
- **Combined:** 80% overall coverage

---

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| `ModuleNotFoundError` | Import path wrong | Run from repo root with `poetry run` |
| Flaky tests | Shared state | Use fresh fixtures per test |
| Slow tests | Network calls | Mock external services |
| Datetime issues | Timezone handling | Always use `timezone.utc` |

### Debugging Tips

```python
# Add to conftest.py for verbose logging
@pytest.fixture(autouse=True)
def setup_logging():
    import logging
    logging.basicConfig(level=logging.DEBUG)

# Inspect test data
def test_debug_load(make_load):
    load = make_load()
    print(load.model_dump_json(indent=2))
    assert False  # Force output display
```
