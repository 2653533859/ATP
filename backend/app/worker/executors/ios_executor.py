"""Appium/XCUITest executor for iOS cases.

The worker talks to the standard W3C WebDriver/Appium HTTP protocol directly,
so the web/API process does not need the Appium Python client installed.  A
macOS worker still needs Appium 2, XCUITest and a signed WDA to execute it.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.minio_client import presigned_url, upload_bytes
from app.core.redis_client import publish_run_event
from app.models.case import RunStatus, StepResult, TestCase, TestRun
from app.models.ios import IosApp, IosDevice
from app.models.project import Module
from app.services.ios_device_leases import (
    IosDeviceLeaseConflict,
    acquire_ios_device_lease,
    heartbeat_ios_device_lease,
    release_ios_device_lease,
)

logger = logging.getLogger(__name__)


class AppiumProtocolError(RuntimeError):
    pass


class IosAppiumClient:
    """Small async client for the W3C WebDriver subset used by ATP."""

    def __init__(self, server_url: str, *, timeout: float = 30.0, http_client: httpx.AsyncClient | None = None):
        self.server_url = server_url.rstrip("/")
        self.http = http_client or httpx.AsyncClient(timeout=timeout)
        self._owns_client = http_client is None
        self.session_id: str | None = None

    async def close(self) -> None:
        if self._owns_client:
            await self.http.aclose()

    async def _request(self, method: str, path: str, *, json_body: dict | None = None) -> Any:
        response = await self.http.request(method, f"{self.server_url}{path}", json=json_body)
        try:
            payload = response.json()
        except ValueError as exc:
            raise AppiumProtocolError(f"Appium 返回了非 JSON 响应: HTTP {response.status_code}") from exc
        if response.status_code >= 400:
            raise AppiumProtocolError(str(payload.get("value") or payload))
        value = payload.get("value", payload)
        if isinstance(value, dict) and value.get("error"):
            raise AppiumProtocolError(str(value))
        return value

    def _session_path(self, suffix: str = "") -> str:
        if not self.session_id:
            raise AppiumProtocolError("Appium 会话尚未建立")
        return f"/session/{self.session_id}{suffix}"

    async def start_session(
        self,
        *,
        udid: str,
        device_name: str | None,
        platform_version: str | None,
        bundle_id: str | None,
        app: str | None,
    ) -> str:
        always_match: dict[str, Any] = {
            "platformName": "iOS",
            "appium:automationName": "XCUITest",
            "appium:udid": udid,
            "appium:noReset": True,
        }
        if device_name:
            always_match["appium:deviceName"] = device_name
        if platform_version:
            always_match["appium:platformVersion"] = platform_version
        if bundle_id:
            always_match["appium:bundleId"] = bundle_id
        if app:
            always_match["appium:app"] = app
        value = await self._request(
            "POST",
            "/session",
            json_body={"capabilities": {"alwaysMatch": always_match, "firstMatch": [{}]}},
        )
        if not isinstance(value, dict):
            raise AppiumProtocolError("Appium 创建会话响应格式无效")
        self.session_id = str(value.get("sessionId") or value.get("session_id") or "")
        if not self.session_id:
            raise AppiumProtocolError("Appium 响应缺少 sessionId")
        return self.session_id

    async def quit(self) -> None:
        if self.session_id:
            try:
                await self._request("DELETE", self._session_path())
            finally:
                self.session_id = None

    async def find_element(self, params: dict[str, Any]) -> str:
        strategy = str(params.get("strategy") or "accessibility_id")
        value = params.get("value") or params.get("accessibility_id") or params.get("text")
        if not value:
            raise AppiumProtocolError("iOS 元素定位缺少 value")
        strategies = {
            "accessibility_id": "accessibility id",
            "id": "id",
            "xpath": "xpath",
            "class_name": "class name",
            "predicate": "-ios predicate string",
            "class_chain": "-ios class chain",
        }
        result = await self._request(
            "POST",
            self._session_path("/element"),
            json_body={"using": strategies.get(strategy, strategy), "value": str(value)},
        )
        if not isinstance(result, dict):
            raise AppiumProtocolError("Appium 元素响应格式无效")
        return str(result.get("element-6066-11e4-a52e-4f735466cecf") or result.get("ELEMENT") or "")

    async def execute_step(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        if action in {"click", "input", "assert_element"}:
            element = await self.find_element(params)
            if action == "click":
                await self._request("POST", self._session_path(f"/element/{element}/click"), json_body={})
            elif action == "input":
                if params.get("clear", True):
                    await self._request("POST", self._session_path(f"/element/{element}/clear"), json_body={})
                await self._request(
                    "POST",
                    self._session_path(f"/element/{element}/value"),
                    json_body={"text": str(params.get("text", "")), "value": list(str(params.get("text", "")))},
                )
            return {"success": True, "element_id": element}
        if action == "assert_text":
            expected = str(params.get("text") or params.get("expected") or "")
            source = str(await self._request("GET", self._session_path("/source")))
            return {"success": expected in source, "expected": expected, "source_contains": expected in source}
        if action == "wait":
            seconds = max(0.0, min(float(params.get("seconds", params.get("timeout", 1))), 300.0))
            await asyncio.sleep(seconds)
            return {"success": True, "wait_seconds": seconds}
        if action == "screenshot":
            return {"success": True, "screenshot_base64": await self.screenshot()}
        if action == "back":
            await self._request("POST", self._session_path("/back"), json_body={})
            return {"success": True}
        if action == "start_app":
            bundle_id = str(params.get("bundle_id") or "")
            await self._request(
                "POST", self._session_path("/appium/device/activate_app"), json_body={"bundleId": bundle_id}
            )
            return {"success": True, "bundle_id": bundle_id}
        if action == "stop_app":
            bundle_id = str(params.get("bundle_id") or "")
            await self._request(
                "POST", self._session_path("/appium/device/terminate_app"), json_body={"bundleId": bundle_id}
            )
            return {"success": True, "bundle_id": bundle_id}
        if action == "get_source":
            return {"success": True, "source": str(await self._request("GET", self._session_path("/source")))[:200_000]}
        if action == "tap":
            await self._request(
                "POST", self._session_path("/actions"), json_body={"actions": [_touch_actions(params, "tap")]}
            )
            return {"success": True}
        if action == "swipe":
            await self._request(
                "POST", self._session_path("/actions"), json_body={"actions": [_touch_actions(params, "swipe")]}
            )
            return {"success": True}
        raise AppiumProtocolError(f"未知 iOS 操作类型: {action}")

    async def screenshot(self) -> str:
        value = await self._request("GET", self._session_path("/screenshot"))
        if not isinstance(value, str):
            raise AppiumProtocolError("Appium 截图响应格式无效")
        return value

    async def start_recording(self) -> None:
        await self._request(
            "POST", self._session_path("/appium/start_recording_screen"), json_body={"videoType": "h264"}
        )

    async def stop_recording(self) -> str | None:
        value = await self._request("POST", self._session_path("/appium/stop_recording_screen"), json_body={})
        return value if isinstance(value, str) and value else None

    async def syslog(self) -> str | None:
        value = await self._request("POST", self._session_path("/log"), json_body={"type": "syslog"})
        return json.dumps(value, ensure_ascii=False)[:2_000_000] if value is not None else None


def _touch_actions(params: dict[str, Any], mode: str) -> dict[str, Any]:
    x = int(params.get("x", 0))
    y = int(params.get("y", 0))
    actions: list[dict[str, Any]] = [
        {"type": "pointerMove", "duration": 0, "x": x, "y": y},
        {"type": "pointerDown", "button": 0},
    ]
    if mode == "swipe":
        actions.append(
            {
                "type": "pointerMove",
                "duration": max(100, int(params.get("duration_ms", 500))),
                "x": int(params.get("to_x", x)),
                "y": int(params.get("to_y", y)),
            }
        )
    actions.append({"type": "pointerUp", "button": 0})
    return {"type": "pointer", "id": "atp-touch", "parameters": {"pointerType": "touch"}, "actions": actions}


async def _safe_publish(run_id: int, payload: dict) -> None:
    try:
        await publish_run_event(run_id, payload)
    except Exception:
        logger.debug("Failed to publish iOS run event", exc_info=True)


async def _resolve_project_id(db: AsyncSession, case: TestCase) -> int | None:
    module_id = getattr(case, "module_id", None)
    if not isinstance(module_id, int):
        return None
    return (await db.execute(select(Module.project_id).where(Module.id == module_id))).scalar_one_or_none()


async def _upload_artifact(run_id: int, name: str, data: bytes, content_type: str) -> str | None:
    try:
        object_name = f"ios-artifacts/runs/{run_id}/{name}"
        await asyncio.to_thread(upload_bytes, object_name, data[:200_000_000], content_type)
        return presigned_url(object_name)
    except Exception:
        logger.warning("iOS artifact upload failed for run %s", run_id, exc_info=True)
        return None


async def run_ios_case(db: AsyncSession, run: TestRun, case: TestCase, extra_vars: dict) -> None:
    cfg = case.config or {}
    steps = cfg.get("steps", [])
    if not isinstance(steps, list) or not steps:
        run.status = RunStatus.error
        run.error_message = "iOS 用例未配置任何步骤"
        await db.commit()
        return
    project_id = await _resolve_project_id(db, case)
    device = await db.get(IosDevice, cfg.get("ios_device_id")) if cfg.get("ios_device_id") else None
    app = await db.get(IosApp, cfg.get("ios_app_id")) if cfg.get("ios_app_id") else None
    if app is not None and project_id is not None and app.project_id != project_id:
        run.status = RunStatus.error
        run.error_message = "IPA 资产不属于当前项目"
        await db.commit()
        return
    udid = str((device.udid if device else cfg.get("udid")) or "")
    server_url = str((device.appium_server_url if device else cfg.get("appium_server_url")) or "")
    if not udid or not server_url:
        run.status = RunStatus.error
        run.error_message = "未配置 iOS UDID 或 Appium 地址"
        await db.commit()
        return

    lease_token: str | None = None
    if device is not None:
        try:
            lease = await acquire_ios_device_lease(
                db,
                device.id,
                owner_id=getattr(run, "triggered_by", None),
                owner_label=f"ios-run:{run.id}",
                ttl_seconds=max(900, int(cfg.get("device_lease_ttl_seconds", 900))),
            )
            lease_token = lease.lease_token
            await db.commit()
        except (IosDeviceLeaseConflict, LookupError) as exc:
            run.status = RunStatus.failed
            run.error_message = f"iOS 设备租约冲突: {exc}"
            await db.commit()
            return

    client = IosAppiumClient(server_url, timeout=float(cfg.get("timeout_seconds", 30)))
    artifacts: dict[str, str] = {}
    passed = True
    started = time.monotonic()
    run.status = RunStatus.running
    await db.commit()
    try:
        app_url = presigned_url(app.object_name, expires_seconds=900) if app is not None else cfg.get("app")
        await client.start_session(
            udid=udid,
            device_name=device.name if device else cfg.get("device_name"),
            platform_version=device.platform_version if device else cfg.get("platform_version"),
            bundle_id=app.bundle_id if app else cfg.get("bundle_id"),
            app=app_url,
        )
        if cfg.get("record_video"):
            try:
                await client.start_recording()
            except AppiumProtocolError:
                logger.info("iOS Appium server does not support screen recording", exc_info=True)
        for index, step in enumerate(steps):
            step_started = time.monotonic()
            action = str(step.get("action", ""))
            name = str(step.get("name") or f"{action}_{index}")
            params = _render_params(step.get("params") or {}, {**extra_vars, "UDID": udid})
            status = RunStatus.passed
            error_message = None
            response_data: dict[str, Any] | None = None
            screenshot_url = None
            try:
                response_data = await client.execute_step(action, params)
                if response_data.get("success") is False:
                    status = RunStatus.failed
                    error_message = f"iOS 断言失败: {response_data}"
            except Exception as exc:
                status = RunStatus.failed
                error_message = str(exc)[:2000]
            if cfg.get("capture_screenshot", True) or action == "screenshot":
                try:
                    screenshot = response_data.get("screenshot_base64") if response_data else await client.screenshot()
                    screenshot_url = await _upload_artifact(
                        run.id, f"step_{index}.png", base64.b64decode(screenshot), "image/png"
                    )
                except Exception:
                    logger.debug("iOS screenshot unavailable for run %s step %s", run.id, index, exc_info=True)
            result = StepResult(
                run_id=run.id,
                step_index=index,
                name=name,
                status=status,
                duration_ms=int((time.monotonic() - step_started) * 1000),
                request_data={"action": action, "params": params},
                response_data=response_data,
                error_message=error_message,
                screenshot_url=screenshot_url,
            )
            db.add(result)
            if lease_token and device is not None:
                await heartbeat_ios_device_lease(db, device.id, lease_token)
            await db.commit()
            await _safe_publish(
                run.id,
                {
                    "type": "step_result",
                    "run_id": run.id,
                    "step": {
                        "step_index": index,
                        "name": name,
                        "status": status.value,
                        "error_message": error_message,
                        "screenshot_url": screenshot_url,
                    },
                },
            )
            if status != RunStatus.passed:
                passed = False
                break
        if cfg.get("record_video"):
            try:
                recording = await client.stop_recording()
                if recording:
                    artifacts["screen_recording"] = (
                        await _upload_artifact(run.id, "screen-recording.mp4", base64.b64decode(recording), "video/mp4")
                        or ""
                    )
            except AppiumProtocolError:
                pass
        try:
            logs = await client.syslog()
            if logs:
                artifacts["syslog"] = (
                    await _upload_artifact(run.id, "syslog.json", logs.encode("utf-8"), "application/json") or ""
                )
        except AppiumProtocolError:
            pass
        run.status = RunStatus.passed if passed else RunStatus.failed
    except Exception as exc:
        run.status = RunStatus.error
        run.error_message = str(exc)[:2000]
    finally:
        try:
            await client.quit()
        except Exception:
            logger.warning("Failed to quit Appium session for run %s", run.id, exc_info=True)
        try:
            await client.close()
        except Exception:
            logger.warning("Failed to close Appium HTTP client for run %s", run.id, exc_info=True)
        if lease_token and device is not None:
            try:
                await release_ios_device_lease(db, device.id, lease_token)
            except Exception:
                logger.warning("Failed to release iOS lease for run %s", run.id, exc_info=True)
        run.duration_ms = int((time.monotonic() - started) * 1000)
        run.result_summary = {
            **(run.result_summary or {}),
            "ios_artifacts": artifacts,
            "udid": udid,
            "appium_server_url": server_url,
        }
        await db.commit()
        await _safe_publish(
            run.id, {"type": "completed", "run_id": run.id, "status": run.status.value, "duration_ms": run.duration_ms}
        )


def _render_params(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, str):
        for key, item in context.items():
            value = value.replace("{{" + str(key) + "}}", str(item))
        return value
    if isinstance(value, dict):
        return {key: _render_params(item, context) for key, item in value.items()}
    if isinstance(value, list):
        return [_render_params(item, context) for item in value]
    return value
