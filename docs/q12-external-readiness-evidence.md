# Q12 External Readiness Evidence Specification

> Updated: 2026-07-10
> Scope: Q12-05 — the two remaining evidence items that require environment access:
> production-like SLO history and a physical Android device execution rehearsal.
> This document fixes the evidence format so capture can start as soon as the
> environment is available, and so the result is reviewable without re-deriving
> what "done" means.

## Part 1 — Production-like SLO History

Builds on `docs/slo-guide.md` (targets, PromQL, and the 7-day/14-day adoption
window). This section defines what must be recorded, not the targets themselves.

### Preconditions

- A production or production-like deployment with Prometheus continuously
  scraping `atp-backend` (and worker metrics on `WORKER_METRICS_PORT`).
- The Grafana `atp-overview` dashboard loads against that Prometheus.
- Traffic is real usage or a documented synthetic profile — not one-shot CI runs.

### Capture Procedure

1. Record the window start date. Evidence windows use absolute dates, never
   "last week".
2. On day 7 (initial production calibration), export for each SLO:
   - API availability (1h window) daily worst and daily mean
   - API P95 latency: the 5m panel and a 1h comparison panel
   - Run success rate (1h window) daily worst and daily mean
   plus request volume, endpoint mix, and 5xx shape notes.
3. On day 14 (stable production calibration), repeat the export and record the
   calibration decision: keep / tighten / loosen each target, whether alerts
   are enabled, and whether any SLO becomes release-blocking.
4. Every breach inside the window gets a one-line triage note (cause,
   platform-vs-tested-system attribution, action).

### Required Record Fields

| Field | Requirement |
|-------|-------------|
| Window | Absolute start/end dates, 7 or 14 consecutive days, no gaps |
| Source | Prometheus instance identity and scrape health during the window |
| Per-SLO results | Achieved value vs target for all three SLOs |
| Breaches | Count, dates, and triage notes (may be zero) |
| Decision | Alert enablement and release-blocking decision with rationale |

### Pass Criteria

- 7 consecutive days of complete scrape data (day-7 record), then 14 (day-14).
- All three SLOs met, or every miss has a triage note and a target decision.
- The day-14 record states the alert/release-gate decision explicitly.

### Evidence Location

`docs/slo-history-<start>-<end>.md`, linked from the release evidence document
current at capture time. Grafana snapshots or CSV exports are attached under
`docs/fixtures/` when the dashboard is the source.

## Part 2 — Physical Android Device Execution Rehearsal

Builds on `docs/android-worker-connectivity-rehearsal.md`, which verified the
worker ADB binary and host ADB-server control path without a device. This
rehearsal closes the remaining gap: device shell/data-plane verification and an
end-to-end special task run on real hardware.

### Preconditions

- One physical Android device with ADB over TCP enabled (`adb tcpip 5555`) or
  attached to the host ADB server (shared-server topology).
- The Compose stack running with the worker `extra_hosts` host-gateway mapping.
- `scripts/android-network-doctor.sh` available in the worker container.

### Rehearsal Procedure

1. Connectivity: run the network doctor in the chosen topology — direct mode,
   or shared-server mode with `ADB_SKIP_SERVER_RESTART=true` and
   `ADB_SKIP_CONNECT=true` plus `ADB_SERVER_SOCKET`. Record full output.
2. Data plane: from the worker container run `adb -s <serial> shell getprop`
   and one `dumpsys meminfo <package>` sample; confirm parseable output.
3. End to end: create a performance-type special task against the device scope,
   trigger it, and let it complete.
4. Verify results: run status `completed`, metric sample count > 0, incident
   table readable (may be empty), CSV and JSON report exports both succeed.

### Required Record Fields

| Field | Requirement |
|-------|-------------|
| Device | Model, Android version, serial (may be masked to last 4) |
| Topology | Direct device TCP or shared host ADB server, with env vars used |
| Doctor output | Full pass/fail lines; any skipped step needs its reason |
| Run identity | Special task id, run id, trigger type, duration |
| Data volume | Metric sample count per metric type; incident count |
| Artifacts | Exported CSV/JSON names and sizes; screenshot/log artifacts if any |
| Anomalies | Retries, disconnects, or manual interventions (may be none) |

### Pass Criteria

- Doctor reports success for every non-skipped step; skips are explained.
- The end-to-end run reaches `completed` with at least one metric sample.
- Both report exports download successfully.

### Evidence Location

`docs/android-device-rehearsal-<date>.md`, linked from the release evidence
document current at capture time.

## Status

Both captures are blocked on environment access (a long-lived scraped
deployment; a physical device). The formats above are frozen so either capture
can be executed and reviewed without further scoping.
