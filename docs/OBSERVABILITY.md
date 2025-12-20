# Observability

## FreightLens Monitoring, Logging, Metrics & Tracing

**Version:** 1.0  
**Last Updated:** 2024-12-19

---

## Overview

FreightLens implements a comprehensive observability stack following the **three pillars**: Logs, Metrics, and Traces. This enables rapid debugging, performance optimization, and proactive incident response.

### Observability Goals

| Goal | Target |
|------|--------|
| Mean Time to Detect (MTTD) | <5 minutes |
| Mean Time to Resolve (MTTR) | <30 minutes |
| Log Retention | 30 days hot, 1 year cold |
| Metric Resolution | 15-second scrape interval |
| Trace Sampling | 100% errors, 10% success |

### Stack Overview

| Component | Tool | Purpose |
|-----------|------|---------|
| Logging | structlog + Loki | Structured JSON logs |
| Metrics | Prometheus + Grafana | Time-series metrics |
| Tracing | OpenTelemetry + Jaeger | Distributed tracing |
| Alerting | Alertmanager + PagerDuty | Incident notification |
| Dashboards | Grafana | Unified visualization |

---

## Logging

### Structured Logging with structlog

All logs are structured JSON for machine parsing and human readability.

#### Configuration

```python
# app/logging_config.py
import structlog
import logging
import sys
from datetime import datetime, timezone

def configure_logging(
    level: str = "INFO",
    json_output: bool = True,
    service_name: str = "freightlens-api"
):
    """Configure structured logging for the application."""
    
    # Shared processors for all loggers
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]
    
    if json_output:
        # Production: JSON format
        renderer = structlog.processors.JSONRenderer()
    else:
        # Development: colored console output
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    
    structlog.configure(
        processors=shared_processors + [
            structlog.processors.CallsiteParameterAdder(
                parameters=[
                    structlog.processors.CallsiteParameter.FILENAME,
                    structlog.processors.CallsiteParameter.LINENO,
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                ]
            ),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Also configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
    )
    
    return structlog.get_logger(service=service_name)
```

#### Log Levels

| Level | Usage | Example |
|-------|-------|---------|
| `DEBUG` | Development details | Query parameters, cache hits |
| `INFO` | Normal operations | Request completed, load imported |
| `WARNING` | Recoverable issues | Rate limit approached, retry |
| `ERROR` | Failures requiring attention | API error, validation failure |
| `CRITICAL` | System-wide failures | Database down, out of memory |

#### Standard Log Fields

Every log entry includes:

```json
{
  "timestamp": "2024-12-19T15:30:00.123Z",
  "level": "info",
  "service": "freightlens-api",
  "environment": "production",
  "version": "1.2.3",
  "host": "api-prod-1",
  "trace_id": "abc123def456",
  "span_id": "789xyz",
  "request_id": "req-uuid-here",
  "message": "Load search completed",
  "filename": "filters.py",
  "lineno": 142,
  "func_name": "filter_loads"
}
```

#### Domain-Specific Log Events

##### API Request Logging

```python
# Middleware logs every request
@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())
    structlog.contextvars.bind_contextvars(request_id=request_id)
    
    log = structlog.get_logger()
    start_time = time.perf_counter()
    
    log.info(
        "request_started",
        method=request.method,
        path=request.url.path,
        query=str(request.query_params),
        client_ip=request.client.host,
        user_agent=request.headers.get("user-agent"),
    )
    
    response = await call_next(request)
    
    duration_ms = (time.perf_counter() - start_time) * 1000
    
    log.info(
        "request_completed",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=round(duration_ms, 2),
    )
    
    response.headers["X-Request-ID"] = request_id
    return response
```

##### Load Search Logging

```python
log.info(
    "load_search",
    query=query_text,
    filters={
        "equipment": equipment,
        "origin": origin,
        "rpm_min": rpm_min,
    },
    result_count=len(results),
    duration_ms=duration,
    cache_hit=cache_hit,
)
```

