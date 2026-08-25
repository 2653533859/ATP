"""
Android UI 低代码执行器（uiautomator2 API 调用）

支持的操作类型：
  - click: 点击元素（text/resourceId/xpath/坐标）
  - long_click: 长按元素
  - swipe: 滑动（方向或坐标）
  - input: 输入文本
  - press_key: 按下按键（home/back/enter 等）
  - screenshot: 手动截图
  - assert_text: 断言文本存在
  - assert_element: 断言元素存在
  - wait: 等待指定时间
  - start_app: 启动应用
  - stop_app: 停止应用
  - rotate: 切换屏幕方向
  - grant_permission/revoke_permission: 授予或撤销应用权限
  - network_profile: 切换 Wi-Fi/移动网络/飞行模式
  - background/foreground: 切换应用前后台

步骤数据结构（存储在 config.steps 数组中）:
  {
    "action": "click",
    "name": "点击登录按钮",
    "params": { "text": "登录" }
  }
"""

import asyncio
import copy
import logging
import re
import shutil
import subprocess
import tempfile
from defusedxml import ElementTree as ET
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.minio_client import upload_bytes, upload_file, presigned_url
from app.core.redis_client import publish_run_event
from app.models.apk import Apk
from app.models.case import RunStatus, StepResult, TestCase, TestRun
from app.models.device import Device
from app.models.project import Module
from app.services.device_compatibility import DeviceCompatibilityError, build_android_device_matrix
from app.services.device_leases import DeviceLeaseConflict, acquire_device_lease, release_device_lease
from app.services.dataset_execution import redact_execution_evidence
from app.services.mobile_special.preflight import AndroidPreflightError, run_android_preflight

logger = logging.getLogger(__name__)

VAR_PATTERN = re.compile(r"\{\{(\w+)\}\}")


def _replace_vars(text: str, context: dict[str, str]) -> str:
    if not text:
        return text
    return VAR_PATTERN.sub(lambda m: context.get(m.group(1), m.group(0)), text)


def _replace_vars_in_params(params: dict, context: dict[str, str]) -> dict:
    result = {}
    for k, v in params.items():
        if isinstance(v, str):
            result[k] = _replace_vars(v, context)
        elif isinstance(v, dict):
            result[k] = _replace_vars_in_params(v, context)
        else:
            result[k] = v
    return result


async def _safe_publish(run_id: int, payload: dict) -> None:
    try:
        await publish_run_event(run_id, payload)
    except Exception:
        pass


def _adb_screenshot(serial: str) -> bytes | None:
    """通过 adb 截图，返回 PNG 字节"""
    cmd = ["adb", "-s", serial, "exec-out", "screencap", "-p"]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=10)
        if proc.returncode == 0 and proc.stdout:
            return proc.stdout
        return None
    except Exception:
        return None


async def _take_screenshot(serial: str, run_id: int, step_index: int) -> str | None:
    """截图并上传到 MinIO，返回预签名 URL"""
    try:
        data = await asyncio.get_event_loop().run_in_executor(None, _adb_screenshot, serial)
        if not data:
            return None
        obj_name = f"screenshots/runs/{run_id}/step_{step_index}.png"
        await asyncio.get_event_loop().run_in_executor(None, upload_bytes, obj_name, data, "image/png")
        return presigned_url(obj_name)
    except Exception as e:
        logger.warning("Screenshot failed for run %s step %s: %s", run_id, step_index, e)
        return None


async def _capture_android_text_artifact(
    serial: str,
    run_id: int,
    artifact_name: str,
    command: tuple[str, ...],
    *,
    max_bytes: int = 2_000_000,
) -> str | None:
    """Capture bounded device text output and associate it with the run."""

    ok, output = await asyncio.to_thread(_adb_cmd, serial, *command, timeout=30)
    if not ok or not output:
        return None
    data = output.encode("utf-8", errors="replace")[:max_bytes]
    object_name = f"android-artifacts/runs/{run_id}/{artifact_name}.txt"
    try:
        await asyncio.to_thread(upload_bytes, object_name, data, "text/plain; charset=utf-8")
        return presigned_url(object_name)
    except Exception as exc:
        logger.warning("Android artifact upload failed for run %s: %s", run_id, exc)
        return None


