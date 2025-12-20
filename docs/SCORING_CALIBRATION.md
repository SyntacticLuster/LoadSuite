# Scoring Calibration & Validation

## Anti-Score-Theater: Making GreenLight Trustworthy

**Version:** 1.0  
**Status:** Draft  
**Last Updated:** 2024-12-19  
**Owner:** Engineering + Data Science

---

## Purpose

A score without validation is marketing—not decision support. This document establishes how FreightLens **calibrates, validates, and governs** the GreenLight scoring engine to ensure it predicts real-world outcomes, not just feels reasonable.

> **Anti-Score-Theater Principle:** Every score must be traceable to ground truth. If we can't validate a factor, we reduce its weight or drop it.

---

## A. Ground Truth Datasets

We define ground truth from sources we control or that users provide—avoiding dependence on privileged third-party data.

### A.1 User-Provided Outcomes (Primary)

Users who accept loads can optionally report actual outcomes. This is our highest-quality signal.

| Field | Type | Collection Point | Required |
|-------|------|------------------|----------|
| `load_id` | UUID | Auto-linked | Yes |
| `accepted_at` | datetime | On accept action | Yes |
| `actual_rate_usd` | float | Post-delivery entry | No |
| `actual_miles_loaded` | float | Post-delivery entry | No |
| `actual_miles_deadhead` | float | Post-delivery entry | No |
| `actual_fuel_cost_usd` | float | Post-delivery entry | No |
| `detention_minutes` | int | Post-delivery entry | No |
| `payment_received_at` | datetime | User logs payment | No |
| `payment_amount_usd` | float | User logs payment | No |
| `outcome_rating` | int (1-5) | Post-delivery prompt | No |
| `would_accept_again` | bool | Post-delivery prompt | No |
| `fallthrough` | bool | If load fell through after accept | No |
| `fallthrough_reason` | enum | Broker cancelled, rate changed, etc. | No |
| `notes` | text | Freeform user feedback | No |

**Minimum Viable Labeling (v1):**
- `accepted_at` (automatic)
- `outcome_rating` (1-5 stars, prompted 24h post-delivery)
- `would_accept_again` (binary, same prompt)

**Incentive:** Users who provide outcomes unlock personalized accuracy stats ("Your GreenLight accuracy: 78%").

### A.2 Implicit Signals (Secondary)

Behavioral signals inferred from user actions—no explicit entry required.

| Signal | Inference | Confidence |
|--------|-----------|------------|
| `accepted` | User clicked "Accept" or "Call Broker" | High |
| `rejected` | User viewed detail, then moved on | Medium |
| `watchlisted` | User saved for later consideration | Medium |
| `time_on_detail_seconds` | Engagement proxy | Low |
| `search_refinement_after_view` | Possible dissatisfaction | Low |

### A.3 Public/Open Signals (Tertiary)

Data from public sources we can use without licensing concerns.

| Source | Data | Confidence | Notes |
|--------|------|------------|-------|
| FMCSA SAFER | Broker authority status, age, insurance | High | Public database |
| FMCSA Complaints | Complaint counts (lagging) | Medium | Updated quarterly |
| EIA Fuel Prices | Regional diesel prices | High | Weekly updates |
| BLS/Census | Regional economic indicators | Medium | Lagging, seasonal |

**Label:** All public signals must be tagged with `source_type: "public"` and `confidence: "verified"` or `confidence: "lagging"`.

### A.4 Data We Explicitly Avoid

| Source | Why Excluded |
|--------|--------------|
| Scraped loadboard data | Licensing risk (see DATA_RIGHTS_AND_SOURCING.md) |
| Third-party broker credit scores | Requires commercial license; use only if contracted |
| Social media sentiment | Unreliable, noisy, potential bias |
| Unverified user claims about others | Defamation risk, gaming vector |

---

## B. Labeling Strategy

### B.1 Outcome Labels (Ground Truth)

