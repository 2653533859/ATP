# ATP SLO Guide

This document defines the ATP SLO baseline. It deliberately reuses the existing Prometheus + Grafana stack and does not introduce a separate SLO platform yet.

## Calibration Status

Q11-10 calibration status: complete for the current pre-production baseline.

Observed traffic window:

- Current evidence source: local, CI, release-readiness, and short-lived staging-style runs captured during Q10/Q11 validation.
- Production Prometheus history: not available in this repository snapshot.
- Decision: keep the Q10 short-window SLOs as pre-production guardrails, but do not treat them as paging-grade production SLOs until continuous production scrape history exists.

Production adoption window:

| Stage | Required history | Purpose | Decision |
|-------|------------------|---------|----------|
| Pre-production baseline | Current local/CI/staging-style validation | Keep dashboard and runbook language aligned before rollout | Active |
| Initial production calibration | 7 consecutive days of Prometheus data | Check request volume, endpoint mix, 5xx shape, and P95 stability | Required before enabling alerts |
| Stable production calibration | 14 consecutive days after first traffic week | Confirm targets are not too loose or too noisy | Required before making SLOs release-blocking |

The current targets are intentionally conservative for an internal automation platform: they should catch backend instability without creating noise while request volume is still low and bursty.

## Scope

The first SLO set covers the core ATP control plane:

| SLO | Target | Window | Data source | Calibration rationale |
|-----|--------|--------|-------------|-----------------------|
| API availability | >= 99.5% | 1h short window | `http_requests_total{job="atp-backend"}` | Allows up to 0.5% backend 5xx during early rollout while still surfacing sustained service faults quickly |
| API P95 latency | <= 2s | 5m rolling window | `http_request_duration_seconds_bucket{job="atp-backend"}` | Matches interactive control-plane expectations for case, run, and report pages without overreacting to isolated cold starts |
| Run success rate | >= 95% | 1h short window | `atp_run_outcomes_total{entity_type,status}` | Useful as an operational symptom metric, but not a pure platform SLO because test failures may come from tested systems |

These are operational guardrails, not release blockers by themselves. A sustained breach should trigger incident review or capacity/debug work before feature work continues.

## Target Rationale

### API Availability: 99.5%

The platform is currently an internal control plane rather than a public user-facing service. A 99.5% target gives a clear reliability bar while leaving enough room for early production calibration, dependency restarts, and low-volume statistical noise.

The 1h window is intentionally short because the current dashboard is used for operational triage. It answers "is the backend unhealthy now?" rather than "did we meet a monthly contract?". After 14 days of production traffic, add a longer 7d or 30d reporting panel before making availability a release-blocking gate.

### API P95 Latency: 2s

The API backs interactive workflows: login, project/case navigation, run detail, dashboard, and management pages. A 2s P95 target is lenient enough for early deployment and database/object-store variability, but still low enough to catch slow query regressions, queue pressure side effects, and overloaded backend instances.

The 5m window is kept for rapid feedback. During production calibration, compare it with a 1h P95 panel before deciding alert thresholds, because low traffic can make a 5m histogram jumpy.

### Run Success Rate: 95%

Run success rate is retained as a high-signal operational indicator, especially for suite and plan execution. It should not be interpreted as platform availability on its own: a failing API/Web/Android test can be caused by the target application under test, test data, device health, or expected assertion changes.

Use this metric to start triage, then separate platform errors from expected test failures by checking run status, worker logs, device state, external target health, and bug tracker side effects.

## PromQL

### API Availability

```promql
1 - (
  sum(rate(http_requests_total{job="atp-backend",status=~"5.."}[1h]))
  /
  clamp_min(sum(rate(http_requests_total{job="atp-backend"}[1h])), 1e-9)
)
```

### API P95 Latency

```promql
histogram_quantile(
  0.95,
  sum(rate(http_request_duration_seconds_bucket{job="atp-backend"}[5m])) by (le)
)
```

### Run Success Rate

```promql
sum(rate(atp_run_outcomes_total{status="passed"}[1h])) by (entity_type)
/
clamp_min(
  sum(rate(atp_run_outcomes_total{status=~"passed|failed|error"}[1h])) by (entity_type),
  1e-9
)
```

`skipped` is exported for visibility but excluded from the success-rate denominator because it usually reflects fail-fast policy rather than an independently executed run.

## Error Budget

The API availability SLO target is 99.5%, so the allowed error budget is 0.5% of backend requests in the measurement window.

The Grafana short-window panel uses:

```promql
clamp_min(
  1 - (
    (
      sum(rate(http_requests_total{job="atp-backend",status=~"5.."}[1h]))
      /
      clamp_min(sum(rate(http_requests_total{job="atp-backend"}[1h])), 1e-9)
    )
    / 0.005
  ),
  0
)
```

Interpretation:

- `1.0`: no API error budget consumed in the current window.
- `0.5`: half of the short-window budget remains.
- `0`: error rate has exhausted or exceeded the short-window budget.

## Grafana

The `ATP Overview` dashboard includes four Q10 SLO panels:

1. `SLO API availability (1h)`
2. `SLO API P95 latency (5m)`
3. `SLO run success rate (1h)`
4. `SLO API error budget remaining (1h)`

Dashboard source: `docker/grafana/dashboards/atp-overview.json`.

## Production Calibration Checklist

Before enabling alerting or treating these SLOs as release gates, collect and record:

1. Prometheus scrape continuity for `atp-backend` across at least 7 days.
2. Request volume per day and top handlers by traffic.
3. 5xx rate split by handler, excluding `/metrics` and `/health`.
4. API P95 over both 5m and 1h windows.
5. Slow query and queue backlog correlation during latency spikes.
6. Run success rate split by `entity_type`, with at least one sample incident classified as platform-caused or test-target-caused.
7. A written decision on whether to keep, tighten, or relax the 99.5% availability and 2s P95 targets.

Deferred until production data exists:

- Paging-grade Grafana alerts.
- Monthly error-budget reporting.
- Release-blocking SLO policy.
- Separate SLOs by endpoint class, such as read-only pages vs execution-triggering APIs.

## Metric Ownership

FastAPI request metrics are provided by `prometheus-fastapi-instrumentator`.

Run outcome metrics are emitted by Celery task completion paths:

- `case`: `run_test_case` and parameterized child/parent runs.
- `suite`: standalone suite runs and suite runs executed inside plans.
- `plan`: plan runs.

Metric:

```text
atp_run_outcomes_total{entity_type="case|suite|plan",status="passed|failed|error|skipped"}
```

All metric writes are best-effort. Metrics failures are logged but must not change test execution state.
