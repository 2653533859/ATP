"""
Android 流畅度测试执行器

执行流程：
  1. 校验设备 + 包名
  2. 启动 App 并进入目标页面
  3. 重置 gfxinfo 数据
  4. 执行场景步骤（滑动、点击等），同时采样 FPS/jank
  5. 收集整个场景的 FPS/jank 数据
  6. 按 stage 汇总流畅度指标
  7. 更新 MobileSpecialRun（completed/failed，summary_json）
"""

import asyncio
import logging
import subprocess
import time
from datetime import datetime
from typing import Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import publish_run_event
from app.models.mobile_special import (
    MobileSpecialRun,
    MobileMetricSample,
    RunStatus,
)
from app.services.adb_resilience import HeartbeatMonitor, ensure_reachable
from app.services.mobile_special.adb_client import (
    run_adb_shell,
    build_gfxinfo_cmd,
)
from app.services.mobile_special.parsers import parse_gfxinfo_framestats
from app.services.mobile_special.preflight import (
    AndroidPreflightError,
    build_android_launch_command,
    launch_android_app,
)
from app.services.mobile_special_events import MobileRunEventRecorder

logger = logging.getLogger(__name__)


async def _safe_publish(run_id: int, payload: dict) -> None:
    try:
        await publish_run_event(run_id, payload, run_type="mobile")
    except Exception:
        pass


def _check_device_reachable(serial: str, timeout: int = 10) -> tuple[bool, str]:
    return ensure_reachable(serial, timeout=timeout)


def _validate_inputs(device_serial: Optional[str], app_package: Optional[str], config_json: dict) -> list[str]:
    errors = []
    if not device_serial:
        errors.append("未指定执行设备 serial")
    if not app_package:
        errors.append("未指定 app_package")
    stages = config_json.get("stages", [])
    if not stages:
        errors.append("未配置任何 stage，请配置场景步骤")
    return errors


def _reset_gfxinfo(serial: str, package: str) -> None:
    """重置 gfxinfo 统计，以便获取新一轮数据"""
    cmd = ["adb", "-s", serial, "shell", "dumpsys", "gfxinfo", package, "reset"]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    except Exception:
        pass


def _parse_framestats(raw: str) -> Optional[dict]:
    """解析 gfxinfo framestats，提取 FPS 和 jank"""
    return parse_gfxinfo_framestats(raw, "")


def _compute_summary(samples: list[dict], crash_count: int, anr_count: int) -> dict:
    """从样本列表计算流畅度汇总"""
    fps_values = [s["metric_value"] for s in samples if s.get("metric_type") == "fps"]
    jank_total = sum(s.get("extra", {}).get("jank_count", 0) for s in samples if s.get("metric_type") == "fps")

    avg_fps = round(sum(fps_values) / len(fps_values), 2) if fps_values else None
    peak_fps = round(max(fps_values), 2) if fps_values else None

    return {
        "avg_fps": avg_fps,
        "peak_fps": peak_fps,
        "total_jank_count": jank_total,
        "crash_count": crash_count,
        "anr_count": anr_count,
        "_fps_sample_count": len(fps_values),
    }


