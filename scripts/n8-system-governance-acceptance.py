#!/usr/bin/env python3
"""Run a redacted N8 system-governance acceptance flow.

The default mode is read-only.  Configuration snapshots and the explicitly
confirmed rollback are opt-in because a revision is an intentional audit
record and is not deleted during cleanup.  Credentials are read only from
environment variables and response bodies are never copied to evidence.

Examples::

    ATP_USERNAME=admin ATP_PASSWORD='...' \
      python scripts/n8-system-governance-acceptance.py \
      --base-url http://127.0.0.1:8000/api/v1 \
      --require-role-matrix --report docs/evidence/n8-system-governance-acceptance.json

    # Add one encrypted revision and explicitly exercise ROLLBACK.
    python scripts/n8-system-governance-acceptance.py \
      --base-url http://127.0.0.1:8000/api/v1 \
      --allow-mutations --rollback --require-rollback --require-role-matrix
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any


SAFE_SCHEMES = {"http", "https"}
REQUIRED_SECTIONS = {
    "startup",
    "environment",
    "global_variable",
    "ai_llm",
    "storage_policy",
    "notification",
    "performance_node",
}
REVISION_DOMAINS = ("environment", "global_variable", "notification", "performance_node", "ai_llm", "storage_policy")
SENSITIVE_KEYS = {
    "access_key",
    "access_token",
    "api_key",
    "authorization",
    "password",
    "passwd",
    "private_key",
    "secret",
    "secret_key",
    "token",
    "url",
    "webhook_url",
    "endpoint",
    "cookie",
    "credential",
}
REDACTED_VALUES = {"******", "[redacted]", "<redacted>"}


class AcceptanceError(RuntimeError):
    """An expected, redacted acceptance failure."""


@dataclass
class CheckRecorder:
    checks: list[dict[str, str]] = field(default_factory=list)

    def add(self, name: str, status: str, details: str) -> None:
        self.checks.append({"name": name, "status": status, "details": details[:500]})


def _safe_url(value: str) -> str:
    """Keep only the public endpoint shape; remove userinfo, query and fragment."""

    parsed = urllib.parse.urlsplit(value.strip())
    if parsed.scheme not in SAFE_SCHEMES or not parsed.hostname:
        return "<invalid-url>"
    host = parsed.hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    netloc = host
    try:
        port = parsed.port
    except ValueError:
        return "<invalid-url>"
    if port is not None:
        netloc = f"{netloc}:{port}"
    path = parsed.path.rstrip("/") or "/"
    return urllib.parse.urlunsplit((parsed.scheme, netloc, path, "", ""))


def _default_report_path() -> Path:
    return Path("docs/evidence/n8-system-governance-acceptance.json")


def _resource_id(payload: Any) -> int:
    if not isinstance(payload, dict) or not isinstance(payload.get("id"), int) or payload["id"] < 1:
        raise AcceptanceError("response did not contain a valid resource id")
    return payload["id"]


def _safe_payload(payload: Any, path: str = "payload") -> None:
    """Reject secret-bearing values before a response can reach evidence."""

    if isinstance(payload, dict):
        for key, value in payload.items():
            normalized = str(key).strip().lower()
            if normalized in SENSITIVE_KEYS and value not in (None, "", False) and str(value) not in REDACTED_VALUES:
                raise AcceptanceError(f"response contained a non-empty sensitive field at {path}.{normalized}")
            _safe_payload(value, f"{path}.{normalized}")
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            _safe_payload(value, f"{path}[{index}]")


class ApiClient:
    """Small cookie-aware JSON client with deliberately redacted errors."""

    def __init__(self, base_url: str, timeout: float = 20.0, token: str | None = None):
        parsed = urllib.parse.urlsplit(base_url.strip())
        if (
            parsed.scheme not in SAFE_SCHEMES
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("base URL must be an http(s) URL without credentials, query or fragment")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.cookies = CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        }
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    def _url(self, path: str) -> str:
        if not path.startswith("/") or "#" in path:
            raise ValueError("acceptance paths must be absolute and fragment-free")
        return f"{self.base_url}{path}"

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> bytes:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(self._url(path), data=data, method=method, headers=self.headers)
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                return response.read(2 * 1024 * 1024)
        except urllib.error.HTTPError as exc:
            exc.read()
            raise AcceptanceError(f"{method} {path} returned HTTP {exc.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            reason = "timeout" if isinstance(exc, TimeoutError) else "request failed"
            raise AcceptanceError(f"{method} {path}: {reason}") from None

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        raw = self._request(method, path, payload)
        if not raw:
            return {}
        try:
            value = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise AcceptanceError(f"{method} {path} returned a non-JSON response") from None
        _safe_payload(value)
        return value

    def request_raw(self, method: str, path: str) -> bytes:
        return self._request(method, path)

    def login(self, username: str, password: str) -> None:
        response = self.request("POST", "/auth/login", {"username": username, "password": password})
        if isinstance(response, dict) and isinstance(response.get("access_token"), str):
            self.headers["Authorization"] = f"Bearer {response['access_token']}"


def _credentials(name: str) -> tuple[str | None, str | None]:
    return os.getenv(f"ATP_{name}_USERNAME"), os.getenv(f"ATP_{name}_PASSWORD")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.getenv("ATP_ACCEPTANCE_BASE_URL") or os.getenv("ATP_BASE_URL"))
    parser.add_argument("--report", type=Path, default=_default_report_path())
    parser.add_argument("--allow-mutations", action="store_true", help="allow encrypted revision creation")
    parser.add_argument("--rollback", action="store_true", help="also exercise the exact ROLLBACK confirmation")
    parser.add_argument("--require-rollback", action="store_true", help="fail when rollback cannot be exercised")
    parser.add_argument("--require-role-matrix", action="store_true", help="fail when viewer credentials are absent")
    parser.add_argument("--timeout", type=float, default=20.0)
    return parser.parse_args(argv)


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _set_overall_status(report: dict[str, Any]) -> None:
    statuses = {item["status"] for item in report["checks"]}
    if "failed" in statuses:
        report["status"] = "failed"
    elif "skipped" in statuses:
        report["status"] = "partial"
    else:
        report["status"] = "passed"


def _assert_http_status(client: ApiClient, method: str, path: str, expected: int) -> None:
    try:
        client.request(method, path)
    except AcceptanceError as exc:
        if f"HTTP {expected}" in str(exc):
            return
        raise
    raise AcceptanceError(f"{method} {path} unexpectedly succeeded")


def _select_revision_entry(overview: Any) -> tuple[str, int] | None:
    if not isinstance(overview, dict) or not isinstance(overview.get("sections"), list):
        raise AcceptanceError("configuration overview did not contain sections")
    sections = {item.get("key"): item for item in overview["sections"] if isinstance(item, dict)}
    for domain in REVISION_DOMAINS:
        entries = sections.get(domain, {}).get("entries", [])
        for entry in entries:
            resource_id = entry.get("resource_id") if isinstance(entry, dict) else None
            if isinstance(resource_id, int) and resource_id > 0:
                return domain, resource_id
    return None


def run_acceptance(args: argparse.Namespace) -> dict[str, Any]:
    recorder = CheckRecorder()
    report: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "N8 system governance and configuration boundaries",
        "status": "failed",
        "endpoint": _safe_url(args.base_url or ""),
        "checks": recorder.checks,
        "resources": {},
    }
    admin_client: ApiClient | None = None

    try:
        if not args.base_url:
            recorder.add("configuration", "failed", "--base-url or ATP_ACCEPTANCE_BASE_URL is required")
            return report
        if args.rollback and not args.allow_mutations:
            recorder.add("mutation-safety", "failed", "--rollback requires --allow-mutations")
            return report

        token = os.getenv("ATP_TOKEN")
        username, password = _credentials("ACCEPTANCE")
        if not token and (not username or not password):
            username = username or os.getenv("ATP_USERNAME")
            password = password or os.getenv("ATP_PASSWORD")
        if not token and (not username or not password):
            recorder.add("authentication", "failed", "set ATP_TOKEN or ATP_USERNAME/ATP_PASSWORD in the environment")
            return report

        admin_client = ApiClient(args.base_url, timeout=args.timeout, token=token)
        if not token:
            admin_client.login(username or "", password or "")
        me = admin_client.request("GET", "/auth/me")
        if not isinstance(me, dict) or me.get("role") != "admin":
            raise AcceptanceError("N8 governance acceptance requires a global admin account")
        recorder.add("authentication", "passed", "authenticated as admin; credentials were not recorded")

        toolbox = admin_client.request("GET", "/remote-toolbox/overview")
        checks = toolbox.get("checks") if isinstance(toolbox, dict) else None
        if not isinstance(checks, list):
            raise AcceptanceError("remote toolbox response did not contain checks")
        keys = {item.get("key") for item in checks if isinstance(item, dict)}
        missing = {"postgres", "redis", "minio"} - keys
        if missing:
            raise AcceptanceError("remote toolbox omitted required dependency checks")
        recorder.add(
            "remote-diagnostics",
            "passed",
            f"remote toolbox returned {len(checks)} redacted checks; service status remains environment evidence",
        )

        overview = admin_client.request("GET", "/configuration-center/overview")
        sections = overview.get("sections") if isinstance(overview, dict) else None
        section_keys = (
            {item.get("key") for item in sections if isinstance(item, dict)} if isinstance(sections, list) else set()
        )
        missing = REQUIRED_SECTIONS - section_keys
        if missing:
            raise AcceptanceError("configuration overview omitted required sections")
        recorder.add(
            "configuration-overview",
            "passed",
            "configuration metadata and availability were returned without secret values",
        )

        revision_target = _select_revision_entry(overview)
        if not args.allow_mutations:
            if args.require_rollback:
                recorder.add("configuration-revision", "failed", "--require-rollback needs --allow-mutations")
            else:
                recorder.add(
                    "configuration-revision",
                    "skipped",
                    "pass --allow-mutations to create a controlled encrypted revision",
                )
        elif revision_target is None:
            if args.require_rollback:
                recorder.add("configuration-revision", "failed", "no visible configuration resource was available")
            else:
                recorder.add("configuration-revision", "skipped", "no visible configuration resource was available")
        else:
            domain, resource_id = revision_target
            revision = admin_client.request(
                "POST",
                "/configuration-center/revisions",
                {"domain": domain, "resource_id": resource_id, "reason": "N8 acceptance snapshot"},
            )
            revision_id = _resource_id(revision)
            report["resources"]["revision_id"] = revision_id
            history = admin_client.request(
                "GET", f"/configuration-center/revisions?domain={domain}&resource_id={resource_id}&limit=5"
            )
            if not isinstance(history, list) or not any(
                item.get("id") == revision_id for item in history if isinstance(item, dict)
            ):
                raise AcceptanceError("created configuration revision was not readable")
            diff = admin_client.request("GET", f"/configuration-center/revisions/{revision_id}/diff")
            if not isinstance(diff, dict) or diff.get("revision_id") != revision_id:
                raise AcceptanceError("configuration revision diff was not readable")
            recorder.add("configuration-revision", "passed", f"created and diffed redacted {domain} revision")

            if not args.rollback:
                if args.require_rollback:
                    recorder.add("configuration-rollback", "failed", "pass --rollback to exercise exact confirmation")
                else:
                    recorder.add(
                        "configuration-rollback", "skipped", "pass --rollback to exercise exact ROLLBACK confirmation"
                    )
            else:
                rollback = admin_client.request(
                    "POST",
                    f"/configuration-center/revisions/{revision_id}/rollback",
                    {"confirmation": "ROLLBACK"},
                )
                if not isinstance(rollback, dict) or rollback.get("source_revision_id") != revision_id:
                    raise AcceptanceError("configuration rollback did not identify the source revision")
                recorder.add(
                    "configuration-rollback", "passed", "single-resource rollback completed with exact confirmation"
                )

        audit = admin_client.request_raw("GET", "/audit-logs/export?limit=100")
        if not audit.startswith((b"\xef\xbb\xbf", b"id,")):
            raise AcceptanceError("audit export did not return a bounded CSV evidence file")
        recorder.add("audit-export", "passed", "administrator audit export returned bounded CSV evidence")

        viewer_username, viewer_password = _credentials("VIEWER")
        if not viewer_username or not viewer_password:
            if args.require_role_matrix:
                recorder.add("role-matrix", "failed", "viewer credentials are required by --require-role-matrix")
            else:
                recorder.add(
                    "role-matrix", "skipped", "set ATP_VIEWER_USERNAME/ATP_VIEWER_PASSWORD to verify governance denial"
                )
        else:
            viewer = ApiClient(args.base_url, timeout=args.timeout)
            viewer.login(viewer_username, viewer_password)
            viewer_me = viewer.request("GET", "/auth/me")
            if isinstance(viewer_me, dict) and viewer_me.get("role") in {"admin", "engineer"}:
                raise AcceptanceError("role-matrix account must be an ordinary viewer")
            _assert_http_status(viewer, "GET", "/remote-toolbox/overview", 403)
            _assert_http_status(viewer, "GET", "/configuration-center/overview", 403)
            _assert_http_status(viewer, "GET", "/audit-logs/export?limit=1", 403)
            recorder.add(
                "role-matrix", "passed", "ordinary viewer was denied remote diagnostics, configuration and audit access"
            )
    except (AcceptanceError, ValueError) as exc:
        recorder.add("acceptance-execution", "failed", str(exc))
    _set_overall_status(report)
    return report


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    report = run_acceptance(args)
    _write_report(args.report, report)
    print(f"N8 system governance acceptance: {report['status']}; evidence={args.report}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
