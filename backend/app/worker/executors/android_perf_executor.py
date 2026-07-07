"""
Android 性能测试执行器

执行流程：
  1. 校验设备可达 + 包名有效
  2. 可选：启动 App（monkey 或 am start）
  3. 启动采样循环（CPU / 内存 / 电池 / 网络），按 interval_seconds 采样
  4. 持续 duration_seconds 后停止
  5. 聚合样本，计算 avg/peak CPU、avg/peak 内存
  6. 上传 CSV 原始数据到 MinIO
  7. 更新 MobileSpecialRun（status=completed/failed，summary_json，duration_ms）
"""

import asyncio
import csv
import io
import json
import logging
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.minio_client import upload_file
from app.core.redis_client import publish_run_event
from app.models.mobile_special import (
    MobileSpecialRun,
    MobileMetricSample,
    MobileRunArtifact,
    RunStatus,
    ArtifactType,
)
from app.services.adb_resilience import HeartbeatMonitor, ensure_reachable, safe_run_adb
from app.services.mobile_special.adb_client import (
    run_adb_shell,
    build_meminfo_cmd,
    build_cpuinfo_cmd,
    build_batterystats_cmd,
    build_pidof_cmd,
)
from app.services.mobile_special.parsers import parse_meminfo, parse_cpuinfo, parse_batterystats, parse_pid

logger = logging.getLogger(__name__)


async def _safe_publish(run_id: int, payload: dict) -> None:
    try:
        await publish_run_event(run_id, payload)
    except Exception:
        pass


def _check_device_reachable(serial: str, timeout: int = 10) -> tuple[bool, str]:
    """复用统一的自愈层；保留旧函数签名供老 monkeypatch 测试兼容。"""
    return ensure_reachable(serial, timeout=timeout)


def _validate_inputs(
    device_serial: Optional[str],
    app_package: Optional[str],
    config_json: dict,
) -> list[str]:
    errors = []
    if not device_serial:
        errors.append("未指定执行设备 serial")
    if not app_package:
        errors.append("未指定 app_package")
    duration = config_json.get("duration_seconds", 0)
    if duration is not None and duration < 0:
        errors.append(f"duration_seconds 不能为负数: {duration}")
    interval = config_json.get("interval_seconds", 5)
    if interval <= 0:
        errors.append(f"interval_seconds 必须大于 0: {interval}")
    return errors


def _start_app(serial: str, package: str) -> bool:
    """使用 am start 启动 App，返回是否成功；走 safe_run_adb 自动重试。"""
    proc = safe_run_adb(
        serial,
        ["shell", "am", "start", "-n", f"{package}/.MainActivity"],
        timeout=15,
        retries=1,
    )
    return proc is not None and proc.returncode == 0


def _resolve_pid(serial: str, package: str) -> Optional[int]:
    cmd = build_pidof_cmd(serial, package)
    raw = run_adb_shell(serial, cmd, timeout=5)
    if raw:
        return parse_pid(raw)
    return None


async def _sample_once(serial: str, package: str) -> list[dict]:
    """执行一次采样，返回样本列表"""
    samples = []
    sample_time = datetime.now()

    # CPU
    raw_cpu = run_adb_shell(serial, build_cpuinfo_cmd(serial, package), timeout=10)
    if raw_cpu:
        result = parse_cpuinfo(raw_cpu, package)
        if result:
            samples.append({**result, "sample_time": sample_time})

    # Memory
    raw_mem = run_adb_shell(serial, build_meminfo_cmd(serial, package), timeout=10)
    if raw_mem:
        result = parse_meminfo(raw_mem, package)
        if result:
            samples.append({**result, "sample_time": sample_time})

    # Battery
    raw_battery = run_adb_shell(serial, build_batterystats_cmd(serial, package), timeout=10)
    if raw_battery:
        result = parse_batterystats(raw_battery, package)
        if result:
            samples.append({**result, "sample_time": sample_time})

    return samples


def _compute_summary(samples: list[dict], crash_count: int, anr_count: int) -> dict:
    """从样本列表计算性能汇总"""
    by_type: dict[str, list[float]] = {}
    for s in samples:
        mt = s.get("metric_type")
        if mt:
            by_type.setdefault(mt, []).append(float(s.get("metric_value", 0)))

    def avg(vals):
        return round(sum(vals) / len(vals), 2) if vals else None

    def peak(vals):
        return round(max(vals), 2) if vals else None

    return {
        "avg_cpu_pct": avg(by_type.get("cpu_pct", [])),
        "peak_cpu_pct": peak(by_type.get("cpu_pct", [])),
        "avg_mem_mb": avg(by_type.get("mem_mb", [])),
        "peak_mem_mb": peak(by_type.get("mem_mb", [])),
        "avg_battery_pct": avg(by_type.get("battery_pct", [])),
        "crash_count": crash_count,
        "anr_count": anr_count,
        "_sample_counts": {mt: len(vals) for mt, vals in by_type.items()},
    }


