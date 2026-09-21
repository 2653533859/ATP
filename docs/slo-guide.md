# ATP SLO Guide

This document defines the ATP SLO baseline. It deliberately reuses the existing Prometheus + Grafana stack and does not introduce a separate SLO platform yet.

## Calibration Status

Q11-10 calibration status: complete for the current pre-production baseline.

Observed traffic window:

- Current evidence source: local, CI, release-readiness, and short-lived staging-style runs captured during Q10/Q11 validation.
- Release Prometheus history: collection started on 2026-09-13 for the current single-node target. The standalone collector retains 15 days and currently scrapes Backend, ordinary Worker, Performance Worker and itself. The first seven-day window, 2026-09-13 through 2026-09-19, has 288/288 Backend and Worker checkpoints every day, but only 2026-09-14 contains traffic: 34 bounded synthetic requests and 3 runs, with 100% availability, 95ms P95 and 100% run success. The other six days have no business samples, so the initial calibration is not accepted; see [`slo-history-2026-09-13-2026-09-19.md`](slo-history-2026-09-13-2026-09-19.md). Ratio queries exclude hours without matching business activity, each SLO receives an independent decision, and midnight range samples are attributed to the day their right-closed interval measures. The collector rejects the current or a future UTC day rather than recording a partial day as history.
- Metric-chain canary: on 2026-09-15, bounded authenticated read traffic and two self-targeted API case runs established HTTP request, latency histogram, and `atp_run_outcomes_total{entity_type="case",status="passed"}` growth across Prometheus scrapes. This verifies instrumentation only; the in-progress UTC day and synthetic traffic are excluded from complete-day calibration evidence.
- New candidate window: 2026-09-20 was rejected because a host restart left Backend and Worker at 276/288 five-minute checkpoints, despite 30 requests, 95ms P95 and two passed runs. A dedicated `tester` account with project 77 `editor` access now runs the bounded canary through a persistent systemd timer. The replacement window starts on 2026-09-21 and still requires complete UTC-day evidence before each day is accepted.
- Decision: keep the Q10 short-window SLOs as pre-production guardrails. Do not enable paging-grade alerts before 7 consecutive days or make SLOs release-blocking before the 14-day calibration is reviewed.

Production adoption window:

| Stage | Required history | Purpose | Decision |
|-------|------------------|---------|----------|
| Pre-production baseline | Current local/CI/staging-style validation | Keep dashboard and runbook language aligned before rollout | Active |
| Initial production calibration | 7 consecutive days of Prometheus data with representative traffic | Check request volume, endpoint mix, 5xx shape, and P95 stability | First 7-day scrape window complete, but 6 days have no business samples and the only evaluable day is bounded synthetic traffic; not accepted, restart the representative window before enabling alerts |
| Stable production calibration | 14 consecutive days after first traffic week | Confirm targets are not too loose or too noisy | Pending; required before making SLOs release-blocking |

在第 7/14 天使用独立入口采集当前发布 Prometheus；日期按 UTC 完整日填写：

```bash
make collect-release-slo-evidence \
  START=YYYY-MM-DD END=YYYY-MM-DD \
  PROMETHEUS_URL=http://127.0.0.1:39090 \
  SOURCE_DEPLOYMENT=atp-single-node
```

在等待完整 UTC 日期间，可用有界 canary 验证指标链。交互运行时可把凭据放入当前进程环境；自动运行应使用 `ATP_PASSWORD_FILE` / `ATP_TOKEN_FILE`。不要把密码写入命令行或 `ARGS`：

```bash
export ATP_USERNAME='<current-account>'
export ATP_PASSWORD='<read-securely>'
make slo-traffic-canary \
  API_BASE_URL=http://192.168.3.196:8000 \
  ARGS='--project-id 77 --iterations 6 --source-deployment atp-single-node'
```

默认入口只登录并读取项目列表和工作台概览。只有显式同时传入 `--case-id` 与 `--confirm-case-run` 才会新增运行记录；运行前会重新确认用例属于所选项目，并要求 API 用例为 active、approved、可自动执行、单步、GET 且目标为本机 HTTP 回环地址。默认执行两次，并在每次终态后等待一个 20 秒 Prometheus 抓取周期：

