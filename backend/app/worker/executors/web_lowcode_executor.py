"""
Web UI 低代码执行器（Playwright 直接 API 调用）

支持的操作类型：
  - goto: 跳转 URL
  - click: 点击元素
  - fill: 输入文本
  - assert_text: 断言页面包含文本
  - assert_visible: 断言元素可见
  - wait: 等待指定时间（毫秒）
  - screenshot: 手动截图
  - select: 下拉选择
  - press: 按下键盘按键
  - hover: 鼠标悬停

步骤数据结构（存储在 config.steps 数组中）:
  {
    "action": "goto",
    "name": "打开首页",
    "params": { "url": "https://example.com" }
  }
"""
import asyncio
import logging
import re
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.minio_client import upload_bytes, upload_file, presigned_url
from app.core.redis_client import publish_run_event
from app.models.case import RunStatus, StepResult, TestCase, TestRun

logger = logging.getLogger(__name__)

# 变量占位符正则: {{VAR_NAME}}
VAR_PATTERN = re.compile(r"\{\{(\w+)\}\}")


def _replace_vars(text: str, context: dict[str, str]) -> str:
    """替换 {{VAR}} 占位符"""
    if not text:
        return text
    return VAR_PATTERN.sub(lambda m: context.get(m.group(1), m.group(0)), text)


def _replace_vars_in_params(params: dict, context: dict[str, str]) -> dict:
    """递归替换 params 中所有字符串值的变量"""
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


async def _take_screenshot(page: Page, run_id: int, step_index: int) -> str | None:
    """截图并上传到 MinIO，返回预签名 URL"""
    try:
        screenshot_bytes = await page.screenshot(type="png")
        obj_name = f"screenshots/runs/{run_id}/step_{step_index}.png"
        await asyncio.get_event_loop().run_in_executor(
            None, upload_bytes, obj_name, screenshot_bytes, "image/png"
        )
        return presigned_url(obj_name)
    except Exception as e:
        logger.warning("Screenshot failed for run %s step %s: %s", run_id, step_index, e)
        return None


async def _execute_step(
    page: Page,
    action: str,
    params: dict,
    timeout_ms: int,
) -> dict[str, Any]:
    """执行单个步骤，返回 {success, error, data}"""
    if action == "goto":
        url = params.get("url", "")
        await page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
        return {"success": True, "data": {"url": page.url}}

    elif action == "click":
        selector = params.get("selector", "")
        await page.click(selector, timeout=timeout_ms)
        return {"success": True}

    elif action == "fill":
        selector = params.get("selector", "")
        value = params.get("value", "")
        await page.fill(selector, value, timeout=timeout_ms)
        return {"success": True}

    elif action == "assert_text":
        text = params.get("text", "")
        try:
            locator = page.locator(f"text={text}")
            await locator.wait_for(state="visible", timeout=timeout_ms)
            return {"success": True}
        except Exception:
            page_text = await page.inner_text("body")
            if text in page_text:
                return {"success": True}
            return {"success": False, "error": f"页面中未找到文本: {text}"}

    elif action == "assert_visible":
        selector = params.get("selector", "")
        try:
            await page.locator(selector).wait_for(state="visible", timeout=timeout_ms)
            return {"success": True}
        except Exception:
            return {"success": False, "error": f"元素不可见: {selector}"}

    elif action == "wait":
        ms = int(params.get("ms", 1000))
        await asyncio.sleep(ms / 1000)
        return {"success": True}

    elif action == "screenshot":
        return {"success": True, "data": {"manual_screenshot": True}}

    elif action == "select":
        selector = params.get("selector", "")
        value = params.get("value", "")
        await page.select_option(selector, value, timeout=timeout_ms)
        return {"success": True}

    elif action == "press":
        key = params.get("key", "Enter")
        selector = params.get("selector", "")
        if selector:
            await page.press(selector, key, timeout=timeout_ms)
        else:
            await page.keyboard.press(key)
        return {"success": True}

    elif action == "hover":
        selector = params.get("selector", "")
        await page.hover(selector, timeout=timeout_ms)
        return {"success": True}

    else:
        return {"success": False, "error": f"未知操作类型: {action}"}


