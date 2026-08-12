"""Run an explicit, credential-free Appium/XCUITest acceptance check.

The command is intentionally opt-in for creating a real iOS session.  A status
check only proves that Appium is reachable; ``--session-smoke`` additionally
creates a W3C session, optionally runs a JSON step file, captures artifacts and
always deletes the session.  Reports contain metadata only, never screenshots,
syslogs, input text, capability values or URL query strings.
"""

from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shlex
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen


_SENSITIVE_KEY_RE = re.compile(
    r"(?:token|secret|password|passwd|api[_-]?key|credential|authorization|cookie|value|text)",
    re.IGNORECASE,
)
_ALLOWED_ACTIONS = {
    "click",
    "input",
    "assert_text",
    "assert_element",
    "wait",
    "screenshot",
    "back",
    "start_app",
    "stop_app",
    "get_source",
    "tap",
    "swipe",
}


class AcceptanceError(RuntimeError):
    """A required Appium acceptance condition was not proven."""


@dataclass
class Check:
    name: str
    status: str
    detail: str


@dataclass
class AcceptanceReport:
    checks: list[Check] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    steps: list[dict[str, Any]] = field(default_factory=list)
    session_id: str | None = None

    def add(self, name: str, status: str, detail: str) -> None:
        self.checks.append(Check(name=name, status=status, detail=_short(detail)))
        print(f"[{status}] {name}: {_short(detail)}")

    def passed(self, name: str, detail: str) -> None:
        self.add(name, "PASS", detail)

    def failed(self, name: str, detail: str) -> None:
        self.add(name, "FAIL", detail)

    @property
    def has_failures(self) -> bool:
        return any(item.status == "FAIL" for item in self.checks)


def _short(value: Any, limit: int = 800) -> str:
    text = str(value).replace("\r", " ").replace("\n", " ").strip()
    return text[:limit] or "unknown error"


def _safe_url(value: str) -> str:
    raw = str(value or "").strip()
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise AcceptanceError("Appium 地址必须是 http(s)://host[:port][/base-path]")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise AcceptanceError("Appium 地址不能包含用户名、密码、查询参数或片段")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


def _redacted_url(value: str) -> str:
    try:
        return _safe_url(value)
    except AcceptanceError:
        parsed = urlsplit(str(value or ""))
        if parsed.scheme and parsed.hostname:
            return urlunsplit((parsed.scheme, parsed.hostname, parsed.path, "<redacted>", ""))
        return "<redacted-url>"


def _safe_argv(argv: list[str]) -> list[str]:
    url_options = {"--appium-url", "--app"}
    safe: list[str] = []
    redact_next = False
    for item in argv:
        if redact_next:
            safe.append(_redacted_url(item) if "://" in item else Path(item).name if item else item)
            redact_next = False
        elif item in url_options:
            safe.append(item)
            redact_next = True
        elif any(item.startswith(f"{option}=") for option in url_options):
            option, raw = item.split("=", 1)
            safe.append(f"{option}={_redacted_url(raw) if '://' in raw else Path(raw).name}")
        else:
            safe.append(item)
    return safe


def _safe_detail(value: Any) -> str:
    if isinstance(value, dict):
        filtered = {
            str(key): "<redacted>" if _SENSITIVE_KEY_RE.search(str(key)) else _safe_detail(item)
            for key, item in value.items()
        }
        return _short(filtered)
    if isinstance(value, list):
        return _short([_safe_detail(item) for item in value])
    return _short(value)


