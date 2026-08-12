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
import copy
import logging
import re
import shutil
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.minio_client import download_file, read_bytes, upload_bytes, upload_file, presigned_url
from app.core.redis_client import publish_run_event
from app.models.case import RunStatus, StepResult, TestCase, TestRun
from app.models.project import Module
from app.models.web_assets import WebElementAsset, WebPageObject, WebVisualBaseline
from app.services.web_visuals import VisualCompareError, compare_png_bytes
from app.services.web_matrix import WebMatrixError, build_web_matrix
from app.services.dataset_execution import redact_execution_evidence
from app.services.web_network_guard import (
    guard_browser_request,
    sanitize_network_url,
)

logger = logging.getLogger(__name__)

# 变量占位符正则: {{VAR_NAME}}
VAR_PATTERN = re.compile(r"\{\{(\w+)\}\}")
WEB_FILE_PROJECT_PREFIX = "web-files/projects/"
SAFE_FILE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize_network_url(url: str) -> str:
    return sanitize_network_url(url)


def _format_exception_message(exc: Exception) -> str:
    message = str(exc).strip()
    return message if message else type(exc).__name__


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


def _locator_to_selector(locator: dict[str, Any]) -> str:
    """Convert a stored element locator into a Playwright selector string."""
    strategy = str(locator.get("strategy", "css")).strip().lower()
    value = str(locator.get("value", "")).strip()
    if not value:
        return ""
    if strategy in {"css", "locator"}:
        return value
    if strategy == "xpath":
        return f"xpath={value}"
    if strategy in {"text", "label", "placeholder", "role"}:
        selector = f"{strategy}={value}"
        name = str(locator.get("name", "")).strip()
        if strategy == "role" and name:
            selector += f'[name="{name.replace(chr(34), chr(92) + chr(34))}"]'
        return selector
    if strategy in {"test_id", "testid"}:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'[data-testid="{escaped}"]'
    return value


def _asset_selectors(asset: WebElementAsset) -> list[str]:
    selectors = [_locator_to_selector(asset.locator)]
    selectors.extend(_locator_to_selector(item) for item in (asset.fallback_locators or []) if isinstance(item, dict))
    return [selector for selector in selectors if selector]


async def _resolve_element_asset(
    db: AsyncSession, case: TestCase, params: dict
) -> tuple[dict, WebElementAsset | None, str | None]:
    """Resolve an optional project-scoped element asset without exposing internal fields."""
    raw_asset_id = params.get("element_asset_id")
    if raw_asset_id is None:
        return params, None, None
    try:
        asset_id = int(raw_asset_id)
    except (TypeError, ValueError):
        return params, None, "元素资产 ID 无效"

    asset = await db.get(WebElementAsset, asset_id)
    if asset is None:
        return params, None, "元素资产不存在"
    module = await db.get(Module, case.module_id)
    if module is None or module.project_id != asset.project_id:
        return params, None, "元素资产不属于当前项目"
    selectors = _asset_selectors(asset)
    if not selectors:
        return params, asset, "元素资产没有可用定位器"

    resolved = {**params, "selector": selectors[0], "_asset_selectors": selectors}
    return resolved, asset, None


async def _mark_element_asset_failed(db: AsyncSession, asset: WebElementAsset | None, reason: str | None) -> None:
    if asset is None or not reason:
        return
    asset.last_failed_at = datetime.now(timezone.utc)
    asset.last_failure_reason = reason[:2000]
    await db.commit()


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
        await asyncio.get_event_loop().run_in_executor(None, upload_bytes, obj_name, screenshot_bytes, "image/png")
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


async def _execute_step_with_asset_fallback(
    page: Page,
    action: str,
    params: dict,
    timeout_ms: int,
) -> dict[str, Any]:
    """Run an element-backed step and try its stored fallback locators in order."""
    selectors = params.get("_asset_selectors")
    if not isinstance(selectors, list) or len(selectors) <= 1:
        return await _execute_step(page, action, params, timeout_ms)

    try:
        result = await _execute_step(page, action, params, timeout_ms)
    except Exception as exc:
        result = {"success": False, "error": _format_exception_message(exc)}
    if result.get("success"):
        return result
    for index, selector in enumerate(selectors[1:], start=1):
        retry_params = {**params, "selector": selector}
        try:
            retry_result = await _execute_step(page, action, retry_params, timeout_ms)
        except Exception as exc:
            retry_result = {"success": False, "error": _format_exception_message(exc)}
        if retry_result.get("success"):
            retry_result["data"] = {**(retry_result.get("data") or {}), "fallback_locator_index": index}
            return retry_result
    return result