| Label | Definition | Computation |
|-------|------------|-------------|
| `profitability_realized` | Actual margin after costs | `(actual_rate - actual_fuel - (actual_miles * user.cost_per_mile)) / actual_rate` |
| `detention_actual` | Real detention minutes experienced | User-reported or inferred from timestamps |
| `payment_delay_days` | Days from delivery to payment | `payment_received_at - delivery_date` |
| `fallthrough` | Load cancelled after accept | Boolean flag |
| `rebook_required` | User had to find replacement | Inferred from fallthrough + subsequent accept |
| `user_satisfaction` | 1-5 rating | Direct user input |
| `repeat_broker` | User accepted from same broker again | Cross-reference historical accepts |

### B.2 Minimum Viable Labels for v1

To ship a validated scoring engine, we need at minimum:

| Label | Source | Target Volume |
|-------|--------|---------------|
| `user_satisfaction` (1-5) | Post-delivery prompt | 500+ labeled loads in 90 days |
| `would_accept_again` | Post-delivery prompt | 500+ labeled loads in 90 days |
| `fallthrough` | Implicit (accept → no delivery logged) | Inferred from all accepts |

**Bootstrap strategy:** Seed with synthetic labeled data for development; replace with real outcomes as users provide them. Clearly mark synthetic data as `provenance.source_type: "synthetic"`.

### B.3 Label Quality Checks

| Check | Rule | Action |
|-------|------|--------|
| Outlier detection | `actual_rate` > 5× or < 0.2× posted rate | Flag for review, exclude from training |
| Impossible values | `detention_minutes` < 0 or > 1440 | Reject |
| Self-contradiction | `user_satisfaction: 5` but `would_accept_again: false` | Flag, still include |
| Timing anomaly | `payment_received_at` before `accepted_at` | Reject |

---

## C. Validation Methodology

### C.1 Offline Backtesting

**Train/Validate Split:**
- Split by time, not random (prevent data leakage)
- Train on months 1-2, validate on month 3
- Roll forward as data accumulates

**Protocol:**
```
1. Freeze scoring weights as of date T
2. Score all loads in validation window [T, T+30d]
3. Collect outcomes for those loads
4. Compare predictions to actuals
```

### C.2 Calibration Curves

For probabilistic outputs (e.g., "detention likelihood: 73%"), we measure calibration:

| Predicted Probability Bucket | Observed Outcome Rate | Target |
|------------------------------|----------------------|--------|
| 0-10% | Should be ~5% | ±5% |
| 10-20% | Should be ~15% | ±5% |
| ... | ... | ... |
| 90-100% | Should be ~95% | ±5% |

**Metric:** Expected Calibration Error (ECE) < 0.10

**Visualization:** Reliability diagram plotted monthly (see OBSERVABILITY.md).

### C.3 Ranking Metrics

For "which loads are best," we measure ranking quality:

| Metric | Formula | Target |
|--------|---------|--------|
| `NDCG@5` | Normalized DCG for top 5 surfaced loads | ≥ 0.70 |
| `NDCG@10` | Normalized DCG for top 10 surfaced loads | ≥ 0.65 |
| `Precision@5` | % of top 5 that user rated ≥4 stars | ≥ 60% |
| `MRR` | Mean Reciprocal Rank of first "good" load | ≥ 0.50 |

**Definition of "good":** `user_satisfaction ≥ 4` OR `would_accept_again = true`

### C.4 Factor-Level Validation

Each scoring factor is validated independently:

| Factor | Ground Truth Label | Metric | Target |
|--------|-------------------|--------|--------|
| `score_rpm` | `profitability_realized` | Pearson r | ≥ 0.50 |
| `score_broker_rating` | `payment_delay_days` (inverse) | Spearman ρ | ≥ 0.40 |
| `score_deadhead` | `user_satisfaction` | Pearson r | ≥ 0.30 |
| `score_dwell_risk` | `detention_actual` | ROC-AUC (high/low) | ≥ 0.65 |

**Action:** Factors that fail validation for 2 consecutive months get weight reduced by 50% until fixed.

### C.5 Drift Detection

Run weekly to catch model degradation:

