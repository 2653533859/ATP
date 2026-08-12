"""Locust executor and CSV-to-platform result adapter."""

from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from app.core import minio_client
from app.services.performance_process import run_performance_process

_THRESHOLD_RE = re.compile(r"^\s*(?:([a-zA-Z0-9_()%-]+)\s*)?(<=|>=|<|>)\s*(-?\d+(?:\.\d+)?)\s*$")


def parse_locust_stats(stats_path: Path, thresholds: object = None) -> dict[str, Any]:
    """Parse Locust's aggregate CSV row into the platform summary contract."""
    with stats_path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    row = next((_row for _row in rows if _is_aggregate_row(_row)), rows[-1] if rows else {})
    request_count = _number(row, "Request Count")
    failure_count = _number(row, "Failure Count")
    error_rate = (
        float(failure_count) / float(request_count)
        if request_count is not None and request_count != 0 and failure_count is not None
        else None
    )
    metrics: dict[str, object] = {
        "rps": _number(row, "Requests/s"),
        "p95_ms": _number(row, "95%"),
        "p99_ms": _number(row, "99%"),
        "error_rate": error_rate,
        "iterations": request_count,
    }
    summary: dict[str, Any] = {
        "executor": "locust",
        **metrics,
        "data_received": None,
        "data_sent": None,
        "thresholds": _evaluate_thresholds(metrics, thresholds),
    }
    return summary


def run_locust_script(
    *,
    run_id: int,
    script_object_name: str,
    options: dict | None = None,
    timeout_seconds: int = 1800,
    cancel_check=None,
    metric_callback=None,
    metric_interval_seconds: float = 5.0,
    max_metric_samples: int = 7200,
) -> tuple[dict[str, Any], str, int]:
    """Execute a stored Locust file in headless mode and persist a common summary."""
    merged_options = options if isinstance(options, dict) else {}
    raw_env_vars = merged_options.get("env")
    env_vars = raw_env_vars if isinstance(raw_env_vars, dict) else {}
    with tempfile.TemporaryDirectory(prefix=f"atp-locust-{run_id}-") as tmp:
        tmp_path = Path(tmp)
        script_path = tmp_path / "locustfile.py"
        csv_prefix = tmp_path / "locust"
        minio_client.download_file(script_object_name, script_path)

        env = os.environ.copy()
        env.update({str(key): str(value) for key, value in env_vars.items()})
        command = [
            sys.executable,
            "-m",
            "locust",
            "-f",
            str(script_path),
            "--headless",
            "--only-summary",
            "--csv",
            str(csv_prefix),
            "-u",
            str(_positive_int(merged_options.get("users"), 1)),
            "-r",
            str(_positive_number(merged_options.get("spawn_rate"), 1)),
            "-t",
            str(merged_options.get("run_time") or merged_options.get("duration") or "30s"),
        ]
        host = merged_options.get("host") or env_vars.get("TARGET_URL") or env_vars.get("BASE_URL")
        if isinstance(host, str) and host.strip():
            command.extend(["--host", host.strip()])
        _append_tag_options(command, "--tags", merged_options.get("tags"))
        _append_tag_options(command, "--exclude-tags", merged_options.get("exclude_tags"))

        completed, duration_ms = run_performance_process(
            command,
            cwd=tmp_path,
            env=env,
            timeout_seconds=timeout_seconds,
            cancel_check=cancel_check,
            metric_callback=metric_callback,
            metric_interval_seconds=metric_interval_seconds,
            max_metric_samples=max_metric_samples,
            popen_factory=subprocess.Popen,
        )
        stats_path = Path(f"{csv_prefix}_stats.csv")
        if not stats_path.exists():
            message = (completed.stderr or completed.stdout or "Locust did not produce stats CSV").strip()
            raise RuntimeError(message[:1000])

        summary = parse_locust_stats(stats_path, merged_options.get("thresholds"))
        summary["exit_code"] = completed.returncode
        if completed.returncode != 0:
            summary["locust_error"] = (completed.stderr or completed.stdout or "").strip()[:1000]
        result_path = tmp_path / "summary.json"
        result_path.write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
        object_name = f"performance/runs/{run_id}/summary.json"
        minio_client.upload_file(object_name, result_path, content_type="application/json")
        return summary, object_name, duration_ms


def _is_aggregate_row(row: dict[str, str]) -> bool:
    values = {str(value or "").strip().lower() for value in row.values()}
    return bool(values & {"aggregated", "aggregate", "total"})


def _number(row: dict[str, str], name: str) -> float | int | None:
    aliases = {
        "95%": {"95%", "95%ile", "95th"},
        "99%": {"99%", "99%ile", "99th"},
    }.get(name, {name})
    raw = next((value for key, value in row.items() if key.strip().lower() in {item.lower() for item in aliases}), None)
    if raw is None:
        return None
    try:
        value = float(str(raw).strip().replace(",", ""))
    except (TypeError, ValueError):
        return None
    return int(value) if value.is_integer() else value


def _positive_int(value: object, fallback: int) -> int:
    if not isinstance(value, (int, float, str)) or isinstance(value, bool):
        return fallback
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return fallback


def _positive_number(value: object, fallback: int) -> int | float:
    if not isinstance(value, (int, float, str)) or isinstance(value, bool):
        return fallback
    try:
        number = float(value)
        return int(number) if number.is_integer() else max(0.1, number)
    except (TypeError, ValueError):
        return fallback


def _append_tag_options(command: list[str], option: str, values: object) -> None:
    if isinstance(values, str):
        values = [values]
    if isinstance(values, (list, tuple)):
        cleaned = [str(item) for item in values if str(item).strip()]
        if cleaned:
            command.extend([option, *cleaned])


def _evaluate_thresholds(metrics: dict[str, object], thresholds: object) -> dict[str, dict[str, dict[str, bool]]]:
    if not isinstance(thresholds, dict):
        return {}
    result: dict[str, dict[str, dict[str, bool]]] = {}
    for metric_name, rules in thresholds.items():
        metric_value = metrics.get(str(metric_name))
        if not isinstance(metric_value, (int, float)) or isinstance(metric_value, bool):
            continue
        if isinstance(rules, str):
            rules = [rules]
        if not isinstance(rules, (list, tuple)):
            continue
        metric_rows: dict[str, dict[str, bool]] = {}
        for raw_rule in rules:
            rule = str(raw_rule)
            match = _THRESHOLD_RE.match(rule)
            if not match:
                metric_rows[rule] = {"ok": False}
                continue
            explicit_metric, operator, raw_target = match.groups()
            if explicit_metric and explicit_metric.lower() not in {str(metric_name).lower(), "value"}:
                metric_rows[rule] = {"ok": False}
                continue
            target = float(raw_target)
            ok = {
                "<": metric_value < target,
                "<=": metric_value <= target,
                ">": metric_value > target,
                ">=": metric_value >= target,
            }[operator]
            metric_rows[rule] = {"ok": ok}
        if metric_rows:
            result[str(metric_name)] = metric_rows
    return result