def _project_file_object(project_id: int | None, object_name: object) -> str | None:
    value = str(object_name or "")
    prefix = f"{WEB_FILE_PROJECT_PREFIX}{project_id}/" if project_id else ""
    return value if prefix and value.startswith(prefix) and len(value) > len(prefix) else None


async def _execute_web_file_step(
    page: Page,
    action: str,
    params: dict,
    timeout_ms: int,
    project_id: int | None,
    run_id: int,
) -> dict[str, Any]:
    """Handle project-scoped upload and download actions with bounded temp files."""
    selector = str(params.get("selector", "")).strip()
    if not selector:
        return {"success": False, "error": "文件步骤缺少选择器"}

    if action == "upload":
        object_name = _project_file_object(project_id, params.get("object_name"))
        if object_name is None:
            return {"success": False, "error": "上传文件引用必须属于当前项目"}
        temp_file = tempfile.NamedTemporaryFile(prefix="atp-web-upload-", delete=False)
        temp_file.close()
        temp_path = Path(temp_file.name)
        try:
            await asyncio.to_thread(download_file, object_name, temp_path)
            await page.set_input_files(selector, str(temp_path), timeout=timeout_ms)
            return {"success": True, "data": {"object_name": object_name}}
        except Exception as exc:
            return {"success": False, "error": _format_exception_message(exc)}
        finally:
            temp_path.unlink(missing_ok=True)

    if action == "download":
        expect_download = getattr(page, "expect_download", None)
        if expect_download is None:
            return {"success": False, "error": "当前浏览器页面不支持下载事件监听"}
        try:
            async with expect_download(timeout=timeout_ms) as download_info:
                await page.click(selector, timeout=timeout_ms)
            download = await download_info.value
            downloaded_path = await download.path()
            if not downloaded_path:
                return {"success": False, "error": "下载未生成本地文件"}
            suggested_name = str(getattr(download, "suggested_filename", "download.bin"))
            safe_name = SAFE_FILE_NAME.sub("_", suggested_name).strip("._") or "download.bin"
            object_name = f"web-files/runs/{run_id}/{uuid.uuid4().hex}_{safe_name}"
            await asyncio.to_thread(upload_file, object_name, downloaded_path, "application/octet-stream")
            return {"success": True, "data": {"object_name": object_name, "filename": safe_name}}
        except Exception as exc:
            return {"success": False, "error": _format_exception_message(exc)}

    return {"success": False, "error": f"未知文件操作类型: {action}"}


async def _execute_visual_assert(
    db: AsyncSession,
    page: Page,
    params: dict,
    project_id: int | None,
    run_id: int,
    step_index: int,
) -> dict[str, Any]:
    try:
        baseline_id = int(params.get("baseline_id"))
    except (TypeError, ValueError):
        return {"success": False, "error": "视觉断言缺少有效基线 ID"}
    baseline = await db.get(WebVisualBaseline, baseline_id)
    if baseline is None:
        return {"success": False, "error": "视觉基线不存在"}
    if project_id is None or baseline.project_id != project_id:
        return {"success": False, "error": "视觉基线不属于当前项目"}
    try:
        current_bytes = await page.screenshot(type="png")
        baseline_bytes = await asyncio.to_thread(read_bytes, baseline.object_name)
        result = compare_png_bytes(
            baseline_bytes,
            current_bytes,
            threshold=float(params.get("threshold", baseline.threshold)),
            pixel_threshold=int(params.get("pixel_threshold", baseline.pixel_threshold)),
            ignore_regions=params.get("ignore_regions", baseline.ignore_regions or []),
        )
    except (VisualCompareError, OSError, ValueError) as exc:
        return {"success": False, "error": str(exc)}
    diff_png = result.pop("diff_png", None)
    if diff_png and not result.get("match"):
        object_name = f"visual-diffs/runs/{run_id}/step_{step_index}.png"
        await asyncio.to_thread(upload_bytes, object_name, diff_png, "image/png")
        result["diff_url"] = presigned_url(object_name)
    return {
        "success": bool(result.get("match")),
        "data": result,
        "error": None if result.get("match") else "视觉差异超过阈值",
    }


