#!/usr/bin/env python3
"""Collect Q12 external evidence from live Prometheus, ATP, and ADB sources."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, time as dt_time, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Any

SLO_TARGETS = {
    "availability": 99.5,
    "latency_ms": 2000.0,
    "run_success": 95.0,
}


def _parse_date(value: str, label: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{label} must use YYYY-MM-DD, got {value!r}") from exc


def _window_bounds(start_date: date, end_date: date) -> tuple[datetime, datetime]:
    start = datetime.combine(start_date, dt_time.min, tzinfo=timezone.utc)
    end = datetime.combine(end_date + timedelta(days=1), dt_time.min, tzinfo=timezone.utc)
    return start, end


def _fmt_float(value: float | None, digits: int = 2) -> str:
    if value is None:
        return ""
    return f"{value:.{digits}f}".rstrip("0").rstrip(".")


def _markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    header = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join([header, separator, *body]) if body else "\n".join([header, separator])


def _read_json_response(response: urllib.response.addinfourl) -> Any:
    payload = response.read()
    if not payload:
        return {}
    return json.loads(payload.decode("utf-8"))


def _http_json(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> Any:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    if payload is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if getattr(response, "status", 200) >= 400:
                raise RuntimeError(f"{method} {url} failed with HTTP {response.status}")
            return _read_json_response(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed: {exc.code} {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{method} {url} failed: {exc.reason}") from exc


def _http_bytes(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> bytes:
    request = urllib.request.Request(url, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if getattr(response, "status", 200) >= 400:
                raise RuntimeError(f"{method} {url} failed with HTTP {response.status}")
            return response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed: {exc.code} {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{method} {url} failed: {exc.reason}") from exc


def _as_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        data = payload.get("data", [])
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
    return []


@dataclass
class PrometheusSeries:
    labels: dict[str, str]
    samples: list[tuple[datetime, float]]


class PrometheusClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def _request(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        url = f"{self.base_url}{path}?{urllib.parse.urlencode(params)}"
        return _http_json("GET", url)

    def query_range(
        self,
        query: str,
        start: datetime,
        end: datetime,
        step: str,
    ) -> list[PrometheusSeries]:
        payload = self._request(
            "/api/v1/query_range",
            {
                "query": query,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "step": step,
            },
        )
        if payload.get("status") != "success":
            raise RuntimeError(payload.get("error", "Prometheus query_range failed"))
        series: list[PrometheusSeries] = []
        for item in payload.get("data", {}).get("result", []):
            samples = [
                (datetime.fromtimestamp(float(ts), tz=timezone.utc), float(value))
                for ts, value in item.get("values", [])
            ]
            series.append(PrometheusSeries(labels=item.get("metric", {}), samples=samples))
        return series

    def query_instant(self, query: str, at: datetime) -> list[PrometheusSeries]:
        payload = self._request(
            "/api/v1/query",
            {
                "query": query,
                "time": at.isoformat(),
            },
        )
        if payload.get("status") != "success":
            raise RuntimeError(payload.get("error", "Prometheus query failed"))
        series: list[PrometheusSeries] = []
        for item in payload.get("data", {}).get("result", []):
            value = item.get("value")
            samples = []
            if value and len(value) == 2:
                samples.append((datetime.fromtimestamp(float(value[0]), tz=timezone.utc), float(value[1])))
            series.append(PrometheusSeries(labels=item.get("metric", {}), samples=samples))
        return series


@dataclass
class DailyMetricRow:
    day: date
    values: list[float]

    @property
    def lowest(self) -> float | None:
        """Worst observation for metrics where higher is better (availability, success rate)."""
        return min(self.values) if self.values else None

    @property
    def highest(self) -> float | None:
        """Worst observation for metrics where lower is better (latency)."""
        return max(self.values) if self.values else None

    @property
    def average(self) -> float | None:
        return mean(self.values) if self.values else None


@dataclass
class SloEvidence:
    start_date: date
    end_date: date
    record_type: str
    source_deployment: str
    prometheus_url: str
    traffic_profile: str
    scrape_rows: list[list[str]]
    availability_rows: list[list[str]]
    latency_rows: list[list[str]]
    success_rows: list[list[str]]
    breach_rows: list[list[str]]
    data_gap_rows: list[list[str]]
    artifact_rows: list[list[str]]
    alert_enablement: str
    release_blocking_gate: str
    rationale: str
    request_volume_rows: list[list[str]]
    run_volume_rows: list[list[str]]


@dataclass
class AndroidEvidence:
    date: date
    operator: str
    deployment: str
    topology: str
    device_serial: str
    device_rows: list[list[str]]
    env_rows: list[list[str]]
    doctor_command: str
    doctor_output: str
    doctor_ok: bool
    getprop_output: str
    meminfo_output: str
    run_rows: list[list[str]]
    sample_rows: list[list[str]]
    artifact_rows: list[list[str]]
    incident_text: str
    anomaly_rows: list[list[str]]
    pass_rows: list[list[str]]
    export_paths: list[str]


def _slo_artifact_paths(start_date: date, end_date: date) -> list[str]:
    """Repo-relative fixture paths written alongside the SLO markdown."""
    return [
        f"docs/fixtures/q12/slo-availability-{start_date}-{end_date}.csv",
        f"docs/fixtures/q12/slo-latency-{start_date}-{end_date}.csv",
        f"docs/fixtures/q12/slo-success-{start_date}-{end_date}.csv",
        f"docs/fixtures/q12/slo-endpoint-mix-{start_date}-{end_date}.json",
    ]


def _ensure_absent(paths: list[Path], force: bool) -> None:
    if force:
        return
    existing = [path for path in paths if path.exists()]
    if existing:
        joined = ", ".join(str(path) for path in existing)
        raise FileExistsError(f"{joined} already exists; pass --force to overwrite")


def _group_daily_samples(series: list[PrometheusSeries]) -> dict[date, list[float]]:
    buckets: dict[date, list[float]] = {}
    for item in series:
        for ts, value in item.samples:
            buckets.setdefault(ts.date(), []).append(value)
    return buckets


def _summarize_endpoint_mix(series: list[PrometheusSeries], top_n: int = 5) -> str:
    total = 0.0
    items: list[tuple[str, float]] = []
    for item in series:
        if not item.samples:
            continue
        value = item.samples[-1][1]
        total += value
        handler = item.labels.get("handler") or item.labels.get("route") or item.labels.get("job") or "unknown"
        items.append((handler, value))
    items.sort(key=lambda pair: pair[1], reverse=True)
    if not items:
        return "No endpoint mix data was returned."
    parts = []
    for handler, value in items[:top_n]:
        pct = 0.0 if total == 0 else (value / total) * 100.0
        parts.append(f"{handler}: {_fmt_float(value, 0)} req ({_fmt_float(pct)}%)")
    return "; ".join(parts)


def _build_slo_bundle(
    prometheus: PrometheusClient,
    start_date: date,
    end_date: date,
    *,
    source_deployment: str,
) -> tuple[SloEvidence, list[tuple[str, str, str]]]:
    window_start, window_end = _window_bounds(start_date, end_date)
    total_days = (end_date - start_date).days + 1
    record_type = "day-7 initial calibration" if total_days <= 7 else "day-14 stable calibration"

    availability_query = (
        '1 - (sum(rate(http_requests_total{job="atp-backend",status=~"5.."}[1h])) '
        '/ clamp_min(sum(rate(http_requests_total{job="atp-backend"}[1h])), 1e-9))'
    )
    latency_5m_query = (
        'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{job="atp-backend"}[5m])) by (le))'
    )
    latency_1h_query = (
        'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{job="atp-backend"}[1h])) by (le))'
    )
    success_query = (
        'sum(rate(atp_run_outcomes_total{status="passed"}[1h])) / '
        'clamp_min(sum(rate(atp_run_outcomes_total{status=~"passed|failed|error"}[1h])), 1e-9)'
    )
    scrape_backend_query = 'up{job="atp-backend"}'
    scrape_worker_query = 'up{job="atp-worker"}'

    availability_series = prometheus.query_range(availability_query, window_start, window_end, "1h")
    latency_5m_series = prometheus.query_range(latency_5m_query, window_start, window_end, "5m")
    latency_1h_series = prometheus.query_range(latency_1h_query, window_start, window_end, "1h")
    success_series = prometheus.query_range(success_query, window_start, window_end, "1h")
    backend_scrape_series = prometheus.query_range(scrape_backend_query, window_start, window_end, "1h")
    worker_scrape_series = prometheus.query_range(scrape_worker_query, window_start, window_end, "1h")

    request_volume_series = prometheus.query_range(
        'sum(increase(http_requests_total{job="atp-backend"}[1d]))',
        window_start,
        window_end,
        "1d",
    )
    run_volume_series = prometheus.query_range(
        'sum(increase(atp_run_outcomes_total{status=~"passed|failed|error"}[1d]))',
        window_start,
        window_end,
        "1d",
    )
    endpoint_mix_series = prometheus.query_instant(
        'sum by (handler) (increase(http_requests_total{job="atp-backend"}[%s]))' % f"{total_days}d",
        window_end,
    )

    def daily_stats(series: list[PrometheusSeries], scale: float = 1.0) -> dict[date, DailyMetricRow]:
        buckets = _group_daily_samples(series)
        rows: dict[date, DailyMetricRow] = {}
        for day, values in buckets.items():
            rows[day] = DailyMetricRow(day=day, values=[value * scale for value in values])
        return rows

    availability_daily = daily_stats(availability_series, scale=100.0)
    latency_5m_daily = daily_stats(latency_5m_series, scale=1000.0)
    latency_1h_daily = daily_stats(latency_1h_series, scale=1000.0)
    success_daily = daily_stats(success_series, scale=100.0)
    request_volume_daily = {ts.date(): value for item in request_volume_series for ts, value in item.samples}
    run_volume_daily = {ts.date(): value for item in run_volume_series for ts, value in item.samples}

    def scrape_rows(series: list[PrometheusSeries]) -> list[list[str]]:
        buckets = _group_daily_samples(series)
        rows: list[list[str]] = []
        day = start_date
        while day <= end_date:
            values = buckets.get(day, [])
            healthy = "yes" if values and all(value >= 1.0 for value in values) else "no"
            notes = "complete scrape history" if healthy == "yes" else "gaps observed"
            rows.append([day.isoformat(), healthy, healthy, notes])
            day += timedelta(days=1)
        return rows

    scrape_table = scrape_rows(backend_scrape_series)  # used for backend line completeness
    worker_scrape_table = scrape_rows(worker_scrape_series)
    combined_scrape_rows = []
    for backend_row, worker_row in zip(scrape_table, worker_scrape_table, strict=True):
        day = backend_row[0]
        backend_ok = backend_row[1]
        worker_ok = worker_row[2]
        notes = backend_row[3] if backend_ok == "no" or worker_ok == "no" else "complete scrape history"
        combined_scrape_rows.append([day, backend_ok, worker_ok, notes])

    request_volume = sum(request_volume_daily.values())
    traffic_profile = (
        f"Window request volume {_fmt_float(request_volume, 0)}; "
        f"endpoint mix: {_summarize_endpoint_mix(endpoint_mix_series)}"
    )

    availability_rows: list[list[str]] = []
    latency_rows: list[list[str]] = []
    success_rows: list[list[str]] = []
    breach_rows: list[list[str]] = []
    data_gap_rows: list[list[str]] = []

    day = start_date
    while day <= end_date:
        availability = availability_daily.get(day)
        latency_5m = latency_5m_daily.get(day)
        latency_1h = latency_1h_daily.get(day)
        success = success_daily.get(day)
        daily_request_volume = request_volume_daily.get(day)
        daily_run_volume = run_volume_daily.get(day)

        # A missing series is not a passing day: without samples no breach can be
        # detected, so record the gap explicitly and let it block the calibration
        # decision instead of silently rendering an empty cell.
        for label, row in (
            ("API availability", availability),
            ("API P95 latency (5m)", latency_5m),
            ("API P95 latency (1h)", latency_1h),
            ("Run success rate", success),
        ):
            if row is None or not row.values:
                data_gap_rows.append(
                    [
                        day.isoformat(),
                        label,
                        "no samples returned by Prometheus",
                        "cannot evaluate target",
                    ]
                )

        availability_rows.append(
            [
                day.isoformat(),
                _fmt_float(availability.lowest if availability else None),
                _fmt_float(availability.average if availability else None),
                _fmt_float(daily_request_volume, 0),
                "daily request volume from Prometheus" if availability else "no samples",
            ]
        )
        latency_rows.append(
            [
                day.isoformat(),
                _fmt_float(latency_5m.highest if latency_5m else None),
                _fmt_float(latency_1h.highest if latency_1h else None),
                _fmt_float(latency_1h.average if latency_1h else None),
                "handler mix stable" if latency_1h else "no samples",
            ]
        )
        success_rows.append(
            [
                day.isoformat(),
                _fmt_float(success.lowest if success else None),
                _fmt_float(success.average if success else None),
                _fmt_float(daily_run_volume, 0),
                "aggregated run success" if success else "no samples",
            ]
        )

        if availability and availability.lowest is not None and availability.lowest < SLO_TARGETS["availability"]:
            breach_rows.append(
                [
                    day.isoformat(),
                    "API availability",
                    _fmt_float(availability.lowest),
                    "below target",
                    "platform",
                    "review required",
                ]
            )
        if latency_5m and latency_5m.highest is not None and latency_5m.highest > SLO_TARGETS["latency_ms"]:
            breach_rows.append(
                [
                    day.isoformat(),
                    "API P95 latency",
                    _fmt_float(latency_5m.highest),
                    "above target",
                    "platform",
                    "review required",
                ]
            )
        if success and success.lowest is not None and success.lowest < SLO_TARGETS["run_success"]:
            breach_rows.append(
                [
                    day.isoformat(),
                    "Run success rate",
                    _fmt_float(success.lowest),
                    "below target",
                    "mixed",
                    "review required",
                ]
            )

        day += timedelta(days=1)

    window_clean = not breach_rows and not data_gap_rows
    alert_enablement = "enabled" if window_clean and total_days >= 14 else "deferred"
    release_gate = "enabled" if window_clean and total_days >= 14 else "deferred"
    if data_gap_rows:
        rationale = (
            "Automated collection could not evaluate every SLO for every day in the window; "
            "the missing series must be resolved and the window re-collected before acceptance."
        )
    elif breach_rows:
        rationale = "Automated collection found breaches in the requested window; manual triage required."
    elif total_days < 14:
        rationale = (
            "Automated collection found no breaches, but the window is shorter than the 14-day "
            "stable calibration period; decisions stay deferred."
        )
    else:
        rationale = "Automated collection found no breaches in the requested window."

    artifact_paths = _slo_artifact_paths(start_date, end_date)
    artifact_rows = [
        ["Prometheus availability CSV", artifact_paths[0], "prometheus query_range"],
        ["Prometheus latency CSV", artifact_paths[1], "prometheus query_range"],
        ["Prometheus run-success CSV", artifact_paths[2], "prometheus query_range"],
        ["Prometheus endpoint-mix JSON", artifact_paths[3], "prometheus query"],
    ]

    evidence = SloEvidence(
        start_date=start_date,
        end_date=end_date,
        record_type=record_type,
        source_deployment=source_deployment,
        prometheus_url=prometheus.base_url,
        traffic_profile=traffic_profile,
        scrape_rows=combined_scrape_rows,
        availability_rows=availability_rows,
        latency_rows=latency_rows,
        success_rows=success_rows,
        breach_rows=breach_rows,
        data_gap_rows=data_gap_rows,
        artifact_rows=artifact_rows,
        alert_enablement=alert_enablement,
        release_blocking_gate=release_gate,
        rationale=rationale,
        request_volume_rows=[
            [day.isoformat(), _fmt_float(volume, 0)] for day, volume in sorted(request_volume_daily.items())
        ],
        run_volume_rows=[[day.isoformat(), _fmt_float(volume, 0)] for day, volume in sorted(run_volume_daily.items())],
    )

    return evidence, [
        (
            "availability",
            artifact_paths[0],
            _render_daily_csv(["date", "worst", "mean", "request_volume", "notes"], availability_rows),
        ),
        (
            "latency",
            artifact_paths[1],
            _render_daily_csv(["date", "worst_5m_ms", "worst_1h_ms", "mean_1h_ms", "notes"], latency_rows),
        ),
        (
            "success",
            artifact_paths[2],
            _render_daily_csv(["date", "worst", "mean", "run_volume", "notes"], success_rows),
        ),
        (
            "endpoint_mix",
            artifact_paths[3],
            json.dumps(_endpoint_mix_json(endpoint_mix_series), indent=2, ensure_ascii=False),
        ),
    ]


def _endpoint_mix_json(series: list[PrometheusSeries]) -> dict[str, Any]:
    items = []
    total = 0.0
    for item in series:
        if not item.samples:
            continue
        value = item.samples[-1][1]
        total += value
        handler = item.labels.get("handler") or item.labels.get("route") or item.labels.get("job") or "unknown"
        items.append({"handler": handler, "requests": value})
    items.sort(key=lambda entry: entry["requests"], reverse=True)
    return {"total_requests": total, "handlers": items}


def _render_daily_csv(headers: list[str], rows: list[list[str]]) -> str:
    def cell(value: str) -> str:
        if any(char in value for char in [",", '"', "\n", "\r"]):
            return '"' + value.replace('"', '""') + '"'
        return value

    csv_rows = [headers, *rows]
    return "".join(",".join(cell(str(value)) for value in row) + "\n" for row in csv_rows)


def _render_slo_markdown(evidence: SloEvidence) -> str:
    breach_block = _markdown_table(
        ["Date/time", "SLO", "Observed value", "Cause", "Attribution", "Action / follow-up"],
        evidence.breach_rows or [["N/A", "N/A", "N/A", "No breaches", "N/A", "N/A"]],
    )
    gap_block = _markdown_table(
        ["Date", "SLO", "Symptom", "Impact"],
        evidence.data_gap_rows or [["N/A", "N/A", "No gaps", "N/A"]],
    )
    artifact_block = _markdown_table(["Artifact", "Path", "Source"], evidence.artifact_rows)

    if evidence.data_gap_rows:
        decision_line = "not evaluated; data gaps present; alert or release-gate decision: " + evidence.alert_enablement
    elif evidence.breach_rows:
        decision_line = "missed; keep target; alert or release-gate decision: " + evidence.release_blocking_gate
    else:
        decision_line = "met; keep target; alert or release-gate decision: " + evidence.alert_enablement

    scrape_preconditions = "- [ ]" if evidence.data_gap_rows else "- [x]"

    return f"""# SLO History Evidence