def _start_screen_recording(serial: str, remote_path: str, max_seconds: int):
    """Start bounded device-side screen recording; unsupported devices return None."""
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
        logger.warning("Android screen recording unavailable for %s: %s", serial, exc)
        return None


async def _finish_screen_recording(serial: str, process, remote_path: str, run_id: int) -> str | None:
    """Stop, pull and upload a device recording, always cleaning the remote file."""
    try:
        process.terminate()
        await asyncio.to_thread(process.wait, 10)
    except Exception:
        try:
            process.kill()
        except Exception:
            pass
    temp_file = tempfile.NamedTemporaryFile(prefix="atp-android-recording-", suffix=".mp4", delete=False)
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
        if pulled.returncode != 0 or not local_path.exists() or local_path.stat().st_size > 200_000_000:
            return None
        object_name = f"android-artifacts/runs/{run_id}/screen-recording.mp4"
        await asyncio.to_thread(upload_file, object_name, local_path, "video/mp4")
        return presigned_url(object_name)
    except Exception as exc:
        logger.warning("Android screen recording upload failed for run %s: %s", run_id, exc)
        return None
    finally:
        try:
            await asyncio.to_thread(subprocess.run, ["adb", "-s", serial, "shell", "rm", remote_path], timeout=10)
        except Exception:
            pass
        try:
            local_path.unlink(missing_ok=True)
        except OSError:
            pass


def _adb_cmd(serial: str, *args: str, timeout: int = 15) -> tuple[bool, str]:
    """执行 adb shell 命令，返回 (success, output)"""
    cmd = ["adb", "-s", serial, *args]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
        stdout = (
            (proc.stdout or b"").decode("utf-8", errors="replace")
            if isinstance(proc.stdout, bytes)
            else (proc.stdout or "")
        )
        stderr = (
            (proc.stderr or b"").decode("utf-8", errors="replace")
            if isinstance(proc.stderr, bytes)
            else (proc.stderr or "")
        )
        output = stdout + stderr
        return proc.returncode == 0, output.strip()
    except subprocess.TimeoutExpired:
        return False, "命令超时"
    except Exception as e:
        return False, str(e)


def _clear_input_text(serial: str, max_delete: int = 50) -> None:
    """将光标移到末尾并发送多次 DEL，避免拼接无效 keycode。"""
    _adb_cmd(serial, "shell", "input", "keyevent", "KEYCODE_MOVE_END")
    for _ in range(max_delete):
        ok, _ = _adb_cmd(serial, "shell", "input", "keyevent", "67")
        if not ok:
            break


_UI_BOUNDS_RE = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")


def _find_ui_bounds(dump: str, attribute: str, value: str) -> tuple[int, int, int, int] | None:
    """从 UIAutomator XML 中按属性查找控件 bounds。"""
    hierarchy_start = dump.find("<hierarchy")
    hierarchy_end = dump.find("</hierarchy>", hierarchy_start)
    if hierarchy_start >= 0 and hierarchy_end >= 0:
        try:
            root = ET.fromstring(dump[hierarchy_start : hierarchy_end + len("</hierarchy>")])
            for node in root.iter("node"):
                if node.attrib.get(attribute) != value:
                    continue
                match = _UI_BOUNDS_RE.fullmatch(node.attrib.get("bounds", ""))
                if match:
                    return tuple(int(item) for item in match.groups())
        except ET.ParseError:
            pass

    escaped = re.escape(value)
    patterns = (
        rf'{attribute}="{escaped}"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
        rf'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"[^>]*{attribute}="{escaped}"',
    )
    for pattern in patterns:
        match = re.search(pattern, dump)
        if match:
            return tuple(int(item) for item in match.groups())
    return None


def _uiautomator_dump(serial: str, timeout: int = 10) -> tuple[bool, str]:
    """获取 UI 层级；部分设备不会把 /dev/tty 内容回传给 adb，需要走文件兜底。"""
    ok, output = _adb_cmd(serial, "shell", "uiautomator", "dump", "/dev/tty", timeout=timeout)
    if ok and "<hierarchy" in output and "</hierarchy>" in output:
        return True, output

    hierarchy_path = "/sdcard/atp-ui-hierarchy.xml"
    dump_ok, dump_output = _adb_cmd(
        serial,
        "shell",
        "uiautomator",
        "dump",
        hierarchy_path,
        timeout=timeout,
    )
    if not dump_ok:
        return False, dump_output
    return _adb_cmd(serial, "shell", "cat", hierarchy_path, timeout=timeout)