async def _expand_page_object_steps(
    db: AsyncSession,
    steps: list[dict],
    project_id: int | None,
) -> tuple[list[dict], str | None]:
    """Expand a page-object step into the object's reusable low-code actions."""
    expanded: list[dict] = []
    for step in steps:
        if step.get("action") != "page_object":
            expanded.append(step)
            continue
        params = step.get("params") if isinstance(step.get("params"), dict) else {}
        try:
            object_id = int(params.get("page_object_id"))
        except (TypeError, ValueError):
            return [], "页面对象步骤缺少有效页面对象 ID"
        page_object = await db.get(WebPageObject, object_id)
        if page_object is None:
            return [], "页面对象不存在"
        if project_id is None or page_object.project_id != project_id:
            return [], "页面对象不属于当前项目"
        refs = {}
        for item in page_object.element_refs or []:
            if isinstance(item, dict) and item.get("alias") is not None:
                refs[str(item["alias"])] = item.get("asset_id")
        actions = page_object.actions or []
        if not actions:
            return [], "页面对象未配置公共动作"
        for action_index, action_def in enumerate(actions):
            if not isinstance(action_def, dict):
                continue
            action = str(action_def.get("step") or action_def.get("action") or "").strip()
            if not action or action == "page_object":
                return [], "页面对象包含无效公共动作"
            action_params = dict(action_def.get("params") or {})
            alias = action_def.get("alias") or action_def.get("element")
            asset_id = action_def.get("asset_id")
            if asset_id is None and alias is not None:
                asset_id = refs.get(str(alias))
            if asset_id is not None:
                action_params.setdefault("element_asset_id", asset_id)
            expanded.append(
                {
                    "action": action,
                    "name": f"{step.get('name', '页面对象')} / {action_def.get('name', f'动作_{action_index + 1}')}",
                    "params": action_params,
                }
            )
    return expanded, None


async def _run_web_matrix(
    db: AsyncSession,
    parent_run: TestRun,
    case: TestCase,
    extra_vars: dict,
    matrix: list[dict[str, Any]],
) -> None:
    """Run each validated matrix variant in an isolated session and browser context."""

    parent_run.status = RunStatus.running
    parent_run.result_summary = {
        **(parent_run.result_summary or {}),
        "matrix_total": len(matrix),
        "matrix_variants": [],
    }
    await db.commit()
    child_specs: list[tuple[int, int, dict[str, Any]]] = []
    for index, variant in enumerate(matrix):
        child = TestRun(
            case_id=case.id,
            triggered_by=parent_run.triggered_by,
            trace_id=parent_run.trace_id,
            status=RunStatus.pending,
            environment=parent_run.environment,
            iteration_index=index,
            iteration_data={"matrix": variant},
            parent_run_id=parent_run.id,
        )
        db.add(child)
        await db.flush()
        child_specs.append((child.id, index, variant))
    await db.commit()

    matrix_results = await asyncio.gather(
        *(
            _run_web_matrix_variant(
                child_id=child_id,
                case_id=case.id,
                module_id=case.module_id,
                base_config=case.config or {},
                extra_vars=extra_vars,
                index=index,
                variant=variant,
            )
            for child_id, index, variant in child_specs
        )
    )

    parent_run.result_summary = {
        **(parent_run.result_summary or {}),
        "matrix_variants": matrix_results,
        "matrix_passed": sum(item["status"] == RunStatus.passed.value for item in matrix_results),
        "matrix_failed": sum(item["status"] == RunStatus.failed.value for item in matrix_results),
        "matrix_error": sum(item["status"] == RunStatus.error.value for item in matrix_results),
    }
    parent_run.status = (
        RunStatus.passed
        if all(item["status"] == RunStatus.passed.value for item in matrix_results)
        else RunStatus.failed
    )
    await db.commit()
    await _safe_publish(
        parent_run.id,
        {
            "type": "completed",
            "run_id": parent_run.id,
            "status": parent_run.status.value,
            "matrix": matrix_results,
        },
    )


async def _run_web_matrix_variant(
    *,
    child_id: int,
    case_id: int,
    module_id: int,
    base_config: dict[str, Any],
    extra_vars: dict,
    index: int,
    variant: dict[str, Any],
) -> dict[str, Any]:
    """Execute one matrix child with an independent DB session and browser context."""
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as child_db:
        child = await child_db.get(TestRun, child_id)
        if child is None:
            return {
                "run_id": child_id,
                "index": index,
                "label": variant.get("label"),
                "browser": variant.get("browser"),
                "viewport": variant.get("viewport"),
                "status": RunStatus.error.value,
                "duration_ms": None,
                "error": "矩阵子运行不存在",
            }
        child.status = RunStatus.running
        await child_db.commit()
        variant_config = copy.deepcopy(base_config)
        variant_config.pop("browser_matrix", None)
        variant_config.update(variant)
        variant_config["_web_matrix_variant"] = True
        case_variant = SimpleNamespace(id=case_id, module_id=module_id, config=variant_config)
        try:
            await run_web_lowcode(child_db, child, case_variant, extra_vars)
        except Exception as exc:
            child.status = RunStatus.error
            child.error_message = str(exc)[:1000]
            await child_db.commit()
        status = child.status.value if hasattr(child.status, "value") else str(child.status)
        return {
            "run_id": child.id,
            "index": index,
            "label": variant.get("label"),
            "browser": variant.get("browser"),
            "viewport": variant.get("viewport"),
            "status": status,
            "duration_ms": child.duration_ms,
        }


