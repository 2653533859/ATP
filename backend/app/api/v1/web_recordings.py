"""Web UI 交互录制 API。

录制会话运行在后端所在机器上，并通过 Playwright 启动可见 Chromium。
页面内的交互事件由初始化脚本采集后回传，最终转换成低代码步骤。
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from playwright.async_api import Browser, BrowserContext, Frame, Page, Playwright, async_playwright

from app.api.deps import get_current_user
from app.core.config import settings
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/web-recordings", tags=["Web 用例录制"])


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


class WebRecordingStart(BaseModel):
    start_url: str = Field(min_length=1, max_length=2048)
    browser: Literal["chromium"] = "chromium"
    viewport_width: int = Field(default=1280, ge=320, le=3840)
    viewport_height: int = Field(default=720, ge=240, le=2160)

    @field_validator("start_url")
    @classmethod
    def validate_start_url(cls, value: str) -> str:
        parsed = urlparse(value.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("起始地址必须是 http 或 https URL")
        return value.strip()


@dataclass
class WebRecordingSession:
    session_id: str
    owner_id: int
    start_url: str
    viewport_width: int
    viewport_height: int
    status: str = "starting"
    error: str | None = None
    steps: list[dict[str, Any]] = field(default_factory=list)
    playwright: Playwright | None = None
    browser: Browser | None = None
    context: BrowserContext | None = None
    page: Page | None = None
    finished_at: float | None = None

    async def start(self) -> None:
        try:
            self.playwright = await async_playwright().start()
            display = settings.WEB_RECORDER_DISPLAY.strip() or os.environ.get("DISPLAY", "").strip()
            if os.name != "nt" and not display:
                raise RuntimeError(
                    "Linux Web 录制需要可见的 X display；请在后端配置 WEB_RECORDER_DISPLAY，"
                    "或在本地带桌面环境启动后端"
                )
            launch_env = dict(os.environ)
            if display:
                launch_env["DISPLAY"] = display
            self.browser = await self.playwright.chromium.launch(headless=False, env=launch_env)
            self.context = await self.browser.new_context(
                viewport={"width": self.viewport_width, "height": self.viewport_height},
            )
            self.page = await self.context.new_page()
            await self.page.expose_binding("atpRecordEvent", self._handle_binding)
            await self.page.add_init_script(_RECORDING_SCRIPT)
            self.page.on("framenavigated", self._handle_navigation)
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

    def snapshot(self) -> dict[str, Any]:
        return {
            "id": self.session_id,
            "status": self.status,
            "start_url": self.start_url,
            "steps": self.steps,
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


@router.post("")
async def start_recording(payload: WebRecordingStart, user: User = Depends(get_current_user)):
    session = await manager.start(payload, user.id)
    return session.snapshot()


@router.get("/{session_id}")
async def get_recording(session_id: str, user: User = Depends(get_current_user)):
    return manager.get(session_id, user.id).snapshot()


@router.post("/{session_id}/stop")
async def stop_recording(session_id: str, user: User = Depends(get_current_user)):
    session = manager.get(session_id, user.id)
    await session.stop()
    return session.snapshot()


async def close_all_recordings() -> None:
    await manager.close_all()
