"""
Android 稳定性测试执行器（智能稳定性 / Monkey 探索模式）

执行流程：
  1. 校验设备 + 包名
  2. 可选：安装/启动 App
  3. 启动 logcat 监听 crash/ANR
  4. 运行 monkey 命令进行随机压力测试
  5. 持续 duration_seconds 后停止
  6. 收集 crash/ANR incidents
  7. 更新 MobileSpecialRun（completed/failed，summary_json）
"""

import asyncio
from contextlib import suppress
import json
import logging
import subprocess
import time
from datetime import datetime
from typing import Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import publish_run_event
from app.models.mobile_special import (
    MobileSpecialRun,
    MobileIncident,
    RunStatus,
    IncidentType,
)
from app.services.adb_resilience import HeartbeatMonitor, ensure_reachable, safe_run_adb
from app.services.mobile_special.adb_client import run_adb_shell
from app.services.mobile_special.parsers import parse_logcat_crash, parse_logcat_anr
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
    duration = config_json.get("duration_seconds", 0)
    if duration is not None and duration <= 0:
        errors.append(f"duration_seconds 必须大于 0: {duration}")
    return errors


def _build_monkey_cmd(
    serial: str,
    package: str,
    interval_ms: int = 500,
    seed: int = 12345,
    count: int = 999999999,
) -> list[str]:
    """构建 monkey 命令，禁用系统按键操作"""
    return [
        "adb",
        "-s",
        serial,
        "shell",
        "monkey",
        "-p",
        package,
        "-s",
        str(seed),
        "--throttle",
        str(interval_ms),
        "--pct-syskeys",
        "0",  # 禁用系统按键避免干扰
        "--pct-nav",
        "0",
        "--pct-majornav",
        "0",
        "-v",  # verbose
        str(count),
    ]


def _parse_monkey_event_line(line: str) -> dict | None:
    """Normalize a verbose Monkey line for the report timeline."""
    text = line.strip()
    if not text:
        return None
    if text.startswith(":Sending"):
        action = text[1:].split(":", 1)[0].strip()
        return {"action": action, "parameters": {"raw": text}}
    if text.startswith("Events injected:"):
        return {"action": "summary", "parameters": {"raw": text}}
    return None


async def _consume_monkey_output(
    stream,
    run_id: int,
    recorder: MobileRunEventRecorder,
) -> int:
    """Persist verbose Monkey output without allowing adb pipes to block."""
    if stream is None:
        return 0
    action_count = 0
    while True:
        line = await stream.readline()
        if not line:
            break
        text = line.decode("utf-8", errors="replace").strip()
        if not text:
            continue
        parsed = _parse_monkey_event_line(text)
        if parsed:
            action_count += 1 if parsed["action"] != "summary" else 0
            await recorder.record(
                event_type="monkey_action" if parsed["action"] != "summary" else "monkey_summary",
                phase="monkey",
                action=parsed["action"],
                level="info",
                message=text[:4000],
                parameters={**parsed["parameters"], "index": action_count},
                result={"raw": text},
                commit=False,
            )
        else:
            await recorder.record(
                event_type="monkey_log",
                phase="monkey",
                level="debug",
                message=text[:4000],
                parameters={"raw": text},
                result={"captured": True},
                commit=False,
            )
        await _safe_publish(
            run_id,
            {
                "type": "log",
                "run_id": run_id,
                "level": "info" if parsed else "debug",
                "message": text[:500],
            },
        )
    await recorder.flush()
    return action_count


def _start_app(serial: str, package: str) -> bool:
    proc = safe_run_adb(
        serial,
        ["shell", "am", "start", "-n", f"{package}/.MainActivity"],
        timeout=15,
        retries=1,
    )
    return proc is not None and proc.returncode == 0


def _parse_logcat_crashes(raw: str) -> list[dict]:
    """解析 logcat FATAL 输出，提取 crash incidents"""
    incidents = parse_logcat_crash(raw)
    anr_incidents = parse_logcat_anr(raw)
    return incidents + anr_incidents


