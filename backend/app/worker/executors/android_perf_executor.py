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
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.minio_client import upload_bytes, upload_file
from app.core.redis_client import publish_run_event
from app.models.mobile_special import (
    MobileSpecialRun,
    MobileMetricSample,
    MobileIncident,
    MobileRunArtifact,
    RunStatus,
    ArtifactType,
)
from app.services.adb_resilience import HeartbeatMonitor, ensure_reachable
from app.services.mobile_special.adb_client import (
    run_adb_shell,
    build_meminfo_cmd,
    build_cpuinfo_cmd,
    build_gfxinfo_cmd,
    build_batterystats_cmd,
    build_pidof_cmd,
    build_proc_status_cmd,
)
from app.services.mobile_special.parsers import (
    parse_meminfo,
    parse_proc_status_memory,
    parse_cpuinfo,
    parse_gfxinfo_framestats,
    parse_batterystats,
    parse_logcat_anr,
    parse_logcat_crash,
    parse_pid,
)
from app.services.mobile_special.preflight import AndroidPreflightError, launch_android_app
from app.services.mobile_special_events import MobileRunEventRecorder

logger = logging.getLogger(__name__)


async def _safe_publish(run_id: int, payload: dict) -> None:
    try:
        await publish_run_event(run_id, payload, run_type="mobile")
    except Exception:
        pass


def _sample_event_metrics(samples: list[dict]) -> list[dict]:
    """Return a bounded, JSON-safe metric snapshot for the live report panel."""
    metrics: list[dict] = []
    for sample in samples:
        value = sample.get("metric_value")
        if not isinstance(value, (int, float)):
            continue
        sample_time = sample.get("sample_time")
        metrics.append(
            {
                "metric_type": str(sample.get("metric_type", "")),
                "metric_value": float(value),
                "sample_time": sample_time.isoformat() if hasattr(sample_time, "isoformat") else str(sample_time or ""),
            }
        )
    return metrics[:12]


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


def _start_app(serial: str, package: str, activity: str | None = None) -> bool:
    """启动 App；未指定 Activity 时使用 Launcher Intent 自动发现入口。"""
    try:
        launch_android_app(serial, package, activity)
        return True
    except AndroidPreflightError:
        return False


def _resolve_pid(serial: str, package: str) -> Optional[int]:
    cmd = build_pidof_cmd(serial, package)
    raw = run_adb_shell(serial, cmd, timeout=5)
    if raw:
        return parse_pid(raw)
    return None


def _clear_logcat_buffer(serial: str) -> None:
    try:
        subprocess.run(["adb", "-s", serial, "logcat", "-c"], capture_output=True, timeout=10)
    except Exception:
        logger.debug("failed to clear logcat for %s", serial, exc_info=True)


def _collect_incidents(serial: str) -> tuple[list[dict], str]:
    raw = run_adb_shell(serial, ["logcat", "-d", "-v", "time", "-t", "10000"], timeout=30) or ""
    if not raw:
        return [], ""
    return parse_logcat_crash(raw) + parse_logcat_anr(raw), raw


