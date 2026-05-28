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
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import publish_run_event
from app.models.mobile_special import (
    MobileSpecialRun,
    MobileMetricSample,
    RunStatus,
)
from app.services.adb_resilience import HeartbeatMonitor, ensure_reachable, safe_run_adb
from app.services.mobile_special.adb_client import (
    run_adb_shell,
    build_gfxinfo_cmd,
)
from app.services.mobile_special.parsers import parse_gfxinfo_framestats

logger = logging.getLogger(__name__)


async def _safe_publish(run_id: int, payload: dict) -> None:
    try:
        await publish_run_event(run_id, payload)
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
    cmd = [
        "adb", "-s", serial, "shell", "input", "swipe",
        str(x1), str(y1), str(x2), str(y2), str(duration_ms)
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return proc.returncode == 0
    except Exception:
        return False


async def _perform_tap(serial: str, x: int, y: int) -> bool:
    """执行点击操作"""
    cmd = ["adb", "-s", serial, "shell", "input", "tap", str(x), str(y)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return proc.returncode == 0
    except Exception:
        return False


async def run_mobile_special_fluency(
    db: AsyncSession,
    run: MobileSpecialRun,
) -> None:
    """执行一个 Android 流畅度专项任务"""
    config = run.config_snapshot or {}

    device_serial = config.get("device_serial") or run.device_serial
    app_package = config.get("app_package") or run.app_package
    stages = config.get("stages", [])

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
    start_cmd = ["adb", "-s", device_serial, "shell", "am", "start", "-n", f"{app_package}/.MainActivity"]
    try:
        subprocess.run(start_cmd, capture_output=True, text=True, timeout=15)
    except Exception as e:
        logger.warning("failed to start app for fluency run %s: %s", run.id, e)

    # 等待应用启动
    await asyncio.sleep(3)

    # 4. 每个 stage 循环采样（外包心跳监控，掉线时提前停止）
    all_samples: list[dict] = []
    start_time = time.monotonic()
    device_lost_at: Optional[float] = None

    def _on_device_lost(reason: str) -> None:
        nonlocal device_lost_at
        device_lost_at = time.monotonic() - start_time
        logger.warning(
            "fluency run %s: device %s lost (%s)", run.id, device_serial, reason,
        )

    try:
        async with HeartbeatMonitor(device_serial, on_lost=_on_device_lost) as hb:
            for idx, stage in enumerate(stages):
                if hb.lost:
                    break
                stage_name = stage.get("name", f"stage_{idx}")
                action = stage.get("action", "swipe")
                duration_between = stage.get("duration_seconds", 5)

                await _safe_publish(run.id, {
                    "type": "stage_start", "run_id": run.id,
                    "stage_index": idx, "stage_name": stage_name,
                })

                # 重置 gfxinfo
                await asyncio.get_event_loop().run_in_executor(
                    None, _reset_gfxinfo, device_serial, app_package
                )

                # 执行 stage 操作
                if action == "swipe":
                    coords = stage.get("coords", {})
                    await _perform_swipe(
                        device_serial,
                        coords.get("x1", 540), coords.get("y1", 1000),
                        coords.get("x2", 540), coords.get("y2", 500),
                    )
                elif action == "tap":
                    coords = stage.get("coords", {})
                    await _perform_tap(device_serial, coords.get("x", 540), coords.get("y", 1000))

                # 等待一段时间
                await asyncio.sleep(duration_between)

                # 采样 FPS
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

                await _safe_publish(run.id, {
                    "type": "stage_end", "run_id": run.id,
                    "stage_index": idx, "stage_name": stage_name,
                })

    except Exception as e:
        logger.exception("fluency execution error for run %s: %s", run.id, e)

    total_ms = int((time.monotonic() - start_time) * 1000)

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

    # 7. 更新 Run
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
