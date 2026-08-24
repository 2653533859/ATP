"""Web UI 交互录制 API。

录制会话运行在后端所在机器上，并通过 Playwright 启动可见 Chromium。
页面内的交互事件由初始化脚本采集后回传，最终转换成低代码步骤。
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
import os
import re
import shutil
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, field_validator
from playwright.async_api import Browser, BrowserContext, Frame, Page, Playwright, async_playwright
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import assert_project_access, get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.minio_client import presigned_url, upload_file
from app.core.url_security import validate_http_url_syntax, validate_public_http_url
from app.models.project import Project
from app.models.user import User
from app.models.user_project import ProjectRole
from app.models.web_assets import WebElementAsset
from app.services.web_network_guard import guard_browser_request, sanitize_network_url
from app.services.web_recording_transport import (
    RemoteWebRecordingManager,
    WebRecordingTransportError,
    list_recording_workers,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/web-recordings", tags=["Web 用例录制"])


_SENSITIVE_TEXT_RE = re.compile(
    r"(?i)(?P<key>[\"']?(?:token|secret|password|passwd|api[_-]?key|authorization|cookie|credential)[\"']?)"
    r"(?P<sep>\s*[:=]\s*)[\"']?[^,;\s}\]\\\"']+[\"']?"
)
_SENSITIVE_HEADER_RE = re.compile(
    r"(?i)^(authorization|cookie|set-cookie|proxy-authorization|x-api-key|x-auth-token)$"
)
_URL_RE = re.compile(r"https?://[^\s'\"<>]+", re.IGNORECASE)


def _safe_text(value: Any, max_length: int = 800) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").replace("\x00", " ").strip()
    text = _URL_RE.sub(lambda match: sanitize_network_url(match.group(0)), text)
    text = _SENSITIVE_TEXT_RE.sub(lambda match: f"{match.group('key')}{match.group('sep')}<redacted>", text)
    return text[:max_length]


def _safe_headers(headers: Any) -> list[dict[str, str]]:
    if not isinstance(headers, list):
        return []
    result: list[dict[str, str]] = []
    for item in headers:
        if not isinstance(item, dict):
            continue
        name = _safe_text(item.get("name"), 128)
        if not name:
            continue
        value = "<redacted>" if _SENSITIVE_HEADER_RE.match(name) else _safe_text(item.get("value"), 512)
        result.append({"name": name, "value": value})
    return result[:100]


def _sanitize_har(data: bytes) -> bytes:
    """Remove credentials, cookies and request bodies before HAR persistence."""
    payload = json.loads(data.decode("utf-8"))
    log = payload.get("log") if isinstance(payload, dict) else None
    entries = log.get("entries") if isinstance(log, dict) else None
    if not isinstance(entries, list):
        raise ValueError("HAR 文件缺少 entries")
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        request = entry.get("request")
        if isinstance(request, dict):
            request["url"] = sanitize_network_url(str(request.get("url") or ""))
            request["headers"] = _safe_headers(request.get("headers"))
            request["cookies"] = []
            request.pop("postData", None)
        response = entry.get("response")
        if isinstance(response, dict):
            response["headers"] = _safe_headers(response.get("headers"))
            response["cookies"] = []
            response.pop("content", None)
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


_RECORDING_SCRIPT = r"""
(() => {
  const quote = (value) => String(value).replace(/\\/g, '\\\\').replace(/"/g, '\\"');

  function selectorFor(element) {
    if (!(element instanceof Element)) return '';
    if (element.id) return `#${CSS.escape(element.id)}`;

    const testId = element.getAttribute('data-testid') || element.getAttribute('data-test-id');
    if (testId) return `[data-testid="${quote(testId)}"]`;

    const name = element.getAttribute('name');
    if (name) return `${element.tagName.toLowerCase()}[name="${quote(name)}"]`;

    const ariaLabel = element.getAttribute('aria-label');
    if (ariaLabel) return `${element.tagName.toLowerCase()}[aria-label="${quote(ariaLabel)}"]`;

    const parts = [];
    let node = element;
    while (node && node !== document.body && parts.length < 6) {
      let part = node.tagName.toLowerCase();
      const parent = node.parentElement;
      if (parent) {
        const siblings = Array.from(parent.children).filter((item) => item.tagName === node.tagName);
        if (siblings.length > 1) part += `:nth-of-type(${siblings.indexOf(node) + 1})`;
      }
      parts.unshift(part);
      node = parent;
    }
    return parts.join(' > ');
  }

  function targetFor(event) {
    const raw = event.target;
    if (!(raw instanceof Element)) return null;
    return raw.closest('input, textarea, select, button, a, [role="button"], [contenteditable="true"]') || raw;
  }

  function send(payload) {
    if (typeof window.atpRecordEvent === 'function') {
      window.atpRecordEvent(payload).catch(() => {});
    }
  }

  document.addEventListener('click', (event) => {
    const target = targetFor(event);
    const selector = target ? selectorFor(target) : '';
    if (selector) send({ type: 'click', selector });
  }, true);

  document.addEventListener('input', (event) => {
    const target = targetFor(event);
    if (
      !(target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target.isContentEditable)
    ) return;
    const sensitive = target instanceof HTMLInputElement && target.type === 'password';
    send({
      type: 'input',
      selector: selectorFor(target),
      value: sensitive ? '' : (target.isContentEditable ? target.textContent || '' : target.value),
      sensitive,
    });
  }, true);

  document.addEventListener('change', (event) => {
    const target = targetFor(event);
    if (target instanceof HTMLSelectElement) {
      send({ type: 'select', selector: selectorFor(target), value: target.value });
    }
  }, true);

  document.addEventListener('keydown', (event) => {
    const key = event.key;
    if (!['Enter', 'Tab', 'Escape'].includes(key)) return;
    const target = targetFor(event);
    send({ type: 'press', selector: target ? selectorFor(target) : '', key });
  }, true);
})();
"""


WebRecordingBrowser = Literal["chromium", "firefox", "webkit"]


class WebRecordingStart(BaseModel):
    start_url: str = Field(min_length=1, max_length=2048)
    project_id: int = Field(ge=1)
    browser: WebRecordingBrowser = "chromium"
    viewport_width: int = Field(default=1280, ge=320, le=3840)
    viewport_height: int = Field(default=720, ge=240, le=2160)

    @field_validator("start_url")
    @classmethod
    def validate_start_url(cls, value: str) -> str:
        return validate_http_url_syntax(value)


@dataclass
class WebRecordingSession:
    session_id: str
    owner_id: int
    start_url: str
    viewport_width: int
    viewport_height: int
    project_id: int | None = None
    browser_name: str = "chromium"
    status: str = "starting"
    error: str | None = None
    steps: list[dict[str, Any]] = field(default_factory=list)
    blocked_requests: list[dict[str, Any]] = field(default_factory=list)
    console_messages: list[dict[str, Any]] = field(default_factory=list)
    page_errors: list[dict[str, Any]] = field(default_factory=list)
    network_events: list[dict[str, Any]] = field(default_factory=list)
    failed_requests: list[dict[str, Any]] = field(default_factory=list)
    error_responses: list[dict[str, Any]] = field(default_factory=list)
    asset_ids: list[int] = field(default_factory=list)
    assets_persisted: bool = False
    artifacts: dict[str, dict[str, Any]] = field(default_factory=dict)
    artifact_error: str | None = None
    playwright: Playwright | None = None
    browser: Browser | None = None
    context: BrowserContext | None = None
    page: Page | None = None
    artifact_dir: Path | None = None
    trace_path: Path | None = None
    har_path: Path | None = None
    report_path: Path | None = None
    trace_started: bool = False
    finished_at: float | None = None

    async def start(self) -> None:
        try:
            self.playwright = await async_playwright().start()
            display = settings.WEB_RECORDER_DISPLAY.strip() or os.environ.get("DISPLAY", "").strip()
            if sys.platform.startswith("linux") and not display:
                raise RuntimeError(
                    "Linux Web 录制需要可见的 X display；请在后端配置 WEB_RECORDER_DISPLAY，"
                    "或在本地带桌面环境启动后端"
                )
            launch_env = dict(os.environ)
            if display:
                launch_env["DISPLAY"] = display
            browser_launcher = getattr(self.playwright, self.browser_name)
            # Playwright WebKit can launch headless on Linux, but its headed
            # process may never finish startup inside the isolated Xvfb
            # recorder container. The independent Worker has no browser window
            # to expose to the user, so keep local/Windows recording visible
            # while using the supported headless path only in Linux Worker mode.
            headless = (
                self.browser_name == "webkit"
                and sys.platform.startswith("linux")
                and settings.WEB_RECORDER_MODE.strip().lower() == "worker"
            )
            self.browser = await browser_launcher.launch(headless=headless, env=launch_env)
            self.artifact_dir = Path(tempfile.mkdtemp(prefix=f"atp_web_recording_{self.session_id}_"))
            self.trace_path = self.artifact_dir / "trace.zip"
            self.har_path = self.artifact_dir / "network.har"
            self.report_path = self.artifact_dir / "report.json"
            self.context = await self.browser.new_context(
                viewport={"width": self.viewport_width, "height": self.viewport_height},
                record_har_path=str(self.har_path),
                record_har_content="omit",
                record_har_mode="minimal",
            )
            tracing = getattr(self.context, "tracing", None)
            if tracing is not None:
                await tracing.start(screenshots=True, snapshots=True, sources=False)
                self.trace_started = True
            await self.context.route("**/*", self._guard_route)
            self.page = await self.context.new_page()
            await self.page.expose_binding("atpRecordEvent", self._handle_binding)
            await self.page.add_init_script(_RECORDING_SCRIPT)
            self.page.on("framenavigated", self._handle_navigation)
            self.page.on("console", self._handle_console)
            self.page.on("pageerror", self._handle_page_error)
            self.page.on("request", self._handle_request)
            self.page.on("requestfailed", self._handle_request_failed)
            self.page.on("response", self._handle_response)
            self._append_step("goto", f"打开 {self.start_url}", {"url": self.start_url})
            await self.page.goto(self.start_url, wait_until="domcontentloaded", timeout=30_000)
            self.status = "recording"
        except Exception as exc:
            self.status = "error"
            self.error = str(exc)[:500]
            self.finished_at = time.monotonic()
            await self.close()
            raise

    async def stop(self) -> None:
        if self.status not in {"stopped", "error"}:
            self.status = "stopping"
            await self.close()
            self.status = "stopped"
            self.finished_at = time.monotonic()

    async def close(self) -> None:
        await self._stop_tracing()
        if self.context:
            with contextlib.suppress(Exception):
                await self.context.close()
            self.context = None
        if self.browser:
            with contextlib.suppress(Exception):
                await self.browser.close()
            self.browser = None
        if self.playwright:
            with contextlib.suppress(Exception):
                await self.playwright.stop()
            self.playwright = None
        self.page = None
        if self.status == "stopping":
            await self._persist_artifacts()
        self._cleanup_artifacts()

    async def screenshot(self) -> bytes:
        if self.page is None or self.status not in {"starting", "recording", "stopping"}:
            raise RuntimeError("录制浏览器当前不可截图")
        return await self.page.screenshot(type="png")

    def current_url(self) -> str:
        if self.page is not None and self.page.url.startswith(("http://", "https://")):
            return self.page.url
        for step in reversed(self.steps):
            params = step.get("params") if isinstance(step.get("params"), dict) else {}
            url = str(params.get("url") or "").strip()
            if url.startswith(("http://", "https://")):
                return url
        return self.start_url

    async def _guard_route(self, route: Any) -> bool:
        return await guard_browser_request(route, self.blocked_requests)

    def _append_capped(self, target: list[dict[str, Any]], value: dict[str, Any], limit: int = 200) -> None:
        if len(target) < limit:
            target.append(value)

    def _handle_console(self, message: Any) -> None:
        self._append_capped(
            self.console_messages,
            {
                "type": _safe_text(getattr(message, "type", "log"), 32),
                "text": _safe_text(getattr(message, "text", "")),
            },
            100,
        )

    def _handle_page_error(self, error: Any) -> None:
        self._append_capped(self.page_errors, {"message": _safe_text(getattr(error, "message", error))}, 100)

    def _handle_request(self, request: Any) -> None:
        self._append_capped(self.network_events, {"type": "request", **self._request_event(request)})

    def _request_event(self, request: Any, *, status: int | None = None, error: str | None = None) -> dict[str, Any]:
        event = {
            "method": _safe_text(getattr(request, "method", "GET"), 16),
            "url": sanitize_network_url(str(getattr(request, "url", ""))),
            "resource_type": _safe_text(getattr(request, "resource_type", "unknown"), 32),
        }
        if status is not None:
            event["status"] = int(status)
        if error:
            event["error"] = _safe_text(error)
        return event

    def _handle_request_failed(self, request: Any) -> None:
        failure = getattr(request, "failure", None)
        if callable(failure):
            failure = failure()
        event = self._request_event(request, error=str(failure or "request failed"))
        self._append_capped(self.failed_requests, event)
        self._append_capped(self.network_events, {"type": "request_failed", **event})

    def _handle_response(self, response: Any) -> None:
        request = getattr(response, "request", None)
        if request is None:
            return
        try:
            status = int(getattr(response, "status", 0))
        except (TypeError, ValueError):
            status = 0
        event = self._request_event(request, status=status)
        self._append_capped(self.network_events, {"type": "response", **event})
        if status >= 400:
            self._append_capped(self.error_responses, event)

    async def _stop_tracing(self) -> None:
        if not self.trace_started or self.context is None or self.trace_path is None:
            return
        tracing = getattr(self.context, "tracing", None)
        try:
            if tracing is not None:
                await tracing.stop(path=str(self.trace_path))
        except Exception as exc:
            self.artifact_error = _safe_text(f"Trace 保存失败: {exc}")
        finally:
            self.trace_started = False

    def _report_steps(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for step in self.steps:
            item = dict(step)
            params = dict(item.get("params") or {}) if isinstance(item.get("params"), dict) else {}
            if params.get("sensitive") or "敏感值" in str(item.get("name") or ""):
                params["value"] = "<redacted>"
            if "url" in params:
                params["url"] = sanitize_network_url(str(params["url"]))
            item["params"] = params
            result.append(item)
        return result

    @staticmethod
    def _report_events(events: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for event in events[:limit]:
            item = dict(event)
            if "url" in item:
                item["url"] = sanitize_network_url(str(item["url"]))
            if "error" in item:
                item["error"] = _safe_text(item["error"])
            result.append(item)
        return result

    def _report_payload(self) -> dict[str, Any]:
        return {
            "report_version": 1,
            "session_id": self.session_id,
            "status": "stopped",
            "project_id": self.project_id,
            "start_url": sanitize_network_url(self.start_url),
            "current_url": sanitize_network_url(self.current_url()),
            "browser": self.browser_name,
            "viewport": {"width": self.viewport_width, "height": self.viewport_height},
            "steps": self._report_steps(),
            "console_messages": self.console_messages[:100],
            "page_errors": self.page_errors[:100],
            "network_events": self._report_events(self.network_events, 200),
            "failed_requests": self._report_events(self.failed_requests, 100),
            "error_responses": self._report_events(self.error_responses, 100),
            "blocked_requests": self._report_events(self.blocked_requests, 100),
            "artifacts": self.artifacts,
        }

    async def _persist_artifacts(self) -> None:
        if self.artifact_dir is None:
            return
        failures: list[str] = []
        if self.har_path and self.har_path.exists():
            try:
                self.har_path.write_bytes(_sanitize_har(self.har_path.read_bytes()))
            except Exception as exc:
                failures.append(_safe_text(f"HAR 脱敏失败: {exc}"))
        specs = (
            ("trace", self.trace_path, "application/zip", f"traces/recordings/{self.project_id}/{self.session_id}/trace.zip"),
            ("har", self.har_path, "application/json", f"reports/recordings/{self.project_id}/{self.session_id}/network.har"),
        )
        for kind, path, content_type, object_name in specs:
            if path is None or not path.exists():
                continue
            try:
                await asyncio.to_thread(upload_file, object_name, path, content_type)
                url = await asyncio.to_thread(presigned_url, object_name)
                self.artifacts[kind] = {
                    "kind": kind,
                    "filename": path.name,
                    "content_type": content_type,
                    "size": path.stat().st_size,
                    "url": url,
                }
            except Exception as exc:
                failures.append(_safe_text(f"{kind} 上传失败: {exc}"))
        if self.report_path is not None:
            try:
                self.report_path.write_text(
                    json.dumps(self._report_payload(), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                object_name = f"reports/recordings/{self.project_id}/{self.session_id}/report.json"
                await asyncio.to_thread(upload_file, object_name, self.report_path, "application/json")
                url = await asyncio.to_thread(presigned_url, object_name)
                self.artifacts["report"] = {
                    "kind": "report",
                    "filename": self.report_path.name,
                    "content_type": "application/json",
                    "size": self.report_path.stat().st_size,
                    "url": url,
                }
            except Exception as exc:
                failures.append(_safe_text(f"运行报告上传失败: {exc}"))
        if failures:
            self.artifact_error = "; ".join(filter(None, [self.artifact_error, *failures]))[:1000]

    def _cleanup_artifacts(self) -> None:
        if self.artifact_dir is not None:
            shutil.rmtree(self.artifact_dir, ignore_errors=True)
            self.artifact_dir = None

    def snapshot(self) -> dict[str, Any]:
        return {
            "id": self.session_id,
            "status": self.status,
            "start_url": self.start_url,
            "current_url": self.current_url(),
            "browser": self.browser_name,
            "project_id": self.project_id,
            "viewport_width": self.viewport_width,
            "viewport_height": self.viewport_height,
            "steps": self.steps,
            "blocked_requests": self.blocked_requests[-100:],
            "console_messages": self.console_messages[-100:],
            "page_errors": self.page_errors[-100:],
            "network_events": self.network_events[-200:],
            "failed_requests": self.failed_requests[-100:],
            "error_responses": self.error_responses[-100:],
            "asset_ids": self.asset_ids,
            "artifacts": self.artifacts,
            "artifact_error": self.artifact_error,
            "error": self.error,
        }

    def _handle_navigation(self, frame: Frame) -> None:
        if self.page is None or frame != self.page.main_frame:
            return
        url = frame.url
        if not url.startswith(("http://", "https://")):
            return
        if self.steps and self.steps[-1].get("action") == "goto" and self.steps[-1].get("params", {}).get("url") == url:
            return
        self._append_step("goto", f"打开 {url}", {"url": url})

    def _handle_binding(self, _source: object, payload: Any) -> None:
        if isinstance(payload, dict):
            self._append_event(payload)

    def _append_event(self, event: dict[str, Any]) -> None:
        event_type = str(event.get("type") or "")
        selector = str(event.get("selector") or "").strip()
        if event_type == "click" and selector:
            self._append_step("click", f"点击 {selector}", {"selector": selector})
        elif event_type == "input" and selector:
            value = str(event.get("value") or "")
            name = "输入敏感值（请手动填写）" if event.get("sensitive") else f"输入 {selector}"
            params = {"selector": selector, "value": value}
            if (
                self.steps
                and self.steps[-1].get("action") == "fill"
                and self.steps[-1].get("params", {}).get("selector") == selector
            ):
                self.steps[-1]["params"] = params
                self.steps[-1]["name"] = name
            else:
                self._append_step("fill", name, params)
        elif event_type == "select" and selector:
            value = str(event.get("value") or "")
            self._append_step("select", f"选择 {selector}", {"selector": selector, "value": value})
        elif event_type == "press":
            key = str(event.get("key") or "Enter")
            self._append_step("press", f"按键 {key}", {"key": key, "selector": selector})

    def _append_step(self, action: str, name: str, params: dict[str, Any]) -> None:
        self.steps.append({"action": action, "name": name, "params": params})


class WebRecordingManager:
    retention_seconds = 300.0

    def __init__(self) -> None:
        self.sessions: dict[str, WebRecordingSession] = {}
        self.lock = asyncio.Lock()

    def _prune_finished(self) -> None:
        cutoff = time.monotonic() - self.retention_seconds
        expired = [
            session_id
            for session_id, session in self.sessions.items()
            if session.finished_at is not None and session.finished_at < cutoff
        ]
        for session_id in expired:
            self.sessions.pop(session_id, None)

    async def start(self, payload: WebRecordingStart, owner_id: int) -> WebRecordingSession:
        async with self.lock:
            self._prune_finished()
            if any(
                session.owner_id == owner_id and session.status in {"starting", "recording", "stopping"}
                for session in self.sessions.values()
            ):
                raise HTTPException(status_code=409, detail="当前用户已有一个正在进行的录制会话")
            session = WebRecordingSession(
                session_id=uuid.uuid4().hex,
                owner_id=owner_id,
                start_url=payload.start_url,
                viewport_width=payload.viewport_width,
                viewport_height=payload.viewport_height,
                project_id=payload.project_id,
                browser_name=payload.browser,
            )
            self.sessions[session.session_id] = session
        try:
            await session.start()
        except Exception as exc:
            self.sessions.pop(session.session_id, None)
            raise HTTPException(status_code=400, detail=f"无法启动录制浏览器: {exc}") from exc
        return session

    def get(self, session_id: str, owner_id: int) -> WebRecordingSession:
        self._prune_finished()
        session = self.sessions.get(session_id)
        if not session or session.owner_id != owner_id:
            raise HTTPException(status_code=404, detail="录制会话不存在")
        return session

    async def close_all(self) -> None:
        sessions = list(self.sessions.values())
        await asyncio.gather(*(session.stop() for session in sessions), return_exceptions=True)
        self.sessions.clear()


manager = WebRecordingManager()
remote_manager = RemoteWebRecordingManager()


def _recording_http_error(exc: WebRecordingTransportError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


def _session_from_snapshot(snapshot: dict[str, Any], owner_id: int) -> WebRecordingSession:
    """Rebuild the persistence-only part of a remote session on the API side."""
    return WebRecordingSession(
        session_id=str(snapshot.get("id") or ""),
        owner_id=owner_id,
        start_url=str(snapshot.get("start_url") or ""),
        viewport_width=int(snapshot.get("viewport_width") or 1280),
        viewport_height=int(snapshot.get("viewport_height") or 720),
        project_id=int(snapshot["project_id"]) if snapshot.get("project_id") is not None else None,
        status=str(snapshot.get("status") or "stopped"),
        error=str(snapshot["error"]) if snapshot.get("error") else None,
        steps=list(snapshot.get("steps") or []),
        blocked_requests=list(snapshot.get("blocked_requests") or []),
        console_messages=list(snapshot.get("console_messages") or []),
        page_errors=list(snapshot.get("page_errors") or []),
        network_events=list(snapshot.get("network_events") or []),
        failed_requests=list(snapshot.get("failed_requests") or []),
        error_responses=list(snapshot.get("error_responses") or []),
        asset_ids=[int(value) for value in snapshot.get("asset_ids") or [] if str(value).isdigit()],
        artifacts=dict(snapshot.get("artifacts") or {}),
        artifact_error=str(snapshot["artifact_error"]) if snapshot.get("artifact_error") else None,
    )


async def _persist_recorded_assets(db: AsyncSession, session: WebRecordingSession) -> None:
    """Persist unique recorded selectors and link the returned steps to them."""
    if session.project_id is None or session.assets_persisted:
        return
    selectors = []
    seen: set[str] = set()
    for step in session.steps:
        params = step.get("params") if isinstance(step.get("params"), dict) else {}
        selector = str(params.get("selector") or "").strip()
        if selector and selector not in seen and step.get("action") in {"click", "fill", "select", "press"}:
            seen.add(selector)
            selectors.append(selector)
    if not selectors:
        session.assets_persisted = True
        return

    existing_result = await db.execute(
        select(WebElementAsset.name).where(WebElementAsset.project_id == session.project_id)
    )
    used_names = {str(name) for name in existing_result.scalars().all()}
    selector_to_asset: dict[str, WebElementAsset] = {}
    for index, selector in enumerate(selectors, start=1):
        base_name = f"录制元素_{index}"
        name = base_name
        suffix = 2
        while name in used_names:
            name = f"{base_name}_{suffix}"
            suffix += 1
        used_names.add(name)
        asset = WebElementAsset(
            project_id=session.project_id,
            owner_id=session.owner_id,
            name=name,
            page_url=session.start_url,
            locator={"strategy": "css", "value": selector},
            fallback_locators=[],
            description="Web 录制自动生成，可在元素库中继续维护",
        )
        db.add(asset)
        selector_to_asset[selector] = asset
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        session.error = "录制步骤已生成，但元素资产名称发生冲突，请稍后重试"
        return

    for step in session.steps:
        params = step.get("params") if isinstance(step.get("params"), dict) else {}
        selector = str(params.get("selector") or "").strip()
        asset = selector_to_asset.get(selector)
        if asset is not None:
            params["element_asset_id"] = asset.id
    await db.commit()
    session.asset_ids = [asset.id for asset in selector_to_asset.values() if asset.id is not None]
    session.assets_persisted = True


def _recording_worker_status(worker: dict[str, Any]) -> dict[str, Any] | None:
    worker_id = str(worker.get("worker_id") or "").strip()
    if not worker_id:
        return None
    try:
        active_sessions = max(0, int(worker.get("active_sessions", 0)))
        capacity = max(1, int(worker.get("capacity", 1)))
    except (TypeError, ValueError):
        active_sessions = 0
        capacity = 1
    updated_at = worker.get("updated_at")
    try:
        updated_at = float(updated_at) if updated_at is not None else None
    except (TypeError, ValueError):
        updated_at = None
    return {
        "worker_id": f"worker-{hashlib.sha256(worker_id.encode('utf-8')).hexdigest()[:12]}",
        "active_sessions": active_sessions,
        "capacity": capacity,
        "available": active_sessions < capacity,
        "updated_at": updated_at,
    }


@router.get("/workers")
async def get_recording_workers(user: User = Depends(get_current_user)):
    """Return a safe health summary so the UI can preflight Web recording."""
    del user  # Authentication is required; worker metadata is intentionally not user-specific.
    configured_mode = settings.WEB_RECORDER_MODE.strip().lower()
    mode = "worker" if configured_mode == "worker" else "local"
    if mode != "worker":
        return {
            "mode": mode,
            "ready": True,
            "workers": [],
            "registered_count": 0,
            "available_count": 0,
        }
    try:
        workers = [
            status for item in await list_recording_workers() if (status := _recording_worker_status(item)) is not None
        ]
    except WebRecordingTransportError as exc:
        raise _recording_http_error(exc) from exc
    available_count = sum(1 for worker in workers if worker["available"])
    return {
        "mode": "worker",
        "ready": available_count > 0,
        "workers": workers,
        "registered_count": len(workers),
        "available_count": available_count,
    }


@router.post("")
async def start_recording(
    payload: WebRecordingStart,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        payload.start_url = await asyncio.to_thread(validate_public_http_url, payload.start_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await assert_project_access(db, user, payload.project_id, ProjectRole.editor)
    if await db.get(Project, payload.project_id) is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    if settings.WEB_RECORDER_MODE.strip().lower() == "worker":
        try:
            return await remote_manager.start(payload.model_dump(), user.id)
        except WebRecordingTransportError as exc:
            raise _recording_http_error(exc) from exc
    session = await manager.start(payload, user.id)
    return session.snapshot()


@router.get("/{session_id}")
async def get_recording(session_id: str, user: User = Depends(get_current_user)):
    if settings.WEB_RECORDER_MODE.strip().lower() == "worker":
        try:
            return await remote_manager.get(session_id, user.id)
        except WebRecordingTransportError as exc:
            raise _recording_http_error(exc) from exc
    return manager.get(session_id, user.id).snapshot()


@router.post("/{session_id}/screenshot", response_class=Response)
async def capture_recording_screenshot(session_id: str, user: User = Depends(get_current_user)):
    if settings.WEB_RECORDER_MODE.strip().lower() == "worker":
        try:
            data = await remote_manager.screenshot(session_id, user.id)
        except WebRecordingTransportError as exc:
            raise _recording_http_error(exc) from exc
        return Response(content=data, media_type="image/png", headers={"Cache-Control": "no-store"})
    session = manager.get(session_id, user.id)
    try:
        data = await session.screenshot()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(content=data, media_type="image/png", headers={"Cache-Control": "no-store"})


@router.post("/{session_id}/stop")
async def stop_recording(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if settings.WEB_RECORDER_MODE.strip().lower() == "worker":
        try:
            snapshot = await remote_manager.stop(session_id, user.id)
        except WebRecordingTransportError as exc:
            raise _recording_http_error(exc) from exc
        session = _session_from_snapshot(snapshot, user.id)
        await _persist_recorded_assets(db, session)
        return session.snapshot()
    session = manager.get(session_id, user.id)
    await session.stop()
    await _persist_recorded_assets(db, session)
    return session.snapshot()


async def close_all_recordings() -> None:
    await manager.close_all()
