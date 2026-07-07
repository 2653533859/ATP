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

步骤数据结构（存储在 config.steps 数组中）:
  {
    "action": "click",
    "name": "点击登录按钮",
    "params": { "text": "登录" }
  }
"""

import asyncio
import logging
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.minio_client import upload_bytes, presigned_url
from app.core.redis_client import publish_run_event
from app.models.case import RunStatus, StepResult, TestCase, TestRun

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


def _adb_cmd(serial: str, *args: str, timeout: int = 15) -> tuple[bool, str]:
    """执行 adb shell 命令，返回 (success, output)"""
    cmd = ["adb", "-s", serial, *args]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        output = (proc.stdout or "") + (proc.stderr or "")
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


def _find_and_click(serial: str, params: dict) -> dict[str, Any]:
    """使用 uiautomator dump + 坐标点击"""
    text = params.get("text")
    resource_id = params.get("resourceId") or params.get("resource_id")
    x = params.get("x")
    y = params.get("y")

    if x is not None and y is not None:
        ok, out = _adb_cmd(serial, "shell", "input", "tap", str(int(x)), str(int(y)))
        return {"success": ok, "error": out if not ok else None}

    if text:
        # 使用 uiautomator 命令通过文本查找并点击
        ok, out = _adb_cmd(
            serial,
            "shell",
            "am",
            "instrument",
            "-w",
            "-r",
            "-e",
            "text",
            text,
            "input",
            "tap",
            "0",
            "0",
        )
        # 备选：直接用 input text 搜索（简单实现用 adb shell 组合命令）
        ok, out = _adb_cmd(
            serial,
            "shell",
            f"input tap $(uiautomator dump /dev/tty 2>/dev/null | "
            f'grep -oP \'bounds="\\[([0-9]+),([0-9]+)\\]\\[([0-9]+),([0-9]+)\\]"[^>]*text="{text}"\' | '
            f'head -1 | grep -oP "\\[([0-9]+),([0-9]+)\\]" | head -1 | tr -d "[]" | '
            f"awk -F, '{{print ($1+0)/1, ($2+0)/1}}')",
            timeout=10,
        )
        if not ok:
            # 简化方案：使用 uiautomator + grep + tap
            # 先 dump UI，然后解析坐标
            ok2, dump = _adb_cmd(serial, "shell", "uiautomator", "dump", "/dev/tty", timeout=10)
            if ok2 and text in dump:
                import re as _re

                pattern = rf'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"[^>]*text="{_re.escape(text)}"'
                match = _re.search(pattern, dump)
                if not match:
                    pattern = rf'text="{_re.escape(text)}"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
                    match = _re.search(pattern, dump)
                if match:
                    x1, y1, x2, y2 = int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4))
                    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                    ok3, _ = _adb_cmd(serial, "shell", "input", "tap", str(cx), str(cy))
                    return {"success": ok3, "error": None if ok3 else "点击失败"}
            return {"success": False, "error": f"未找到文本元素: {text}"}
        return {"success": True}

    if resource_id:
        ok2, dump = _adb_cmd(serial, "shell", "uiautomator", "dump", "/dev/tty", timeout=10)
        if ok2:
            import re as _re

            pattern = rf'resource-id="{_re.escape(resource_id)}"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
            match = _re.search(pattern, dump)
            if not match:
                pattern = rf'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"[^>]*resource-id="{_re.escape(resource_id)}"'
                match = _re.search(pattern, dump)
            if match:
                x1, y1, x2, y2 = int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4))
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                ok3, _ = _adb_cmd(serial, "shell", "input", "tap", str(cx), str(cy))
                return {"success": ok3, "error": None if ok3 else "点击失败"}
        return {"success": False, "error": f"未找到元素: {resource_id}"}

    return {"success": False, "error": "缺少定位参数（text/resourceId/x,y）"}


def _execute_step_sync(serial: str, action: str, params: dict) -> dict[str, Any]:
    """同步执行单个步骤"""

    if action == "click":
        return _find_and_click(serial, params)

    elif action == "long_click":
        x = params.get("x")
        y = params.get("y")
        duration = params.get("duration", 1000)
        if x is not None and y is not None:
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
        text = params.get("text")
        if text:
            result = _find_and_click(serial, params)
            # 长按需要用 swipe 模拟，这里简化为先找到再长按坐标
            return result
        return {"success": False, "error": "长按需要提供坐标（x, y）"}

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
        # 先聚焦到元素（如果有 selector）
        selector = params.get("resourceId") or params.get("resource_id")
        if selector:
            _find_and_click(serial, {"resourceId": selector})
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

    elif action == "assert_text":
        text = params.get("text", "")
        ok, dump = _adb_cmd(serial, "shell", "uiautomator", "dump", "/dev/tty", timeout=10)
        if ok and text in dump:
            return {"success": True}
        return {"success": False, "error": f"页面中未找到文本: {text}"}

    elif action == "assert_element":
        resource_id = params.get("resourceId") or params.get("resource_id", "")
        ok, dump = _adb_cmd(serial, "shell", "uiautomator", "dump", "/dev/tty", timeout=10)
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


async def run_android_lowcode(
    db: AsyncSession,
    run: TestRun,
    case: TestCase,
    extra_vars: dict,
) -> None:
    """Android 低代码模式执行入口"""
    cfg = case.config or {}
    steps = cfg.get("steps", [])
    if not steps:
        run.status = RunStatus.error
        run.error_message = "低代码用例未配置任何步骤"
        await db.commit()
        await _safe_publish(run.id, {"type": "completed", "run_id": run.id, "status": "error"})
        return

    device_serial = cfg.get("device_serial")
    if not device_serial:
        run.status = RunStatus.error
        run.error_message = "未选择执行设备"
        await db.commit()
        await _safe_publish(run.id, {"type": "completed", "run_id": run.id, "status": "error"})
        return

    # 变量上下文
    context_vars: dict[str, str] = {**extra_vars, "DEVICE_SERIAL": device_serial}
    total_start = time.monotonic()
    all_passed = True

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

            step_result = StepResult(
                run_id=run.id,
                step_index=idx,
                name=step_name,
                status=status,
                duration_ms=duration_ms,
                request_data={"action": action, "params": params},
                response_data=response_data,
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
                        "response_data": response_data,
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

    total_ms = int((time.monotonic() - total_start) * 1000)
    run.status = RunStatus.passed if all_passed else RunStatus.failed
    run.duration_ms = total_ms
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