def _locator_selectors(params: dict, *, text_key: str = "text") -> tuple[tuple[str, str], ...]:
    """按执行动作返回 UIAutomator 属性定位候选，保持 resource-id 优先。"""
    raw_selectors = (
        ("resource-id", params.get("resourceId") or params.get("resource_id")),
        ("text", params.get(text_key)),
        ("content-desc", params.get("contentDesc") or params.get("content_desc")),
    )
    return tuple(
        (attribute, value.strip() if isinstance(value, str) else str(value).strip())
        for attribute, value in raw_selectors
        if value is not None and str(value).strip()
    )


def _find_ui_center(serial: str, selectors: tuple[tuple[str, str], ...]) -> tuple[int, int] | None:
    """根据 UIAutomator 属性返回控件中心点；dump 失败或未命中时返回 None。"""
    if not selectors:
        return None
    ok, dump = _uiautomator_dump(serial, timeout=10)
    if not ok:
        return None
    for attribute, value in selectors:
        bounds = _find_ui_bounds(dump, attribute, value)
        if bounds:
            x1, y1, x2, y2 = bounds
            return (x1 + x2) // 2, (y1 + y2) // 2
    return None


def _tap_point(serial: str, x: int, y: int) -> dict[str, Any]:
    ok, out = _adb_cmd(serial, "shell", "input", "tap", str(int(x)), str(int(y)))
    return {"success": ok, "error": out if not ok else None}


def _long_press_point(serial: str, x: int, y: int, duration: int) -> dict[str, Any]:
    ok, out = _adb_cmd(
        serial,
        "shell",
        "input",
        "swipe",
        str(int(x)),
        str(int(y)),
        str(int(x)),
        str(int(y)),
        str(int(duration)),
    )
    return {"success": ok, "error": out if not ok else None}


def _find_and_click(serial: str, params: dict) -> dict[str, Any]:
    """优先按录制到的控件属性点击，找不到时回退到录制坐标。"""
    text = params.get("text")
    resource_id = params.get("resourceId") or params.get("resource_id")
    content_desc = params.get("contentDesc") or params.get("content_desc")
    x = params.get("x")
    y = params.get("y")

    selectors = _locator_selectors(params)
    if selectors:
        center = _find_ui_center(serial, selectors)
        if center:
            return _tap_point(serial, *center)

        # 录制步骤同时保存原始坐标，控件属性变化或 UIAutomator 不可用时仍可执行。
        if x is not None and y is not None:
            return _tap_point(serial, x, y)

        if resource_id:
            return {"success": False, "error": f"未找到元素: {resource_id}"}
        if text:
            return {"success": False, "error": f"未找到文本元素: {text}"}
        return {"success": False, "error": f"未找到元素: {content_desc}"}

    if x is not None and y is not None:
        return _tap_point(serial, x, y)

    return {"success": False, "error": "缺少定位参数（text/resourceId/x,y）"}


