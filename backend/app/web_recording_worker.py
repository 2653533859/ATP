"""Standalone Web recording worker entry point.

Run with ``python -m app.web_recording_worker`` in a process/container that has
Chromium and an accessible display.  The API remains responsible for auth,
project access and asset persistence; this process owns Playwright sessions.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
from pathlib import Path
import signal
from typing import Any

from app.api.v1.web_recordings import WebRecordingSession, WebRecordingStart
from app.core import redis_client as _redis_client
from app.core.config import settings
from app.services.web_recording_transport import (
    WebRecordingTransportError,
    default_worker_id,
    register_recording_worker,
    unregister_recording_worker,
    worker_queue_key,
)

logger = logging.getLogger(__name__)


class WebRecordingWorker:
    """Own browser sessions for one Redis-routed recording worker instance."""

    def __init__(self, worker_id: str | None = None) -> None:
        self.worker_id = worker_id or default_worker_id()
        self.capacity = max(1, int(settings.WEB_RECORDER_WORKER_MAX_SESSIONS))
        self.sessions: dict[str, WebRecordingSession] = {}
        self.pending_sessions: set[str] = set()
        self.stop_event = asyncio.Event()

    def _active_count(self) -> int:
        return len(self.sessions) + len(self.pending_sessions)

    @staticmethod
    def _health_file() -> Path | None:
        value = os.environ.get("WEB_RECORDER_HEALTH_FILE", "").strip()
        return Path(value) if value else None

    def _touch_health_file(self) -> None:
        path = self._health_file()
        if path is None:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
        except OSError:
            logger.exception("Unable to update Web recording Worker health file %s", path)

    def _clear_health_file(self) -> None:
        path = self._health_file()
        if path is None:
            return
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.exception("Unable to remove Web recording Worker health file %s", path)

    async def _reply(self, client: Any, command: dict[str, Any], payload: dict[str, Any]) -> None:
        reply_key = str(command.get("reply_key") or "").strip()
        if not reply_key:
            return
        await client.rpush(reply_key, json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        await client.expire(reply_key, max(5, int(settings.WEB_RECORDER_REPLY_TTL_SECONDS)))

    def _missing(self) -> dict[str, Any]:
        return {"ok": False, "code": "not_found", "error": "录制会话不存在或已结束"}

    async def _start(self, command: dict[str, Any]) -> dict[str, Any]:
        if self._active_count() >= self.capacity:
            return {"ok": False, "code": "busy", "error": "录制 Worker 已达到并发上限"}
        raw_payload = command.get("payload")
        if not isinstance(raw_payload, dict):
            return {"ok": False, "code": "invalid", "error": "录制启动参数无效"}
        try:
            payload = WebRecordingStart.model_validate(raw_payload)
            session_id = str(command.get("session_id") or "").strip()
            owner_id = int(str(command.get("owner_id")))
            if not session_id or owner_id < 1:
                raise ValueError("session_id 或 owner_id 无效")
        except (TypeError, ValueError) as exc:
            return {"ok": False, "code": "invalid", "error": f"录制启动参数无效: {exc}"}

        session = WebRecordingSession(
            session_id=session_id,
            owner_id=owner_id,
            start_url=payload.start_url,
            viewport_width=payload.viewport_width,
            viewport_height=payload.viewport_height,
            project_id=payload.project_id,
            browser_name=payload.browser,
        )
        self.pending_sessions.add(session_id)
        try:
            await session.start()
        except Exception as exc:
            logger.warning("Web recording session %s failed to start: %s", session_id, exc)
            return {"ok": False, "code": "start_failed", "error": str(exc)[:500], "snapshot": session.snapshot()}
        finally:
            self.pending_sessions.discard(session_id)
        self.sessions[session_id] = session
        return {"ok": True, "snapshot": session.snapshot()}

    async def _dispatch(self, command: dict[str, Any]) -> dict[str, Any]:
        action = str(command.get("action") or "").strip()
        session_id = str(command.get("session_id") or "").strip()
        if action == "start":
            return await self._start(command)
        session = self.sessions.get(session_id)
        if session is None:
            return self._missing()
        if action == "snapshot":
            return {"ok": True, "snapshot": session.snapshot()}
        if action == "screenshot":
            try:
                data = await session.screenshot()
            except RuntimeError as exc:
                return {"ok": False, "code": "not_ready", "error": str(exc)}
            return {"ok": True, "data": base64.b64encode(data).decode("ascii")}
        if action == "stop":
            await session.stop()
            snapshot = session.snapshot()
            self.sessions.pop(session_id, None)
            return {"ok": True, "snapshot": snapshot}
        return {"ok": False, "code": "invalid", "error": f"不支持的录制 Worker 操作: {action}"}

    async def _process(self, client: Any, raw_command: Any) -> None:
        try:
            command = json.loads(raw_command)
        except (TypeError, ValueError, json.JSONDecodeError):
            logger.warning("Ignoring malformed Web recording command")
            return
        if not isinstance(command, dict):
            return
        try:
            response = await self._dispatch(command)
        except Exception as exc:
            logger.exception("Web recording command failed")
            response = {"ok": False, "code": "worker_error", "error": str(exc)[:500]}
        try:
            await self._reply(client, command, response)
        except Exception:
            logger.exception("Unable to reply to Web recording command")

    async def close(self) -> None:
        await asyncio.gather(*(session.stop() for session in self.sessions.values()), return_exceptions=True)
        self.sessions.clear()

    async def _heartbeat_loop(self, client: Any) -> None:
        heartbeat_seconds = max(1, int(settings.WEB_RECORDER_WORKER_HEARTBEAT_SECONDS))
        while not self.stop_event.is_set():
            try:
                await register_recording_worker(
                    self.worker_id,
                    active_sessions=self._active_count(),
                    capacity=self.capacity,
                    client=client,
                )
                self._touch_health_file()
            except WebRecordingTransportError:
                logger.exception("Web recording Worker heartbeat failed")
                self._clear_health_file()
            except Exception:
                # Redis client implementations and connection pools may raise
                # exceptions outside the transport wrapper. Keep the retry
                # loop alive and make the probe fail until a heartbeat works.
                logger.exception("Web recording Worker heartbeat crashed")
                self._clear_health_file()
            await asyncio.sleep(heartbeat_seconds)

    async def run(self) -> None:
        # A previous process may have left the marker behind after a hard
        # termination. Never expose that stale marker while this process is
        # waiting for its first successful Redis registration.
        self._clear_health_file()
        client = _redis_client.get_async_redis()
        heartbeat_seconds = max(1, int(settings.WEB_RECORDER_WORKER_HEARTBEAT_SECONDS))
        try:
            await register_recording_worker(
                self.worker_id,
                active_sessions=self._active_count(),
                capacity=self.capacity,
                client=client,
            )
            self._touch_health_file()
        except WebRecordingTransportError:
            # Keep the command loop alive; the heartbeat task will retry while
            # Redis is temporarily unavailable during process startup.
            logger.exception("Web recording Worker initial registration failed")
        except Exception:
            # Do not terminate the worker when a raw Redis/client exception is
            # raised before the first heartbeat retry can run.
            logger.exception("Web recording Worker initial registration crashed")
        heartbeat_task = asyncio.create_task(self._heartbeat_loop(client))
        try:
            while not self.stop_event.is_set():
                try:
                    item = await client.blpop(
                        worker_queue_key(self.worker_id),
                        timeout=heartbeat_seconds,
                    )
                except WebRecordingTransportError:
                    logger.exception("Web recording Worker Redis control plane unavailable")
                    await asyncio.sleep(heartbeat_seconds)
                    continue
                except Exception:
                    logger.exception("Web recording Worker command loop failed")
                    await asyncio.sleep(heartbeat_seconds)
                    continue
                if item:
                    await self._process(client, item[1])
        finally:
            self.stop_event.set()
            heartbeat_task.cancel()
            await asyncio.gather(heartbeat_task, return_exceptions=True)
            await self.close()
            await unregister_recording_worker(self.worker_id, client=client)
            self._clear_health_file()
            close = getattr(_redis_client, "close_async_redis", None)
            if close is not None:
                await close(client)
            else:
                close_method = getattr(client, "aclose", None)
                if close_method is not None:
                    await close_method()


async def main() -> None:
    worker = WebRecordingWorker()
    loop = asyncio.get_running_loop()
    for signal_name in ("SIGINT", "SIGTERM"):
        signal_value = getattr(signal, signal_name, None)
        if signal_value is None:
            continue
        try:
            loop.add_signal_handler(signal_value, worker.stop_event.set)
        except (NotImplementedError, RuntimeError):
            # Windows only supports signal handlers from the main thread.
            continue
    logger.info("Web recording worker %s started with capacity %s", worker.worker_id, worker.capacity)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