| Check | Method | Alert Threshold |
|-------|--------|-----------------|
| Score distribution shift | KL divergence vs. baseline | > 0.15 |
| Factor contribution shift | Mean contribution per factor | > 20% change |
| Outcome correlation drop | Rolling 30-day r(score, satisfaction) | < 0.40 |
| Calibration drift | ECE increase | > 0.05 from baseline |

**Response:** Alert triggers review; if confirmed, initiate weight recalibration.

---

## D. Weight Governance

### D.1 Initial Weights Rationale

| Factor | Default Weight | Rationale |
|--------|----------------|-----------|
| `rpm` | 1.5 | Primary driver of profitability; validated historically |
| `net_profit` | 1.3 | Direct margin proxy; user cost inputs vary |
| `revenue_per_hour` | 0.8 | Important but depends on dwell estimates (less reliable) |
| `deadhead` | 1.2 | Strong user preference signal; validated |
| `pickup_urgency` | 0.6 | Context-dependent; some users prefer planning time |
| `equipment_match` | 2.0 | Hard constraint; 0 score if no match |
| `broker_rating` | 1.0 | Moderate signal; ratings can be gamed |
| `days_to_pay` | 1.1 | Cash flow critical for owner-operators |
| `dwell_risk` | 0.9 | Facility data often incomplete; lower until validated |
| `backhaul_probability` | 0.7 | Predictive but uncertain; depends on market data |

### D.2 Weight Update Process

**Cadence:** Quarterly review (or upon drift alert)

**Process:**
1. **Data collection:** Aggregate 90 days of labeled outcomes
2. **Factor validation:** Run per-factor correlation analysis
3. **Proposal:** Data team proposes weight adjustments with evidence
4. **Review:** Product + Engineering review for unintended consequences
5. **A/B test:** 10% of users get new weights for 2 weeks
6. **Guardrail check:** Ensure no metric regresses > 10%
7. **Rollout:** Graduate to 100% if guardrails pass

**Guardrails:**
- No single factor weight > 2.5×
- Total weight change per quarter < 30%
- User satisfaction (mean) must not drop

### D.3 User-Adjustable Preferences vs. Global Defaults

| Setting | Who Controls | Range | Effect |
|---------|--------------|-------|--------|
| Global weights | FreightLens (data-driven) | N/A | Baseline for all users |
| User weight overrides | User (Preferences panel) | 0.0 – 2.0 | Multiplier on global weight |
| Factor visibility | User | On/Off | Hides factor from "Why this score" but still computed |

**Rule:** User overrides are respected but we still compute with global weights for validation purposes (track both).

---

## E. Explainability Requirements

### E.1 Per-Load Reason Codes

Every scored load includes:

```json
{
  "score": 82,
  "confidence": "high",
  "confidence_score": 88,
  "reasons": [
    {
      "factor": "rpm",
      "label": "Rate per mile",
      "value": 2.65,
      "benchmark": 2.40,
      "contribution": 18.2,
      "direction": "positive",
      "explanation": "+10% above lane average"
    },
    {
      "factor": "deadhead",
      "label": "Empty miles",
      "value": 35,
      "benchmark": 100,
      "contribution": 14.5,
      "direction": "positive",
      "explanation": "Low deadhead (35 mi)"
    },
    {
      "factor": "broker_rating",
      "label": "Broker reputation",
      "value": 3.8,
      "benchmark": 4.0,
      "contribution": -3.2,
      "direction": "negative",
      "explanation": "Below average rating (3.8★)"
    }
  ],
  "top_positive": ["rpm", "deadhead"],
  "top_negative": ["broker_rating"],
  "missing_factors": ["facility_dwell"]
}
```

### E.2 Confidence Intervals

For probabilistic estimates, show uncertainty:

| Estimate | Display Format | Example |
|----------|----------------|---------|
| Days to pay | Point + range | "28 days (22–38)" |
| Detention likelihood | Bucket + % | "Medium (45–65%)" |
| Backhaul probability | % + confidence | "62% backhaul (±15%)" |

### E.3 Contribution Breakdown UI

