"""Safe Android app setup actions shared by mobile special executors."""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

from app.core.minio_client import download_file
from app.services.adb_resilience import safe_run_adb


class AndroidPreflightError(RuntimeError):
    """Raised when a requested Android setup action cannot be completed."""


def _run_adb(serial: str, args: list[str], *, timeout: int = 60):
    process = safe_run_adb(serial, args, timeout=timeout, retries=1)
    if process is None:
        raise AndroidPreflightError(f"ADB 执行失败: {' '.join(args)}")
    return process


def _run_adb_checked(serial: str, args: list[str], *, timeout: int = 60) -> None:
    process = _run_adb(serial, args, timeout=timeout)
    if process.returncode != 0:
        detail = (process.stderr or process.stdout or "").strip()
        suffix = f" ({detail[:300]})" if detail else ""
        raise AndroidPreflightError(f"ADB 操作失败: {' '.join(args)}{suffix}")


def build_android_launch_command(package: str, activity: str | None = None) -> list[str]:
    """Build a safe launch command for an Android package.

    An explicit activity is useful for deep links or apps with a known entry
    point. When it is omitted, Android's launcher intent is used so the
    executor does not assume every APK has ``.MainActivity``.
    """

    normalized_package = str(package or "").strip()
    if not normalized_package:
        raise AndroidPreflightError("启动应用需要 app_package")
    normalized_activity = str(activity or "").strip()
    if normalized_activity:
        component = normalized_activity if "/" in normalized_activity else f"{normalized_package}/{normalized_activity}"
        return ["shell", "am", "start", "-n", component]
    return [
        "shell",
        "monkey",
        "-p",
        normalized_package,
        "-c",
        "android.intent.category.LAUNCHER",
        "1",
    ]


def launch_android_app(serial: str, package: str, activity: str | None = None) -> list[str]:
    """Launch an Android app and return the executed ADB arguments."""

    command = build_android_launch_command(package, activity)
    _run_adb_checked(serial, command, timeout=15)
    return command


async def run_android_preflight(
    *,
    serial: str,
    package: str | None,
    config: dict,
    apk_object_name: str | None = None,
) -> dict[str, object]:
    """Apply opt-in install/uninstall/clear/launch actions before an Android run."""

    normalized_package = str(package or config.get("app_package") or "").strip()
    requested_actions = {
        "install": bool(config.get("install_apk") or config.get("install_before")),
        "uninstall_before": bool(config.get("uninstall_before")),
        "clear_data_before": bool(config.get("clear_data_before")),
        "launch_before": bool(config.get("launch_before")),
    }
    if not any(requested_actions.values()):
        return {"actions": [], "package": normalized_package}
    if not serial:
        raise AndroidPreflightError("未指定 Android 设备 serial")
    if (
        config.get("uninstall_before") or config.get("clear_data_before") or config.get("launch_before")
    ) and not normalized_package:
        raise AndroidPreflightError("Android 前置操作需要 app_package")

    actions: list[str] = []
    install_requested = requested_actions["install"]
    if config.get("uninstall_before"):
        process = await asyncio.to_thread(_run_adb, serial, ["shell", "pm", "uninstall", normalized_package])
        detail = (process.stderr or process.stdout or "").lower()
        if process.returncode != 0 and "unknown package" not in detail and "not installed" not in detail:
            raise AndroidPreflightError(f"卸载应用失败: {normalized_package}")
        actions.append("uninstall_before")

    if install_requested:
        if not apk_object_name:
            raise AndroidPreflightError("已开启 APK 安装，但没有绑定 APK 资产")
        suffix = Path(str(apk_object_name)).suffix or ".apk"
        temp_path = ""
        try:
            with tempfile.NamedTemporaryFile(prefix="atp-apk-", suffix=suffix, delete=False) as handle:
                temp_path = handle.name
            await asyncio.to_thread(download_file, apk_object_name, temp_path)
            await asyncio.to_thread(_run_adb_checked, serial, ["install", "-r", "-t", temp_path], timeout=120)
            actions.append("install")
        finally:
            if temp_path:
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    if config.get("clear_data_before"):
        await asyncio.to_thread(_run_adb_checked, serial, ["shell", "pm", "clear", normalized_package])
        actions.append("clear_data_before")

    if config.get("launch_before"):
        await asyncio.to_thread(
            launch_android_app,
            serial,
            normalized_package,
            str(config.get("launch_activity") or "").strip() or None,
        )
        actions.append("launch_before")

    return {"actions": actions, "package": normalized_package}


async def run_android_postflight(*, serial: str, package: str | None, config: dict) -> list[str]:
    """Apply opt-in cleanup after a run; cleanup errors are reported to the caller."""

    normalized_package = str(package or config.get("app_package") or "").strip()
    if not config.get("uninstall_after"):
        return []
    if not normalized_package:
        raise AndroidPreflightError("卸载后置操作需要 app_package")
    await asyncio.to_thread(_run_adb_checked, serial, ["shell", "pm", "uninstall", normalized_package])
    return ["uninstall_after"]