def _artifact(report: AcceptanceReport, directory: Path, name: str, data: bytes, content_type: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    safe_name = Path(name).name
    output = directory / safe_name
    output.write_bytes(data)
    report.artifacts.append(
        {
            "name": safe_name,
            "content_type": content_type,
            "size_bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    )


class AppiumClient:
    def __init__(self, base_url: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session_id: str | None = None

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        request = Request(
            self._url(path),
            data=data,
            method=method.upper(),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise AcceptanceError(f"Appium {method.upper()} {path} HTTP {exc.code}: {_short(exc.reason)}") from exc
        except (OSError, URLError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AcceptanceError(f"Appium {method.upper()} {path} 请求失败: {_short(exc)}") from exc
        if not isinstance(payload, dict):
            raise AcceptanceError(f"Appium {method.upper()} {path} 返回格式无效")
        value = payload.get("value", payload)
        if isinstance(value, dict) and value.get("error"):
            raise AcceptanceError(f"Appium {method.upper()} {path} 协议错误: {_safe_detail(value)}")
        return value

    def session_path(self, suffix: str = "") -> str:
        if not self.session_id:
            raise AcceptanceError("Appium 会话尚未建立")
        return f"/session/{self.session_id}{suffix}"


def _capabilities(args: argparse.Namespace) -> dict[str, Any]:
    always: dict[str, Any] = {
        "platformName": "iOS",
        "appium:automationName": "XCUITest",
        "appium:udid": args.udid,
        "appium:noReset": True,
    }
    for option, capability in (
        ("device_name", "appium:deviceName"),
        ("platform_version", "appium:platformVersion"),
        ("bundle_id", "appium:bundleId"),
    ):
        value = str(getattr(args, option) or "").strip()
        if value:
            always[capability] = value
    if args.app:
        always["appium:app"] = args.app
    return {"capabilities": {"alwaysMatch": always, "firstMatch": [{}]}}


def _load_steps(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AcceptanceError(f"步骤文件读取失败: {_short(exc)}") from exc
    if not isinstance(payload, list) or len(payload) > 100:
        raise AcceptanceError("步骤文件必须是最多 100 项的 JSON 数组")
    steps: list[dict[str, Any]] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict) or str(item.get("action") or "") not in _ALLOWED_ACTIONS:
            raise AcceptanceError(f"步骤 {index} 的 action 不受支持")
        steps.append(item)
    return steps


def _element_params(params: dict[str, Any]) -> tuple[str, str]:
    strategy = str(params.get("strategy") or "accessibility_id")
    value = params.get("value") or params.get("accessibility_id") or params.get("text")
    if not value:
        raise AcceptanceError("元素步骤缺少定位 value")
    strategies = {
        "accessibility_id": "accessibility id",
        "id": "id",
        "xpath": "xpath",
        "class_name": "class name",
        "predicate": "-ios predicate string",
        "class_chain": "-ios class chain",
    }
    return strategies.get(strategy, strategy), str(value)


def _execute_step(client: AppiumClient, action: str, params: dict[str, Any]) -> dict[str, Any]:
    session_path = client.session_path
    if action in {"click", "input", "assert_element"}:
        using, value = _element_params(params)
        element = client.request("POST", session_path("/element"), {"using": using, "value": value})
        if not isinstance(element, dict):
            raise AcceptanceError("元素响应格式无效")
        element_id = str(element.get("element-6066-11e4-a52e-4f735466cecf") or element.get("ELEMENT") or "")
        if not element_id:
            raise AcceptanceError("元素响应缺少 element id")
        if action == "click":
            client.request("POST", session_path(f"/element/{element_id}/click"), {})
        elif action == "input":
            if params.get("clear", True):
                client.request("POST", session_path(f"/element/{element_id}/clear"), {})
            text = str(params.get("text", ""))
            client.request("POST", session_path(f"/element/{element_id}/value"), {"text": text, "value": list(text)})
        return {"success": True}
    if action == "assert_text":
        expected = str(params.get("text") or params.get("expected") or "")
        source = str(client.request("GET", session_path("/source")))
        return {"success": bool(expected and expected in source)}
    if action == "wait":
        seconds = max(0.0, min(float(params.get("seconds", params.get("timeout", 1))), 300.0))
        time.sleep(seconds)
        return {"success": True}
    if action == "screenshot":
        return {"success": True, "screenshot_base64": client.request("GET", session_path("/screenshot"))}
    if action == "get_source":
        client.request("GET", session_path("/source"))
        return {"success": True}
    if action == "back":
        client.request("POST", session_path("/back"), {})
        return {"success": True}
    if action in {"start_app", "stop_app"}:
        bundle_id = str(params.get("bundle_id") or "")
        if not bundle_id:
            raise AcceptanceError(f"{action} 缺少 bundle_id")
        endpoint = "/appium/device/activate_app" if action == "start_app" else "/appium/device/terminate_app"
        client.request("POST", session_path(endpoint), {"bundleId": bundle_id})
        return {"success": True}
    if action in {"tap", "swipe"}:
        x, y = int(params.get("x", 0)), int(params.get("y", 0))
        actions = [
            {"type": "pointerMove", "duration": 0, "x": x, "y": y},
            {"type": "pointerDown", "button": 0},
        ]
        if action == "swipe":
            actions.append(
                {
                    "type": "pointerMove",
                    "duration": max(100, int(params.get("duration_ms", 500))),
                    "x": int(params.get("to_x", x)),
                    "y": int(params.get("to_y", y)),
                }
            )
        actions.append({"type": "pointerUp", "button": 0})
        client.request(
            "POST",
            session_path("/actions"),
            {
                "actions": [
                    {"type": "pointer", "id": "atp-touch", "parameters": {"pointerType": "touch"}, "actions": actions}
                ]
            },
        )
        return {"success": True}
    raise AcceptanceError(f"未知步骤 action: {action}")


def _run_session_smoke(client: AppiumClient, args: argparse.Namespace, report: AcceptanceReport) -> None:
    if not args.udid:
        raise AcceptanceError("--session-smoke 必须指定 --udid")
    steps = _load_steps(args.steps_file)
    value = client.request("POST", "/session", _capabilities(args))
    if not isinstance(value, dict):
        raise AcceptanceError("Appium 创建会话响应格式无效")
    client.session_id = str(value.get("sessionId") or value.get("session_id") or "")
    if not client.session_id:
        raise AcceptanceError("Appium 响应缺少 sessionId")
    report.session_id = "created"
    report.passed("appium-session", "XCUITest W3C session created")
    if args.record_video:
        client.request("POST", client.session_path("/appium/start_recording_screen"), {"videoType": "h264"})
    try:
        for index, step in enumerate(steps):
            action = str(step["action"])
            try:
                response = _execute_step(client, action, step.get("params") or {})
                if response.get("success") is False:
                    raise AcceptanceError("步骤返回 success=false")
                report.steps.append({"index": index, "action": action, "status": "passed"})
            except Exception as exc:
                report.steps.append({"index": index, "action": action, "status": "failed", "error": _safe_detail(exc)})
                raise
        report.passed("appium-steps", f"executed {len(steps)} configured step(s)")
    finally:
        artifact_dir = Path(args.artifact_dir) if args.artifact_dir else None
        if artifact_dir is not None:
            screenshot = client.request("GET", client.session_path("/screenshot"))
            if isinstance(screenshot, str):
                _artifact(
                    report, artifact_dir, "screenshot.png", base64.b64decode(screenshot, validate=True), "image/png"
                )
        if args.record_video:
            recording = client.request("POST", client.session_path("/appium/stop_recording_screen"), {})
            if artifact_dir is not None and isinstance(recording, str) and recording:
                _artifact(
                    report,
                    artifact_dir,
                    "screen-recording.mp4",
                    base64.b64decode(recording, validate=True),
                    "video/mp4",
                )
        if args.collect_syslog:
            logs = client.request("POST", client.session_path("/log"), {"type": "syslog"})
            if artifact_dir is not None:
                _artifact(
                    report,
                    artifact_dir,
                    "syslog.json",
                    json.dumps(logs, ensure_ascii=False).encode("utf-8"),
                    "application/json",
                )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--appium-url", required=True, help="Appium HTTP(S) 地址，例如 http://mac-worker:4723")
    parser.add_argument("--udid", help="iPhone/Simulator UDID；session smoke 必填")
    parser.add_argument("--device-name")
    parser.add_argument("--platform-version")
    parser.add_argument("--bundle-id")
    parser.add_argument("--app", help="Appium 可访问的 IPA/应用路径或 URL")
    parser.add_argument("--session-smoke", action="store_true", help="显式创建并销毁真实 XCUITest session")
    parser.add_argument("--steps-file", type=Path, help="最多 100 项的 iOS 低代码步骤 JSON 文件")
    parser.add_argument("--artifact-dir", type=Path, help="保存截图/录屏/syslog 的本地目录")
    parser.add_argument("--record-video", action="store_true")
    parser.add_argument("--collect-syslog", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--report", type=Path, help="脱敏 JSON 报告路径")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.timeout_seconds <= 0 or args.timeout_seconds > 300:
        raise SystemExit("--timeout-seconds 必须在 0 和 300 之间")
    if (args.record_video or args.collect_syslog) and not args.session_smoke:
        raise SystemExit("--record-video/--collect-syslog 必须同时指定 --session-smoke")
    report = AcceptanceReport()
    started = time.monotonic()
    try:
        appium_url = _safe_url(args.appium_url)
        client = AppiumClient(appium_url, args.timeout_seconds)
        status = client.request("GET", "/status")
        if not isinstance(status, dict) or status.get("ready") is not True:
            raise AcceptanceError(f"Appium status 未 ready: {_safe_detail(status)}")
        report.passed("appium-status", "Appium status ready=true")
        if args.session_smoke:
            _run_session_smoke(client, args, report)
    except Exception as exc:
        report.failed("ios-appium-acceptance", _safe_detail(exc))
    finally:
        if "client" in locals() and client.session_id:
            try:
                client.request("DELETE", client.session_path())
                report.passed("appium-session-cleanup", "session deleted")
            except Exception as exc:
                report.failed("appium-session-cleanup", _safe_detail(exc))
            client.session_id = None

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "command": " ".join(shlex.quote(item) for item in _safe_argv(sys.argv)),
        "appium_url": _redacted_url(args.appium_url),
        "udid_present": bool(args.udid),
        "bundle_id_present": bool(args.bundle_id),
        "app_name": Path(args.app).name
        if args.app and "://" not in args.app
        else ("<remote-app>" if args.app else None),
        "session_smoke": args.session_smoke,
        "duration_ms": int((time.monotonic() - started) * 1000),
        "status": "failed" if report.has_failures else "passed",
        "checks": [check.__dict__ for check in report.checks],
        "steps": report.steps,
        "artifacts": report.artifacts,
    }
    report_path = (
        args.report or Path(".local-run") / f"ios-appium-acceptance-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Report: {report_path}")
    return 1 if report.has_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