async def run_mobile_special_perf(
    db: AsyncSession,
    run: MobileSpecialRun,
) -> None:
    """执行一个 Android 性能专项任务"""
    task = run.task
    config = run.config_snapshot or {}

    device_serial = config.get("device_serial") or (run.device_serial if run.device_serial else None)
    app_package = config.get("app_package") or run.app_package

    duration_seconds = config.get("duration_seconds", 300)
    interval_seconds = config.get("interval_seconds", 5)

    # 1. 校验输入
    validation_errors = _validate_inputs(device_serial, app_package, config)
    if validation_errors:
        run.status = RunStatus.failed
        run.finished_at = datetime.now()
        run.summary_json = {"error_message": "; ".join(validation_errors)}
        await db.commit()
        await _safe_publish(
            run.id,
            {
                "type": "completed",
                "run_id": run.id,
                "status": RunStatus.failed.value,
                "summary": run.summary_json,
            },
        )
        return

    # 2. 校验设备
    reachable, device_message = await asyncio.get_event_loop().run_in_executor(
        None, _check_device_reachable, device_serial
    )
    if not reachable:
        run.status = RunStatus.failed
        run.finished_at = datetime.now()
        run.summary_json = {"error_message": f"设备不可达: {device_message}"}
        await db.commit()
        await _safe_publish(
            run.id,
            {
                "type": "completed",
                "run_id": run.id,
                "status": RunStatus.failed.value,
                "summary": run.summary_json,
            },
        )
        return

    run.started_at = datetime.now()
    run.status = RunStatus.running
    await db.commit()

    await _safe_publish(
        run.id,
        {
            "type": "started",
            "run_id": run.id,
            "device_serial": device_serial,
        },
    )

    # 3. 启动 App（可选）
    if config.get("auto_start", True):
        await asyncio.get_event_loop().run_in_executor(None, _start_app, device_serial, app_package)
        # 等待应用完全启动
        await asyncio.sleep(3)

    # 4. 采样循环（外包心跳监控，掉线时停止）
    all_samples: list[dict] = []
    start_time = time.monotonic()
    sample_count = 0
    device_lost_at: Optional[float] = None

    def _on_device_lost(reason: str) -> None:
        nonlocal device_lost_at
        device_lost_at = time.monotonic() - start_time
        logger.warning(
            "perf run %s: device %s lost during sampling (%s)",
            run.id,
            device_serial,
            reason,
        )

    try:
        async with HeartbeatMonitor(device_serial, on_lost=_on_device_lost, executor_label="perf") as hb:
            while (time.monotonic() - start_time) < duration_seconds:
                if hb.lost:
                    break
                samples = await _sample_once(device_serial, app_package)
                all_samples.extend(samples)
                sample_count += 1

                await _safe_publish(
                    run.id,
                    {
                        "type": "sampling",
                        "run_id": run.id,
                        "sample_count": sample_count,
                        "samples": len(samples),
                    },
                )

                await asyncio.sleep(interval_seconds)
    except Exception as e:
        logger.exception("perf sampling error for run %s: %s", run.id, e)

    # 5. 聚合汇总
    summary = _compute_summary(all_samples, crash_count=0, anr_count=0)
    if device_lost_at is not None:
        summary["device_lost"] = True
        summary["device_lost_at_sec"] = round(device_lost_at, 2)
    total_ms = int((time.monotonic() - start_time) * 1000)

    # 6. 保存样本到 DB
    for sample_data in all_samples:
        sample = MobileMetricSample(
            run_id=run.id,
            sample_time=sample_data.get("sample_time", datetime.now()),
            metric_type=sample_data["metric_type"],
            metric_value=sample_data["metric_value"],
            source=sample_data.get("source"),
            extra_json=sample_data.get("extra", {}),
        )
        db.add(sample)
    await db.commit()

    # 7. 上传 CSV artifact
    if all_samples:
        csv_buffer = io.StringIO()
        writer = csv.DictWriter(csv_buffer, fieldnames=["sample_time", "metric_type", "metric_value", "source"])
        writer.writeheader()
        for s in all_samples:
            writer.writerow(
                {
                    "sample_time": s.get("sample_time", "").isoformat() if s.get("sample_time") else "",
                    "metric_type": s.get("metric_type", ""),
                    "metric_value": s.get("metric_value", ""),
                    "source": s.get("source", ""),
                }
            )
        csv_content = csv_buffer.getvalue().encode("utf-8")

        artifact_name = f"mobile-special/runs/{run.id}/metrics.csv"
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: upload_file(artifact_name, csv_buffer.getvalue(), "text/csv"),
            )
            artifact = MobileRunArtifact(
                run_id=run.id,
                artifact_type=ArtifactType.csv,
                file_path=artifact_name,
                file_name=f"run_{run.id}_metrics.csv",
                file_size=len(csv_content),
            )
            db.add(artifact)
        except Exception as e:
            logger.warning("failed to upload perf CSV for run %s: %s", run.id, e)

    # 8. 更新 Run
    run.status = RunStatus.completed
    run.finished_at = datetime.now()
    run.duration_ms = total_ms
    run.summary_json = summary
    await db.commit()

    await _safe_publish(
        run.id,
        {
            "type": "completed",
            "run_id": run.id,
            "status": RunStatus.completed.value,
            "duration_ms": total_ms,
            "summary": summary,
        },
    )
