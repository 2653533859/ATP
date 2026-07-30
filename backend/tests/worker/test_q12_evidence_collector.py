from __future__ import annotations

import importlib.util
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest


def _load_collector(repo_root: Path):
    script = repo_root / "scripts" / "collect-q12-evidence.py"
    spec = importlib.util.spec_from_file_location("collect_q12_evidence", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_validator(repo_root: Path):
    script = repo_root / "scripts" / "validate-q12-evidence.py"
    spec = importlib.util.spec_from_file_location("validate_q12_evidence", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _series(module, labels: dict[str, str], values: list[tuple[str, float]]):
    samples = [(datetime.fromisoformat(ts).replace(tzinfo=timezone.utc), value) for ts, value in values]
    return module.PrometheusSeries(labels=labels, samples=samples)


def test_collect_q12_evidence_writes_reports_and_artifacts(repo_root, tmp_path, monkeypatch):
    module = _load_collector(repo_root)

    class FakePrometheus:
        def __init__(self, base_url: str):
            self.base_url = base_url

        def query_range(self, query: str, start, end, step: str):
            if 'up{job="atp-backend"}' in query:
                return [_series(module, {}, [("2026-07-01T00:00:00", 1.0), ("2026-07-02T00:00:00", 1.0)])]
            if 'up{job="atp-worker"}' in query:
                return [_series(module, {}, [("2026-07-01T00:00:00", 1.0), ("2026-07-02T00:00:00", 1.0)])]
            if 'status=~"5.."' in query:
                return [_series(module, {}, [("2026-07-01T00:00:00", 0.998), ("2026-07-02T00:00:00", 0.999)])]
            if "http_request_duration_seconds_bucket" in query and "[5m]" in query:
                return [_series(module, {}, [("2026-07-01T00:00:00", 1.8), ("2026-07-02T00:00:00", 1.75)])]
            if "http_request_duration_seconds_bucket" in query and "[1h]" in query:
                return [_series(module, {}, [("2026-07-01T00:00:00", 1.7), ("2026-07-02T00:00:00", 1.65)])]
            if "atp_run_outcomes_total" in query and 'status="passed"' in query:
                return [_series(module, {}, [("2026-07-01T00:00:00", 0.96), ("2026-07-02T00:00:00", 0.97)])]
            if 'sum(increase(http_requests_total{job="atp-backend"}[1d]))' in query:
                return [_series(module, {}, [("2026-07-01T00:00:00", 100.0), ("2026-07-02T00:00:00", 120.0)])]
            if 'sum(increase(atp_run_outcomes_total{status=~"passed|failed|error"}[1d]))' in query:
                return [_series(module, {}, [("2026-07-01T00:00:00", 10.0), ("2026-07-02T00:00:00", 12.0)])]
            raise AssertionError(f"unexpected query_range: {query}")

        def query_instant(self, query: str, at):
            if 'sum(increase(http_requests_total{job="atp-backend"}' in query:
                return [_series(module, {}, [("2026-07-02T00:00:00", 220.0)])]
            if 'sum by (handler) (increase(http_requests_total{job="atp-backend"}' in query:
                return [
                    _series(module, {"handler": "/api/v1/cases"}, [("2026-07-02T00:00:00", 180.0)]),
                    _series(module, {"handler": "/api/v1/runs"}, [("2026-07-02T00:00:00", 40.0)]),
                ]
            raise AssertionError(f"unexpected query_instant: {query}")

    class FakeATPApi:
        def __init__(self, *args, **kwargs):
            self.runs = 0

        def login(self):
            return "token"

        def get_json(self, path: str):
            if path == "/devices":
                return [{"id": 42, "serial": "192.168.1.8:5555"}]
            if path == "/devices/42":
                return {"id": 42, "serial": "192.168.1.8:5555", "model": "Pixel 8", "os_version": "15"}
            if path == "/mobile-special/tasks/7":
                return {"id": 7, "task_type": "performance"}
            if path == "/mobile-special/runs/9":
                self.runs += 1
                if self.runs == 1:
                    return {"id": 9, "status": "pending"}
                return {
                    "id": 9,
                    "status": "completed",
                    "trigger_type": "manual",
                    "duration_ms": 412000,
                    "created_at": "2026-07-02T08:00:00+00:00",
                }
            if path == "/mobile-special/runs/9/samples":
                return [{"metric_type": "cpu_pct"}, {"metric_type": "mem_mb"}]
            if path == "/mobile-special/runs/9/incidents":
                return []
            if path == "/mobile-special/runs/9/artifacts":
                return {
                    "data": [{"artifact_type": "csv_report", "file_name": "mobile_run_9_metrics.csv", "file_size": 12}]
                }
            raise AssertionError(f"unexpected api get: {path}")

        def post_json(self, path: str, payload: dict):
            assert path == "/mobile-special/tasks/7/run"
            assert payload == {"device_id": 42, "app_package": "com.example.app"}
            return {"id": 9}

        def get_bytes(self, path: str):
            if path.endswith("/export/csv"):
                return b"id,run_id\n1,9\n"
            if path.endswith("/export/json"):
                return b'{"run":{"id":9}}'
            raise AssertionError(f"unexpected bytes path: {path}")

    def fake_run_command(cmd, *, env=None, cwd=None):
        if cmd[0] == "bash" and cmd[1].endswith("scripts/android-network-doctor.sh"):
            return 0, "[OK] all good"
        if cmd[:4] == ["adb", "-s", "192.168.1.8:5555", "shell"] and cmd[4] == "getprop":
            return 0, "[ro.product.model]: [Pixel 8]"
        if cmd[:4] == ["adb", "-s", "192.168.1.8:5555", "shell"] and cmd[4] == "dumpsys":
            return 0, "TOTAL PSS: 123456 KB"
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(module, "PrometheusClient", FakePrometheus)
    monkeypatch.setattr(module, "ATPApiClient", FakeATPApi)
    monkeypatch.setattr(module, "_run_command", fake_run_command)
    monkeypatch.setattr(module.time, "sleep", lambda *_args, **_kwargs: None)

    written = module.run(
        repo_root=tmp_path,
        start=date(2026, 7, 1),
        end=date(2026, 7, 2),
        android_date=date(2026, 7, 2),
        prometheus_url="http://prom",
        api_base_url="http://api",
        token="token",
        username=None,
        password=None,
        task_id=7,
        device_serial="192.168.1.8:5555",
        app_package="com.example.app",
        device_id=None,
        doctor_target="192.168.1.8:5555",
        operator="qa",
        source_deployment="staging-prod",
        deployment="staging-prod",
        topology="shared host ADB server",
        adb_server_socket="tcp:host.docker.internal:5037",
        skip_server_restart=True,
        skip_connect=True,
        fixtures_dir=tmp_path / "docs/fixtures/q12",
        force=True,
        timeout_seconds=10,
        poll_seconds=0,
    )

    assert (tmp_path / "docs/slo-history-2026-07-01-2026-07-02.md").exists()
    assert (tmp_path / "docs/android-device-rehearsal-2026-07-02.md").exists()
    assert (tmp_path / "docs/q12-acceptance-summary.md").exists()
    assert (tmp_path / "docs/fixtures/q12/mobile_run_9.csv").exists()
    assert (tmp_path / "docs/fixtures/q12/mobile_run_9.json").exists()
    assert any(path.name == "q12-acceptance-summary.md" for path in written)

    slo = (tmp_path / "docs/slo-history-2026-07-01-2026-07-02.md").read_text(encoding="utf-8")
    android = (tmp_path / "docs/android-device-rehearsal-2026-07-02.md").read_text(encoding="utf-8")
    acceptance = (tmp_path / "docs/q12-acceptance-summary.md").read_text(encoding="utf-8")

    assert "make collect-q12-evidence" not in slo
    assert "Window: 2026-07-01 to 2026-07-02" in slo
    assert "Pixel 8" in android
    assert "192.168.1.8:5555" in android
    assert "Q12 external evidence is accepted" in acceptance

    validator = _load_validator(repo_root)
    assert (
        validator.validate_all(
            tmp_path / "docs/slo-history-2026-07-01-2026-07-02.md",
            tmp_path / "docs/android-device-rehearsal-2026-07-02.md",
            tmp_path / "docs/q12-acceptance-summary.md",
        )
        == []
    )


class _StubPrometheus:
    """Serves one fixed value list per metric family for the whole window."""

    base_url = "http://prom"

    def __init__(self, *, availability, latency, success, day="2026-07-01"):
        self._availability = availability
        self._latency = latency
        self._success = success
        self._day = day

    def _series(self, module, values):
        samples = [
            (datetime.fromisoformat(f"{self._day}T{hour:02d}:00:00").replace(tzinfo=timezone.utc), value)
            for hour, value in enumerate(values)
        ]
        return [module.PrometheusSeries(labels={}, samples=samples)]

    def bind(self, module):
        self._module = module
        return self

    def query_range(self, query: str, start, end, step: str):
        if "http_request_duration_seconds_bucket" in query:
            return self._series(self._module, self._latency)
        if query.startswith("1 - ("):
            return self._series(self._module, self._availability)
        if "atp_run_outcomes_total" in query and 'status="passed"' in query:
            return self._series(self._module, self._success)
        return self._series(self._module, [1.0, 1.0])

    def query_instant(self, query: str, at):
        return []


def test_latency_worst_is_the_daily_peak_and_breaches_are_flagged(repo_root):
    """P95 latency is a lower-is-better metric: the daily worst must be the peak.

    Taking the minimum instead hides spikes entirely -- a day swinging between
    200 ms and 5000 ms against a 2000 ms target would report 200 ms and record
    no breach, which silently green-lights the Q12 acceptance decision.
    """
    module = _load_collector(repo_root)
    prometheus = _StubPrometheus(
        availability=[0.999, 0.999],
        latency=[0.2, 5.0, 0.25, 4.8],
        success=[0.99, 0.99],
    ).bind(module)

    evidence, _artifacts = module._build_slo_bundle(
        prometheus,
        date(2026, 7, 1),
        date(2026, 7, 1),
        source_deployment="staging-prod",
    )

    latency_row = evidence.latency_rows[0]
    assert latency_row[1] == "5000", "5m worst must be the peak, not the trough"
    assert latency_row[2] == "5000", "1h worst must be the peak, not the trough"
    assert float(latency_row[1]) >= float(latency_row[3]), "worst can never be below the daily mean"

    breaches = [row for row in evidence.breach_rows if row[1] == "API P95 latency"]
    assert breaches, "a 5000 ms peak against a 2000 ms target must be recorded as a breach"
    assert breaches[0][2] == "5000"


def test_availability_and_success_worst_stay_the_daily_trough(repo_root):
    """Higher-is-better metrics keep min semantics, and their breaches still fire."""
    module = _load_collector(repo_root)
    prometheus = _StubPrometheus(
        availability=[0.999, 0.98],
        latency=[0.2, 0.3],
        success=[0.99, 0.90],
    ).bind(module)

    evidence, _artifacts = module._build_slo_bundle(
        prometheus,
        date(2026, 7, 1),
        date(2026, 7, 1),
        source_deployment="staging-prod",
    )

    assert evidence.availability_rows[0][1] == "98"
    assert evidence.success_rows[0][1] == "90"
    breached = {row[1] for row in evidence.breach_rows}
    assert breached == {"API availability", "Run success rate"}


def test_window_without_samples_is_a_data_gap_not_a_pass(repo_root):
    """No data must never read as a clean window.

    An empty result set produces no breaches, so a gate keyed only on breaches
    would enable alerts and the release gate off a misconfigured Prometheus.
    """
    module = _load_collector(repo_root)

    class EmptyPrometheus:
        base_url = "http://prom"

        def query_range(self, query: str, start, end, step: str):
            return []

        def query_instant(self, query: str, at):
            return []

    evidence, _artifacts = module._build_slo_bundle(
        EmptyPrometheus(),
        date(2026, 7, 1),
        date(2026, 7, 14),
        source_deployment="staging-prod",
    )

    assert not evidence.breach_rows
    # 14 days x 4 evaluated SLO series
    assert len(evidence.data_gap_rows) == 56
    assert evidence.alert_enablement == "deferred"
    assert evidence.release_blocking_gate == "deferred"
    assert "could not evaluate" in evidence.rationale

    rendered = module._render_slo_markdown(evidence)
    assert "## Data Gaps" in rendered
    assert "no samples returned by Prometheus" in rendered
    assert "not evaluated; data gaps present" in rendered
    # Preconditions must not claim a full scrape history when days are missing.
    assert "- [ ] Prometheus continuously scraped" in rendered


def test_full_window_without_breaches_enables_the_gate(repo_root):
    """The clean 14-day path still reaches enabled, so the gap guard is not a blanket block."""
    module = _load_collector(repo_root)
    prometheus = _StubPrometheus(
        availability=[0.999, 0.999],
        latency=[0.2, 0.3],
        success=[0.99, 0.99],
    ).bind(module)

    def query_range(query, start, end, step):
        base = _StubPrometheus.query_range(prometheus, query, start, end, step)
        samples = []
        for day_offset in range(14):
            for index, (_ts, value) in enumerate(base[0].samples):
                stamp = datetime(2026, 7, 1, index, tzinfo=timezone.utc) + timedelta(days=day_offset)
                samples.append((stamp, value))
        return [module.PrometheusSeries(labels={}, samples=samples)]

    prometheus.query_range = query_range

    evidence, _artifacts = module._build_slo_bundle(
        prometheus,
        date(2026, 7, 1),
        date(2026, 7, 14),
        source_deployment="staging-prod",
    )

    assert evidence.breach_rows == []
    assert evidence.data_gap_rows == []
    assert evidence.alert_enablement == "enabled"
    assert evidence.release_blocking_gate == "enabled"


def test_existing_evidence_aborts_before_any_collection(repo_root, tmp_path, monkeypatch):
    """The device rehearsal is expensive: refuse on existing files before running it."""
    module = _load_collector(repo_root)

    def explode(*_args, **_kwargs):
        raise AssertionError("collection must not start when evidence already exists")

    monkeypatch.setattr(module, "PrometheusClient", explode)
    monkeypatch.setattr(module, "ATPApiClient", explode)
    monkeypatch.setattr(module, "_build_slo_bundle", explode)
    monkeypatch.setattr(module, "_collect_android_evidence", explode)

    existing = tmp_path / "docs" / "android-device-rehearsal-2026-07-02.md"
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_text("previous rehearsal", encoding="utf-8")

    kwargs = dict(
        repo_root=tmp_path,
        start=date(2026, 7, 1),
        end=date(2026, 7, 2),
        android_date=date(2026, 7, 2),
        prometheus_url="http://prom",
        api_base_url="http://api",
        token="token",
        username=None,
        password=None,
        task_id=7,
        device_serial="192.168.1.8:5555",
        app_package="com.example.app",
        device_id=None,
        doctor_target="192.168.1.8:5555",
        operator="qa",
        source_deployment="staging-prod",
        deployment="staging-prod",
        topology="shared host ADB server",
        adb_server_socket=None,
        skip_server_restart=True,
        skip_connect=True,
        fixtures_dir=tmp_path / "docs/fixtures/q12",
        force=False,
        timeout_seconds=10,
        poll_seconds=0,
    )

    with pytest.raises(FileExistsError) as excinfo:
        module.run(**kwargs)
    assert "android-device-rehearsal-2026-07-02.md" in str(excinfo.value)

    # The pre-existing file is left untouched by the aborted run.
    assert existing.read_text(encoding="utf-8") == "previous rehearsal"


def test_integer_counts_keep_their_trailing_zeros(repo_root):
    """Zero-digit formatting must not strip significant zeros off a count."""
    module = _load_collector(repo_root)

    assert module._fmt_float(200.0, 0) == "200"
    assert module._fmt_float(10500.0, 0) == "10500"
    # Decimal padding is still trimmed for the percentage columns.
    assert module._fmt_float(99.50, 2) == "99.5"
    assert module._fmt_float(100.0, 2) == "100"
    assert module._fmt_float(None, 0) == ""


def test_daily_volume_is_filed_under_the_day_it_measures(repo_root):
    """`increase(...[1d])` is stamped at the END of the interval it covers.

    Filing the midnight sample under `ts.date()` shifts every day's traffic
    forward by one and pulls the day before the window into the table, so the
    volume column would describe a different window than the SLO columns beside
    it.
    """
    module = _load_collector(repo_root)

    # One sample per midnight boundary, as Prometheus returns for step=1d over
    # a window whose end bound is the midnight after the last day.
    volume_samples = [
        (datetime(2026, 6, 30, tzinfo=timezone.utc), 999.0),  # covers 06-29, outside
        (datetime(2026, 7, 1, tzinfo=timezone.utc), 100.0),  # covers 06-30, outside
        (datetime(2026, 7, 2, tzinfo=timezone.utc), 200.0),  # covers 07-01
        (datetime(2026, 7, 3, tzinfo=timezone.utc), 300.0),  # covers 07-02
        (datetime(2026, 7, 4, tzinfo=timezone.utc), 400.0),  # covers 07-03
    ]

    class _VolumePrometheus(_StubPrometheus):
        def query_range(self, query, start, end, step):
            if "increase(" in query:
                return [self._module.PrometheusSeries(labels={}, samples=volume_samples)]
            return super().query_range(query, start, end, step)

    prometheus = _VolumePrometheus(
        availability=[0.999],
        latency=[0.2],
        success=[0.99],
    ).bind(module)

    evidence, _artifacts = module._build_slo_bundle(
        prometheus,
        date(2026, 7, 1),
        date(2026, 7, 3),
        source_deployment="staging-prod",
    )

    expected = [["2026-07-01", "200"], ["2026-07-02", "300"], ["2026-07-03", "400"]]
    assert evidence.request_volume_rows == expected
    assert evidence.run_volume_rows == expected
    # Out-of-window boundary samples must not inflate the window total.
    assert "900" in evidence.traffic_profile


def test_auth_credentials_come_from_atp_prefixed_env_vars(repo_root, monkeypatch, capsys):
    """Bare USERNAME/PASSWORD collide with names the shell or CI runner exports.

    Reading them would silently authenticate as whoever is logged into the host,
    so the collector only honours the ATP_-prefixed names.
    """
    module = _load_collector(repo_root)
    for name in ("ATP_TOKEN", "ATP_USERNAME", "ATP_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("USERNAME", "shell-user")
    monkeypatch.setenv("PASSWORD", "shell-password")

    argv = [
        "--start",
        "2026-07-01",
        "--end",
        "2026-07-02",
        "--android-date",
        "2026-07-02",
        "--task-id",
        "7",
        "--device-serial",
        "192.168.1.8:5555",
        "--app-package",
        "com.example.app",
    ]

    assert module.main(argv) == 2, "host USERNAME/PASSWORD must not satisfy the auth check"
    assert "ATP_USERNAME/ATP_PASSWORD" in capsys.readouterr().err

    monkeypatch.setenv("ATP_USERNAME", "atp-user")
    monkeypatch.setenv("ATP_PASSWORD", "atp-password")
    captured: dict = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(module, "run", fake_run)

    assert module.main(argv) == 0
    assert captured["username"] == "atp-user"
    assert captured["password"] == "atp-password"
