#!/usr/bin/env python3
"""Generate bounded authenticated read traffic and an optional safe API case canary."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from http.cookiejar import CookieJar
import json
import os
from pathlib import Path
import stat
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener


TERMINAL_RUN_STATUSES = {"passed", "failed", "error", "cancelled"}
SAFE_CANARY_HOSTS = {"127.0.0.1", "localhost", "::1"}


class CanaryError(RuntimeError):
    """The bounded traffic canary could not prove a required condition."""


def _secret_from_environment(name: str) -> str:
    """Read a secret from NAME or NAME_FILE without exposing its value."""
    direct_value = os.environ.get(name, "")
    file_name = os.environ.get(f"{name}_FILE", "").strip()
    if direct_value and file_name:
        raise CanaryError(f"set only one of {name} and {name}_FILE")
    if not file_name:
        return direct_value

    path = Path(file_name)
    try:
        metadata = path.stat()
        credential_directory = os.environ.get("CREDENTIALS_DIRECTORY", "").strip()
        systemd_credential = bool(
            credential_directory and path.resolve(strict=True).parent == Path(credential_directory).resolve(strict=True)
        )
        if not stat.S_ISREG(metadata.st_mode):
            raise CanaryError(f"{name}_FILE must be a regular file")
        if os.name == "posix" and stat.S_IMODE(metadata.st_mode) & 0o077 and not systemd_credential:
            raise CanaryError(f"{name}_FILE must not be accessible by group or other users")
        value = path.read_text(encoding="utf-8").strip()
    except CanaryError:
        raise
    except OSError as exc:
        raise CanaryError(f"cannot read {name}_FILE: {type(exc).__name__}") from exc
    if not value:
        raise CanaryError(f"{name}_FILE is empty")
    return value


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
            raise CanaryError(f"API {method.upper()} {path} returned HTTP {exc.code}") from exc
        except (OSError, URLError) as exc:
            raise CanaryError(f"API {method.upper()} {path} connection failed: {type(exc).__name__}") from exc
        if not body:
            return None
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CanaryError(f"API {method.upper()} {path} returned non-JSON content") from exc


def _client_from_environment(base_url: str, *, timeout: float) -> ApiClient:
    token = _secret_from_environment("ATP_TOKEN").strip()
    if token:
        return ApiClient(base_url, token=token, timeout=timeout)

    username = os.environ.get("ATP_USERNAME", "").strip()
    password = _secret_from_environment("ATP_PASSWORD")
    if not username or not password:
        raise CanaryError("set ATP_TOKEN or both ATP_USERNAME and ATP_PASSWORD")
    client = ApiClient(base_url, token=None, timeout=timeout)
    result = client.request("POST", "/api/v1/auth/login", {"username": username, "password": password})
    if not isinstance(result, dict) or result.get("authenticated") is not True:
        raise CanaryError("login did not establish a Cookie session")
    return client


def _items(payload: Any, label: str) -> list[dict[str, Any]]:
    values = payload if isinstance(payload, list) else payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(values, list) or not all(isinstance(item, dict) for item in values):
        raise CanaryError(f"{label} response has an invalid shape")
    return values


def _select_project(client: ApiClient, project_id: int | None) -> int:
    projects = _items(client.request("GET", "/api/v1/projects?limit=100"), "projects")
    visible_ids = [item.get("id") for item in projects if isinstance(item.get("id"), int)]
    if project_id is not None:
        if project_id not in visible_ids:
            raise CanaryError(f"project_id={project_id} is not visible to the authenticated account")
        return project_id
    if not visible_ids:
        raise CanaryError("the authenticated account has no visible project")
    return visible_ids[0]


def _generate_read_traffic(client: ApiClient, *, project_id: int, iterations: int, delay_seconds: float) -> int:
    request_count = 0
    for index in range(iterations):
        client.request("GET", "/api/v1/projects?limit=100")
        client.request("GET", "/api/v1/workbench/overview?" + urlencode({"project_id": project_id}))
        request_count += 2
        if index + 1 < iterations and delay_seconds:
            time.sleep(delay_seconds)
    return request_count


def _validate_case_canary(client: ApiClient, *, project_id: int, case_id: int) -> dict[str, Any]:
    cases = _items(
        client.request(
            "GET",
            "/api/v1/cases?" + urlencode({"project_id": project_id, "status": "active", "review_status": "approved"}),
        ),
        "cases",
    )
    if not any(item.get("id") == case_id for item in cases):
        raise CanaryError(f"case_id={case_id} is not an active approved case in project_id={project_id}")

    case = client.request("GET", f"/api/v1/cases/{case_id}")
    if not isinstance(case, dict):
        raise CanaryError("case response has an invalid shape")
    config = case.get("config") if isinstance(case.get("config"), dict) else {}
    parsed_target = urlsplit(str(config.get("url") or config.get("base_url") or ""))
    try:
        target_port = parsed_target.port
    except ValueError as exc:
        raise CanaryError("case canary safety checks failed: target") from exc
    steps = case.get("steps") if isinstance(case.get("steps"), list) else []
    checks = {
        "case_type": case.get("case_type") == "api",
        "status": case.get("status") == "active",
        "review_status": case.get("review_status") == "approved",
        "automation_status": case.get("automation_status") in {"auto", "semi_auto"},
        "ready": case.get("is_ready_for_execution") is True,
        "method": str(config.get("method", "")).upper() == "GET",
        "target": parsed_target.scheme == "http" and parsed_target.hostname in SAFE_CANARY_HOSTS,
        "steps": len(steps) == 1,
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise CanaryError("case canary safety checks failed: " + ", ".join(failed))
    return {
        "case_id": case_id,
        "method": "GET",
        "target_host": parsed_target.hostname,
        "target_port": target_port,
        "step_count": 1,
    }


def _run_case_canaries(
    client: ApiClient,
    *,
    case_id: int,
    run_count: int,
    run_timeout_seconds: float,
    poll_seconds: float,
    scrape_wait_seconds: float,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for index in range(run_count):
        run = client.request("POST", f"/api/v1/cases/{case_id}/run", {})
        if not isinstance(run, dict) or not isinstance(run.get("id"), int):
            raise CanaryError("case run response has an invalid shape")
        run_id = run["id"]
        status = str(run.get("status", ""))
        deadline = time.monotonic() + run_timeout_seconds
        while status not in TERMINAL_RUN_STATUSES and time.monotonic() < deadline:
            time.sleep(poll_seconds)
            current = client.request("GET", f"/api/v1/runs/{run_id}")
            if not isinstance(current, dict):
                raise CanaryError("run status response has an invalid shape")
            status = str(current.get("status", ""))
        if status not in TERMINAL_RUN_STATUSES:
            raise CanaryError(f"run_id={run_id} did not reach a terminal state")
        results.append({"run_id": run_id, "status": status})
        if status != "passed":
            raise CanaryError(f"run_id={run_id} reached terminal status {status}")
        if scrape_wait_seconds:
            time.sleep(scrape_wait_seconds)
    return results


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base-url", required=True, help="ATP origin, for example http://127.0.0.1:8000")
    parser.add_argument("--project-id", type=int)
    parser.add_argument("--iterations", type=int, default=6)
    parser.add_argument("--delay-seconds", type=float, default=0.2)
    parser.add_argument("--case-id", type=int)
    parser.add_argument("--confirm-case-run", action="store_true")
    parser.add_argument("--run-count", type=int, default=2)
    parser.add_argument("--run-timeout-seconds", type=float, default=90)
    parser.add_argument("--poll-seconds", type=float, default=2)
    parser.add_argument("--scrape-wait-seconds", type=float, default=20)
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument("--source-deployment", default="production-like")
    parser.add_argument("--report", type=Path, default=Path(".local-run/slo-traffic-canary.json"))
    args = parser.parse_args(argv)

    parsed_base = urlsplit(args.api_base_url)
    if (
        parsed_base.scheme not in {"http", "https"}
        or not parsed_base.hostname
        or parsed_base.username
        or parsed_base.password
        or parsed_base.query
        or parsed_base.fragment
    ):
        parser.error("--api-base-url must be an http(s) URL without user info, query, or fragment")
    if not 1 <= args.iterations <= 100 or not 0 <= args.delay_seconds <= 60:
        parser.error("--iterations must be 1..100 and --delay-seconds must be 0..60")
    if args.project_id is not None and args.project_id < 1:
        parser.error("--project-id must be positive")
    if (args.case_id is None) != (not args.confirm_case_run):
        parser.error("--case-id and --confirm-case-run must be supplied together")
    if args.case_id is not None and args.case_id < 1:
        parser.error("--case-id must be positive")
    if not 1 <= args.run_count <= 10:
        parser.error("--run-count must be 1..10")
    if args.run_timeout_seconds <= 0 or args.poll_seconds <= 0 or not 0 <= args.scrape_wait_seconds <= 120:
        parser.error("run timeout/poll must be positive and scrape wait must be 0..120")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    return args


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    generated_at = datetime.now(timezone.utc).isoformat()
    payload: dict[str, Any] = {
        "generated_at": generated_at,
        "status": "failed",
        "source_deployment": args.source_deployment,
        "traffic_profile": "bounded authenticated reads",
        "credentials_in_report": False,
    }
    try:
        client = _client_from_environment(args.api_base_url, timeout=args.timeout)
        project_id = _select_project(client, args.project_id)
        read_requests = _generate_read_traffic(
            client,
            project_id=project_id,
            iterations=args.iterations,
            delay_seconds=args.delay_seconds,
        )
        payload.update({"project_id": project_id, "authenticated_read_requests": read_requests})
        if args.case_id is not None:
            payload["case_canary"] = _validate_case_canary(client, project_id=project_id, case_id=args.case_id)
            payload["case_canary"]["runs"] = _run_case_canaries(
                client,
                case_id=args.case_id,
                run_count=args.run_count,
                run_timeout_seconds=args.run_timeout_seconds,
                poll_seconds=args.poll_seconds,
                scrape_wait_seconds=args.scrape_wait_seconds,
            )
            payload["traffic_profile"] += " plus explicit self-targeted API case runs"
        payload["status"] = "passed"
    except CanaryError as exc:
        payload["error"] = str(exc)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
