# ATP SLO Thin Slice

This document defines the Q10 SLO thin slice. It deliberately reuses the existing Prometheus + Grafana stack and does not introduce a separate SLO platform yet.

## Scope

The first SLO set covers the core ATP control plane:

| SLO | Target | Window | Data source |
|-----|--------|--------|-------------|
| API availability | >= 99.5% | 1h short window | `http_requests_total{job="atp-backend"}` |
| API P95 latency | <= 2s | 5m rolling window | `http_request_duration_seconds_bucket{job="atp-backend"}` |
| Run success rate | >= 95% | 1h short window | `atp_run_outcomes_total{entity_type,status}` |

These are operational guardrails, not release blockers by themselves. A sustained breach should trigger incident review or capacity/debug work before feature work continues.

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