async def _perform_swipe(serial: str, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> bool:
    """执行滑动操作"""
    cmd = ["adb", "-s", serial, "shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration_ms)]
    try:
        proc = await asyncio.to_thread(subprocess.run, cmd, capture_output=True, text=True, timeout=10)
        return proc.returncode == 0
    except Exception:
        return False


async def _perform_tap(serial: str, x: int, y: int) -> bool:
    """执行点击操作"""
    cmd = ["adb", "-s", serial, "shell", "input", "tap", str(x), str(y)]
    try:
        proc = await asyncio.to_thread(subprocess.run, cmd, capture_output=True, text=True, timeout=10)
        return proc.returncode == 0
    except Exception:
        return False


async def run_mobile_special_fluency(
    db: AsyncSession,
    run: MobileSpecialRun,
    cancel_check: Callable[[], bool] | None = None,
) -> None:
    """执行一个 Android 流畅度专项任务"""
    config = run.config_snapshot or {}

    device_serial = config.get("device_serial") or run.device_serial
    app_package = config.get("app_package") or run.app_package
    stages = config.get("stages", [])
    events = MobileRunEventRecorder(db, run.id)
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
        message="开始执行流畅度场景",
        parameters={"device_serial": device_serial, "app_package": app_package, "stage_count": len(stages)},
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
            "current_step": "准备流畅度场景",
            "device_status": "online",
        },
    )

    # 3. 启动 App（前置操作已启动时由 tasks_mobile_special 设置 auto_start=false）
    launch_activity = str(config.get("launch_activity") or "").strip() or None
    launch_args = build_android_launch_command(app_package, launch_activity)
    start_cmd = ["adb", "-s", device_serial, *launch_args]
    execution_error: str | None = None
    if config.get("auto_start", True):
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                launch_android_app,
                device_serial,
                app_package,
                launch_activity,
            )
            start_result = type("StartResult", (), {"returncode": 0})()
        except AndroidPreflightError as exc:
            execution_error = f"应用启动失败: {str(exc)[:500]}"
            start_result = type("StartResult", (), {"returncode": 1})()
        await events.record(
            event_type="action",
            phase="app_setup",
            action="start_app",
            parameters={"package": app_package, "command": start_cmd},
            result={
                "ok": start_result.returncode == 0,
                "return_code": start_result.returncode,
                "error": execution_error,
            },
        )
    else:
        start_result = type("StartResult", (), {"returncode": 0})()
        await events.record(
            event_type="action",
            phase="app_setup",
            action="start_app",
            parameters={"package": app_package, "command": start_cmd},
            result={"ok": True, "skipped": True, "reason": "前置操作已启动应用"},
        )

    # 等待应用启动
    if not execution_error:
        await asyncio.sleep(3)
    else:
        # 启动失败时不再对设备发送动作，避免把前置失败误报为场景成功。
        stages = []

    # 4. 每个 stage 循环采样（外包心跳监控，掉线时提前停止）
    all_samples: list[dict] = []
    start_time = time.monotonic()
    device_lost_at: Optional[float] = None
    cancelled = False

    def _on_device_lost(reason: str) -> None:
        nonlocal device_lost_at
        device_lost_at = time.monotonic() - start_time
        logger.warning(
            "fluency run %s: device %s lost (%s)",
            run.id,
            device_serial,
            reason,
        )

    try:
        async with HeartbeatMonitor(device_serial, on_lost=_on_device_lost, executor_label="fluency") as hb:
            for idx, stage in enumerate(stages):
                if hb.lost:
                    break
                if cancel_check is not None and await asyncio.to_thread(cancel_check):
                    cancelled = True
                    break
                stage_name = stage.get("name", f"stage_{idx}")
                action = stage.get("action", "swipe")
                duration_between = stage.get("duration_seconds", 5)

                await _safe_publish(
                    run.id,
                    {
                        "type": "stage_start",
                        "run_id": run.id,
                        "stage_index": idx,
                        "stage_name": stage_name,
                        "phase": "stage",
                        "progress": 35 + round(idx / max(len(stages), 1) * 60),
                        "current_step": stage_name,
                        "device_serial": device_serial,
                        "device_status": "online",
                    },
                )
                await events.record(
                    event_type="stage_start",
                    phase="stage",
                    action="start_stage",
                    message=stage_name,
                    parameters={"stage_index": idx, "stage": stage},
                    result={"started": True},
                )
                await _safe_publish(
                    run.id,
                    {
                        "type": "log",
                        "run_id": run.id,
                        "level": "info",
                        "message": f"开始流畅度步骤：{stage_name}",
                    },
                )

                # 重置 gfxinfo
                await asyncio.get_event_loop().run_in_executor(None, _reset_gfxinfo, device_serial, app_package)

                # 执行 stage 操作
                if action == "swipe":
                    coords = stage.get("coords", {})
                    action_ok = await _perform_swipe(
                        device_serial,
                        coords.get("x1", 540),
                        coords.get("y1", 1000),
                        coords.get("x2", 540),
                        coords.get("y2", 500),
                    )
                elif action == "tap":
                    coords = stage.get("coords", {})
                    action_ok = await _perform_tap(device_serial, coords.get("x", 540), coords.get("y", 1000))
                else:
                    action_ok = False
                    execution_error = f"不支持的流畅度操作: {action}"

                await events.record(
                    event_type="action",
                    phase="stage",
                    action=action,
                    message=stage_name,
                    parameters={
                        "stage_index": idx,
                        "coords": stage.get("coords", {}),
                        "duration_seconds": duration_between,
                    },
                    result={"ok": bool(action_ok), "error": execution_error if not action_ok else None},
                )
                if not action_ok:
                    execution_error = execution_error or f"流畅度操作失败: {stage_name}"
                    break

                # 等待一段时间
                remaining = float(duration_between)
                while remaining > 0:
                    sleep_for = min(1.0, remaining)
                    await asyncio.sleep(sleep_for)
                    remaining -= sleep_for
                    if cancel_check is not None and await asyncio.to_thread(cancel_check):
                        cancelled = True
                        break
                if cancelled:
                    break

                # 采样 FPS
                result: dict = {}
                raw = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: run_adb_shell(device_serial, build_gfxinfo_cmd(device_serial, app_package), timeout=10),
                )
                if raw:
                    result = _parse_framestats(raw)
                    if result:
                        result["sample_time"] = datetime.now()
                        result["stage_name"] = stage_name
                        all_samples.append(result)

                await _safe_publish(
                    run.id,
                    {
                        "type": "stage_end",
                        "run_id": run.id,
                        "stage_index": idx,
                        "stage_name": stage_name,
                        "phase": "stage",
                        "progress": 35 + round((idx + 1) / max(len(stages), 1) * 60),
                        "current_step": f"完成：{stage_name}",
                        "device_serial": device_serial,
                        "device_status": "online",
                        "sample_metrics": [
                            {
                                "metric_type": result.get("metric_type", "fps"),
                                "metric_value": float(result.get("metric_value", 0)),
                                "sample_time": result.get("sample_time").isoformat()
                                if hasattr(result.get("sample_time"), "isoformat")
                                else str(result.get("sample_time") or ""),
                            }
                        ]
                        if result
                        else [],
                    },
                )
                await events.record(
                    event_type="stage_end",
                    phase="stage",
                    action="finish_stage",
                    message=stage_name,
                    parameters={"stage_index": idx},
                    result={"ok": True, "sampled": bool(result)},
                )

    except Exception as e:
        logger.exception("fluency execution error for run %s: %s", run.id, e)
        execution_error = f"流畅度执行失败: {str(e)[:500]}"

    total_ms = int((time.monotonic() - start_time) * 1000)

    await _safe_publish(
        run.id,
        {
            "type": "phase",
            "run_id": run.id,
            "phase": "finalizing",
            "progress": 95,
            "current_step": "整理流畅度指标",
            "device_serial": device_serial,
            "device_status": "online" if device_lost_at is None else "offline",
        },
    )

    # 5. 保存样本
    for sample_data in all_samples:
        sample = MobileMetricSample(
            run_id=run.id,
            sample_time=sample_data.get("sample_time", datetime.now()),
            metric_type=sample_data.get("metric_type", "fps"),
            metric_value=sample_data.get("metric_value", 0),
            source=sample_data.get("source"),
            extra_json=sample_data.get("extra", {}),
        )
        db.add(sample)
    await db.commit()

    # 6. 构建 summary
    summary = _compute_summary(all_samples, crash_count=0, anr_count=0)
    if device_lost_at is not None:
        summary["device_lost"] = True
        summary["device_lost_at_sec"] = round(device_lost_at, 2)
    if execution_error:
        summary["error_message"] = execution_error

    # 7. 更新 Run
    if cancelled:
        run.status = RunStatus.stopped
    elif execution_error:
        run.status = RunStatus.failed
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
        parameters={"cancelled": cancelled},
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
            "current_step": (
                "执行完成"
                if run.status == RunStatus.completed
                else "执行失败"
                if run.status == RunStatus.failed
                else "执行已停止"
            ),
            "device_status": "online" if device_lost_at is None else "offline",
            "error": summary.get("error_message"),
        },
    )