##### Scoring Engine Logging

```python
log.debug(
    "score_calculated",
    load_id=load.id,
    score=final_score,
    category_scores={
        "profitability": prof_score,
        "feasibility": feas_score,
        "risk": risk_score,
        "preference": pref_score,
    },
    top_factors=[
        {"factor": "rpm", "contribution": 22.3},
        {"factor": "deadhead", "contribution": 18.1},
    ],
    confidence=confidence,
)
```

##### Ingestion Pipeline Logging

```python
log.info(
    "ingestion_batch_completed",
    source="dat_api",
    batch_id=batch_id,
    records_received=1000,
    records_valid=985,
    records_duplicate=12,
    records_invalid=3,
    duration_ms=1250,
)

log.warning(
    "ingestion_validation_failed",
    source="truckstop_api",
    record_id=external_id,
    errors=["missing_origin", "invalid_rate"],
)
```

##### Alert Trigger Logging

```python
log.info(
    "alert_triggered",
    alert_id=alert.id,
    alert_name=alert.name,
    user_id=alert.user_id,
    matching_loads=len(matches),
    channels=alert.channels,
)
```

#### Log Aggregation with Loki

Logs ship to Grafana Loki via Promtail:

```yaml
# promtail-config.yaml
server:
  http_listen_port: 9080

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: freightlens
    static_configs:
      - targets:
          - localhost
        labels:
          job: freightlens-api
          __path__: /var/log/freightlens/*.log
    pipeline_stages:
      - json:
          expressions:
            level: level
            service: service
            trace_id: trace_id
            request_id: request_id
      - labels:
          level:
          service:
      - timestamp:
          source: timestamp
          format: RFC3339Nano
```

#### Log Queries (LogQL)

```logql
# All errors in the last hour
{service="freightlens-api"} |= "error" | json | level="error"

# Slow requests (>500ms)
{service="freightlens-api"} | json | duration_ms > 500

# Specific trace
{service="freightlens-api"} | json | trace_id="abc123def456"

# Ingestion failures by source
sum by (source) (
  count_over_time(
    {service="freightlens-api"} 
    | json 
    | message="ingestion_validation_failed" [1h]
  )
)
```

---

## Metrics

### Prometheus Metrics

Metrics exposed at `/metrics` endpoint using `prometheus-client`.

#### Configuration

```python
# app/metrics.py
from prometheus_client import Counter, Histogram, Gauge, Info
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response

# Application info
app_info = Info("freightlens", "FreightLens application info")
app_info.info({
    "version": "1.2.3",
    "python_version": "3.13",
    "environment": os.getenv("ENVIRONMENT", "development"),
})

# Request metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"]
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

# Load metrics
loads_total = Gauge(
    "freightlens_loads_total",
    "Total loads in dataset",
    ["source"]
)

load_searches_total = Counter(
    "freightlens_load_searches_total",
    "Total load searches performed",
    ["cache_hit"]
)

load_search_results = Histogram(
    "freightlens_load_search_results",
    "Number of results per search",
    buckets=[0, 1, 5, 10, 25, 50, 100, 250, 500, 1000]
)

# Scoring metrics
scores_calculated_total = Counter(
    "freightlens_scores_calculated_total",
    "Total scores calculated"
)

score_distribution = Histogram(
    "freightlens_score_distribution",
    "Distribution of GreenLight scores",
    buckets=[0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
)

score_calculation_duration_seconds = Histogram(
    "freightlens_score_calculation_duration_seconds",
    "Score calculation duration",
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1]
)

# Ingestion metrics
ingestion_records_total = Counter(
    "freightlens_ingestion_records_total",
    "Total records ingested",
    ["source", "status"]  # status: valid, invalid, duplicate
)

ingestion_batch_duration_seconds = Histogram(
    "freightlens_ingestion_batch_duration_seconds",
    "Ingestion batch processing duration",
    ["source"],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0]
)

ingestion_lag_seconds = Gauge(
    "freightlens_ingestion_lag_seconds",
    "Lag between record timestamp and ingestion",
    ["source"]
)

# Broker metrics
broker_lookups_total = Counter(
    "freightlens_broker_lookups_total",
    "Total broker profile lookups",
    ["cache_hit"]
)

broker_risk_score_distribution = Histogram(
    "freightlens_broker_risk_score_distribution",
    "Distribution of broker risk scores",
    buckets=[0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
)

# Alert metrics
alerts_triggered_total = Counter(
    "freightlens_alerts_triggered_total",
    "Total alerts triggered",
    ["alert_type", "channel"]
)

alerts_active = Gauge(
    "freightlens_alerts_active",
    "Number of active alerts"
)

# Watchlist metrics
watchlist_operations_total = Counter(
    "freightlens_watchlist_operations_total",
    "Watchlist operations",
    ["operation"]  # add, remove, refresh
)

# Cache metrics
cache_hits_total = Counter(
    "freightlens_cache_hits_total",
    "Cache hits",
    ["cache_name"]
)

cache_misses_total = Counter(
    "freightlens_cache_misses_total",
    "Cache misses",
    ["cache_name"]
)

cache_size = Gauge(
    "freightlens_cache_size",
    "Current cache size",
    ["cache_name"]
)

# External API metrics
external_api_requests_total = Counter(
    "freightlens_external_api_requests_total",
    "External API requests",
    ["api", "endpoint", "status"]
)

external_api_duration_seconds = Histogram(
    "freightlens_external_api_duration_seconds",
    "External API request duration",
    ["api", "endpoint"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

# Endpoint to expose metrics
@app.get("/metrics")
async def metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )
```

