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
import json
import logging
import subprocess
import time
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import publish_run_event
from app.models.mobile_special import (
    MobileSpecialRun,
    MobileIncident,
    RunStatus,
    IncidentType,
)
from app.services.mobile_special.adb_client import run_adb_shell
from app.services.mobile_special.parsers import parse_logcat_crash, parse_logcat_anr

logger = logging.getLogger(__name__)


async def _safe_publish(run_id: int, payload: dict) -> None:
    try:
        await publish_run_event(run_id, payload)
    except Exception:
        pass


def _check_device_reachable(serial: str, timeout: int = 10) -> tuple[bool, str]:
    cmd = ["adb", "-s", serial, "get-state"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        stdout = (proc.stdout or "").strip()
        if proc.returncode == 0 and stdout == "device":
            return True, "设备在线"
        if stdout == "offline":
            return False, f"设备 {serial} 当前处于 offline"
        if stdout == "unauthorized":
            return False, f"设备 {serial} 未授权，请在手机上确认 USB 调试授权"
        return False, f"设备 {serial} 不可用：{stdout}"
    except Exception as e:
        return False, str(e)[:500]


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
        "adb", "-s", serial, "shell",
        "monkey",
        "-p", package,
        "-s", str(seed),
        "--throttle", str(interval_ms),
        "--pct-syskeys", "0",  # 禁用系统按键避免干扰
        "--pct-nav", "0",
        "--pct-majornav", "0",
        "-v",  # verbose
        str(count),
    ]


def _start_app(serial: str, package: str) -> bool:
    cmd = ["adb", "-s", serial, "shell", "am", "start", "-n", f"{package}/.MainActivity"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return proc.returncode == 0
    except Exception:
        return False


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
) -> None:
    """执行一个 Android 稳定性专项任务（Monkey 探索模式）"""
    config = run.config_snapshot or {}

    device_serial = config.get("device_serial") or run.device_serial
    app_package = config.get("app_package") or run.app_package

    duration_seconds = config.get("duration_seconds", 300)
    operation_interval_ms = config.get("operation_interval_ms", 500)
    seed = config.get("monkey_seed", 12345)

    # 1. 校验输入
    validation_errors = _validate_inputs(device_serial, app_package, config)
    if validation_errors:
        run.status = RunStatus.failed
        run.finished_at = datetime.now()
        run.summary_json = {"error_message": "; ".join(validation_errors)}
        await db.commit()
        await _safe_publish(run.id, {
            "type": "completed", "run_id": run.id,
            "status": RunStatus.failed.value,
        })
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
        await _safe_publish(run.id, {
            "type": "completed", "run_id": run.id,
            "status": RunStatus.failed.value,
        })
        return

    run.started_at = datetime.now()
    run.status = RunStatus.running
    await db.commit()

    await _safe_publish(run.id, {
        "type": "started", "run_id": run.id, "device_serial": device_serial,
    })

    # 3. 启动 App
    if config.get("auto_start", True):
        await asyncio.get_event_loop().run_in_executor(
            None, _start_app, device_serial, app_package
        )
        await asyncio.sleep(3)

    # 4. 启动 logcat 监控 crash/ANR
    logcat_task = asyncio.create_task(
        _run_logcat_monitor(device_serial, run.id, duration_seconds)
    )

    # 5. 执行 monkey 命令
    monkey_cmd = _build_monkey_cmd(
        serial=device_serial,
        package=app_package,
        interval_ms=operation_interval_ms,
        seed=seed,
        count=999999999,
    )

    start_time = time.monotonic()
    completed_actions = 0

    try:
        proc = await asyncio.create_subprocess_exec(
            *monkey_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # 按 interval 报告进度
        elapsed = 0
        while (time.monotonic() - start_time) < duration_seconds:
            await asyncio.sleep(min(30, duration_seconds - elapsed))
            elapsed = time.monotonic() - start_time
            completed_actions += 100  # 粗略估算
            await _safe_publish(run.id, {
                "type": "progress", "run_id": run.id,
                "elapsed_seconds": int(elapsed),
                "completed_actions": completed_actions,
            })
            if elapsed >= duration_seconds:
                break

        # 停止 monkey
        try:
            proc.terminate()
            await asyncio.wait_for(proc.wait(), timeout=5)
        except Exception:
            pass

    except Exception as e:
        logger.exception("monkey execution error for run %s: %s", run.id, e)

    # 6. 等待 logcat 完成
    crashes, anrs = await asyncio.wait_for(logcat_task, timeout=30)
    total_ms = int((time.monotonic() - start_time) * 1000)

    # 7. 保存 incidents
    all_incidents = crashes + anrs
    crash_count = len([i for i in all_incidents if i.get("incident_type") == IncidentType.crash.value])
    anr_count = len([i for i in all_incidents if i.get("incident_type") == IncidentType.anr.value])

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

    # 9. 更新 Run
    run.status = RunStatus.completed
    run.finished_at = datetime.now()
    run.duration_ms = total_ms
    run.summary_json = summary
    await db.commit()

    await _safe_publish(run.id, {
        "type": "completed", "run_id": run.id,
        "status": RunStatus.completed.value,
        "duration_ms": total_ms,
        "summary": summary,
    })
