# Monetization Strategy

## FreightLens Outcome-Based Pricing Tiers

**Version:** 1.0  
**Status:** Draft  
**Last Updated:** 2024-12-19  
**Owner:** Product + Revenue

---

## Philosophy

FreightLens sells **decision advantage**, not software access. Our pricing reflects the measurable value carriers extract: higher realized margins, fewer bad-broker losses, reduced detention, and hours saved in load selection.

> **Principle:** If we can't measure the outcome, we don't charge for it.

We avoid feature-gating that cripples usability. Instead, tiers unlock higher precision, historical depth, and proactive automation—directly tied to operational scale.

---

## Tier Summary

| Tier | Target User | Core Outcome | Pricing Anchor |
|------|-------------|--------------|----------------|
| **Driver** | Owner-operators (1 truck) | Higher realized $/mile after all costs | Positioned within common loadboard subscription bands; value justified by profit uplift documentation |
| **Fleet** | Small fleets (2–20 trucks) | Portfolio optimization + risk reduction | Premium justified by fleet-wide savings on detention, bad debt, deadhead |
| **Operations** | Dispatch teams (10–50+ trucks) | Time reclaimed + decision velocity | Enterprise-adjacent; justified by dispatcher productivity gains |

---

## Tier 1: Driver

### A. Who It's For

- **Owner-operators** running 1 truck
- Independent contractors seeking better load selection
- New entrants learning the market

### B. Job-to-be-Done Outcomes

| Outcome | User Language |
|---------|---------------|
| Higher net $/mile | "I want to know my true take-home after fuel and deadhead—not just the posted rate." |
| Avoid bad brokers | "I've been burned. I need to know who pays slow or disputes loads." |
| Faster decision-making | "I spend 2+ hours/day scrolling. I want the best loads surfaced first." |
| Reduce unprofitable accepts | "I sometimes accept loads that cost me money—I don't realize until after." |
| Visibility into risk | "What am I not seeing that could bite me?" |

### C. KPIs & Computation

| Metric | Formula | Target |
|--------|---------|--------|
| `realized_rpm_improvement` | `(avg_realized_rpm_post - avg_realized_rpm_pre) / avg_realized_rpm_pre` | ≥ +8% within 90 days |
| `accepted_load_profit_margin` | `(rate - total_cost) / rate` for user-confirmed loads | ≥ 20% average |
| `bad_broker_exposure_rate` | `loads_accepted_from_low_rated_brokers / total_accepts` | ≤ 5% |
| `daily_selection_time_minutes` | User-reported or session-inferred | ≤ 45 min (down from 120+) |
| `score_accuracy` | `correlation(greenlight_score, user_outcome_rating)` | ≥ 0.65 |

### D. Value Proof (In-App Weekly/Monthly)

**Weekly Dashboard Card:**
```
YOUR WEEK IN FOCUS
─────────────────────────────────────────
Loads evaluated:         47
Accepted (GreenLight ≥75): 3
Avg. realized RPM:       $2.68 (+$0.21 vs. pre-FreightLens avg)
Bad broker avoidance:    2 loads flagged, 0 accepted
Est. profit protected:   ~$340 (avoided 1 slow-pay broker)
```

**Monthly Summary (email + in-app):**
- Realized $/mile trend chart
- Broker quality distribution of accepted loads
- "You avoided X loads with detention risk flags—here's what that saved"

### E. Pricing Anchor Positioning

Positioned **within the range of common loadboard subscription services**. The premium over free tiers is justified by documented profit uplift—users see their improvement in weekly dashboards. If a user's realized RPM improves by even 5%, the subscription pays for itself many times over on typical monthly miles.

### F. Positioning Statement

> **"Know your true take-home on every load—before you accept."**

---

## Tier 2: Fleet

### A. Who It's For

- **Fleet owners** with 2–20 trucks
- Operations managers splitting time between driving and dispatching
- Carriers scaling beyond owner-operator

### B. Job-to-be-Done Outcomes

| Outcome | User Language |
|---------|---------------|
| Portfolio-level visibility | "I need to see all my trucks' opportunities in one view—not per-truck tabs." |
| Risk aggregation | "If one broker is bad, I want to know before I put 5 trucks on their loads." |
| Detention reduction | "Detention kills my margins. I want to avoid bad facilities." |
| Lane intelligence | "I want to know if a lane I'm considering is trending up or down." |
| Reduced deadhead fleet-wide | "Every 10 miles of empty driving costs me money across the fleet." |

### C. KPIs & Computation

| Metric | Formula | Target |
|--------|---------|--------|
| `fleet_utilization_rate` | `total_loaded_miles / (total_loaded + total_empty)` | ≥ 80% |
| `fleet_avg_realized_rpm` | `sum(load_rate - load_cost) / sum(load_miles)` | +12% vs. pre-signup baseline |
| `detention_hours_per_1k_miles` | `sum(detention_minutes) / (total_miles / 1000) / 60` | ≤ 1.5 hours |
| `broker_concentration_risk` | `loads_from_top_3_brokers / total_loads` | ≤ 40% |
| `bad_debt_exposure_usd` | `sum(unpaid_or_disputed_invoices)` | ≤ 2% of gross |

### D. Value Proof (In-App Weekly/Monthly)

**Weekly Fleet Digest:**
```
FLEET PERFORMANCE (8 trucks)
─────────────────────────────────────────
Loads moved:             34
Fleet utilization:       82% (+4% vs. last month)
Avg. realized RPM:       $2.54
Detention events:        3 (down from 7)
Broker risk alerts:      2 flagged, 1 accepted (MC-XXXXXX)
Est. value protected:    ~$1,200 (detention + bad broker avoidance)
```