```bash
make slo-traffic-canary \
  API_BASE_URL=http://192.168.3.196:8000 \
  ARGS='--project-id 77 --case-id 42 --confirm-case-run --source-deployment atp-single-node'
```

报告默认写入忽略目录 `.local-run/slo-traffic-canary.json`，不记录账号、密码、Token 或业务响应正文。Canary 只验证指标能增长；仍必须在 UTC 日结束后用 `collect-release-slo-evidence` 生成完整日证据。

Linux 发布机使用仓库中的 [`deploy/systemd/atp-slo-canary.service`](../deploy/systemd/atp-slo-canary.service) 和 [`deploy/systemd/atp-slo-canary.timer`](../deploy/systemd/atp-slo-canary.timer)。服务通过 `LoadCredential` 将 root 管理的 `0600` 密码映射到受保护的运行时目录，使用专用低权限 ATP 账号，不在 unit、命令行、日志或报告中记录密码。Timer 每日 08:30（Asia/Shanghai）触发并带最多 5 分钟随机延迟；`Persistent=true` 会在错过计划后补跑。安装后必须执行 `systemd-analyze verify`、手动启动一次 service，并核对退出码、脱敏报告、Prometheus 三条指标链和下一次 timer 时间。

采集器按 5 分钟检查点验证 Backend/Worker 抓取连续性，并把 `NaN`、无穷值、无样本、少于 288 个日检查点或 `up=0`
统一记录为数据缺口；任何缺口都会让 alert/release gate 保持 `deferred`。不足 7 天的运行只标记为 preflight。

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
  sum(rate(http_requests_total{job="atp-backend",status="5xx"}[1h]))
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
      sum(rate(http_requests_total{job="atp-backend",status="5xx"}[1h]))
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

## Triage Runbook

Use this runbook when a SLO panel breaches its target for at least two consecutive refreshes, or when an operator sees the same symptom in user reports.

### First Five Minutes

1. Confirm the panel window and target: availability `1h`, P95 `5m`, run success rate `1h`, or error budget `1h`.
2. Check whether Prometheus is scraping fresh samples for `atp-backend`, `atp-worker`, and `celery-exporter`.
3. Compare the breached panel with request volume. Very low traffic can make short windows noisy; still continue if users are affected.
4. Open the nearest related panel in `ATP Overview`: HTTP 5xx rate, HTTP P95 by handler, slow query rate, Celery queue length, or run success rate by entity type.
5. Pick one incident owner and capture the time window, affected panel, and first hypothesis before changing config or restarting services.

### API Availability Breach

Signal:

- `SLO API availability (1h)` drops below `99.5%`.
- `SLO API error budget remaining (1h)` approaches `0`.
- HTTP 5xx rate is non-zero for the same time window.

First checks:

1. Split 5xx by handler:

   ```promql
   sum(rate(http_requests_total{job="atp-backend",status="5xx"}[5m])) by (handler)
   ```

2. Check whether errors are isolated to execution/reporting endpoints or affect login, project, and case navigation too.
3. Inspect backend logs for the same time window, grouping by exception type and `trace_id` when present.
4. Verify Postgres, Redis, and MinIO connectivity before restarting the backend.
5. If a recent deployment exists, compare the first error timestamp with the deployment timestamp and review migration / dependency changes.

Escalate when:

- Multiple core handlers fail for more than 15 minutes.
- Errors continue after dependency health is confirmed.
- A migration or config change is suspected and rollback may be needed.

### API P95 Latency Breach

Signal:

- `SLO API P95 latency (5m)` is above `2s`.
- Handler-level HTTP P95 or slow query panels rise in the same window.

First checks:

1. Identify the slowest handlers:

   ```promql
   histogram_quantile(
     0.95,
     sum(rate(http_request_duration_seconds_bucket{job="atp-backend"}[5m])) by (le, handler)
   )
   ```