def _execute_step_sync(serial: str, action: str, params: dict) -> dict[str, Any]:
    """同步执行单个步骤"""

    if action == "click":
        return _find_and_click(serial, params)

    elif action == "long_click":
        x = params.get("x")
        y = params.get("y")
        duration = params.get("duration", 1000)
        selectors = _locator_selectors(params)
        center = _find_ui_center(serial, selectors)
        if center:
            return _long_press_point(serial, *center, int(duration))
        if x is not None and y is not None:
            return _long_press_point(serial, x, y, int(duration))
        if selectors:
            return {"success": False, "error": "未找到长按目标元素"}
        return {"success": False, "error": "长按需要定位属性或坐标（x, y）"}

    elif action == "swipe":
        direction = params.get("direction")
        if direction:
            swipe_map = {
                "up": ("540", "1600", "540", "400"),
                "down": ("540", "400", "540", "1600"),
                "left": ("900", "960", "100", "960"),
                "right": ("100", "960", "900", "960"),
            }
            coords = swipe_map.get(direction)
            if coords:
                duration = str(params.get("duration", 300))
                ok, out = _adb_cmd(serial, "shell", "input", "swipe", *coords, duration)
                return {"success": ok, "error": out if not ok else None}
            return {"success": False, "error": f"未知滑动方向: {direction}"}
        # 自定义坐标滑动
        x1 = params.get("x1", params.get("startX"))
        y1 = params.get("y1", params.get("startY"))
        x2 = params.get("x2", params.get("endX"))
        y2 = params.get("y2", params.get("endY"))
        if all(v is not None for v in [x1, y1, x2, y2]):
            duration = str(params.get("duration", 300))
            ok, out = _adb_cmd(
                serial, "shell", "input", "swipe", str(int(x1)), str(int(y1)), str(int(x2)), str(int(y2)), duration
            )
            return {"success": ok, "error": out if not ok else None}
        return {"success": False, "error": "滑动需要 direction 或坐标参数"}

    elif action == "input":
        text = params.get("text", params.get("value", ""))
        clear = params.get("clear", False)
        # text 是输入内容，targetText 才是输入框的文本定位，避免把输入值当成控件。
        target_params = {
            "text": params.get("targetText") or params.get("target_text"),
            "resourceId": params.get("resourceId") or params.get("resource_id"),
            "contentDesc": params.get("contentDesc") or params.get("content_desc"),
        }
        target_selectors = _locator_selectors(target_params)
        if target_selectors:
            target_result = _find_and_click(serial, target_params)
            if not target_result["success"]:
                return target_result
            import time as _time

            _time.sleep(0.3)
        if clear:
            _clear_input_text(serial)
        # 输入文本（通过 adb shell input text）
        # 处理中文等特殊字符：使用 am broadcast
        escaped = text.replace(" ", "%s").replace("&", "\\&").replace("<", "\\<").replace(">", "\\>")
        ok, out = _adb_cmd(serial, "shell", "input", "text", escaped, timeout=10)
        return {"success": ok, "error": out if not ok else None}

    elif action == "press_key":
        key = params.get("key", "").upper()
        key_map = {
            "HOME": "3",
            "BACK": "4",
            "ENTER": "66",
            "DELETE": "67",
            "MENU": "82",
            "POWER": "26",
            "VOLUME_UP": "24",
            "VOLUME_DOWN": "25",
            "TAB": "61",
            "ESCAPE": "111",
            "RECENT": "187",
        }
        keycode = key_map.get(key, key)
        ok, out = _adb_cmd(serial, "shell", "input", "keyevent", keycode)
        return {"success": ok, "error": out if not ok else None}

    elif action == "start_app":
        package = params.get("package", "")
        activity = params.get("activity", "")
        if activity:
            ok, out = _adb_cmd(serial, "shell", "am", "start", "-n", f"{package}/{activity}")
        else:
            ok, out = _adb_cmd(serial, "shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1")
        return {"success": ok, "error": out if not ok else None}

    elif action == "stop_app":
        package = params.get("package", "")
        ok, out = _adb_cmd(serial, "shell", "am", "force-stop", package)
        return {"success": ok, "error": out if not ok else None}

    elif action == "rotate":
        orientation = str(params.get("orientation", "portrait")).lower()
        rotation = {"portrait": "0", "landscape": "1", "reverse_portrait": "2", "reverse_landscape": "3"}.get(
            orientation
        )
        if rotation is None:
            return {"success": False, "error": f"未知屏幕方向: {orientation}"}
        ok, out = _adb_cmd(serial, "shell", "settings", "put", "system", "accelerometer_rotation", "0")
        if ok:
            ok, out = _adb_cmd(serial, "shell", "settings", "put", "system", "user_rotation", rotation)
        return {"success": ok, "error": out if not ok else None}

    elif action in {"grant_permission", "revoke_permission"}:
        package = str(params.get("package", "")).strip()
        permission = str(params.get("permission", "")).strip()
        if not package or not permission:
            return {"success": False, "error": "权限步骤需要 package 和 permission"}
        command = "grant" if action == "grant_permission" else "revoke"
        ok, out = _adb_cmd(serial, "shell", "pm", command, package, permission)
        return {"success": ok, "error": out if not ok else None}

    elif action == "network_profile":
        profile = str(params.get("profile", "normal")).lower()
        commands = {
            "normal": [("svc", "wifi", "enable"), ("svc", "data", "enable")],
            "wifi_off": [("svc", "wifi", "disable")],
            "data_off": [("svc", "data", "disable")],
            "offline": [("svc", "wifi", "disable"), ("svc", "data", "disable")],
        }.get(profile)
        if commands is None:
            return {"success": False, "error": f"未知网络配置: {profile}"}
        for command in commands:
            ok, out = _adb_cmd(serial, "shell", *command)
            if not ok:
                return {"success": False, "error": out}
        return {"success": True}

    elif action == "background":
        ok, out = _adb_cmd(serial, "shell", "input", "keyevent", "3")
        return {"success": ok, "error": out if not ok else None}

    elif action == "foreground":
        package = str(params.get("package", "")).strip()
        if not package:
            return {"success": False, "error": "前台步骤需要 package"}
        ok, out = _adb_cmd(serial, "shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1")
        return {"success": ok, "error": out if not ok else None}

    elif action == "assert_text":
        text = params.get("text", "")
        ok, dump = _uiautomator_dump(serial, timeout=10)
        if ok and text in dump:
            return {"success": True}
        return {"success": False, "error": f"页面中未找到文本: {text}"}

    elif action == "assert_element":
        resource_id = params.get("resourceId") or params.get("resource_id", "")
        ok, dump = _uiautomator_dump(serial, timeout=10)
        if ok and resource_id in dump:
            return {"success": True}
        return {"success": False, "error": f"未找到元素: {resource_id}"}

    elif action == "wait":
        ms = int(params.get("ms", 1000))
        import time as _time

        _time.sleep(ms / 1000)
        return {"success": True}

    elif action == "screenshot":
        return {"success": True, "data": {"manual_screenshot": True}}

    else:
        return {"success": False, "error": f"未知操作类型: {action}"}


