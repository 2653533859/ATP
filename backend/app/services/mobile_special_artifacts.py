"""Capture bounded Android end-of-run artifacts for mobile special reports."""

from __future__ import annotations

import asyncio
import logging
import subprocess
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.minio_client import upload_bytes
from app.models.mobile_special import ArtifactType, MobileRunArtifact, MobileSpecialRun
from app.services.mobile_special_events import MobileRunEventRecorder, sanitize_mobile_payload

logger = logging.getLogger(__name__)

MAX_LOGCAT_BYTES = 5_000_000
MAX_SCREENSHOT_BYTES = 10_000_000


def _safe_error(message: str) -> str:
    """Keep storage/ADB error summaries free of common credentials."""
    value = sanitize_mobile_payload({"error": message}).get("error", "未知产物错误")
    return str(value)[:300]


def _capture_logcat(serial: str) -> tuple[bytes | None, str | None]:
    try:
        process = subprocess.run(
            ["adb", "-s", serial, "logcat", "-d", "-v", "time", "-t", "10000"],
            capture_output=True,
            text=False,
            timeout=30,
        )
    except FileNotFoundError:
        return None, "adb 命令未找到"
    except subprocess.TimeoutExpired:
        return None, "读取设备日志超时"
    except OSError as exc:
        return None, f"读取设备日志失败: {exc}"
    if process.returncode != 0:
        detail = (process.stderr or b"").decode("utf-8", errors="replace").strip()
        return None, f"读取设备日志失败: {detail[:300] or f'返回码 {process.returncode}'}"
    data = (process.stdout or b"")[:MAX_LOGCAT_BYTES]
    if not data:
        return None, "设备日志为空"
    return data, None


def _capture_screenshot(serial: str) -> tuple[bytes | None, str | None]:
    try:
        process = subprocess.run(
            ["adb", "-s", serial, "exec-out", "screencap", "-p"],
            capture_output=True,
            text=False,
            timeout=20,
        )
    except FileNotFoundError:
        return None, "adb 命令未找到"
    except subprocess.TimeoutExpired:
        return None, "获取设备截图超时"
    except OSError as exc:
        return None, f"获取设备截图失败: {exc}"
    if process.returncode != 0:
        detail = (process.stderr or b"").decode("utf-8", errors="replace").strip()
        return None, f"获取设备截图失败: {detail[:300] or f'返回码 {process.returncode}'}"
    data = (process.stdout or b"")[:MAX_SCREENSHOT_BYTES]
    if not data:
        return None, "设备截图为空"
    if not data.startswith(b"\x89PNG"):
        return None, "设备截图不是有效 PNG"
    return data, None


async def _capture_one(
    db: AsyncSession,
    recorder: MobileRunEventRecorder,
    *,
    run_id: int,
    serial: str,
    kind: str,
    requested: bool,
) -> dict[str, Any]:
    if not requested:
        return {"requested": False, "saved": False}

    is_logcat = kind == "logcat"
    capture = _capture_logcat if is_logcat else _capture_screenshot
    artifact_type = ArtifactType.raw_log if is_logcat else ArtifactType.screenshot
    extension = "txt" if is_logcat else "png"
    content_type = "text/plain; charset=utf-8" if is_logcat else "image/png"
    file_name = f"run_{run_id}_final.{extension}"
    object_name = f"android-special/runs/{run_id}/final-{kind}.{extension}"

    await recorder.record(
        event_type="artifact_capture",
        phase="artifacts",
        action=f"capture_{kind}",
        parameters={"requested": True, "artifact_type": artifact_type.value},
        commit=False,
    )
    data, error = await asyncio.to_thread(capture, serial)
    if error or data is None:
        await recorder.record(
            event_type="artifact_capture",
            phase="artifacts",
            action=f"capture_{kind}",
            level="warning",
            result={"ok": False, "error": error or "未获取到设备产物"},
            commit=False,
        )
        return {"requested": True, "saved": False, "error": error or "未获取到设备产物"}

    try:
        await asyncio.to_thread(upload_bytes, object_name, data, content_type)
    except Exception as exc:
        logger.warning("failed to upload %s artifact for mobile run %s: %s", kind, run_id, exc)
        error = _safe_error(f"上传{('设备日志' if is_logcat else '设备截图')}失败: {exc}")
        await recorder.record(
            event_type="artifact_capture",
            phase="artifacts",
            action=f"upload_{kind}",
            level="warning",
            result={"ok": False, "error": error},
            commit=False,
        )
        return {"requested": True, "saved": False, "error": error}

    db.add(
        MobileRunArtifact(
            run_id=run_id,
            artifact_type=artifact_type,
            file_path=object_name,
            file_name=file_name,
            file_size=len(data),
        )
    )
    await recorder.record(
        event_type="artifact_capture",
        phase="artifacts",
        action=f"upload_{kind}",
        result={"ok": True, "file_name": file_name, "file_size": len(data)},
        commit=False,
    )
    return {
        "requested": True,
        "saved": True,
        "artifact_type": artifact_type.value,
        "file_name": file_name,
        "file_size": len(data),
    }


async def capture_mobile_run_artifacts(
    db: AsyncSession,
    run: MobileSpecialRun,
    recorder: MobileRunEventRecorder,
) -> dict[str, Any]:
    """Capture configured final artifacts without changing the run outcome."""
    config = run.config_snapshot or {}
    requested = {
        "logcat": config.get("capture_device_logs") is True,
        "screenshot": config.get("capture_screenshot") is True,
    }
    if not any(requested.values()):
        return {}

    statuses: dict[str, Any] = {}
    if not run.device_serial:
        for kind, enabled in requested.items():
            if enabled:
                statuses[kind] = {"requested": True, "saved": False, "error": "未指定设备 serial"}
                await recorder.record(
                    event_type="artifact_capture",
                    phase="artifacts",
                    action=f"capture_{kind}",
                    level="warning",
                    result={"ok": False, "error": "未指定设备 serial"},
                    commit=False,
                )
    else:
        for kind, enabled in requested.items():
            statuses[kind] = await _capture_one(
                db,
                recorder,
                run_id=run.id,
                serial=run.device_serial,
                kind=kind,
                requested=enabled,
            )

    summary = dict(run.summary_json or {})
    previous = summary.get("android_artifacts")
    artifact_summary = dict(previous) if isinstance(previous, dict) else {}
    artifact_summary.update(statuses)
    summary["android_artifacts"] = artifact_summary
    run.summary_json = summary
    had_pending_events = recorder.pending > 0
    await recorder.flush()
    if not had_pending_events:
        # A run that already reached the event cap still needs its artifact
        # rows and summary persisted.
        await db.commit()
    return statuses
