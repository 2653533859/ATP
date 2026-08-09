"""JMeter JMX executor and JTL result adapter."""

from __future__ import annotations

import csv
import json
import os
import statistics
import subprocess
import tempfile
import zipfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from app.core import minio_client
from app.services.performance_process import run_performance_process


def parse_jmeter_jtl(jtl_path: Path, thresholds: object = None) -> dict[str, Any]:
    """Parse JMeter CSV JTL into the platform's common performance summary."""
    with jtl_path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    elapsed: list[float] = []
    timestamps: list[float] = []
    for row in rows:
        elapsed_value = _number(row.get("elapsed"))
        if elapsed_value is not None:
            elapsed.append(elapsed_value)
        timestamp_value = _number(row.get("timeStamp"))
        if timestamp_value is not None:
            timestamps.append(timestamp_value)
    failures = sum(1 for row in rows if str(row.get("success", "")).strip().lower() in {"false", "0"})
    request_count = len(rows)
    duration_seconds = (max(timestamps) - min(timestamps)) / 1000 if len(timestamps) > 1 else 0
    rps = request_count / duration_seconds if duration_seconds > 0 else None
    metrics = {
        "rps": rps,
        "p95_ms": _percentile(elapsed, 0.95),
        "p99_ms": _percentile(elapsed, 0.99),
        "error_rate": failures / request_count if request_count else None,
        "iterations": request_count,
        "data_received": sum(_number(row.get("bytes")) or 0 for row in rows),
        "data_sent": sum(_number(row.get("sentBytes")) or 0 for row in rows),
    }
    return {"executor": "jmeter", **metrics, "thresholds": _evaluate_thresholds(metrics, thresholds)}


def run_jmeter_script(
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
    merged_options = options if isinstance(options, dict) else {}
    raw_env = merged_options.get("env")
    env_values = raw_env if isinstance(raw_env, dict) else {}
    with tempfile.TemporaryDirectory(prefix=f"atp-jmeter-{run_id}-") as tmp:
        tmp_path = Path(tmp)
        script_path = tmp_path / "test.jmx"
        jtl_path = tmp_path / "result.jtl"
        minio_client.download_file(script_object_name, script_path)
        env = os.environ.copy()
        env.update({str(key): str(value) for key, value in env_values.items()})
        completed, duration_ms = run_performance_process(
            ["jmeter", "-n", "-t", str(script_path), "-l", str(jtl_path)],
            cwd=tmp_path,
            env=env,
            timeout_seconds=timeout_seconds,
            cancel_check=cancel_check,
            metric_callback=metric_callback,
            metric_interval_seconds=metric_interval_seconds,
            max_metric_samples=max_metric_samples,
            popen_factory=subprocess.Popen,
        )
        if not jtl_path.exists():
            message = (completed.stderr or completed.stdout or "JMeter did not produce JTL").strip()
            raise RuntimeError(message[:1000])
        summary = parse_jmeter_jtl(jtl_path, merged_options.get("thresholds"))
        summary["exit_code"] = completed.returncode
        if completed.returncode != 0:
            summary["jmeter_error"] = (completed.stderr or completed.stdout or "").strip()[:1000]
        if merged_options.get("html_report") or merged_options.get("jmeter_html_report"):
            html_dir = tmp_path / "html-report"
            html_dir.mkdir()
            html_process = subprocess.run(
                ["jmeter", "-g", str(jtl_path), "-o", str(html_dir)],
                cwd=tmp_path,
                env=env,
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
            if html_process.returncode != 0:
                summary["html_report_error"] = (html_process.stderr or html_process.stdout or "").strip()[:1000]
            elif any(html_dir.iterdir()):
                archive = tmp_path / "jmeter-html-report.zip"
                with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as stream:
                    for path in html_dir.rglob("*"):
                        if path.is_file():
                            stream.write(path, path.relative_to(html_dir).as_posix())
                html_object_name = f"performance/runs/{run_id}/jmeter-html-report.zip"
                minio_client.upload_file(html_object_name, archive, content_type="application/zip")
                summary["html_report_object_name"] = html_object_name
        result_path = tmp_path / "summary.json"
        result_path.write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
        object_name = f"performance/runs/{run_id}/summary.json"
        minio_client.upload_file(object_name, result_path, content_type="application/json")
        return summary, object_name, duration_ms


def _number(value: object) -> float | None:
    try:
        return float(str(value).strip()) if value not in {None, ""} else None
    except (TypeError, ValueError):
        return None


def _percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    return statistics.quantiles(values, n=100, method="inclusive")[min(99, max(0, int(quantile * 100) - 1))]


def _evaluate_thresholds(metrics: Mapping[str, object], thresholds: object) -> dict[str, dict[str, dict[str, bool]]]:
    if not isinstance(thresholds, dict):
        return {}
    result: dict[str, dict[str, dict[str, bool]]] = {}
    for metric, rules in thresholds.items():
        value = metrics.get(str(metric))
        if not isinstance(value, (int, float)):
            continue
        if isinstance(rules, str):
            rules = [rules]
        if not isinstance(rules, (list, tuple)):
            continue
        rows: dict[str, dict[str, bool]] = {}
        for rule in rules:
            text = str(rule).strip()
            for operator in ("<=", ">=", "<", ">"):
                if not text.startswith(operator):
                    continue
                try:
                    target = float(text[len(operator) :].strip())
                except ValueError:
                    break
                rows[text] = {
                    "ok": {"<": value < target, "<=": value <= target, ">": value > target, ">=": value >= target}[
                        operator
                    ]
                }
                break
        if rows:
            result[str(metric)] = rows
    return result