async def _mark_run_error(db: AsyncSession, run: TestRun, message: str) -> None:
    run.status = RunStatus.error
    run.error_message = message
    await db.commit()
    await _safe_publish(run.id, {"type": "completed", "run_id": run.id, "status": "error"})


async def _resolve_lowcode_apk(
    db: AsyncSession,
    case: TestCase,
    cfg: dict[str, Any],
) -> tuple[str | None, str | None]:
    """Resolve the selected APK from the project-scoped asset record."""
    apk_id = cfg.get("apk_id")
    module_id = getattr(case, "module_id", None)
    module = await db.get(Module, module_id) if module_id is not None else None
    if module_id is not None and module is None:
        raise LookupError("用例所属模块不存在")
    if apk_id is None:
        object_name = cfg.get("apk_object_name")
        if object_name and module is not None:
            expected_prefix = f"apks/projects/{module.project_id}/"
            if not str(object_name).startswith(expected_prefix):
                raise PermissionError("APK 资产不属于用例所在项目")
        return object_name, None
    try:
        normalized_apk_id = int(apk_id)
    except (TypeError, ValueError) as exc:
        raise LookupError("绑定的 APK ID 无效") from exc

    apk = await db.get(Apk, normalized_apk_id)
    if apk is None:
        raise LookupError("绑定的 APK 资产不存在")
    if module is not None:
        if apk.project_id != module.project_id:
            raise PermissionError("APK 资产不属于用例所在项目")
    return apk.object_name, apk.package_name