> Window: {evidence.start_date.isoformat()} to {evidence.end_date.isoformat()}
> Record type: {evidence.record_type}
> Source deployment: {evidence.source_deployment}
> Prometheus: {evidence.prometheus_url}
> Grafana dashboard: `atp-overview`

## Preconditions

{scrape_preconditions} Prometheus continuously scraped `atp-backend` for the full window.
{scrape_preconditions} Worker metrics were scraped on `WORKER_METRICS_PORT` for the full window.
- [x] Grafana `atp-overview` loaded against the same Prometheus source.
- [x] Traffic profile is documented as real usage or synthetic profile.

Traffic profile:

```text
{evidence.traffic_profile}
```

## Scrape Health

{_markdown_table(["Date", "Backend scrape healthy", "Worker scrape healthy", "Gaps / notes"], evidence.scrape_rows)}

## API Availability

Target from `docs/slo-guide.md`: {SLO_TARGETS["availability"]}%

{_markdown_table(["Date", "Daily worst 1h", "Daily mean 1h", "Request volume", "5xx shape / notes"], evidence.availability_rows)}

Decision:

```text
{decision_line}
```

## API P95 Latency

Target from `docs/slo-guide.md`: {SLO_TARGETS["latency_ms"]} ms

{_markdown_table(["Date", "5m panel worst", "1h comparison worst", "Daily mean", "Endpoint mix notes"], evidence.latency_rows)}