async def run_web_lowcode(
    db: AsyncSession,
    run: TestRun,
    case: TestCase,
    extra_vars: dict,
) -> None:
    """低代码模式执行入口"""
    cfg = case.config or {}
    evidence_redact_fields = cfg.get("dataset_redact_fields") or []
    if not cfg.get("_web_matrix_variant"):
        try:
            matrix = build_web_matrix(cfg)
        except WebMatrixError as exc:
            run.status = RunStatus.error
            run.error_message = str(exc)
            await db.commit()
            await _safe_publish(run.id, {"type": "completed", "run_id": run.id, "status": "error"})
            return
        if len(matrix) > 1:
            await _run_web_matrix(db, run, case, extra_vars, matrix)
            return
        cfg = copy.deepcopy(cfg)
        cfg.pop("browser_matrix", None)
        cfg.update(matrix[0])
        cfg["_web_matrix_variant"] = True
    steps = list(cfg.get("steps", []))
    if not steps:
        run.status = RunStatus.error
        run.error_message = "低代码用例未配置任何步骤"
        await db.commit()
        await _safe_publish(run.id, {"type": "completed", "run_id": run.id, "status": "error"})
        return

    headless = cfg.get("headless", True)
    browser_name = cfg.get("browser", "chromium")
    if browser_name not in {"chromium", "firefox", "webkit"}:
        run.status = RunStatus.error
        run.error_message = f"不支持的浏览器: {browser_name}，可选 chromium、firefox、webkit"
        await db.commit()
        await _safe_publish(run.id, {"type": "completed", "run_id": run.id, "status": "error"})
        return
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
    trace_url: str | None = None
    file_actions = {"upload", "download"}
    visual_actions = {"visual_assert"}
    page_object_actions = {"page_object"}
    requires_project = any(
        isinstance(step.get("params"), dict)
        and (
            step.get("action") in file_actions
            or step.get("action") in visual_actions
            or step.get("action") in page_object_actions
            or step["params"].get("element_asset_id") is not None
        )
        for step in steps
    )
    case_project_id: int | None = None
    if requires_project:
        module = await db.get(Module, case.module_id)
        case_project_id = getattr(module, "project_id", None)
    if page_object_actions.intersection({step.get("action") for step in steps}):
        steps, expansion_error = await _expand_page_object_steps(db, steps, case_project_id)
        if expansion_error:
            run.status = RunStatus.error
            run.error_message = expansion_error
            await db.commit()
            await _safe_publish(run.id, {"type": "completed", "run_id": run.id, "status": "error"})
            return

    video_dir = Path(tempfile.mkdtemp(prefix=f"atp_video_{run.id}_"))
    trace_path = video_dir / "trace.zip"
    network_events: list[dict] = []
    console_events: list[dict] = []
    blocked_requests: list[dict] = []

    try:
        pw = await async_playwright().start()
        browser_launcher = getattr(pw, browser_name)
        browser = await browser_launcher.launch(
            headless=headless,
            args=["--no-sandbox"],
        )
        context_options: dict[str, Any] = {
            "viewport": {"width": viewport_w, "height": viewport_h},
            "record_video_dir": str(video_dir),
            "record_video_size": {"width": viewport_w, "height": viewport_h},
        }
        if cfg.get("device_scale_factor") is not None:
            context_options["device_scale_factor"] = float(cfg["device_scale_factor"])
        if cfg.get("locale"):
            context_options["locale"] = str(cfg["locale"])
        if cfg.get("user_agent"):
            context_options["user_agent"] = str(cfg["user_agent"])
        browser_context: BrowserContext = await browser.new_context(**context_options)

        async def _guard_route(route: Any) -> bool:
            return await guard_browser_request(route, blocked_requests)

        await browser_context.route("**/*", _guard_route)
        page: Page = await browser_context.new_page()

        tracing = getattr(browser_context, "tracing", None)
        trace_enabled = bool(cfg.get("collect_trace", True)) and tracing is not None
        if trace_enabled:
            await tracing.start(screenshots=True, snapshots=True, sources=False)

        if hasattr(page, "on"):
            page.on(
                "request",
                lambda request: network_events.append(
                    {
                        "type": "request",
                        "method": request.method,
                        "url": _sanitize_network_url(request.url),
                        "resource_type": request.resource_type,
                    }
                )
                if len(network_events) < 500
                else None,
            )
            page.on(
                "response",
                lambda response: network_events.append(
                    {
                        "type": "response",
                        "status": response.status,
                        "url": _sanitize_network_url(response.url),
                    }
                )
                if len(network_events) < 500
                else None,
            )
            page.on(
                "console",
                lambda message: console_events.append({"type": message.type, "text": message.text})
                if len(console_events) < 500
                else None,
            )

        for idx, step_def in enumerate(steps):
            step_start = time.monotonic()
            action = step_def.get("action", "")
            step_name = step_def.get("name", f"{action}_{idx}")
            raw_params = step_def.get("params", {})
            params = _replace_vars_in_params(raw_params, context_vars)
            params, asset, asset_error = await _resolve_element_asset(db, case, params)
            persisted_params = {key: value for key, value in params.items() if not key.startswith("_")}

            status = RunStatus.passed
            error_message = None
            screenshot_url = None
            response_data: dict | None = None

            try:
                if asset_error:
                    result = {"success": False, "error": asset_error}
                elif action in file_actions:
                    result = await _execute_web_file_step(
                        page, action, params, step_timeout_ms, case_project_id, run.id
                    )
                elif action in visual_actions:
                    result = await _execute_visual_assert(db, page, params, case_project_id, run.id, idx)
                else:
                    result = await _execute_step_with_asset_fallback(page, action, params, step_timeout_ms)
                if not result.get("success"):
                    status = RunStatus.failed
                    error_message = result.get("error")
                    all_passed = False
                    await _mark_element_asset_failed(db, asset, error_message)
                response_data = result.get("data")
            except Exception as e:
                status = RunStatus.failed
                error_message = str(e)[:2000]
                all_passed = False
                await _mark_element_asset_failed(db, asset, error_message)

            # 每步都截图（失败时特别重要）
            screenshot_url = await _take_screenshot(page, run.id, idx)

            duration_ms = int((time.monotonic() - step_start) * 1000)
            persisted_request_data = redact_execution_evidence(
                {"action": action, "params": persisted_params}, evidence_redact_fields
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
        logger.exception("web_lowcode run %s error: %s", run.id, e)
        all_passed = False
        run.error_message = _format_exception_message(e)[:500]

    finally:
        # Trace 必须在 context close 前停止，否则 trace.zip 可能不完整。
        tracing = getattr(browser_context, "tracing", None) if browser_context else None
        if tracing is not None:
            try:
                await tracing.stop(path=str(trace_path))
            except Exception as e:
                logger.warning("Trace export failed for run %s: %s", run.id, e)
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
        try:
            if trace_path.exists():
                obj_name = f"traces/runs/{run.id}/trace.zip"
                await asyncio.get_event_loop().run_in_executor(
                    None, upload_file, obj_name, str(trace_path), "application/zip"
                )
                trace_url = presigned_url(obj_name)
        except Exception as e:
            logger.warning("Trace upload failed for run %s: %s", run.id, e)
        finally:
            shutil.rmtree(video_dir, ignore_errors=True)

    total_ms = int((time.monotonic() - total_start) * 1000)
    if blocked_requests and all_passed:
        all_passed = False
        run.error_message = "浏览器请求被网络安全策略阻止"
    run.status = RunStatus.passed if all_passed else RunStatus.failed
    run.duration_ms = total_ms
    run.result_summary = {
        **(run.result_summary or {}),
        **({"video_url": video_url} if video_url else {}),
        **({"trace_url": trace_url} if trace_url else {}),
        "network_events": network_events[-500:],
        "console_events": console_events[-500:],
        "blocked_requests": blocked_requests[-100:],
    }
    await db.commit()

    await _safe_publish(
        run.id,
        {
            "type": "completed",
            "run_id": run.id,
            "status": run.status.value,
            "duration_ms": total_ms,
            **({"video_url": video_url} if video_url else {}),
            **({"trace_url": trace_url} if trace_url else {}),
        },
    )