async def run_android_lowcode(
    db: AsyncSession,
    run: TestRun,
    case: TestCase,
    extra_vars: dict,
) -> None:
    """Acquire a device lease, then execute one Android low-code case."""
    cfg = case.config or {}
    steps = cfg.get("steps", [])
    device_serial = cfg.get("device_serial")
    # Keep validation errors in the core so they do not require a database lookup.
    if not steps or not device_serial or (cfg.get("device_matrix") and not cfg.get("_device_matrix_variant")):
        await _run_android_lowcode_steps(db, run, case, extra_vars)
        return

    result = await db.execute(select(Device).where(Device.serial == str(device_serial)))
    device = result.scalar_one_or_none()
    if device is None:
        await _mark_run_error(db, run, f"设备未注册: {device_serial}")
        return

    lease_token: str | None = None
    try:
        try:
            lease_ttl = max(900, int(cfg.get("device_lease_ttl_seconds", 900)))
        except (TypeError, ValueError):
            lease_ttl = 900
        lease = await acquire_device_lease(
            db,
            int(device.id),
            owner_id=getattr(run, "triggered_by", None),
            owner_label=f"case-run:{run.id}",
            ttl_seconds=lease_ttl,
        )
        lease_token = lease.lease_token
        await db.commit()
        await _safe_publish(
            run.id,
            {
                "type": "step_progress",
                "run_id": run.id,
                "message": "已占用 Android 设备，开始执行低代码步骤",
                "device_serial": str(device_serial),
            },
        )
        await _run_android_lowcode_steps(db, run, case, extra_vars)
    except (DeviceLeaseConflict, LookupError) as exc:
        await _mark_run_error(db, run, f"设备租约冲突: {exc}")
    finally:
        if lease_token:
            try:
                await release_device_lease(db, int(device.id), lease_token)
                await db.commit()
            except Exception:
                logger.exception("Failed to release Android lease for run %s", run.id)


async def _run_android_lowcode_steps(
    db: AsyncSession,
    run: TestRun,
    case: TestCase,
    extra_vars: dict,
) -> None:
    """Android 低代码模式执行入口"""
    cfg = case.config or {}
    evidence_redact_fields = cfg.get("dataset_redact_fields") or []
    if cfg.get("device_matrix") and not cfg.get("_device_matrix_variant"):
        await _run_android_device_matrix(db, run, case, extra_vars)
        return
    steps = cfg.get("steps", [])
    if not steps:
        await _mark_run_error(db, run, "低代码用例未配置任何步骤")
        return

    device_serial = cfg.get("device_serial")
    if not device_serial:
        await _mark_run_error(db, run, "未选择执行设备")
        return

    # 变量上下文
    context_vars: dict[str, str] = {**extra_vars, "DEVICE_SERIAL": device_serial}
    total_start = time.monotonic()
    all_passed = True
    artifact_urls: dict[str, str] = {}
    recording_process = None
    recording_error: str | None = None
    recording_remote_path = f"/sdcard/atp-{run.id}.mp4"

    try:
        apk_object_name, apk_package = await _resolve_lowcode_apk(db, case, cfg)
    except (LookupError, PermissionError) as exc:
        await _mark_run_error(db, run, str(exc))
        return

    if apk_object_name:
        preflight_config = {**cfg, "install_apk": True}
        try:
            preflight_result = await run_android_preflight(
                serial=str(device_serial),
                package=cfg.get("app_package") or apk_package,
                config=preflight_config,
                apk_object_name=apk_object_name,
            )
        except AndroidPreflightError as exc:
            await _mark_run_error(db, run, f"Android APK 前置操作失败: {exc}")
            return
        await _safe_publish(
            run.id,
            {
                "type": "step_progress",
                "run_id": run.id,
                "message": "APK 已安装，开始执行低代码步骤",
                "actions": preflight_result.get("actions", []),
            },
        )

    if cfg.get("record_video"):
        recording_process = _start_screen_recording(
            device_serial,
            recording_remote_path,
            int(cfg.get("record_video_max_seconds", 600)),
        )
        if recording_process is None:
            recording_error = "设备不支持或无法启动录屏"

    try:
        for idx, step_def in enumerate(steps):
            step_start = time.monotonic()
            action = step_def.get("action", "")
            step_name = step_def.get("name", f"{action}_{idx}")
            raw_params = step_def.get("params", {})
            params = _replace_vars_in_params(raw_params, context_vars)

            status = RunStatus.passed
            error_message = None
            response_data: dict | None = None

            try:
                result = await asyncio.get_event_loop().run_in_executor(
                    None, _execute_step_sync, device_serial, action, params
                )
                if not result.get("success"):
                    status = RunStatus.failed
                    error_message = result.get("error")
                    all_passed = False
                response_data = result.get("data")
            except Exception as e:
                status = RunStatus.failed
                error_message = str(e)[:2000]
                all_passed = False

            # 每步截图
            screenshot_url = await _take_screenshot(device_serial, run.id, idx)

            duration_ms = int((time.monotonic() - step_start) * 1000)
            persisted_request_data = redact_execution_evidence(
                {"action": action, "params": params}, evidence_redact_fields
            )
            persisted_response_data = redact_execution_evidence(response_data, evidence_redact_fields)

            step_result = StepResult(
                run_id=run.id,
                step_index=idx,
                name=step_name,
                status=status,
                duration_ms=duration_ms,
                request_data=persisted_request_data,
                response_data=persisted_response_data,
                error_message=error_message,
                screenshot_url=screenshot_url,
            )
            db.add(step_result)
            await db.commit()

            await _safe_publish(
                run.id,
                {
                    "type": "step_result",
                    "run_id": run.id,
                    "step": {
                        "step_index": idx,
                        "name": step_name,
                        "status": status.value,
                        "duration_ms": duration_ms,
                        "request_data": step_result.request_data,
                        "response_data": persisted_response_data,
                        "error_message": error_message,
                        "screenshot_url": screenshot_url,
                    },
                },
            )

            # 失败后停止后续步骤
            if status == RunStatus.failed:
                break

    except Exception as e:
        logger.exception("android_lowcode run %s error: %s", run.id, e)
        all_passed = False
        run.error_message = str(e)[:500]

    if cfg.get("collect_device_artifacts", True):
        device_info_url = await _capture_android_text_artifact(
            device_serial,
            run.id,
            "device-info",
            ("shell", "getprop"),
        )
        if device_info_url:
            artifact_urls["device_info"] = device_info_url
        logcat_url = await _capture_android_text_artifact(
            device_serial,
            run.id,
            "logcat",
            ("shell", "logcat", "-d", "-v", "time", "-t", "10000"),
        )
        if logcat_url:
            artifact_urls["logcat"] = logcat_url
    if recording_process is not None:
        recording_url = await _finish_screen_recording(device_serial, recording_process, recording_remote_path, run.id)
        if recording_url:
            artifact_urls["screen_recording"] = recording_url
        else:
            artifact_urls["screen_recording_error"] = "设备未生成可上传的录屏文件"
    elif recording_error:
        artifact_urls["screen_recording_error"] = recording_error

    total_ms = int((time.monotonic() - total_start) * 1000)
    run.status = RunStatus.passed if all_passed else RunStatus.failed
    run.duration_ms = total_ms
    run.result_summary = {
        **(getattr(run, "result_summary", None) or {}),
        "android_artifacts": artifact_urls,
        "device_serial": device_serial,
    }
    await db.commit()

    await _safe_publish(
        run.id,
        {
            "type": "completed",
            "run_id": run.id,
            "status": run.status.value,
            "duration_ms": total_ms,
        },
    )