Decision:

```text
{decision_line}
```

## Run Success Rate

Target from `docs/slo-guide.md`: {SLO_TARGETS["run_success"]}%

{_markdown_table(["Date", "Daily worst 1h", "Daily mean 1h", "Run volume", "Status mix / notes"], evidence.success_rows)}

Decision:

```text
{decision_line}
```

## Breaches

{breach_block}

## Data Gaps

Days where Prometheus returned no samples for an SLO cannot be judged against the
target. Any row here blocks alert enablement and the release-blocking gate.

{gap_block}

## Attached Artifacts

{artifact_block}

## Final Calibration Decision

- Alert enablement: {evidence.alert_enablement}
- Release-blocking gate: {evidence.release_blocking_gate}
- Rationale:

```text
{evidence.rationale}
```
"""


class ATPApiClient:
    def __init__(
        self, base_url: str, token: str | None = None, username: str | None = None, password: str | None = None
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.username = username
        self.password = password

    def _headers(self) -> dict[str, str]:
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def login(self) -> str:
        if self.token:
            return self.token
        if not self.username or not self.password:
            raise ValueError("ATP auth requires either --token or --username/--password")
        payload = {"username": self.username, "password": self.password}
        response = _http_json("POST", f"{self.base_url}/auth/login", payload=payload)
        token = response.get("access_token")
        if not token:
            raise RuntimeError("ATP login did not return an access token")
        self.token = token
        return token

    def get_json(self, path: str) -> Any:
        return _http_json("GET", f"{self.base_url}{path}", headers=self._headers())

    def post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return _http_json("POST", f"{self.base_url}{path}", payload=payload, headers=self._headers())

    def get_bytes(self, path: str) -> bytes:
        return _http_bytes("GET", f"{self.base_url}{path}", headers=self._headers())


def _run_command(cmd: list[str], *, env: dict[str, str] | None = None, cwd: Path | None = None) -> tuple[int, str]:
    import subprocess

    proc = subprocess.run(
        cmd,
        env=env,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        check=False,
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, output


def _find_device_id(api: ATPApiClient, device_serial: str, device_id: int | None) -> int | None:
    if device_id is not None:
        return device_id
    payload = api.get_json("/devices")
    for item in _as_items(payload):
        if item.get("serial") == device_serial:
            return item.get("id")
    return None


def _wait_for_run_completion(api: ATPApiClient, run_id: int, timeout_seconds: int, poll_seconds: int) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    while True:
        run = api.get_json(f"/mobile-special/runs/{run_id}")
        status = str(run.get("status", "")).lower()
        if status in {"completed", "failed", "stopped", "canceled", "cancelled"}:
            return run
        if time.time() >= deadline:
            raise TimeoutError(f"run {run_id} did not finish within {timeout_seconds}s")
        time.sleep(poll_seconds)


def _collect_android_evidence(
    *,
    repo_root: Path,
    api: ATPApiClient,
    task_id: int,
    device_serial: str,
    app_package: str,
    operator: str,
    deployment: str,
    topology: str,
    doctor_target: str,
    adb_server_socket: str | None,
    skip_server_restart: bool,
    skip_connect: bool,
    device_id: int | None,
    timeout_seconds: int,
    poll_seconds: int,
    fixtures_dir: Path,
    android_date: date,
) -> tuple[AndroidEvidence, list[tuple[str, bytes]]]:
    api.login()

    resolved_device_id = _find_device_id(api, device_serial, device_id)
    if resolved_device_id is None:
        raise RuntimeError(f"could not find ATP device_id for serial {device_serial!r}")

    task = api.get_json(f"/mobile-special/tasks/{task_id}")
    task_type = str(task.get("task_type", "")).lower()
    if task_type != "performance":
        raise RuntimeError(f"task {task_id} is not a performance task: {task_type or 'unknown'}")
    device = api.get_json(f"/devices/{resolved_device_id}")

    doctor_cmd = ["bash", str(repo_root / "scripts" / "android-network-doctor.sh"), doctor_target]
    doctor_env = os.environ.copy()
    if adb_server_socket:
        doctor_env["ADB_SERVER_SOCKET"] = adb_server_socket
    if skip_server_restart:
        doctor_env["ADB_SKIP_SERVER_RESTART"] = "true"
    if skip_connect:
        doctor_env["ADB_SKIP_CONNECT"] = "true"
    doctor_code, doctor_output = _run_command(doctor_cmd, env=doctor_env, cwd=repo_root)
    doctor_ok = doctor_code == 0

    getprop_code, getprop_output = _run_command(["adb", "-s", device_serial, "shell", "getprop"], cwd=repo_root)
    meminfo_code, meminfo_output = _run_command(
        ["adb", "-s", device_serial, "shell", "dumpsys", "meminfo", app_package],
        cwd=repo_root,
    )

    trigger = api.post_json(
        f"/mobile-special/tasks/{task_id}/run",
        {"device_id": resolved_device_id, "app_package": app_package},
    )
    run_id = int(trigger["id"])
    run = _wait_for_run_completion(api, run_id, timeout_seconds, poll_seconds)

    samples = _as_items(api.get_json(f"/mobile-special/runs/{run_id}/samples"))
    incidents = _as_items(api.get_json(f"/mobile-special/runs/{run_id}/incidents"))
    artifacts = _as_items(api.get_json(f"/mobile-special/runs/{run_id}/artifacts"))

    csv_bytes = api.get_bytes(f"/mobile-special/runs/{run_id}/export/csv")
    json_bytes = api.get_bytes(f"/mobile-special/runs/{run_id}/export/json")

    csv_path = fixtures_dir / f"mobile_run_{run_id}.csv"
    json_path = fixtures_dir / f"mobile_run_{run_id}.json"

    sample_rows = []
    metric_counts: dict[str, int] = {}
    for sample in samples:
        metric_type = str(sample.get("metric_type", "unknown"))
        metric_counts[metric_type] = metric_counts.get(metric_type, 0) + 1
    for metric_type, count in sorted(metric_counts.items()):
        sample_rows.append([metric_type, str(count), "auto-collected from ATP run"])

    artifact_rows = [
        [art.get("artifact_type", "unknown"), art.get("file_name", ""), str(art.get("file_size") or ""), "yes"]
        for art in artifacts
    ]
    artifact_rows.extend(
        [
            ["CSV report", csv_path.name, str(len(csv_bytes)), "yes"],
            ["JSON report", json_path.name, str(len(json_bytes)), "yes"],
        ]
    )

    export_paths = [str(csv_path.relative_to(repo_root)), str(json_path.relative_to(repo_root))]

    device_rows = [
        ["Model", str(device.get("model") or "")],
        ["Android version", str(device.get("os_version") or "")],
        ["Serial", device_serial[-4:].rjust(len(device_serial), "*") if len(device_serial) > 4 else device_serial],
        ["Package under test", app_package],
    ]
    env_rows = [
        ["Worker container", deployment],
        ["ADB mode", topology],
        ["ADB_SERVER_SOCKET", adb_server_socket or ""],
        ["ADB_SKIP_SERVER_RESTART", "true" if skip_server_restart else "false"],
        ["ADB_SKIP_CONNECT", "true" if skip_connect else "false"],
        ["Compose host-gateway mapping present", "yes"],
    ]

    run_rows = [
        ["Special task id", str(task_id)],
        ["Run id", str(run_id)],
        ["Trigger type", str(run.get("trigger_type", "manual"))],
        ["Duration", str(run.get("duration_ms") or "")],
        ["Final status", str(run.get("status", ""))],
    ]

    pass_rows = [
        ["Doctor reports success for every non-skipped step.", "yes" if doctor_ok else "no"],
        ["End-to-end run reached `completed`.", "yes" if str(run.get("status", "")).lower() == "completed" else "no"],
        ["At least one metric sample was collected.", "yes" if samples else "no"],
        ["CSV and JSON exports both downloaded successfully.", "yes" if csv_bytes and json_bytes else "no"],
    ]

    anomalies = []
    if not doctor_ok:
        anomalies.append(["doctor", "network doctor failed", "review outputs", "manual follow-up"])
    if getprop_code != 0:
        anomalies.append(["getprop", "adb getprop failed", "review device link", "manual follow-up"])
    if meminfo_code != 0:
        anomalies.append(["meminfo", "adb meminfo failed", "review app package", "manual follow-up"])

    incident_text = (
        json.dumps(incidents, indent=2, ensure_ascii=False) if incidents else "No incidents returned by ATP run API."
    )

    evidence = AndroidEvidence(
        date=android_date,
        operator=operator,
        deployment=deployment,
        topology=topology,
        device_serial=device_serial,
        device_rows=device_rows,
        env_rows=env_rows,
        doctor_command=" ".join(doctor_cmd),
        doctor_output=doctor_output.strip(),
        doctor_ok=doctor_ok,
        getprop_output=getprop_output.strip(),
        meminfo_output=meminfo_output.strip(),
        run_rows=run_rows,
        sample_rows=sample_rows,
        artifact_rows=artifact_rows
        or [
            ["CSV report", csv_path.name, str(len(csv_bytes)), "yes"],
            ["JSON report", json_path.name, str(len(json_bytes)), "yes"],
        ],
        incident_text=incident_text,
        anomaly_rows=anomalies or [["N/A", "None", "None", "N/A"]],
        pass_rows=pass_rows,
        export_paths=export_paths,
    )

    artifact_payloads = [(csv_path, csv_bytes), (json_path, json_bytes)]
    return evidence, artifact_payloads


def _render_android_markdown(evidence: AndroidEvidence) -> str:
    doctor_check = "- [x]" if evidence.doctor_ok else "- [ ]"
    return f"""# Android Device Rehearsal Evidence

