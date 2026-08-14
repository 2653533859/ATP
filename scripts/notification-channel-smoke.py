"""Run a safe end-to-end acceptance check for one notification channel.

The command authenticates with ``ATP_TOKEN`` or ``ATP_USERNAME``/``ATP_PASSWORD``,
invokes the existing notification test-send endpoint, and verifies the resulting
delivery history row. Credentials are never accepted as command-line arguments
or written to the JSON report.

Example::

    python scripts/notification-channel-smoke.py \
      --api-base-url https://atp.example.test \
      --config-id 7 \
      --wait-seconds 15 \
      --report docs/evidence/notification-smoke-2026-08-13.json
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
from typing import Any
from http.cookiejar import CookieJar
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener


_SENSITIVE_TEXT_RE = re.compile(
    r"(?i)(?P<key>token|secret|password|passwd|api[_-]?key|authorization|cookie)(?P<sep>\s*[:=]\s*)[^,;\s}]+"
)
_URL_QUERY_SECRET_RE = re.compile(
    r"(?i)(?P<prefix>[?&](?:key|token|secret|api[_-]?key|authorization|cookie)\s*=\s*)"
    r"(?P<value>[^&#\s,;)}\]<>\"']+)"
)


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


def _safe_error(value: Any) -> str:
    text = str(value).replace("\r", " ").replace("\n", " ").strip()
    text = _SENSITIVE_TEXT_RE.sub(lambda match: f"{match.group('key')}{match.group('sep')}<redacted>", text)
    text = _URL_QUERY_SECRET_RE.sub(lambda match: f"{match.group('prefix')}<redacted>", text)
    return text[:800] or "unknown error"


def _redact_url(value: str) -> str:
    parsed = urlsplit(str(value))
    if not parsed.scheme or not parsed.netloc:
        return str(value)
    netloc = parsed.netloc.rsplit("@", 1)[-1] if parsed.username or parsed.password else parsed.netloc
    if parsed.username or parsed.password:
        netloc = f"<redacted>@{netloc}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, "<redacted>" if parsed.query else "", ""))


def _safe_argv(argv: list[str]) -> list[str]:
    safe: list[str] = []
    redact_next = False
    for item in argv:
        if redact_next:
            safe.append(_redact_url(item))
            redact_next = False
        elif item == "--api-base-url":
            safe.append(item)
            redact_next = True
        elif item.startswith("--api-base-url="):
            safe.append(f"--api-base-url={_redact_url(item.split('=', 1)[1])}")
        else:
            safe.append(item)
    return safe


def _safe_inputs(args: argparse.Namespace) -> dict[str, Any]:
    values = vars(args).copy()
    values["api_base_url"] = _redact_url(str(values["api_base_url"]))
    values["report"] = str(values["report"])
    return values


class ApiClient:
    def __init__(self, base_url: str, *, token: str | None, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self._opener = build_opener(HTTPCookieProcessor(CookieJar()))

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
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
                body = response.read()
        except HTTPError as exc:
            try:
                detail = json.loads(exc.read().decode("utf-8", errors="replace"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                detail = exc.reason
            raise SmokeError(f"API {method.upper()} {path} 返回 HTTP {exc.code}: {_safe_error(detail)}") from exc
        except (OSError, URLError) as exc:
            raise SmokeError(f"API {method.upper()} {path} 连接失败: {_safe_error(exc)}") from exc
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
    result = client.request("POST", "/api/v1/auth/login", {"username": username, "password": password})
    if not isinstance(result, dict) or result.get("authenticated") is not True:
        raise SmokeError("登录响应未建立 Cookie 会话")
    return client


def _client_from_environment(base_url: str, *, timeout: float) -> ApiClient:
    token = os.environ.get("ATP_TOKEN", "").strip()
    if token:
        return ApiClient(base_url, token=token, timeout=timeout)
    return _login(base_url, timeout=timeout)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="验证一个真实通知渠道的测试发送与投递历史")
    parser.add_argument("--api-base-url", required=True, help="ATP API 地址，例如 https://atp.example.test")
    parser.add_argument("--config-id", required=True, type=int, help="要验收的通知配置 ID")
    parser.add_argument("--wait-seconds", type=float, default=15, help="等待投递历史写入的最长时间，默认 15 秒")
    parser.add_argument("--poll-interval", type=float, default=1, help="投递历史轮询间隔，默认 1 秒")
    parser.add_argument("--timeout", type=float, default=10, help="单次 API 请求超时时间，默认 10 秒")
    parser.add_argument(
        "--report",
        type=Path,
        default=Path(".local-run") / "notification-channel-smoke.json",
        help="脱敏 JSON 报告路径",
    )
    args = parser.parse_args()
    parsed = urlsplit(str(args.api_base_url))
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        parser.error("--api-base-url 必须是没有用户信息的 http(s) 地址")
    if args.config_id < 1 or args.wait_seconds < 0 or args.poll_interval <= 0 or args.timeout <= 0:
        parser.error("--config-id 必须大于 0，等待、轮询和超时时间必须有效")
    return args


def main() -> int:
    args = _parse_args()
    report = CheckReport()
    try:
        client = _client_from_environment(str(args.api_base_url), timeout=args.timeout)
        config = client.request("GET", f"/api/v1/notifications/{args.config_id}")
        if not isinstance(config, dict) or not config.get("id"):
            raise SmokeError("通知配置响应无效")
        channel = str(config.get("channel", "unknown"))
        report.passed("notification-config", f"config_id={args.config_id}, channel={channel}")

        before = client.request(
            "GET",
            "/api/v1/notifications/deliveries?" + urlencode({"config_id": args.config_id, "limit": 20}),
        )
        before_ids = (
            {item.get("id") for item in before if isinstance(item, dict)} if isinstance(before, list) else set()
        )
        send_error: SmokeError | None = None
        try:
            result = client.request("POST", f"/api/v1/notifications/{args.config_id}/test")
            attempts = result.get("attempts") if isinstance(result, dict) else None
            report.passed("notification-test-send", f"请求成功，attempts={attempts or 1}")
        except SmokeError as exc:
            send_error = exc
            report.failed("notification-test-send", _safe_error(exc))

        deadline = time.monotonic() + args.wait_seconds
        latest: dict[str, Any] | None = None
        while True:
            deliveries = client.request(
                "GET",
                "/api/v1/notifications/deliveries?" + urlencode({"config_id": args.config_id, "limit": 20}),
            )
            if isinstance(deliveries, list):
                candidates = [
                    item for item in deliveries if isinstance(item, dict) and item.get("id") not in before_ids
                ]
                if candidates:
                    latest = candidates[0]
                    break
            if time.monotonic() >= deadline:
                break
            time.sleep(min(args.poll_interval, max(0.01, deadline - time.monotonic())))

        if latest is None:
            raise SmokeError("测试发送后未在投递历史中找到新记录") from send_error
        status = str(latest.get("status", "unknown"))
        attempts = latest.get("attempts", "?")
        if status != "sent":
            detail = f"status={status}, attempts={attempts}"
            error = latest.get("error_message")
            if error:
                detail += f", error={_safe_error(error)}"
            raise SmokeError(detail) from send_error
        report.passed("notification-delivery", f"status=sent, channel={channel}, attempts={attempts}")
    except SmokeError as exc:
        if not report.checks or report.checks[-1].status != "FAIL":
            report.failed("notification-channel", _safe_error(exc))
    except Exception as exc:  # pragma: no cover - defensive CLI boundary
        report.failed("notification-channel", _safe_error(exc))
    finally:
        report.write(args.report, args=args)
    return 1 if report.has_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