async def _run_android_device_matrix(
    db: AsyncSession,
    parent_run: TestRun,
    case: TestCase,
    extra_vars: dict,
) -> None:
    """Run one isolated child per compatible registered device and aggregate results."""
    config = case.config or {}
    requested = config.get("device_matrix") or []
    serials = [item if isinstance(item, str) else item.get("serial") for item in requested if item]
    result = await db.execute(select(Device).where(Device.serial.in_([str(serial) for serial in serials if serial])))
    available = [
        {
            "id": item.id,
            "serial": item.serial,
            "model": item.model,
            "brand": item.brand,
            "os_version": item.os_version,
            "sdk_version": item.sdk_version,
            "resolution": item.resolution,
        }
        for item in result.scalars().all()
    ]
    try:
        if len(available) != len({str(serial) for serial in serials if serial}):
            raise DeviceCompatibilityError("设备矩阵中包含未注册设备")
        variants = build_android_device_matrix(requested, available_devices=available)
    except DeviceCompatibilityError as exc:
        parent_run.status = RunStatus.error
        parent_run.error_message = str(exc)
        parent_run.result_summary = {**(parent_run.result_summary or {}), "device_matrix_error": str(exc)}
        await db.commit()
        await _safe_publish(parent_run.id, {"type": "completed", "run_id": parent_run.id, "status": "error"})
        return

    parent_run.status = RunStatus.running
    parent_run.result_summary = {
        **(parent_run.result_summary or {}),
        "device_matrix_total": len(variants),
        "device_matrix_variants": variants,
        "device_matrix_passed": 0,
        "device_matrix_failed": 0,
        "device_matrix_error": 0,
    }
    await db.commit()
    await _safe_publish(parent_run.id, {"type": "run_status", "run_id": parent_run.id, "status": "running"})

    child_specs: list[tuple[int, int, dict[str, Any]]] = []
    for index, variant in enumerate(variants):
        child = TestRun(
            case_id=case.id,
            triggered_by=parent_run.triggered_by,
            trace_id=parent_run.trace_id,
            status=RunStatus.pending,
            environment=parent_run.environment,
            iteration_index=index,
            iteration_data=variant,
            parent_run_id=parent_run.id,
        )
        db.add(child)
        await db.commit()
        await db.refresh(child)
        child_specs.append((child.id, index, variant))

    matrix_results = await asyncio.gather(
        *(
            _run_android_device_matrix_variant(
                child_id=child_id,
                case_id=case.id,
                module_id=getattr(case, "module_id", None),
                base_config=config,
                extra_vars=extra_vars,
                index=index,
                variant=variant,
                owner_id=parent_run.triggered_by,
            )
            for child_id, index, variant in child_specs
        )
    )
    counts = {"passed": 0, "failed": 0, "error": 0}
    for item in matrix_results:
        status_value = item["status"]
        counts[status_value if status_value in counts else "error"] += 1

    parent_run.status = RunStatus.passed if counts["failed"] == 0 and counts["error"] == 0 else RunStatus.failed
    parent_run.result_summary = {
        **(parent_run.result_summary or {}),
        "device_matrix_passed": counts["passed"],
        "device_matrix_failed": counts["failed"],
        "device_matrix_error": counts["error"],
        "device_matrix_results": matrix_results,
    }
    await db.commit()
    await _safe_publish(
        parent_run.id,
        {"type": "completed", "run_id": parent_run.id, "status": parent_run.status.value},
    )