**In detail panel:**
```
WHY THIS SCORE: 82/100
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[████████████████░░░░] RPM          +18.2  +10% above market
[██████████████░░░░░░] Deadhead     +14.5  35 mi (low)
[████████████░░░░░░░░] Broker       +12.0  4.1★ (156 reviews)
[██████████░░░░░░░░░░] Profit est   +10.8  ~$380 net
[████░░░░░░░░░░░░░░░░] Urgency       +4.2  Pickup in 18h
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[░░░░░░░░░░░░░░░░░░░░] Dwell risk   -2.5  Unknown facility
[░░░░░░░░░░░░░░░░░░░░] Backhaul     -1.8  Low return probability

⚠️ Missing: Facility dwell data (score adjusted down)
```

---

## F. Anti-Gaming & Anti-Hallucination

### F.1 Never Fabricate Missing Fields

| Rule | Implementation |
|------|----------------|
| No synthetic fills | If `broker.rating` is null, do not impute a value |
| Explicit unknowns | Display "Unknown" or "—" in UI |
| Score penalty | Missing critical fields reduce confidence bucket |

### F.2 Confidence Degradation Rules

| Condition | Confidence Impact | Score Impact |
|-----------|-------------------|--------------|
| `rate_total_usd` missing | Confidence → Low | Score = 0 (cannot evaluate) |
| `distance_miles` missing | Confidence → Low | Score = 0 (cannot compute RPM) |
| `broker.rating` missing | Confidence -10 | Weight → 0.5× for broker factor |
| `broker.rating_count` < 5 | Confidence -5 | Show "limited data" badge |
| Load age > 4 hours | Confidence -5 per hour | Show "stale" badge after 6h |
| Source is `QUARANTINED` | Confidence → Low | Reduce all weights 50% |
| Facility data missing | No change to confidence | Show "Unknown facility" in reasons |

### F.3 Gaming Vectors & Mitigations

| Vector | Risk | Mitigation |
|--------|------|------------|
| Fake positive outcomes | User inflates own accuracy stats | Rate-limit feedback; cross-check with implicit signals |
| Broker rating manipulation | Brokers create fake reviews | Require load-linked ratings; weight by transaction volume |
| Load reposting | Same load posted repeatedly to game freshness | Deduplication by origin+dest+rate+broker (see INGESTION.md) |
| Weight manipulation | User sets all weights to 0 except one | Minimum weight floor of 0.2 for safety factors |

### F.4 Audit Trail

Every score computation is logged:

```json
{
  "event": "score_computed",
  "load_id": "abc-123",
  "timestamp": "2024-12-19T15:30:00Z",
  "score": 82,
  "confidence": "high",
  "weights_version": "2024-Q4-v2",
  "user_overrides": {"rpm": 1.8},
  "factors": { ... },
  "missing_fields": ["facility_id"],
  "data_quality_flags": ["broker_low_review_count"]
}
```

---

## G. Artifacts to Add to Repository

### G.1 This Document

**File:** `docs/SCORING_CALIBRATION.md` (this file)

### G.2 Metrics for OBSERVABILITY.md

Add the following metrics:

```yaml
# Scoring Validation Metrics
scoring_validation:
  - name: score_outcome_correlation
    type: gauge
    description: "Rolling 30-day Pearson r between GreenLight score and user satisfaction"
    labels: [period]
    
  - name: score_calibration_ece
    type: gauge
    description: "Expected Calibration Error for probability estimates"
    labels: [estimate_type]
    
  - name: score_ndcg_at_k
    type: gauge
    description: "NDCG for top-k surfaced loads"
    labels: [k]
    
  - name: score_precision_at_k
    type: gauge
    description: "Precision for top-k loads (rated ≥4)"
    labels: [k]
    
  - name: factor_validation_correlation
    type: gauge
    description: "Per-factor correlation with ground truth"
    labels: [factor_name]
    
  - name: score_drift_kl_divergence
    type: gauge
    description: "KL divergence of score distribution vs. baseline"
    labels: []
    
  - name: outcomes_collected_total
    type: counter
    description: "Count of user-provided outcome labels"
    labels: [label_type]
    
  - name: confidence_bucket_distribution
    type: histogram
    description: "Distribution of loads by confidence bucket"
    labels: [bucket]
```