async def run_web_lowcode(
    db: AsyncSession,
    run: TestRun,
    case: TestCase,
    extra_vars: dict,
) -> None:
    """低代码模式执行入口"""
    cfg = case.config or {}
    steps = cfg.get("steps", [])
    if not steps:
        run.status = RunStatus.error
        run.error_message = "低代码用例未配置任何步骤"
        await db.commit()
        await _safe_publish(run.id, {"type": "completed", "run_id": run.id, "status": "error"})
        return

    headless = cfg.get("headless", True)
    viewport_w = cfg.get("viewport", {}).get("width", 1280)
    viewport_h = cfg.get("viewport", {}).get("height", 720)
    timeout_sec = max(1, int(cfg.get("timeout", 60)))
    step_timeout_ms = timeout_sec * 1000

    # 变量上下文
    context_vars: dict[str, str] = {**extra_vars}

    total_start = time.monotonic()
    all_passed = True
    browser: Browser | None = None
    browser_context: BrowserContext | None = None
    pw = None
    video_url: str | None = None
    video_dir = Path(tempfile.mkdtemp(prefix=f"atp_video_{run.id}_"))

    try:
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(
            headless=headless,
            args=["--no-sandbox"],
        )
        browser_context: BrowserContext = await browser.new_context(
            viewport={"width": viewport_w, "height": viewport_h},
            record_video_dir=str(video_dir),
            record_video_size={"width": viewport_w, "height": viewport_h},
        )
        page: Page = await browser_context.new_page()

        for idx, step_def in enumerate(steps):
            step_start = time.monotonic()
            action = step_def.get("action", "")
            step_name = step_def.get("name", f"{action}_{idx}")
            raw_params = step_def.get("params", {})
            params = _replace_vars_in_params(raw_params, context_vars)

            status = RunStatus.passed
            error_message = None
            screenshot_url = None
            response_data: dict | None = None

            try:
                result = await _execute_step(page, action, params, step_timeout_ms)
                if not result.get("success"):
                    status = RunStatus.failed
                    error_message = result.get("error")
                    all_passed = False
                response_data = result.get("data")
            except Exception as e:
                status = RunStatus.failed
                error_message = str(e)[:2000]
                all_passed = False

            # 每步都截图（失败时特别重要）
            screenshot_url = await _take_screenshot(page, run.id, idx)

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

            await _safe_publish(run.id, {
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
            })

            # 失败后停止后续步骤
            if status == RunStatus.failed:
                break

    except Exception as e:
        logger.exception("web_lowcode run %s error: %s", run.id, e)
        all_passed = False
        run.error_message = str(e)[:500]

    finally:
        # 关闭 context 以确保录像写入完成
        if browser_context:
            try:
                await browser_context.close()
            except Exception:
                pass
        if browser:
            await browser.close()
        if pw:
            try:
                await pw.stop()
            except Exception:
                pass

        # 上传录像到 MinIO
        try:
            video_files = list(video_dir.glob("*.webm"))
            if video_files:
                video_path = video_files[0]
                obj_name = f"videos/runs/{run.id}/recording.webm"
                await asyncio.get_event_loop().run_in_executor(
                    None, upload_file, obj_name, str(video_path), "video/webm"
                )
                video_url = presigned_url(obj_name)
        except Exception as e:
            logger.warning("Video upload failed for run %s: %s", run.id, e)
        finally:
            shutil.rmtree(video_dir, ignore_errors=True)

    total_ms = int((time.monotonic() - total_start) * 1000)
    run.status = RunStatus.passed if all_passed else RunStatus.failed
    run.duration_ms = total_ms
    run.result_summary = {
        **(run.result_summary or {}),
        **({"video_url": video_url} if video_url else {}),
    }
    await db.commit()

    await _safe_publish(run.id, {
        "type": "completed",
        "run_id": run.id,
        "status": run.status.value,
        "duration_ms": total_ms,
        **({"video_url": video_url} if video_url else {}),
    })