**Monthly Report:**
- Per-truck performance comparison
- Lane profitability heatmap (headhaul vs. backhaul)
- Broker scorecard (aggregated exposure + payment velocity)
- "What-if" scenarios: "If you'd avoided high-detention facilities, you'd have saved X hours"

### E. Pricing Anchor Positioning

Positioned as a **premium over the Driver tier** at a per-truck or flat fleet rate. The cost is justified by **fleet-wide savings**: reduced detention, lower deadhead, and early warning on bad brokers before multiple trucks are exposed. The monthly report shows aggregate savings—often 10–20× the subscription cost.

### F. Positioning Statement

> **"See your entire operation. Protect your margins across every truck."**

---

## Tier 3: Operations

### A. Who It's For

- **Dispatch teams** managing 10–50+ trucks
- Fleet operations with dedicated back-office staff
- Carriers with multiple dispatchers / shift coverage

### B. Job-to-be-Done Outcomes

| Outcome | User Language |
|---------|---------------|
| Dispatcher productivity | "My dispatchers spend too much time hunting. I want loads matched to trucks automatically." |
| Decision velocity | "When a load falls through, we need to rebook in minutes, not hours." |
| Auditability | "I need to know who accepted what and why—for post-mortems and training." |
| Proactive alerting | "Don't make me check. Push me the opportunities and risks." |
| Benchmarking | "How does my operation compare to market norms?" |

### C. KPIs & Computation

| Metric | Formula | Target |
|--------|---------|--------|
| `dispatcher_loads_per_hour` | `loads_booked / dispatcher_active_hours` | ≥ 3.0 (up from ~1.5) |
| `rebook_latency_minutes` | `time_to_confirm_replacement / fallthrough_events` | ≤ 20 min |
| `decision_audit_coverage` | `loads_with_logged_accept_reason / total_accepted` | 100% |
| `alert_action_rate` | `alerts_acted_upon / alerts_triggered` | ≥ 70% |
| `ops_nps` | Quarterly dispatcher satisfaction survey | ≥ 40 |

### D. Value Proof (In-App Weekly/Monthly)

**Weekly Ops Dashboard:**
```
DISPATCH OPERATIONS (3 dispatchers, 28 trucks)
─────────────────────────────────────────
Loads booked:            112
Avg. time-to-book:       18 min (down from 35 min)
Fallthrough recovery:    4/5 rebooked within 30 min
Alert → action rate:     74%
Est. hours saved:        ~22 dispatcher-hours (vs. manual workflow)
```

**Monthly Ops Report:**
- Dispatcher leaderboard (gamified, opt-in)
- Shift coverage gaps identified
- Benchmark comparison: "Your rebook latency is in the top 20% of similar fleets"
- Decision audit log export (for owner review)

### E. Pricing Anchor Positioning

Positioned as **enterprise-adjacent** with value tied to dispatcher productivity. If a dispatcher saves 5 hours/week and covers more trucks with the same headcount, the cost pays for itself in labor efficiency alone. Pricing may include per-seat and per-truck components, justified by measurable time savings and rebook velocity.

### F. Positioning Statement

> **"Dispatch faster. Recover instantly. See everything."**

---

## Cross-Tier Features

Some capabilities are present across tiers but with **different depth or automation**:

| Capability | Driver | Fleet | Operations |
|------------|--------|-------|------------|
| GreenLight scoring | ✓ | ✓ | ✓ |
| Broker risk flags | Basic (rating + days-to-pay) | Aggregated fleet exposure | Aggregated + alerts |
| Lane intelligence | Current rates | 30-day trends | 90-day trends + forecasts |
| Saved filters | 3 | 10 | Unlimited |
| Alerts | 2 lane alerts | 10 alerts | Unlimited + Slack/webhook |
| Export | CSV (self loads only) | CSV + PDF reports | API access + integrations |
| Portfolio view | — | Multi-truck grid | Multi-dispatcher, shift assignment |
| Decision audit log | — | — | Full audit trail |
| Benchmarking | — | — | Market comparisons |

---

## Value Documentation Cadence

| Artifact | Cadence | Delivery |
|----------|---------|----------|
| Weekly performance card | Weekly (Monday AM) | In-app dashboard + optional email |
| Monthly value report | Monthly (1st of month) | In-app + email + PDF export |
| Quarterly ROI summary | Quarterly | In-app + email |
| Annual value retrospective | Annually | PDF report for user's accountant/partner |

---

## Anti-Patterns We Avoid

| Anti-Pattern | Why We Avoid It |
|--------------|-----------------|
| Feature-gating core safety info | Broker risk flags should never be paywalled for safety—basic visibility is free |
| Charging for data we don't own | User-provided outcomes are theirs; we charge for analysis, not their data |
| Hidden "gotcha" pricing | All tier limits are visible; overages have clear warnings before charge |
| Vanity metrics | We don't show "loads viewed" as value—only realized outcomes |

---

## Assumptions

1. **Baseline data exists:** We assume users on Driver tier provide minimal outcome feedback (accept/reject, optional realized revenue) to compute improvement metrics.
2. **Session tracking enabled:** Time-to-decision metrics rely on session instrumentation (see OBSERVABILITY.md).
3. **No legal advice:** Tier names and positioning are product decisions, not legal structures.
4. **Market anchoring:** We reference "common loadboard subscription bands" without quoting specific competitor prices.

---

## Next Steps

1. Instrument outcome collection (see OBSERVABILITY.md additions)
2. Build weekly value card component (see TRUST_UI_SPEC.md)
3. Define baseline capture flow for new signups
4. A/B test value messaging in onboarding