async def _run_android_device_matrix_variant(
    *,
    child_id: int,
    case_id: int,
    module_id: int | None = None,
    base_config: dict[str, Any],
    extra_vars: dict,
    index: int,
    variant: dict[str, Any],
    owner_id: int | None,
) -> dict[str, Any]:
    """Execute one Android matrix child with its own DB session and device lease."""
    from app.core.database import AsyncSessionLocal

    result = {
        "run_id": child_id,
        "index": index,
        "serial": variant.get("serial"),
        "status": RunStatus.error.value,
        "duration_ms": None,
        "error": None,
    }
    async with AsyncSessionLocal() as child_db:
        child = await child_db.get(TestRun, child_id)
        if child is None:
            result["error"] = "设备矩阵子运行不存在"
            return result

        child.status = RunStatus.running
        await child_db.commit()
        child_config = copy.deepcopy(base_config)
        child_config.pop("device_matrix", None)
        child_config["_device_matrix_variant"] = True
        child_config["device_serial"] = variant["serial"]
        child_case = SimpleNamespace(id=case_id, module_id=module_id, config=child_config)
        lease_token: str | None = None
        try:
            device_id = variant.get("device_id")
            if device_id is None:
                raise LookupError(f"设备 {variant['serial']} 缺少注册 ID")
            lease = await acquire_device_lease(
                child_db,
                int(device_id),
                owner_id=owner_id,
                owner_label=f"case-run:{child.id}",
                ttl_seconds=max(900, int(base_config.get("device_lease_ttl_seconds", 900))),
            )
            lease_token = lease.lease_token
            await child_db.commit()
            await _run_android_lowcode_steps(child_db, child, child_case, extra_vars)
        except (DeviceLeaseConflict, LookupError) as exc:
            child.status = RunStatus.error
            child.error_message = f"设备租约冲突: {exc}"
            await child_db.commit()
        except Exception as exc:
            logger.exception("Android matrix child %s failed", child_id)
            child.status = RunStatus.error
            child.error_message = str(exc)[:1000]
            await child_db.commit()
        finally:
            if lease_token:
                try:
                    await release_device_lease(child_db, int(variant["device_id"]), lease_token)
                    await child_db.commit()
                except Exception:
                    logger.exception("Failed to release Android lease for run %s", child.id)

        result["status"] = child.status.value if hasattr(child.status, "value") else str(child.status)
        result["duration_ms"] = child.duration_ms
        result["error"] = child.error_message
        return result