### G.3 Evaluation Dataset Schema for DATA_MODEL.md

Add the following entity:

```python
class OutcomeLabel:
    """Ground truth label for scoring validation."""
    
    id: str                          # UUID
    load_id: str                     # Reference to scored load
    user_id: str                     # Who provided the label
    
    # Timing
    accepted_at: datetime            # When user accepted the load
    labeled_at: datetime             # When outcome was reported
    
    # Core outcomes
    user_satisfaction: int | None    # 1-5 rating
    would_accept_again: bool | None  # Binary recommendation
    fallthrough: bool                # Did load fall through?
    fallthrough_reason: str | None   # Enum: broker_cancelled, rate_changed, etc.
    
    # Financial outcomes (optional)
    actual_rate_usd: float | None
    actual_miles_loaded: float | None
    actual_miles_deadhead: float | None
    actual_fuel_cost_usd: float | None
    profitability_realized: float | None  # Computed if actuals provided
    
    # Operational outcomes (optional)
    detention_minutes: int | None
    payment_received_at: datetime | None
    payment_delay_days: int | None   # Computed
    
    # Metadata
    label_source: LabelSource        # "user_explicit", "user_implicit", "inferred"
    confidence: LabelConfidence      # "high", "medium", "low"
    notes: str | None
    
    # Provenance
    created_at: datetime
    updated_at: datetime


class LabelSource(str, Enum):
    USER_EXPLICIT = "user_explicit"   # User entered in form
    USER_IMPLICIT = "user_implicit"   # Inferred from actions
    INFERRED = "inferred"             # System-derived
    SYNTHETIC = "synthetic"           # Test/bootstrap data


class LabelConfidence(str, Enum):
    HIGH = "high"       # User-provided core fields
    MEDIUM = "medium"   # Partial data or implicit
    LOW = "low"         # Inferred with uncertainty
```

### G.4 Validation Job Specification

```python
class ValidationJob:
    """Scheduled job to compute validation metrics."""
    
    job_id: str
    job_type: Literal["daily_metrics", "weekly_drift", "quarterly_weights"]
    
    # Time window
    window_start: datetime
    window_end: datetime
    
    # Results
    metrics: dict[str, float]        # Computed metrics
    alerts: list[ValidationAlert]    # Threshold violations
    recommendations: list[str]       # Suggested actions
    
    # Metadata
    executed_at: datetime
    execution_duration_ms: int
    status: Literal["success", "partial", "failed"]


class ValidationAlert:
    metric_name: str
    current_value: float
    threshold: float
    direction: Literal["above", "below"]
    severity: Literal["warning", "critical"]
    message: str
```

---

## H. Implementation Checklist

### Phase 1: Instrumentation (Week 1-2)
- [ ] Add outcome collection UI (post-delivery prompt)
- [ ] Instrument score computation logging
- [ ] Add confidence score to API responses
- [ ] Implement missing field detection

### Phase 2: Baseline (Week 3-4)
- [ ] Collect 500+ labeled outcomes (or use synthetic bootstrap)
- [ ] Compute initial correlation metrics
- [ ] Generate first calibration curve
- [ ] Establish baseline distributions

### Phase 3: Validation Loop (Week 5-6)
- [ ] Implement weekly drift detection job
- [ ] Build validation dashboard in Grafana
- [ ] Create alerting rules for metric degradation
- [ ] Document weight update process

### Phase 4: Governance (Ongoing)
- [ ] Schedule quarterly weight reviews
- [ ] Implement A/B testing infrastructure
- [ ] Create factor deprecation process
- [ ] Publish validation reports to users (transparency)

---

## Assumptions

1. **User willingness:** We assume 10-20% of users will provide outcome labels if prompted simply.
2. **Synthetic bootstrap:** Initial validation uses synthetic labeled data; clearly marked and replaced.
3. **Correlation thresholds:** Targets (r ≥ 0.5, etc.) are starting points; will adjust based on domain learning.
4. **No external dependencies:** Ground truth comes from users and public data only.