2. Check slow query rate and backend logs for `slow_query` entries.
3. Check Celery queue length. Some UI/API paths can appear slow when execution-triggering calls wait on overloaded dependencies.
4. Check MinIO storage stats if report, screenshot, video, APK, or script endpoints are slow.
5. Use `trace_id` to jump from slow-query logs to Jaeger spans when tracing is enabled.

Escalate when:

- P95 remains above target for three consecutive 5m windows.
- The slowest handler is a critical interactive flow such as login, run detail, or case navigation.
- Slow queries point to a repeated ORM/API path that needs an index or query rewrite.

### Run Success Rate Breach

Signal:

- `SLO run success rate (1h)` drops below `95%` for `case`, `suite`, or `plan`.
- User reports mention failed scheduled plans or unexpected execution errors.

First checks:

1. Identify the affected entity type:

   ```promql
   sum(rate(atp_run_outcomes_total{status=~"passed|failed|error"}[1h])) by (entity_type, status)
   ```

2. Separate `failed` from `error`:

   - `failed`: likely assertion failure, target application change, data issue, or expected test failure.
   - `error`: likely platform, worker, device, dependency, script, or configuration issue.

3. For `case` drops, sample recent `TestRun` rows and inspect `error_message`, step results, screenshots, or script logs.
4. For `suite` or `plan` drops, check child runs first. Parent failures often summarize child case failures.
5. Check Celery queue length, worker timeout counters, ADB reconnect/heartbeat panels, and MinIO access when errors cluster around Web/Android/report artifacts.

Escalate when:

- `error` grows faster than `failed`.
- Multiple unrelated projects fail at the same time.
- Scheduled plans fail but manual reruns pass, suggesting queue, worker, or dependency instability.

### Error Budget Exhaustion

Signal:

- `SLO API error budget remaining (1h)` reaches `0`.
- API availability is below target or 5xx rate remains elevated.

First checks:

1. Treat this as an availability incident, not a separate root cause.
2. Verify whether the budget was consumed by one spike or a sustained error rate.
3. If one spike consumed the budget but traffic is now healthy, record the root cause and keep watching the next 1h window.
4. If the budget remains at `0`, pause non-urgent deploys and focus on restoring backend health.

Escalate when:

- Error budget remains exhausted after the immediate 5xx cause is mitigated.
- The same handler consumes budget repeatedly across separate windows.

### Incident Record Template

Use this lightweight format in the incident tracker or release notes:

```text
Time window:
Breached SLO:
Observed value:
Affected handlers / entity types:
First hypothesis:
Checks completed:
Root cause:
Mitigation:
Follow-up:
```

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

## Alert Threshold Decision

Q11-12 decision: defer paging-grade SLO alerts until production Prometheus history exists.

Rationale:

- The current evidence window is local, CI, release-readiness, and short-lived staging-style validation. It is enough for dashboard guardrails, but not enough to tune alert noise.
- The SLO panels use short windows (`1h` availability/error budget, `5m` P95). These are useful for triage, but can be noisy under low traffic.
- The repository already includes platform health warning alerts in `deploy/grafana/alerts/atp-alerts.yaml`, including API 5xx, queue backlog, DB connection pressure, Celery failures, timeouts, and ADB health. Those remain the active alert layer until SLO-specific production history is available.

Deferred SLO alert candidates:

| Candidate | Draft threshold | Hold time | Severity | Enable after |
|-----------|-----------------|-----------|----------|--------------|
| API availability burn | `< 99.5%` over `1h` | 15m | warning | 7 consecutive days of production scrape history and handler mix review |
| API P95 latency | `> 2s` over `5m`, confirmed by `1h` P95 trend | 15m | warning | 7 consecutive days of traffic and low-volume noise review |
| API error budget exhausted | remaining budget `== 0` over `1h` | 10m | warning | Availability alert has acceptable noise in staging/production |
| Run success rate | `< 95%` by entity type over `1h` | 30m | ticket-only | At least one classified incident separates platform-caused errors from expected test failures |

Do not make these paging alerts or release-blocking gates until the stable production calibration window is complete. If early production traffic is sparse, keep using the Grafana panels and the triage runbook instead of adding more alerts.

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
