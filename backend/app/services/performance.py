"""k6 performance run helpers."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from collections.abc import Callable
from typing import Any

from app.core import minio_client
from app.services.performance_process import PerformanceRunCancelled, run_performance_process


_K6_OPTION_KEYS = {
    "batch",
    "batchPerHost",
    "discardResponseBodies",
    "duration",
    "gracefulRampDown",
    "gracefulStop",
    "insecureSkipTLSVerify",
    "iterations",
    "maxRedirects",
    "minIterationDuration",
    "noConnectionReuse",
    "scenarios",
    "stages",
    "thresholds",
    "vus",
}


def _metric_value(metrics: dict[str, Any], metric_name: str, value_name: str) -> float | int | None:
    metric = metrics.get(metric_name) or {}
    values = metric.get("values") if isinstance(metric, dict) else {}
    if not isinstance(values, dict):
        values = {}
    if not values and isinstance(metric, dict):
        values = metric
    value = values.get(value_name)
    if value is None and value_name == "rate":
        value = values.get("value")
    if isinstance(value, (int, float)):
        return value
    return None


def _normalize_thresholds(metric_thresholds: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for rule, result in metric_thresholds.items():
        if isinstance(result, bool):
            # k6 summary-export stores whether a threshold was crossed; crossed=false means passed.
            normalized[rule] = {"ok": not result}
        elif isinstance(result, dict):
            normalized[rule] = result
        else:
            normalized[rule] = {"ok": False}
    return normalized


def parse_k6_summary(summary: dict[str, Any]) -> dict[str, Any]:
    metrics = summary.get("metrics") if isinstance(summary, dict) else {}
    if not isinstance(metrics, dict):
        metrics = {}

    thresholds: dict[str, Any] = {}
    for metric_name, metric in metrics.items():
        metric_thresholds = metric.get("thresholds") if isinstance(metric, dict) else None
        if metric_thresholds:
            thresholds[metric_name] = _normalize_thresholds(metric_thresholds)

    return {
        "executor": "k6",
        "rps": _metric_value(metrics, "http_reqs", "rate"),
        "p95_ms": _metric_value(metrics, "http_req_duration", "p(95)"),
        "p99_ms": _metric_value(metrics, "http_req_duration", "p(99)"),
        "error_rate": _metric_value(metrics, "http_req_failed", "rate"),
        "iterations": _metric_value(metrics, "iterations", "count"),
        "data_received": _metric_value(metrics, "data_received", "count"),
        "data_sent": _metric_value(metrics, "data_sent", "count"),
        "thresholds": thresholds,
    }


def run_k6_script(
    *,
    run_id: int,
    script_object_name: str,
    options: dict | None = None,
    timeout_seconds: int = 1800,
    cancel_check: Callable[[], bool] | None = None,
    metric_callback: Callable[[], None] | None = None,
    metric_interval_seconds: float = 5.0,
    max_metric_samples: int = 7200,
) -> tuple[dict[str, Any], str, int]:
    """Execute a stored k6 script and return parsed summary, raw object name, duration ms."""
    merged_options = options if isinstance(options, dict) else {}
    raw_env_vars = merged_options.get("env")
    env_vars = raw_env_vars if isinstance(raw_env_vars, dict) else {}

    with tempfile.TemporaryDirectory(prefix=f"atp-k6-{run_id}-") as tmp:
        tmp_path = Path(tmp)
        script_path = tmp_path / "script.js"
        result_path = tmp_path / "result.json"
        minio_client.download_file(script_object_name, script_path)

        env = os.environ.copy()
        env.update({str(key): str(value) for key, value in env_vars.items()})
        k6_options = {key: merged_options[key] for key in _K6_OPTION_KEYS if key in merged_options}
        if k6_options:
            env["ATP_K6_OPTIONS"] = json.dumps(k6_options, ensure_ascii=False)

        completed, duration_ms = run_performance_process(
            ["k6", "run", "--summary-export", str(result_path), str(script_path)],
            cwd=tmp_path,
            env=env,
            timeout_seconds=timeout_seconds,
            cancel_check=cancel_check,
            metric_callback=metric_callback,
            metric_interval_seconds=metric_interval_seconds,
            max_metric_samples=max_metric_samples,
            # Keep the existing test seam and allow callers to replace the process boundary.
            popen_factory=subprocess.Popen,
        )

        if not result_path.exists():
            message = (completed.stderr or completed.stdout or "k6 did not produce summary").strip()
            raise RuntimeError(message[:1000])

        raw = json.loads(result_path.read_text(encoding="utf-8"))
        parsed = parse_k6_summary(raw)
        parsed["exit_code"] = completed.returncode
        if completed.returncode != 0:
            parsed["k6_error"] = (completed.stderr or completed.stdout or "").strip()[:1000]

        object_name = f"performance/runs/{run_id}/summary.json"
        minio_client.upload_file(object_name, result_path, content_type="application/json")
        return parsed, object_name, duration_ms
