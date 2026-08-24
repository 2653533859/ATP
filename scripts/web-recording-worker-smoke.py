"""Verify a Redis-routed Web Recording Worker from an external environment.

The command authenticates with ``ATP_TOKEN`` or ``ATP_USERNAME``/``ATP_PASSWORD``
and checks the worker status endpoint.  It only starts a real browser session
when ``--run-recording`` is explicitly supplied.  Credentials and URL query
strings are never written to the JSON report.

Preflight only::

    python scripts/web-recording-worker-smoke.py \
      --api-base-url https://atp.example.test \
      --project-id 7

Run a real session against an existing editor-accessible project::

    python scripts/web-recording-worker-smoke.py \
      --api-base-url https://atp.example.test \
      --project-id 7 \
      --start-url https://target.example.test \
      --browser chromium --run-recording --screenshot
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shlex
import sys
import time
from http.cookiejar import CookieJar
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener


_SENSITIVE_TEXT_RE = re.compile(
    r"(?i)(?P<key>token|secret|password|passwd|api[_-]?key|authorization|cookie)" r"(?P<sep>\s*[:=]\s*)[^,;\s}\]]+"
)
_URL_RE = re.compile(r"https?://[^\s'\"<>]+")


class SmokeError(RuntimeError):
    """An acceptance check could not prove its required condition."""


@dataclass
class Check:
    name: str
    status: str
    detail: str


class CheckReport:
    def __init__(self) -> None:
        self.checks: list[Check] = []

    def add(self, name: str, status: str, detail: str) -> None:
        self.checks.append(Check(name=name, status=status, detail=detail))
        print(f"[{status}] {name}: {detail}")

    def passed(self, name: str, detail: str) -> None:
        self.add(name, "PASS", detail)

    def failed(self, name: str, detail: str) -> None:
        self.add(name, "FAIL", detail)

    @property
    def has_failures(self) -> bool:
        return any(item.status == "FAIL" for item in self.checks)

    def write(self, path: Path, *, args: argparse.Namespace) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "command": " ".join(shlex.quote(item) for item in _safe_argv(sys.argv)),
            "inputs": _safe_inputs(args),
            "status": "failed" if self.has_failures else "passed",
            "checks": [asdict(item) for item in self.checks],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _redact_url(value: str) -> str:
    parsed = urlsplit(str(value))
    if not parsed.scheme or not parsed.netloc:
        return str(value)
    netloc = parsed.netloc.rsplit("@", 1)[-1] if parsed.username or parsed.password else parsed.netloc
    if parsed.username or parsed.password:
        netloc = f"<redacted>@{netloc}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, "<redacted>" if parsed.query else "", ""))


def _safe_error(value: Any) -> str:
    text = str(value).replace("\r", " ").replace("\n", " ").replace("\x00", " ").strip()
    text = _URL_RE.sub(lambda match: _redact_url(match.group(0)), text)
    text = _SENSITIVE_TEXT_RE.sub(lambda match: f"{match.group('key')}{match.group('sep')}<redacted>", text)
    return text[:800] or "unknown error"


def _safe_argv(argv: list[str]) -> list[str]:
    safe: list[str] = []
    redact_next = False
    for item in argv:
        if redact_next:
            safe.append(_redact_url(item))
            redact_next = False
        elif item in {"--api-base-url", "--start-url"}:
            safe.append(item)
            redact_next = True
        elif item.startswith("--api-base-url="):
            safe.append(f"--api-base-url={_redact_url(item.split('=', 1)[1])}")
        elif item.startswith("--start-url="):
            safe.append(f"--start-url={_redact_url(item.split('=', 1)[1])}")
        else:
            safe.append(item)
    return safe


def _safe_inputs(args: argparse.Namespace) -> dict[str, Any]:
    values = vars(args).copy()
    values["api_base_url"] = _redact_url(str(values["api_base_url"]))
    if values.get("start_url"):
        values["start_url"] = _redact_url(str(values["start_url"]))
    values["report"] = str(values["report"])
    return values


class ApiClient:
    def __init__(self, base_url: str, *, token: str | None, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self._opener = build_opener(HTTPCookieProcessor(CookieJar()))

    def request_raw(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> tuple[dict[str, str], bytes]:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Accept": "application/json"}
        if method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
            headers["X-Requested-With"] = "XMLHttpRequest"
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = Request(
            f"{self.base_url}/{path.lstrip('/')}",
            data=data,
            headers=headers,
            method=method.upper(),
        )
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                return {str(key).lower(): str(value) for key, value in response.headers.items()}, response.read()
        except HTTPError as exc:
            try:
                detail = json.loads(exc.read().decode("utf-8", errors="replace"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                detail = exc.reason
            raise SmokeError(f"API {method.upper()} {path} 返回 HTTP {exc.code}: {_safe_error(detail)}") from exc
        except (OSError, URLError) as exc:
            raise SmokeError(f"API {method.upper()} {path} 连接失败: {_safe_error(exc)}") from exc

    def request_json(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        _headers, body = self.request_raw(method, path, payload)
        if not body:
            return None
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SmokeError(f"API {method.upper()} {path} 返回了非 JSON 内容") from exc


def _login(base_url: str, *, timeout: float) -> ApiClient:
    username = os.environ.get("ATP_USERNAME", "").strip()
    password = os.environ.get("ATP_PASSWORD", "")
    if not username or not password:
        raise SmokeError("验收需要 ATP_TOKEN，或同时设置 ATP_USERNAME 与 ATP_PASSWORD")
    client = ApiClient(base_url, token=None, timeout=timeout)
    result = client.request_json("POST", "/api/v1/auth/login", {"username": username, "password": password})
    if not isinstance(result, dict) or result.get("authenticated") is not True:
        raise SmokeError("登录响应未建立 Cookie 会话")
    return client


def _client_from_environment(base_url: str, *, timeout: float) -> ApiClient:
    token = os.environ.get("ATP_TOKEN", "").strip()
    if token:
        return ApiClient(base_url, token=token, timeout=timeout)
    return _login(base_url, timeout=timeout)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="验收 Redis 路由的 Web 录制 Worker")
    parser.add_argument("--api-base-url", required=True, help="ATP API 地址，例如 https://atp.example.test")
    parser.add_argument("--project-id", required=True, type=int, help="已有且当前账号具备编辑权限的项目 ID")
    parser.add_argument("--start-url", help="真实录制目标 URL；只有 --run-recording 时必填")
    parser.add_argument("--browser", choices=("chromium", "firefox", "webkit"), default="chromium")
    parser.add_argument("--run-recording", action="store_true", help="显式启动并停止一次真实录制会话")
    parser.add_argument("--screenshot", action="store_true", help="真实录制期间额外验证截图接口")
    parser.add_argument("--wait-seconds", type=float, default=30, help="等待 Worker 可用的最长时间，默认 30 秒")
    parser.add_argument("--poll-interval", type=float, default=1, help="Worker 状态轮询间隔，默认 1 秒")
    parser.add_argument("--timeout", type=float, default=15, help="单次 API 请求超时时间，默认 15 秒")
    parser.add_argument(
        "--report",
        type=Path,
        default=Path(".local-run") / "web-recording-worker-smoke.json",
        help="脱敏 JSON 报告路径",
    )
    args = parser.parse_args()
    parsed = urlsplit(str(args.api_base_url))
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        parser.error("--api-base-url 必须是没有用户信息的 http(s) 地址")
    if args.project_id < 1 or args.wait_seconds < 0 or args.poll_interval <= 0 or args.timeout <= 0:
        parser.error("项目 ID 必须大于 0，等待、轮询和超时时间必须有效")
    if args.run_recording and not args.start_url:
        parser.error("--run-recording 必须同时提供 --start-url")
    if args.screenshot and not args.run_recording:
        parser.error("--screenshot 必须与 --run-recording 一起使用")
    if args.start_url:
        target = urlsplit(str(args.start_url))
        if target.scheme not in {"http", "https"} or not target.hostname or target.username or target.password:
            parser.error("--start-url 必须是没有用户信息的 http(s) 地址")
    return args


def _wait_for_worker(client: ApiClient, args: argparse.Namespace, report: CheckReport) -> None:
    deadline = time.monotonic() + args.wait_seconds
    while True:
        payload = client.request_json("GET", "/api/v1/web-recordings/workers")
        if not isinstance(payload, dict):
            raise SmokeError("Worker 状态响应无效")
        mode = str(payload.get("mode") or "")
        registered = int(payload.get("registered_count") or 0)
        available = int(payload.get("available_count") or 0)
        if mode == "worker" and available > 0:
            report.passed(
                "worker-preflight", f"mode=worker, registered_count={registered}, available_count={available}"
            )
            return
        if time.monotonic() >= deadline:
            raise SmokeError(
                f"没有可用的 Web 录制 Worker: mode={mode}, registered_count={registered}, available_count={available}"
            )
        time.sleep(min(args.poll_interval, max(0.01, deadline - time.monotonic())))


def _run_recording(client: ApiClient, args: argparse.Namespace, report: CheckReport) -> None:
    payload = {
        "project_id": args.project_id,
        "start_url": args.start_url,
        "browser": args.browser,
    }
    result = client.request_json("POST", "/api/v1/web-recordings", payload)
    if not isinstance(result, dict) or not result.get("id"):
        raise SmokeError("录制启动响应无效")
    session_id = str(result["id"])
    stopped = False
    try:
        status = str(result.get("status") or "")
        if status != "recording":
            raise SmokeError(f"录制会话未进入 recording: status={status}")
        report.passed("recording-start", f"browser={args.browser}, status=recording")
        snapshot = client.request_json("GET", f"/api/v1/web-recordings/{session_id}")
        if not isinstance(snapshot, dict) or str(snapshot.get("status") or "") != "recording":
            raise SmokeError("录制会话查询未保持 recording 状态")
        report.passed("recording-snapshot", f"steps={len(snapshot.get('steps') or [])}")
        if args.screenshot:
            headers, image = client.request_raw("POST", f"/api/v1/web-recordings/{session_id}/screenshot")
            content_type = headers.get("content-type", "").split(";", 1)[0].lower()
            if content_type != "image/png" or not image:
                raise SmokeError(f"截图响应无效: content_type={content_type}, bytes={len(image)}")
            report.passed("recording-screenshot", f"content_type=image/png, bytes={len(image)}")
        stopped_snapshot = client.request_json("POST", f"/api/v1/web-recordings/{session_id}/stop")
        stopped = True
        if not isinstance(stopped_snapshot, dict) or str(stopped_snapshot.get("status") or "") != "stopped":
            raise SmokeError("录制停止响应未进入 stopped 状态")
        report.passed("recording-stop", "status=stopped")
        artifacts = stopped_snapshot.get("artifacts")
        required_artifacts = {"trace", "har", "report"}
        if not isinstance(artifacts, dict) or not required_artifacts.issubset(artifacts):
            raise SmokeError("停止响应缺少 Trace、HAR 或运行报告证据")
        if any(not isinstance(artifacts[name], dict) or not artifacts[name].get("url") for name in required_artifacts):
            raise SmokeError("录制证据缺少可访问 URL")
        report.passed(
            "recording-evidence",
            f"trace/har/report=3, console={len(stopped_snapshot.get('console_messages') or [])}, "
            f"network={len(stopped_snapshot.get('network_events') or [])}",
        )
        final_snapshot = client.request_json("GET", f"/api/v1/web-recordings/{session_id}")
        if not isinstance(final_snapshot, dict) or str(final_snapshot.get("status") or "") != "stopped":
            raise SmokeError("停止后的录制报告无法再次查询")
        report.passed("recording-report-query", "stopped snapshot remains available")
    finally:
        if not stopped:
            try:
                client.request_json("POST", f"/api/v1/web-recordings/{session_id}/stop")
            except SmokeError as exc:
                report.failed("recording-cleanup", _safe_error(exc))


def main() -> int:
    args = _parse_args()
    report = CheckReport()
    try:
        client = _client_from_environment(str(args.api_base_url), timeout=args.timeout)
        _wait_for_worker(client, args, report)
        if args.run_recording:
            _run_recording(client, args, report)
        else:
            report.passed("recording-run", "未执行真实录制；如需验证浏览器启动、截图和停止，请显式传入 --run-recording")
    except SmokeError as exc:
        report.failed("web-recording-worker", _safe_error(exc))
    except Exception as exc:  # pragma: no cover - defensive CLI boundary
        report.failed("web-recording-worker", _safe_error(exc))
    finally:
        report.write(args.report, args=args)
    return 1 if report.has_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