def _start_screen_recording(serial: str, remote_path: str, max_seconds: int):
    """Start an optional device-side recording for incident replay."""
    try:
        return subprocess.Popen(
            [
                "adb",
                "-s",
                serial,
                "shell",
                "screenrecord",
                "--time-limit",
                str(max(1, min(max_seconds, 1800))),
                "--bit-rate",
                "4000000",
                remote_path,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
    except Exception as exc:
        logger.warning("failed to start Android replay recording for %s: %s", serial, exc)
        return None


def _replay_window_seconds(value: object) -> int:
    """Normalize the rolling replay segment length to a safe device limit."""
    try:
        requested = int(value or 30)
    except (TypeError, ValueError):
        requested = 30
    return max(5, min(requested, 1800))


async def _remove_remote_recording(serial: str, remote_path: str) -> None:
    try:
        await asyncio.to_thread(subprocess.run, ["adb", "-s", serial, "shell", "rm", remote_path], timeout=10)
    except Exception:
        logger.debug("failed to remove Android replay segment %s", remote_path, exc_info=True)


async def _finish_screen_recording(
    serial: str,
    process,
    remote_path: str,
    run_id: int,
    *,
    save: bool,
    cleanup_paths: list[str] | None = None,
) -> tuple[str | None, int | None]:
    """Stop, optionally upload, and always remove a device-side recording."""
    if process is not None:
        try:
            process.terminate()
            await asyncio.to_thread(process.wait, 10)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass

    paths_to_cleanup = list(dict.fromkeys([*(cleanup_paths or []), remote_path]))
    if not save:
        for path in paths_to_cleanup:
            await _remove_remote_recording(serial, path)
        return None, None

    temp_file = tempfile.NamedTemporaryFile(prefix="atp-android-replay-", suffix=".mp4", delete=False)
    temp_file.close()
    local_path = Path(temp_file.name)
    try:
        pulled = await asyncio.to_thread(
            subprocess.run,
            ["adb", "-s", serial, "pull", remote_path, str(local_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if pulled.returncode != 0 or not local_path.exists():
            return None, None
        file_size = local_path.stat().st_size
        if file_size <= 0 or file_size > 200_000_000:
            return None, None
        object_name = f"android-special/runs/{run_id}/incident-replay.mp4"
        await asyncio.to_thread(upload_file, object_name, local_path, "video/mp4")
        return object_name, file_size
    except Exception as exc:
        logger.warning("failed to upload Android replay for run %s: %s", run_id, exc)
        return None, None
    finally:
        for path in paths_to_cleanup:
            await _remove_remote_recording(serial, path)
        try:
            local_path.unlink(missing_ok=True)
        except OSError:
            pass


async def _sample_once(
    serial: str,
    package: str,
    *,
    collect_performance: bool = True,
    collect_jank: bool = False,
) -> list[dict]:
    """执行一次采样，返回样本列表"""
    samples = []
    sample_time = datetime.now()

    if collect_performance:
        # CPU
        raw_cpu = run_adb_shell(serial, build_cpuinfo_cmd(serial, package), timeout=10)
        if raw_cpu:
            result = parse_cpuinfo(raw_cpu, package)
            if result:
                samples.append({**result, "sample_time": sample_time})
            elif _resolve_pid(serial, package) is not None:
                # Android may omit a process whose measured CPU is 0%.  The PID
                # confirms that the app is alive, so retain a valid zero sample.
                samples.append(
                    {
                        "metric_type": "cpu_pct",
                        "metric_value": 0.0,
                        "source": "dumpsys cpuinfo",
                        "extra": {"package": package, "assumed_zero": True},
                        "sample_time": sample_time,
                    }
                )

        # Memory
        raw_mem = run_adb_shell(serial, build_meminfo_cmd(serial, package), timeout=10)
        result = parse_meminfo(raw_mem or "", package)
        if result:
            samples.append({**result, "sample_time": sample_time})
        else:
            pid = _resolve_pid(serial, package)
            if pid is not None:
                raw_status = run_adb_shell(serial, build_proc_status_cmd(serial, pid), timeout=5)
                result = parse_proc_status_memory(raw_status or "", package)
                if result:
                    samples.append({**result, "sample_time": sample_time})

        # Battery
        raw_battery = run_adb_shell(serial, build_batterystats_cmd(serial, package), timeout=10)
        if raw_battery:
            result = parse_batterystats(raw_battery, package)
            if result:
                samples.append({**result, "sample_time": sample_time})
                temperature = result.get("extra", {}).get("temperature_c")
                if isinstance(temperature, (int, float)):
                    samples.append(
                        {
                            "metric_type": "temperature_c",
                            "metric_value": float(temperature),
                            "source": result.get("source"),
                            "extra": {"package": package},
                            "sample_time": sample_time,
                        }
                    )

    if collect_jank:
        raw_gfx = run_adb_shell(serial, build_gfxinfo_cmd(serial, package), timeout=15)
        if raw_gfx:
            result = parse_gfxinfo_framestats(raw_gfx, package)
            if result:
                samples.append({**result, "sample_time": sample_time})
                jank_count = result.get("extra", {}).get("jank_count")
                if isinstance(jank_count, (int, float)):
                    samples.append(
                        {
                            "metric_type": "jank_count",
                            "metric_value": float(jank_count),
                            "source": result.get("source"),
                            "extra": {"package": package},
                            "sample_time": sample_time,
                        }
                    )

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

    jank_values = by_type.get("jank_count", [])
    if jank_values:
        total_jank_count = int(sum(jank_values))
    else:
        total_jank_count = int(
            sum(s.get("extra", {}).get("jank_count", 0) for s in samples if s.get("metric_type") == "fps")
        )

    return {
        "avg_cpu_pct": avg(by_type.get("cpu_pct", [])),
        "peak_cpu_pct": peak(by_type.get("cpu_pct", [])),
        "avg_mem_mb": avg(by_type.get("mem_mb", [])),
        "peak_mem_mb": peak(by_type.get("mem_mb", [])),
        "avg_battery_pct": avg(by_type.get("battery_pct", [])),
        "avg_temperature_c": avg(by_type.get("temperature_c", [])),
        "peak_temperature_c": peak(by_type.get("temperature_c", [])),
        "avg_fps": avg(by_type.get("fps", [])),
        "peak_fps": peak(by_type.get("fps", [])),
        "total_jank_count": total_jank_count,
        "crash_count": crash_count,
        "anr_count": anr_count,
        "_sample_counts": {mt: len(vals) for mt, vals in by_type.items()},
    }


async def run_mobile_special_perf(
    db: AsyncSession,
    run: MobileSpecialRun,
    cancel_check: Callable[[], bool] | None = None,
    recorder: MobileRunEventRecorder | None = None,
) -> None:
    """执行一个 Android 性能专项任务"""
    task = run.task
    config = run.config_snapshot or {}

    device_serial = config.get("device_serial") or (run.device_serial if run.device_serial else None)
    app_package = config.get("app_package") or run.app_package

    duration_seconds = config.get("duration_seconds", 300)
    interval_seconds = config.get("interval_seconds", 5)
    collect_performance = config.get("collect_performance", True)
    collect_jank = config.get("collect_jank", False)
    capture_replay = config.get("capture_replay", False)
    # A replay is only useful when the run also checks logcat.  Keep incident
    # detection on automatically if a caller enables replay alone.
    collect_incidents = config.get("collect_incidents", False) or capture_replay
    capture_on_incident = config.get("capture_on_incident", True)
    replay_seconds = _replay_window_seconds(config.get("replay_seconds", 30))
    events = recorder or MobileRunEventRecorder(db, run.id)
    await events.initialize()

    # 1. 校验输入
    validation_errors = _validate_inputs(device_serial, app_package, config)
    if validation_errors:
        run.status = RunStatus.failed
        run.finished_at = datetime.now()
        run.summary_json = {"error_message": "; ".join(validation_errors)}
        await db.commit()
        await events.record(
            event_type="validation",
            phase="validation",
            level="error",
            message="输入校验失败",
            parameters={"device_serial": device_serial, "app_package": app_package},
            result={"ok": False, "errors": validation_errors},
        )
        await _safe_publish(
            run.id,
            {
                "type": "completed",
                "run_id": run.id,
                "status": RunStatus.failed.value,
                "summary": run.summary_json,
                "progress": 100,
                "current_step": "输入校验失败",
                "device_status": "unknown",
                "error": run.summary_json["error_message"],
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
        await events.record(
            event_type="device_check",
            phase="device_setup",
            level="error",
            message="设备不可达",
            parameters={"device_serial": device_serial},
            result={"ok": False, "detail": device_message},
        )
        await _safe_publish(
            run.id,
            {
                "type": "completed",
                "run_id": run.id,
                "status": RunStatus.failed.value,
                "summary": run.summary_json,
                "progress": 100,
                "current_step": "设备不可用",
                "device_status": "offline",
                "error": run.summary_json["error_message"],
            },
        )
        return

    run.started_at = datetime.now()
    run.status = RunStatus.running
    await db.commit()
    await events.record(
        event_type="run_started",
        phase="device_setup",
        action="connect_device",
        message="开始执行 Android 性能采样",
        parameters={
            "device_serial": device_serial,
            "app_package": app_package,
            "duration_seconds": duration_seconds,
            "interval_seconds": interval_seconds,
        },
        result={"ok": True},
    )

    await _safe_publish(
        run.id,
        {
            "type": "started",
            "run_id": run.id,
            "device_serial": device_serial,
            "phase": "running",
            "progress": 35,
            "current_step": "启动专项执行器",
            "device_status": "online",
        },
    )

    # 3. 启动 App（可选）
    if config.get("auto_start", True):
        await _safe_publish(
            run.id,
            {
                "type": "log",
                "run_id": run.id,
                "level": "info",
                "message": f"启动应用 {app_package}",
            },
        )
        launch_activity = str(config.get("launch_activity") or "").strip() or None
        if launch_activity:
            app_started = await asyncio.get_event_loop().run_in_executor(
                None, _start_app, device_serial, app_package, launch_activity
            )
        else:
            app_started = await asyncio.get_event_loop().run_in_executor(None, _start_app, device_serial, app_package)
        await events.record(
            event_type="action",
            phase="app_setup",
            action="start_app",
            parameters={"package": app_package},
            result={"ok": bool(app_started)},
        )
        if not app_started:
            error_message = f"应用启动失败: {app_package}"
            run.status = RunStatus.failed
            run.finished_at = datetime.now()
            run.duration_ms = 0
            run.summary_json = {"error_message": error_message, "app_package": app_package}
            await db.commit()
            await events.record(
                event_type="run_completed",
                phase="finalizing",
                action="complete_run",
                result={"status": run.status.value, "summary": run.summary_json},
            )
            await _safe_publish(
                run.id,
                {
                    "type": "completed",
                    "run_id": run.id,
                    "status": run.status.value,
                    "duration_ms": 0,
                    "summary": run.summary_json,
                    "progress": 100,
                    "current_step": "应用启动失败",
                    "device_status": "online",
                    "error": error_message,
                },
            )
            return
        # 等待应用完全启动
        await asyncio.sleep(3)

    recording_process = None
    replay_error: str | None = None
    recording_segment = 0
    recording_remote_path = f"/sdcard/atp_mobile_run_{run.id}_{recording_segment}.mp4"
    recording_remote_paths: list[str] = []
    if collect_incidents:
        await asyncio.to_thread(_clear_logcat_buffer, device_serial)
    if capture_replay:
        await _safe_publish(
            run.id,
            {
                "type": "phase",
                "run_id": run.id,
                "phase": "recording",
                "progress": 38,
                "current_step": "准备异常回放录制",
                "device_serial": device_serial,
                "device_status": "online",
            },
        )
        recording_process = await asyncio.to_thread(
            _start_screen_recording,
            device_serial,
            recording_remote_path,
            replay_seconds,
        )
        if recording_process is None:
            replay_error = "设备不支持或无法启动异常回放录屏"
        recording_remote_paths.append(recording_remote_path)
        await events.record(
            event_type="action",
            phase="recording",
            action="start_screen_recording",
            parameters={"remote_path": recording_remote_path, "max_seconds": replay_seconds, "rolling": True},
            result={"ok": recording_process is not None},
        )

    # 4. 采样循环（外包心跳监控，掉线时停止）
    all_samples: list[dict] = []
    start_time = time.monotonic()
    sample_count = 0
    device_lost_at: Optional[float] = None
    cancelled = False

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
                if cancel_check is not None and await asyncio.to_thread(cancel_check):
                    cancelled = True
                    break
                if capture_replay and recording_process is not None and recording_process.poll() is not None:
                    # screenrecord cannot run indefinitely. Rotate fixed-size segments and
                    # retain only the previous + current segment to bound device storage.
                    if len(recording_remote_paths) >= 2:
                        await _remove_remote_recording(device_serial, recording_remote_paths.pop(0))
                    recording_segment += 1
                    recording_remote_path = f"/sdcard/atp_mobile_run_{run.id}_{recording_segment}.mp4"
                    recording_process = await asyncio.to_thread(
                        _start_screen_recording,
                        device_serial,
                        recording_remote_path,
                        replay_seconds,
                    )
                    if recording_process is None:
                        replay_error = "设备不支持或无法启动异常回放录屏"
                    recording_remote_paths.append(recording_remote_path)
                    await events.record(
                        event_type="action",
                        phase="recording",
                        action="rotate_screen_recording",
                        parameters={
                            "remote_path": recording_remote_path,
                            "segment": recording_segment,
                            "max_seconds": replay_seconds,
                        },
                        result={"ok": recording_process is not None},
                    )
                samples = await _sample_once(
                    device_serial,
                    app_package,
                    collect_performance=collect_performance,
                    collect_jank=collect_jank,
                )
                all_samples.extend(samples)
                sample_count += 1

                await _safe_publish(
                    run.id,
                    {
                        "type": "sampling",
                        "run_id": run.id,
                        "sample_count": sample_count,
                        "samples": len(samples),
                        "progress": min(
                            95,
                            max(
                                35,
                                round((time.monotonic() - start_time) / max(float(duration_seconds), 1) * 60 + 35),
                            ),
                        ),
                        "elapsed_seconds": round(time.monotonic() - start_time, 1),
                        "duration_seconds": float(duration_seconds),
                        "phase": "sampling",
                        "current_step": "采集设备性能指标",
                        "device_serial": device_serial,
                        "device_status": "online",
                        "sample_metrics": _sample_event_metrics(samples),
                    },
                )
                await events.record(
                    event_type="sampling",
                    phase="sampling",
                    action="collect_metrics",
                    parameters={
                        "sample_index": sample_count,
                        "collect_performance": collect_performance,
                        "collect_jank": collect_jank,
                    },
                    result={"sample_count": len(samples), "metrics": _sample_event_metrics(samples)},
                )

                await asyncio.sleep(interval_seconds)
    except Exception as e:
        logger.exception("perf sampling error for run %s: %s", run.id, e)

    incidents_data: list[dict] = []
    raw_logcat = ""
    await _safe_publish(
        run.id,
        {
            "type": "phase",
            "run_id": run.id,
            "phase": "incidents",
            "progress": 95,
            "current_step": "收集 Crash/ANR 与日志",
            "device_serial": device_serial,
            "device_status": "online" if device_lost_at is None else "offline",
        },
    )
    if collect_incidents:
        incidents_data, raw_logcat = await asyncio.to_thread(_collect_incidents, device_serial)
        for incident in incidents_data:
            await _safe_publish(
                run.id,
                {
                    "type": "incident",
                    "run_id": run.id,
                    "incident_type": incident.get("incident_type", "crash"),
                    "title": incident.get("title") or "检测到移动端异常",
                    "detail": str(incident.get("detail") or "")[:500],
                    "incident_count": len(incidents_data),
                },
            )
            await events.record(
                event_type="incident",
                phase="incidents",
                action=incident.get("incident_type", "crash"),
                level="error",
                message=incident.get("title") or "检测到移动端异常",
                parameters={"detail": str(incident.get("detail") or "")[:500]},
                result={"incident_type": incident.get("incident_type", "crash")},
            )
    crash_count = sum(1 for item in incidents_data if item.get("incident_type") == "crash")
    anr_count = sum(1 for item in incidents_data if item.get("incident_type") == "anr")

    # 5. 聚合汇总
    summary = _compute_summary(all_samples, crash_count=crash_count, anr_count=anr_count)
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

    incident_rows = []
    for incident_data in incidents_data:
        incident = MobileIncident(
            run_id=run.id,
            incident_type=incident_data.get("incident_type", "crash"),
            event_time=incident_data.get("event_time", datetime.now()),
            title=incident_data.get("title"),
            detail=incident_data.get("detail"),
            process_name=incident_data.get("process_name"),
            thread_name=incident_data.get("thread_name"),
        )
        db.add(incident)
        incident_rows.append(incident)

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
                lambda: upload_bytes(artifact_name, csv_content, "text/csv"),
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

    replay_object_name = None
    replay_size = None
    if recording_process is not None or recording_remote_paths:
        replay_object_name, replay_size = await _finish_screen_recording(
            device_serial,
            recording_process,
            recording_remote_path,
            run.id,
            save=bool(incidents_data) and capture_on_incident,
            cleanup_paths=recording_remote_paths,
        )
    if incidents_data and raw_logcat and capture_on_incident:
        log_object_name = f"android-special/runs/{run.id}/incident.log"
        try:
            log_bytes = raw_logcat.encode("utf-8", errors="replace")[:5_000_000]
            await asyncio.to_thread(upload_bytes, log_object_name, log_bytes, "text/plain; charset=utf-8")
            db.add(
                MobileRunArtifact(
                    run_id=run.id,
                    artifact_type=ArtifactType.raw_log,
                    file_path=log_object_name,
                    file_name=f"run_{run.id}_incident.log",
                    file_size=len(log_bytes),
                )
            )
        except Exception as exc:
            logger.warning("failed to upload incident log for run %s: %s", run.id, exc)
    if replay_object_name:
        db.add(
            MobileRunArtifact(
                run_id=run.id,
                artifact_type=ArtifactType.replay,
                file_path=replay_object_name,
                file_name=f"run_{run.id}_incident-replay.mp4",
                file_size=replay_size,
            )
        )
        for incident in incident_rows:
            incident.artifact_path = replay_object_name

    if capture_replay:
        if incidents_data and capture_on_incident and not replay_object_name:
            replay_error = replay_error or "检测到异常，但未生成可上传的回放视频"
        if replay_object_name:
            replay_error = None
        summary["incident_replay"] = {
            "requested": True,
            "saved": bool(replay_object_name),
            "error": replay_error,
        }

    # 8. 更新 Run
    if cancelled:
        run.status = RunStatus.stopped
    elif not all_samples and not incidents_data:
        run.status = RunStatus.failed
        summary["error_message"] = "未采集到有效性能指标"
    else:
        run.status = RunStatus.completed
    run.finished_at = datetime.now()
    run.duration_ms = total_ms
    run.summary_json = summary
    await db.commit()
    await events.record(
        event_type="run_completed",
        phase="finalizing",
        action="complete_run",
        parameters={"cancelled": cancelled, "capture_replay": capture_replay},
        result={"status": run.status.value, "summary": summary},
        duration_ms=total_ms,
    )

    await _safe_publish(
        run.id,
        {
            "type": "completed",
            "run_id": run.id,
            "status": run.status.value,
            "duration_ms": total_ms,
            "summary": summary,
            "progress": 100,
            "current_step": "执行完成" if run.status == RunStatus.completed else "执行已停止",
            "device_status": "online" if device_lost_at is None else "offline",
            "error": summary.get("error_message"),
        },
    )