#### Prometheus Configuration

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - alertmanager:9093

rule_files:
  - /etc/prometheus/rules/*.yml

scrape_configs:
  - job_name: "freightlens-api"
    static_configs:
      - targets: ["api:8035"]
    metrics_path: /metrics
    scrape_interval: 15s

  - job_name: "freightlens-workers"
    static_configs:
      - targets: ["worker-1:9090", "worker-2:9090"]

  - job_name: "node-exporter"
    static_configs:
      - targets: ["node-exporter:9100"]
```

#### Key Metrics Dashboard (PromQL)

##### Request Rate & Latency

```promql
# Request rate (requests/second)
sum(rate(http_requests_total{service="freightlens-api"}[5m]))

# P50 latency
histogram_quantile(0.50, 
  sum(rate(http_request_duration_seconds_bucket[5m])) by (le)
)

# P95 latency
histogram_quantile(0.95,
  sum(rate(http_request_duration_seconds_bucket[5m])) by (le)
)

# P99 latency
histogram_quantile(0.99,
  sum(rate(http_request_duration_seconds_bucket[5m])) by (le)
)

# Error rate
sum(rate(http_requests_total{status_code=~"5.."}[5m])) /
sum(rate(http_requests_total[5m]))
```

##### Load Search Performance

```promql
# Searches per minute
sum(rate(freightlens_load_searches_total[1m])) * 60

# Cache hit ratio
sum(rate(freightlens_load_searches_total{cache_hit="true"}[5m])) /
sum(rate(freightlens_load_searches_total[5m]))

# Average results per search
sum(rate(freightlens_load_search_results_sum[5m])) /
sum(rate(freightlens_load_search_results_count[5m]))
```

##### Ingestion Health

```promql
# Ingestion rate by source
sum by (source) (rate(freightlens_ingestion_records_total{status="valid"}[5m]))

# Invalid record rate
sum(rate(freightlens_ingestion_records_total{status="invalid"}[5m])) /
sum(rate(freightlens_ingestion_records_total[5m]))

# Ingestion lag
max by (source) (freightlens_ingestion_lag_seconds)
```

##### Scoring Engine

```promql
# Scores calculated per second
rate(freightlens_scores_calculated_total[5m])

# Score calculation P95 latency
histogram_quantile(0.95,
  sum(rate(freightlens_score_calculation_duration_seconds_bucket[5m])) by (le)
)

# Average score
sum(rate(freightlens_score_distribution_sum[5m])) /
sum(rate(freightlens_score_distribution_count[5m]))
```

---

## Tracing

### OpenTelemetry Integration

Distributed tracing with OpenTelemetry, exported to Jaeger.

#### Configuration

```python
# app/tracing.py
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.trace import Status, StatusCode

def configure_tracing(
    service_name: str = "freightlens-api",
    jaeger_host: str = "localhost",
    jaeger_port: int = 6831,
    sample_rate: float = 0.1,  # 10% sampling for success, 100% for errors
):
    """Configure OpenTelemetry tracing."""
    
    resource = Resource.create({
        SERVICE_NAME: service_name,
        "service.version": "1.2.3",
        "deployment.environment": os.getenv("ENVIRONMENT", "development"),
    })
    
    provider = TracerProvider(resource=resource)
    
    jaeger_exporter = JaegerExporter(
        agent_host_name=jaeger_host,
        agent_port=jaeger_port,
    )
    
    provider.add_span_processor(
        BatchSpanProcessor(jaeger_exporter)
    )
    
    trace.set_tracer_provider(provider)
    
    # Auto-instrument FastAPI
    FastAPIInstrumentor.instrument_app(app)
    
    # Auto-instrument HTTP clients
    HTTPXClientInstrumentor().instrument()
    
    # Inject trace IDs into logs
    LoggingInstrumentor().instrument()
    
    return trace.get_tracer(service_name)


tracer = configure_tracing()
```

#### Custom Spans

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

async def filter_loads(query: LoadsQuery) -> list[Load]:
    with tracer.start_as_current_span("filter_loads") as span:
        span.set_attribute("query.equipment", query.equipment)
        span.set_attribute("query.origin", query.q)
        
        # Filter phase
        with tracer.start_as_current_span("apply_filters"):
            filtered = apply_filters(loads, query)
            span.set_attribute("filtered_count", len(filtered))
        
        # Scoring phase
        with tracer.start_as_current_span("calculate_scores"):
            scored = []
            for load in filtered:
                with tracer.start_as_current_span("score_single_load") as load_span:
                    load_span.set_attribute("load.id", load.id)
                    score = calculate_score(load)
                    load_span.set_attribute("load.score", score)
                    scored.append((load, score))
        
        # Sorting phase
        with tracer.start_as_current_span("sort_results"):
            results = sort_loads(scored, query.sort)
        
        span.set_attribute("result_count", len(results))
        return results
```

#### Span Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `http.method` | string | HTTP method (auto) |
| `http.url` | string | Request URL (auto) |
| `http.status_code` | int | Response status (auto) |
| `load.id` | string | Load identifier |
| `load.score` | float | GreenLight score |
| `query.equipment` | string | Equipment filter |
| `query.origin` | string | Origin filter |
| `broker.mc_number` | string | Broker MC number |
| `ingestion.source` | string | Data source |
| `ingestion.batch_id` | string | Batch identifier |
| `cache.hit` | bool | Cache hit/miss |
| `db.operation` | string | Database operation |

#### Error Handling

```python
from opentelemetry.trace import Status, StatusCode

async def process_ingestion(batch: IngestBatch):
    with tracer.start_as_current_span("process_ingestion") as span:
        span.set_attribute("batch.id", batch.id)
        span.set_attribute("batch.source", batch.source)
        span.set_attribute("batch.size", len(batch.records))
        
        try:
            result = await ingest_records(batch)
            span.set_attribute("result.valid", result.valid_count)
            span.set_attribute("result.invalid", result.invalid_count)
            
        except ValidationError as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise
            
        except ExternalAPIError as e:
            span.set_status(Status(StatusCode.ERROR, "External API failure"))
            span.record_exception(e)
            span.set_attribute("error.external_api", e.api_name)
            raise
```

#### Trace Context Propagation

```python
from opentelemetry.propagate import inject, extract
from opentelemetry.trace import get_current_span

# Outgoing requests: inject trace context
async def call_external_api(url: str, payload: dict):
    headers = {}
    inject(headers)  # Adds traceparent header
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers)
    
    return response

# Incoming requests: extract trace context (automatic with FastAPI instrumentation)
```

#### Jaeger Configuration

```yaml
# docker-compose.yml (Jaeger)
services:
  jaeger:
    image: jaegertracing/all-in-one:1.52
    environment:
      - COLLECTOR_ZIPKIN_HOST_PORT=:9411
    ports:
      - "5775:5775/udp"   # agent zipkin.thrift
      - "6831:6831/udp"   # agent jaeger.thrift
      - "6832:6832/udp"   # agent jaeger.thrift (binary)
      - "5778:5778"       # agent config
      - "16686:16686"     # query UI
      - "14268:14268"     # collector HTTP
      - "14250:14250"     # collector gRPC
```

---

## Alerting

### Alert Rules

```yaml
# prometheus-rules/freightlens.yml
groups:
  - name: freightlens-api
    rules:
      # High error rate
      - alert: HighErrorRate
        expr: |
          sum(rate(http_requests_total{status_code=~"5.."}[5m])) /
          sum(rate(http_requests_total[5m])) > 0.01
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value | humanizePercentage }} (threshold: 1%)"

      # High latency
      - alert: HighLatencyP95
        expr: |
          histogram_quantile(0.95,
            sum(rate(http_request_duration_seconds_bucket[5m])) by (le)
          ) > 1.0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High P95 latency"
          description: "P95 latency is {{ $value | humanizeDuration }}"

      # API down
      - alert: APIDown
        expr: up{job="freightlens-api"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "FreightLens API is down"
          description: "API instance has been unreachable for 1 minute"

  - name: freightlens-ingestion
    rules:
      # Ingestion lag
      - alert: HighIngestionLag
        expr: max(freightlens_ingestion_lag_seconds) > 300
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High ingestion lag"
          description: "Ingestion lag is {{ $value | humanizeDuration }}"

      # Ingestion failure rate
      - alert: HighIngestionFailureRate
        expr: |
          sum(rate(freightlens_ingestion_records_total{status="invalid"}[10m])) /
          sum(rate(freightlens_ingestion_records_total[10m])) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High ingestion failure rate"
          description: "{{ $value | humanizePercentage }} of records are invalid"

      # Ingestion stopped
      - alert: IngestionStopped
        expr: |
          sum(rate(freightlens_ingestion_records_total[10m])) == 0
        for: 15m
        labels:
          severity: critical
        annotations:
          summary: "No records ingested"
          description: "No records have been ingested in the last 15 minutes"

  - name: freightlens-scoring
    rules:
      # Slow scoring
      - alert: SlowScoreCalculation
        expr: |
          histogram_quantile(0.95,
            sum(rate(freightlens_score_calculation_duration_seconds_bucket[5m])) by (le)
          ) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Slow score calculation"
          description: "P95 scoring latency is {{ $value | humanizeDuration }}"

  - name: freightlens-external
    rules:
      # External API errors
      - alert: ExternalAPIErrors
        expr: |
          sum by (api) (
            rate(freightlens_external_api_requests_total{status!="200"}[5m])
          ) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "External API errors"
          description: "API {{ $labels.api }} is returning errors"

      # External API latency
      - alert: ExternalAPILatency
        expr: |
          histogram_quantile(0.95,
            sum by (api, le) (
              rate(freightlens_external_api_duration_seconds_bucket[5m])
            )
          ) > 5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "External API slow"
          description: "API {{ $labels.api }} P95 latency is {{ $value | humanizeDuration }}"

  - name: freightlens-cache
    rules:
      # Low cache hit rate
      - alert: LowCacheHitRate
        expr: |
          sum(rate(freightlens_cache_hits_total[5m])) /
          (sum(rate(freightlens_cache_hits_total[5m])) + 
           sum(rate(freightlens_cache_misses_total[5m]))) < 0.5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Low cache hit rate"
          description: "Cache hit rate is {{ $value | humanizePercentage }}"
```

### Alertmanager Configuration

```yaml
# alertmanager.yml
global:
  resolve_timeout: 5m
  slack_api_url: 'https://hooks.slack.com/services/xxx/yyy/zzz'

route:
  group_by: ['alertname', 'severity']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  receiver: 'default-receiver'
  routes:
    - match:
        severity: critical
      receiver: 'pagerduty-critical'
    - match:
        severity: warning
      receiver: 'slack-warning'

receivers:
  - name: 'default-receiver'
    slack_configs:
      - channel: '#freightlens-alerts'
        send_resolved: true

  - name: 'slack-warning'
    slack_configs:
      - channel: '#freightlens-alerts'
        send_resolved: true
        title: '{{ .CommonAnnotations.summary }}'
        text: '{{ .CommonAnnotations.description }}'

  - name: 'pagerduty-critical'
    pagerduty_configs:
      - service_key: '<pagerduty-service-key>'
        severity: critical
```

---

## Dashboards

### Grafana Dashboard Structure

```
📊 FreightLens Dashboards
├── 📈 Overview
│   ├── Request rate & latency
│   ├── Error rate
│   ├── Active loads
│   └── System health
├── 📊 Load Search
│   ├── Searches/minute
│   ├── Cache hit ratio
│   ├── Results distribution
│   └── Filter breakdown
├── 🎯 Scoring Engine
│   ├── Scores calculated
│   ├── Score distribution
│   ├── Calculation latency
│   └── Factor weights
├── 📥 Ingestion Pipeline
│   ├── Records by source
│   ├── Valid vs invalid
│   ├── Ingestion lag
│   └── Deduplication rate
├── 🏢 Broker Intelligence
│   ├── Lookups/minute
│   ├── Cache performance
│   └── Risk score distribution
├── 🔔 Alerts & Watchlists
│   ├── Alerts triggered
│   ├── Active alerts
│   ├── Watchlist operations
│   └── Notification delivery
├── 🔌 External APIs
│   ├── Request rate by API
│   ├── Latency by endpoint
│   ├── Error rate
│   └── Rate limit usage
└── 🖥️ Infrastructure
    ├── CPU & memory
    ├── Network I/O
    ├── Disk usage
    └── Container health
```

### Dashboard JSON (Overview)

```json
{
  "title": "FreightLens Overview",
  "uid": "freightlens-overview",
  "tags": ["freightlens", "overview"],
  "panels": [
    {
      "title": "Request Rate",
      "type": "stat",
      "targets": [
        {
          "expr": "sum(rate(http_requests_total[5m]))",
          "legendFormat": "req/s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "reqps",
          "thresholds": {
            "steps": [
              {"value": 0, "color": "green"},
              {"value": 100, "color": "yellow"},
              {"value": 500, "color": "red"}
            ]
          }
        }
      }
    },
    {
      "title": "P95 Latency",
      "type": "gauge",
      "targets": [
        {
          "expr": "histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "s",
          "min": 0,
          "max": 2,
          "thresholds": {
            "steps": [
              {"value": 0, "color": "green"},
              {"value": 0.5, "color": "yellow"},
              {"value": 1, "color": "red"}
            ]
          }
        }
      }
    },
    {
      "title": "Error Rate",
      "type": "stat",
      "targets": [
        {
          "expr": "sum(rate(http_requests_total{status_code=~\"5..\"}[5m])) / sum(rate(http_requests_total[5m]))"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "percentunit",
          "thresholds": {
            "steps": [
              {"value": 0, "color": "green"},
              {"value": 0.01, "color": "yellow"},
              {"value": 0.05, "color": "red"}
            ]
          }
        }
      }
    },
    {
      "title": "Active Loads",
      "type": "stat",
      "targets": [
        {
          "expr": "sum(freightlens_loads_total)"
        }
      ]
    }
  ]
}
```

---

## Health Checks

### Endpoint Implementation

```python
# app/health.py
from fastapi import APIRouter
from pydantic import BaseModel
from enum import Enum
import asyncio

router = APIRouter()

class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"

class ComponentHealth(BaseModel):
    name: str
    status: HealthStatus
    latency_ms: float | None = None
    message: str | None = None

class HealthResponse(BaseModel):
    status: HealthStatus
    version: str
    uptime_seconds: float
    components: list[ComponentHealth]

async def check_database() -> ComponentHealth:
    """Check database connectivity."""
    start = time.perf_counter()
    try:
        # Ping database
        await db.execute("SELECT 1")
        latency = (time.perf_counter() - start) * 1000
        return ComponentHealth(
            name="database",
            status=HealthStatus.HEALTHY,
            latency_ms=latency
        )
    except Exception as e:
        return ComponentHealth(
            name="database",
            status=HealthStatus.UNHEALTHY,
            message=str(e)
        )

async def check_cache() -> ComponentHealth:
    """Check cache connectivity."""
    start = time.perf_counter()
    try:
        await cache.ping()
        latency = (time.perf_counter() - start) * 1000
        return ComponentHealth(
            name="cache",
            status=HealthStatus.HEALTHY,
            latency_ms=latency
        )
    except Exception as e:
        return ComponentHealth(
            name="cache",
            status=HealthStatus.DEGRADED,
            message=str(e)
        )

async def check_external_apis() -> ComponentHealth:
    """Check external API availability."""
    try:
        # Check critical external APIs
        results = await asyncio.gather(
            check_dat_api(),
            check_fmcsa_api(),
            return_exceptions=True
        )
        failures = [r for r in results if isinstance(r, Exception)]
        if not failures:
            return ComponentHealth(name="external_apis", status=HealthStatus.HEALTHY)
        elif len(failures) < len(results):
            return ComponentHealth(
                name="external_apis",
                status=HealthStatus.DEGRADED,
                message=f"{len(failures)} API(s) unavailable"
            )
        else:
            return ComponentHealth(
                name="external_apis",
                status=HealthStatus.UNHEALTHY,
                message="All external APIs unavailable"
            )
    except Exception as e:
        return ComponentHealth(
            name="external_apis",
            status=HealthStatus.UNHEALTHY,
            message=str(e)
        )

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Comprehensive health check."""
    components = await asyncio.gather(
        check_database(),
        check_cache(),
        check_external_apis(),
    )
    
    # Determine overall status
    statuses = [c.status for c in components]
    if HealthStatus.UNHEALTHY in statuses:
        overall = HealthStatus.UNHEALTHY
    elif HealthStatus.DEGRADED in statuses:
        overall = HealthStatus.DEGRADED
    else:
        overall = HealthStatus.HEALTHY
    
    return HealthResponse(
        status=overall,
        version=app_version,
        uptime_seconds=get_uptime(),
        components=list(components)
    )

@router.get("/health/live")
async def liveness():
    """Kubernetes liveness probe - is the process alive?"""
    return {"status": "ok"}

@router.get("/health/ready")
async def readiness():
    """Kubernetes readiness probe - can we serve traffic?"""
    # Check critical dependencies
    db_ok = await check_database()
    if db_ok.status == HealthStatus.UNHEALTHY:
        return Response(status_code=503, content="Database unavailable")
    return {"status": "ready"}
```

### Kubernetes Probes

```yaml
# k8s/deployment.yaml
spec:
  containers:
    - name: freightlens-api
      livenessProbe:
        httpGet:
          path: /health/live
          port: 8035
        initialDelaySeconds: 10
        periodSeconds: 10
        timeoutSeconds: 5
        failureThreshold: 3
      
      readinessProbe:
        httpGet:
          path: /health/ready
          port: 8035
        initialDelaySeconds: 5
        periodSeconds: 5
        timeoutSeconds: 3
        failureThreshold: 2
      
      startupProbe:
        httpGet:
          path: /health/live
          port: 8035
        initialDelaySeconds: 0
        periodSeconds: 5
        failureThreshold: 30
```

---

## Runbook Integration

### On-Call Playbooks

| Alert | Runbook |
|-------|---------|
| `HighErrorRate` | [runbook/high-error-rate.md](runbook/high-error-rate.md) |
| `HighLatencyP95` | [runbook/high-latency.md](runbook/high-latency.md) |
| `APIDown` | [runbook/api-down.md](runbook/api-down.md) |
| `HighIngestionLag` | [runbook/ingestion-lag.md](runbook/ingestion-lag.md) |
| `IngestionStopped` | [runbook/ingestion-stopped.md](runbook/ingestion-stopped.md) |
| `ExternalAPIErrors` | [runbook/external-api.md](runbook/external-api.md) |

### Example Runbook: High Error Rate

```markdown
# High Error Rate

## Alert
`HighErrorRate`: Error rate exceeds 1% for 2+ minutes

## Symptoms
- Users seeing 500 errors
- API returning internal server errors
- Error logs showing exceptions

## Investigation Steps

1. **Check error logs**
   ```logql
   {service="freightlens-api"} | json | level="error" | line_format "{{.message}}"
   ```

2. **Identify error patterns**
   ```promql
   topk(10, sum by (endpoint, status_code) (
     rate(http_requests_total{status_code=~"5.."}[5m])
   ))
   ```

3. **Check recent deployments**
   - Review last deployment time
   - Check for configuration changes

4. **Check external dependencies**
   - Database connectivity
   - External API status
   - Cache availability

## Resolution

### If database issue:
- Check connection pool exhaustion
- Verify database is responsive
- Consider failing over to replica

### If external API issue:
- Enable circuit breaker
- Fall back to cached data
- Contact vendor if applicable

### If code bug:
- Identify problematic commit
- Rollback if necessary
- Hotfix and redeploy

## Escalation
- After 15 min: Page on-call engineer
- After 30 min: Page engineering manager
- After 1 hour: Incident commander
```

---

## Development Mode

### Local Observability Stack

```yaml
# docker-compose.observability.yml
version: "3.8"
services:
  prometheus:
    image: prom/prometheus:v2.48.0
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana:10.2.2
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - ./grafana/dashboards:/var/lib/grafana/dashboards

  loki:
    image: grafana/loki:2.9.2
    ports:
      - "3100:3100"

  jaeger:
    image: jaegertracing/all-in-one:1.52
    ports:
      - "16686:16686"
      - "6831:6831/udp"
```

### Environment Variables

```bash
# .env.development
LOG_LEVEL=DEBUG
LOG_JSON=false
OTEL_EXPORTER_JAEGER_AGENT_HOST=localhost
OTEL_EXPORTER_JAEGER_AGENT_PORT=6831
PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus
```

---

## Security Considerations

### Log Redaction

```python
# Sensitive data patterns to redact
REDACT_PATTERNS = [
    (r'"password"\s*:\s*"[^"]*"', '"password": "[REDACTED]"'),
    (r'"api_key"\s*:\s*"[^"]*"', '"api_key": "[REDACTED]"'),
    (r'"authorization"\s*:\s*"[^"]*"', '"authorization": "[REDACTED]"'),
    (r'\b\d{3}-\d{2}-\d{4}\b', '[SSN-REDACTED]'),  # SSN
    (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL-REDACTED]'),
]

def redact_sensitive_data(log_entry: str) -> str:
    """Redact sensitive data from log entries."""
    for pattern, replacement in REDACT_PATTERNS:
        log_entry = re.sub(pattern, replacement, log_entry)
    return log_entry
```

### Metrics Security

- Metrics endpoint requires authentication in production
- No PII in metric labels
- Cardinality limits on label values

### Trace Security

- Traces sampled to reduce data volume
- Sensitive attributes excluded
- Access controlled via Jaeger RBAC