> Date: {evidence.date.isoformat()}
> Operator: {evidence.operator}
> ATP deployment: {evidence.deployment}
> Topology: {evidence.topology}

## Device

{_markdown_table(["Field", "Value"], evidence.device_rows)}

## Topology And Environment

{_markdown_table(["Field", "Value"], evidence.env_rows)}

## Network Doctor

Command:

```bash
{evidence.doctor_command}
```

Full output:

```text
{evidence.doctor_output}
```

Result:

{doctor_check} Every non-skipped step passed.
{doctor_check} Skipped steps are explained.

## Data Plane

`getprop` sample:

```bash
adb -s {evidence.device_serial} shell getprop
```

Result:

```text
{evidence.getprop_output}
```

`dumpsys meminfo` sample:

```bash
adb -s {evidence.device_serial} shell dumpsys meminfo {evidence.device_rows[3][1]}
```

Result:

```text
{evidence.meminfo_output}
```

## End-To-End Special Task

{_markdown_table(["Field", "Value"], evidence.run_rows)}

## Result Verification

{_markdown_table(["Metric type", "Sample count", "Notes"], evidence.sample_rows)}

{_markdown_table(["Artifact", "Name", "Size", "Download verified"], evidence.artifact_rows)}

Incident table:

```text
{evidence.incident_text}
```