def _clear_logcat_buffer(serial: str) -> None:
    try:
        subprocess.run(
            ["adb", "-s", serial, "logcat", "-c"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        logger.debug("failed to clear logcat buffer for %s", serial, exc_info=True)


def _build_logcat_cmd(serial: str) -> list[str]:
    return ["adb", "-s", serial, "logcat", "-v", "time"]


async def _run_logcat_monitor(
    serial: str,
    run_id: int,
    duration_seconds: int,
) -> tuple[list[dict], list[dict]]:
    """后台运行 logcat，收集 crash 和 ANR"""
    raw_lines: list[str] = []
    start_time = time.monotonic()

    await asyncio.get_event_loop().run_in_executor(None, _clear_logcat_buffer, serial)

    proc = await asyncio.create_subprocess_exec(
        *_build_logcat_cmd(serial),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        while (time.monotonic() - start_time) < duration_seconds:
            if proc.stdout is None:
                break
            try:
                line = await asyncio.wait_for(proc.stdout.readline(), timeout=1)
            except asyncio.TimeoutError:
                if proc.returncode is not None:
                    break
                continue
            if not line:
                if proc.returncode is not None:
                    break
                continue
            raw_lines.append(line.decode("utf-8", errors="ignore"))
    finally:
        if proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except Exception:
                proc.kill()
                await proc.wait()

    raw_log = "".join(raw_lines)
    crashes = _parse_logcat_crashes(raw_log)
    return crashes, []


async def run_mobile_special_stability(
    db: AsyncSession,
    run: MobileSpecialRun,
    cancel_check: Callable[[], bool] | None = None,
) -> None:
    """执行一个 Android 稳定性专项任务（Monkey 探索模式）"""
    config = run.config_snapshot or {}

    device_serial = config.get("device_serial") or run.device_serial
    app_package = config.get("app_package") or run.app_package

    duration_seconds = config.get("duration_seconds", 300)
    operation_interval_ms = config.get("operation_interval_ms", 500)
    seed = config.get("monkey_seed", 12345)
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
        message="开始执行 Monkey 稳定性探索",
        parameters={"device_serial": device_serial, "app_package": app_package},
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
            "current_step": "启动 Monkey 稳定性探索",
            "device_status": "online",
        },
    )

    # 3. 启动 App
    if config.get("auto_start", True):
        app_started = await asyncio.get_event_loop().run_in_executor(None, _start_app, device_serial, app_package)
        await events.record(
            event_type="action",
            phase="app_setup",
            action="start_app",
            parameters={"package": app_package},
            result={"ok": bool(app_started)},
        )
        await asyncio.sleep(3)

    # 4. 启动 logcat 监控 crash/ANR
    logcat_task = asyncio.create_task(_run_logcat_monitor(device_serial, run.id, duration_seconds))

    # 5. 执行 monkey 命令（外包心跳监控；掉线时同时取消 monkey 和 logcat）
    monkey_cmd = _build_monkey_cmd(
        serial=device_serial,
        package=app_package,
        interval_ms=operation_interval_ms,
        seed=seed,
        count=999999999,
    )

    await _safe_publish(
        run.id,
        {
            "type": "log",
            "run_id": run.id,
            "level": "info",
            "message": "开始执行 Monkey 稳定性探索",
        },
    )
    await events.record(
        event_type="monkey_start",
        phase="monkey",
        action="start_monkey",
        message="开始执行 Monkey 稳定性探索",
        parameters={
            "command": monkey_cmd,
            "seed": seed,
            "duration_seconds": duration_seconds,
            "operation_interval_ms": operation_interval_ms,
        },
        result={"started": True},
    )

    start_time = time.monotonic()
    completed_actions = 0
    device_lost_at: Optional[float] = None
    monkey_proc: Optional[asyncio.subprocess.Process] = None
    cancelled = False

    def _on_device_lost(reason: str) -> None:
        nonlocal device_lost_at
        device_lost_at = time.monotonic() - start_time
        logger.warning(
            "stability run %s: device %s lost (%s)",
            run.id,
            device_serial,
            reason,
        )
        # 终止 monkey 子进程
        if monkey_proc is not None and monkey_proc.returncode is None:
            try:
                monkey_proc.terminate()
            except Exception:
                pass

    try:
        async with HeartbeatMonitor(device_serial, on_lost=_on_device_lost, executor_label="stability") as hb:
            monkey_proc = await asyncio.create_subprocess_exec(
                *monkey_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            output_task = asyncio.create_task(
                _consume_monkey_output(getattr(monkey_proc, "stdout", None), run.id, events)
            )

            # 每秒检查取消信号，每 30 秒报告一次进度。
            elapsed = 0.0
            next_progress_at = 30.0
            while (time.monotonic() - start_time) < duration_seconds:
                if hb.lost:
                    break
                if cancel_check is not None and await asyncio.to_thread(cancel_check):
                    cancelled = True
                    break
                await asyncio.sleep(min(1.0, max(0.0, duration_seconds - elapsed)))
                elapsed = time.monotonic() - start_time
                if elapsed >= next_progress_at or elapsed >= duration_seconds:
                    completed_actions = max(completed_actions, int(elapsed * 100 / 30))
                    await _safe_publish(
                        run.id,
                        {
                            "type": "progress",
                            "run_id": run.id,
                            "elapsed_seconds": int(elapsed),
                            "completed_actions": completed_actions,
                            "progress": min(95, 35 + round(elapsed / max(float(duration_seconds), 1) * 60)),
                            "duration_seconds": float(duration_seconds),
                            "phase": "running",
                            "current_step": "Monkey 稳定性探索",
                            "device_serial": device_serial,
                            "device_status": "online",
                        },
                    )
                    await events.record(
                        event_type="monkey_progress",
                        phase="monkey",
                        action="progress",
                        parameters={"elapsed_seconds": int(elapsed), "duration_seconds": float(duration_seconds)},
                        result={"completed_action_count": completed_actions},
                    )
                    next_progress_at += 30
                if elapsed >= duration_seconds:
                    break

            # 停止 monkey
            if monkey_proc is not None and monkey_proc.returncode is None:
                try:
                    monkey_proc.terminate()
                    await asyncio.wait_for(monkey_proc.wait(), timeout=5)
                except Exception:
                    pass

            if "output_task" in locals():
                try:
                    completed_actions = max(completed_actions, await asyncio.wait_for(output_task, timeout=5))
                except Exception:
                    output_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await output_task

    except Exception as e:
        logger.exception("monkey execution error for run %s: %s", run.id, e)

    # 6. 等待 logcat 完成；取消时立即终止 logcat 子进程。
    if cancelled:
        logcat_task.cancel()
        with suppress(asyncio.CancelledError):
            await logcat_task
        crashes, anrs = [], []
    else:
        crashes, anrs = await asyncio.wait_for(logcat_task, timeout=30)
    total_ms = int((time.monotonic() - start_time) * 1000)

    # 7. 保存 incidents
    all_incidents = crashes + anrs
    await _safe_publish(
        run.id,
        {
            "type": "phase",
            "run_id": run.id,
            "phase": "incidents",
            "progress": 95,
            "current_step": "分析 Crash/ANR 日志",
            "device_serial": device_serial,
            "device_status": "online" if device_lost_at is None else "offline",
        },
    )
    for incident in all_incidents:
        await _safe_publish(
            run.id,
            {
                "type": "incident",
                "run_id": run.id,
                "incident_type": incident.get("incident_type", "crash"),
                "title": incident.get("title") or "检测到移动端异常",
                "detail": str(incident.get("detail") or "")[:500],
                "incident_count": len(all_incidents),
            },
        )
    crash_count = len([i for i in all_incidents if i.get("incident_type") == IncidentType.crash.value])
    anr_count = len([i for i in all_incidents if i.get("incident_type") == IncidentType.anr.value])
    await events.record(
        event_type="phase",
        phase="incidents",
        action="collect_incidents",
        parameters={"logcat_collected": True},
        result={"crash_count": crash_count, "anr_count": anr_count},
    )

    for inc in all_incidents:
        incident = MobileIncident(
            run_id=run.id,
            incident_type=inc.get("incident_type", IncidentType.crash),
            event_time=inc.get("event_time", datetime.now()),
            title=inc.get("title"),
            detail=inc.get("detail"),
            process_name=inc.get("process_name"),
            thread_name=inc.get("thread_name"),
        )
        db.add(incident)
    await db.commit()

    # 8. 构建 summary
    summary = {
        "explore_duration_seconds": int(total_ms / 1000),
        "operation_interval_ms": operation_interval_ms,
        "crash_count": crash_count,
        "anr_count": anr_count,
        "completed_action_count": completed_actions,
        "app_restart_count": 0,
    }
    if device_lost_at is not None:
        summary["device_lost"] = True
        summary["device_lost_at_sec"] = round(device_lost_at, 2)

    # 9. 更新 Run
    run.status = RunStatus.stopped if cancelled else RunStatus.completed
    run.finished_at = datetime.now()
    run.duration_ms = total_ms
    run.summary_json = summary
    await db.commit()
    await events.record(
        event_type="run_completed",
        phase="finalizing",
        action="complete_run",
        parameters={"seed": seed, "cancelled": cancelled},
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
        },
    )