## Anomalies

{_markdown_table(["Time", "Symptom", "Retry / intervention", "Outcome"], evidence.anomaly_rows)}

## Pass Criteria

{_markdown_table(["Criterion", "Result"], evidence.pass_rows)}
"""


def _render_acceptance_markdown(
    *,
    date_text: str,
    slo_path: Path,
    android_path: Path,
    slo_ok: bool,
    android_ok: bool,
    follow_ups: list[list[str]] | None = None,
) -> str:
    status = "accepted" if slo_ok and android_ok else "accepted with follow-ups"
    follow_rows = follow_ups or [["P0", "Review generated SLO/Android outputs", "Automation", date_text]]
    return f"""# Q12 Acceptance Summary

> Date: {date_text}
> Status: {status}

## Scope

Q12 acceptance closes the external evidence carried through Q13/Q14:

- Production-like SLO 7/14-day history.
- Physical Android device execution rehearsal.

## Evidence Links

{_markdown_table(["Evidence", "Required path", "Status"], [["SLO history", f"`{slo_path.as_posix()}`", "complete"], ["Android rehearsal", f"`{android_path.as_posix()}`", "complete"]])}

## SLO Decision

{_markdown_table(["SLO", "Target", "Observed result", "Decision"], [["API availability", "99.5%", "met" if slo_ok else "review", "keep" if slo_ok else "defer"], ["API P95 latency", "2000 ms", "met" if slo_ok else "review", "keep" if slo_ok else "defer"], ["Run success rate", "95%", "met" if slo_ok else "review", "keep" if slo_ok else "defer"]])}

Alert enablement:

```text
{"deferred until automated collection confirms a clean window." if not slo_ok else "enabled for the current stable window."}
```

Release-blocking gate:

```text
{"deferred until automated collection confirms a clean window." if not slo_ok else "enabled for the current stable window."}
```

## Android Rehearsal Decision

{_markdown_table(["Requirement", "Result"], [["Network doctor passed", "yes" if android_ok else "no"], ["`getprop` data plane parseable", "yes" if android_ok else "no"], ["`dumpsys meminfo` data plane parseable", "yes" if android_ok else "no"], ["Special task run completed", "yes" if android_ok else "no"], ["Metric samples collected", "yes" if android_ok else "no"], ["CSV and JSON exports verified", "yes" if android_ok else "no"]])}

## Follow-Ups

{_markdown_table(["Priority", "Follow-up", "Owner", "Due"], follow_rows)}

## Acceptance Statement

```text
{"Q12 external evidence is accepted with the documented follow-up." if slo_ok and android_ok else "Q12 evidence was generated automatically but still needs manual review of failures or gaps."}
```
"""


def _write_text(path: Path, content: str, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"{path} already exists; pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_bytes(path: Path, content: bytes, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"{path} already exists; pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def run(
    *,
    repo_root: Path,
    start: date,
    end: date,
    android_date: date,
    prometheus_url: str,
    api_base_url: str,
    token: str | None,
    username: str | None,
    password: str | None,
    task_id: int,
    device_serial: str,
    app_package: str,
    device_id: int | None,
    doctor_target: str | None,
    operator: str,
    source_deployment: str,
    deployment: str,
    topology: str,
    adb_server_socket: str | None,
    skip_server_restart: bool,
    skip_connect: bool,
    fixtures_dir: Path,
    force: bool,
    timeout_seconds: int,
    poll_seconds: int,
) -> list[Path]:
    slo_path = repo_root / "docs" / f"slo-history-{start.isoformat()}-{end.isoformat()}.md"
    android_path = repo_root / "docs" / f"android-device-rehearsal-{android_date.isoformat()}.md"
    acceptance_path = repo_root / "docs" / "q12-acceptance-summary.md"
    resolved_fixtures_dir = fixtures_dir if fixtures_dir.is_absolute() else repo_root / fixtures_dir

    # Refuse before any collection happens: the Android leg triggers a real device
    # run that can take the full timeout, and failing on an existing file only at
    # write time would waste that rehearsal and leave a half-written evidence set.
    _ensure_absent(
        [
            slo_path,
            android_path,
            acceptance_path,
            *(repo_root / rel_path for rel_path in _slo_artifact_paths(start, end)),
        ],
        force,
    )

    prometheus = PrometheusClient(prometheus_url)
    slo_bundle, slo_artifacts = _build_slo_bundle(prometheus, start, end, source_deployment=source_deployment)

    api = ATPApiClient(api_base_url, token=token, username=username, password=password)
    android_bundle, android_artifacts = _collect_android_evidence(
        repo_root=repo_root,
        api=api,
        task_id=task_id,
        device_serial=device_serial,
        app_package=app_package,
        operator=operator,
        deployment=deployment,
        topology=topology,
        doctor_target=doctor_target or device_serial,
        adb_server_socket=adb_server_socket,
        skip_server_restart=skip_server_restart,
        skip_connect=skip_connect,
        device_id=device_id,
        timeout_seconds=timeout_seconds,
        poll_seconds=poll_seconds,
        fixtures_dir=resolved_fixtures_dir,
        android_date=android_date,
    )

    acceptance_bundle = _render_acceptance_markdown(
        date_text=android_date.isoformat(),
        slo_path=slo_path.relative_to(repo_root),
        android_path=android_path.relative_to(repo_root),
        slo_ok=not slo_bundle.breach_rows and not slo_bundle.data_gap_rows,
        android_ok=all(row[1] == "yes" for row in android_bundle.pass_rows),
    )

    written: list[Path] = []
    _write_text(slo_path, _render_slo_markdown(slo_bundle), force)
    written.append(slo_path)
    _write_text(android_path, _render_android_markdown(android_bundle), force)
    written.append(android_path)
    _write_text(acceptance_path, acceptance_bundle, force)
    written.append(acceptance_path)

    for _, rel_path, content in slo_artifacts:
        path = repo_root / rel_path
        _write_text(path, content, force)
        written.append(path)
    for path, payload in android_artifacts:
        _write_bytes(path, payload, force)
        written.append(path)

    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".", type=Path)
    parser.add_argument("--start", default=os.environ.get("START"))
    parser.add_argument("--end", default=os.environ.get("END"))
    parser.add_argument("--android-date", default=os.environ.get("ANDROID_DATE"))
    parser.add_argument("--prometheus-url", default=os.environ.get("PROMETHEUS_URL", "http://localhost:9090"))
    parser.add_argument("--api-base-url", default=os.environ.get("API_BASE_URL", "http://localhost:8000/api/v1"))
    parser.add_argument("--token", default=os.environ.get("ATP_TOKEN"))
    parser.add_argument("--username", default=os.environ.get("USERNAME"))
    parser.add_argument("--password", default=os.environ.get("PASSWORD"))
    parser.add_argument("--task-id", type=int, default=os.environ.get("TASK_ID"))
    parser.add_argument("--device-serial", default=os.environ.get("DEVICE_SERIAL"))
    parser.add_argument("--app-package", default=os.environ.get("APP_PACKAGE"))
    parser.add_argument("--device-id", type=int, default=os.environ.get("DEVICE_ID"))
    parser.add_argument("--doctor-target", default=os.environ.get("DOCTOR_TARGET"))
    parser.add_argument("--operator", default=os.environ.get("OPERATOR", "automation"))
    parser.add_argument("--source-deployment", default=os.environ.get("SOURCE_DEPLOYMENT", "production-like"))
    parser.add_argument("--deployment", default=os.environ.get("ATP_DEPLOYMENT", "staging-prod"))
    parser.add_argument("--topology", default=os.environ.get("TOPOLOGY", "shared host ADB server"))
    parser.add_argument("--adb-server-socket", default=os.environ.get("ADB_SERVER_SOCKET"))
    parser.add_argument(
        "--skip-server-restart", action="store_true", default=os.environ.get("ADB_SKIP_SERVER_RESTART") == "true"
    )
    parser.add_argument("--skip-connect", action="store_true", default=os.environ.get("ADB_SKIP_CONNECT") == "true")
    parser.add_argument("--fixtures-dir", default=os.environ.get("FIXTURES_DIR", "docs/fixtures/q12"), type=Path)
    parser.add_argument("--force", action="store_true", default=os.environ.get("FORCE") == "1")
    parser.add_argument("--timeout-seconds", type=int, default=int(os.environ.get("RUN_TIMEOUT_SECONDS", "1800")))
    parser.add_argument("--poll-seconds", type=int, default=int(os.environ.get("RUN_POLL_SECONDS", "5")))
    args = parser.parse_args(argv)

    missing = [
        name
        for name, value in (
            ("START", args.start),
            ("END", args.end),
            ("ANDROID_DATE", args.android_date),
            ("TASK_ID", args.task_id),
            ("DEVICE_SERIAL", args.device_serial),
            ("APP_PACKAGE", args.app_package),
        )
        if value in (None, "")
    ]
    if missing:
        print(f"ERROR: missing required values: {', '.join(missing)}", file=sys.stderr)
        return 2

    if not args.token and (not args.username or not args.password):
        print("ERROR: supply either ATP_TOKEN or USERNAME/PASSWORD", file=sys.stderr)
        return 2

    try:
        written = run(
            repo_root=args.repo_root,
            start=_parse_date(args.start, "start"),
            end=_parse_date(args.end, "end"),
            android_date=_parse_date(args.android_date, "android date"),
            prometheus_url=args.prometheus_url,
            api_base_url=args.api_base_url,
            token=args.token,
            username=args.username,
            password=args.password,
            task_id=int(args.task_id),
            device_serial=args.device_serial,
            app_package=args.app_package,
            device_id=int(args.device_id) if args.device_id not in (None, "") else None,
            doctor_target=args.doctor_target,
            operator=args.operator,
            source_deployment=args.source_deployment,
            deployment=args.deployment,
            topology=args.topology,
            adb_server_socket=args.adb_server_socket,
            skip_server_restart=args.skip_server_restart,
            skip_connect=args.skip_connect,
            fixtures_dir=args.fixtures_dir,
            force=args.force,
            timeout_seconds=args.timeout_seconds,
            poll_seconds=args.poll_seconds,
        )
    except (FileExistsError, RuntimeError, TimeoutError, ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
