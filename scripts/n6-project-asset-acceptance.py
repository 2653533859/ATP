#!/usr/bin/env python3
"""Run the safe N6 project-asset and project-role acceptance flow.

The command creates one temporary project and removes it in a ``finally`` block.
Credentials are read only from environment variables; the evidence report keeps
only status, resource IDs and redacted paths.  Mutations and execution are
explicit opt-ins so importing or invoking the parser cannot change a target.

Examples::

    ATP_USERNAME=admin ATP_PASSWORD='...' \
      python scripts/n6-project-asset-acceptance.py \
      --base-url http://127.0.0.1:8000/api/v1 \
      --allow-mutations --execute --target-url http://127.0.0.1:8000/health \
      --require-role-matrix --report docs/evidence/n6-project-asset-acceptance.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any


TERMINAL_RUN_STATUSES = {"passed", "failed", "error", "cancelled", "stopped", "success", "completed"}
SAFE_SCHEMES = {"http", "https"}


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


def _safe_target_url(value: str) -> str:
    """Validate the optional read-only execution target without echoing secrets."""
    parsed = urllib.parse.urlsplit(value.strip())
    if parsed.scheme not in SAFE_SCHEMES or not parsed.hostname:
        raise ValueError("target URL must be an http(s) URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("target URL must not contain credentials, query or fragment")
    return value.strip()


def _default_report_path() -> Path:
    return Path("docs/evidence/n6-project-asset-acceptance.json")


def _resource_id(payload: Any, key: str = "id") -> int:
    if not isinstance(payload, dict) or not isinstance(payload.get(key), int) or payload[key] < 1:
        raise AcceptanceError(f"response did not contain a valid {key}")
    return payload[key]


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

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(self._url(path), data=data, method=method, headers=self.headers)
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                raw = response.read(2 * 1024 * 1024)
                if not raw:
                    return {}
                return json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            exc.read()
            raise AcceptanceError(f"{method} {path} returned HTTP {exc.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            reason = "timeout" if isinstance(exc, TimeoutError) else "request failed"
            raise AcceptanceError(f"{method} {path}: {reason}") from None

    def login(self, username: str, password: str) -> None:
        response = self.request("POST", "/auth/login", {"username": username, "password": password})
        if isinstance(response, dict) and isinstance(response.get("access_token"), str):
            self.headers["Authorization"] = f"Bearer {response['access_token']}"

    def assert_not_found(self, path: str) -> None:
        try:
            self.request("GET", path)
        except AcceptanceError as exc:
            if "HTTP 404" in str(exc):
                return
            raise
        raise AcceptanceError(f"cleanup verification found a resource at {path}")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.getenv("ATP_ACCEPTANCE_BASE_URL") or os.getenv("ATP_BASE_URL"))
    parser.add_argument("--report", type=Path, default=_default_report_path())
    parser.add_argument("--allow-mutations", action="store_true", help="required before creating or deleting data")
    parser.add_argument("--execute", action="store_true", help="trigger the generated plan and poll its report")
    parser.add_argument("--require-role-matrix", action="store_true", help="fail if viewer credentials are absent")
    parser.add_argument("--target-url", default=os.getenv("ATP_ACCEPTANCE_TARGET_URL"))
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--run-timeout", type=float, default=90.0)
    parser.add_argument("--poll-interval", type=float, default=2.0)
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


def _first_module_id(payload: Any) -> int:
    if not isinstance(payload, list):
        raise AcceptanceError("project modules response was not a list")
    queue = list(payload)
    while queue:
        item = queue.pop(0)
        if isinstance(item, dict) and isinstance(item.get("id"), int):
            return item["id"]
        if isinstance(item, dict) and isinstance(item.get("children"), list):
            queue.extend(item["children"])
    raise AcceptanceError("temporary project did not contain a module")


def _case_payload(module_id: int, target_url: str) -> dict[str, Any]:
    return {
        "name": "N6 acceptance API case",
        "description": "Temporary case for project asset and role acceptance.",
        "summary": "Read-only project acceptance request",
        "case_type": "api",
        "module_id": module_id,
        "priority": "P2",
        "case_level": "smoke",
        "automation_status": "auto",
        "tags": ["n6-acceptance"],
        "steps": [{"step_no": 1, "action": "发送只读健康检查请求", "test_data": target_url}],
        "config": {"method": "GET", "url": target_url, "headers": {}},
    }


def _credentials(name: str) -> tuple[str | None, str | None]:
    return os.getenv(f"ATP_{name}_USERNAME"), os.getenv(f"ATP_{name}_PASSWORD")


def run_acceptance(args: argparse.Namespace) -> dict[str, Any]:
    recorder = CheckRecorder()
    report: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "N6 project asset and role matrix",
        "status": "failed",
        "endpoint": _safe_url(args.base_url or ""),
        "checks": recorder.checks,
        "resources": {},
    }
    project_id: int | None = None
    admin_client: ApiClient | None = None
    viewer_client: ApiClient | None = None
    viewer_id: int | None = None

    try:
        if not args.base_url:
            recorder.add("configuration", "failed", "--base-url or ATP_ACCEPTANCE_BASE_URL is required")
            return report
        if not args.allow_mutations:
            recorder.add(
                "mutation-safety", "failed", "pass --allow-mutations before creating or deleting acceptance data"
            )
            return report
        if args.execute and not args.target_url:
            recorder.add(
                "configuration", "failed", "--target-url or ATP_ACCEPTANCE_TARGET_URL is required with --execute"
            )
            return report
        target_url = _safe_target_url(args.target_url) if args.execute else "https://example.invalid/n6-unused"

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
        role = str(me.get("role")) if isinstance(me, dict) else ""
        if role not in {"admin", "engineer"}:
            raise AcceptanceError("authenticated account must be admin or engineer")
        recorder.add("authentication", "passed", f"authenticated as {role}; credentials were not recorded")

        project_name = f"ATP N6 acceptance {datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        project = admin_client.request(
            "POST",
            "/projects",
            {"name": project_name, "description": "temporary N6 acceptance project", "template": "blank"},
        )
        project_id = _resource_id(project)
        report["resources"]["project_id"] = project_id
        recorder.add("project-create", "passed", f"created temporary project id={project_id}")

        modules = admin_client.request("GET", f"/projects/{project_id}/modules")
        module_id = _first_module_id(modules)
        report["resources"]["module_id"] = module_id
        recorder.add("module-discovery", "passed", f"selected module id={module_id}")

        case = admin_client.request("POST", "/cases", _case_payload(module_id, target_url))
        case_id = _resource_id(case)
        report["resources"]["case_id"] = case_id
        recorder.add("case-create", "passed", f"created case id={case_id}")

        admin_client.request("POST", f"/cases/{case_id}/submit-review", {"comment": "N6 acceptance submit"})
        approved = admin_client.request("POST", f"/cases/{case_id}/approve", {"comment": "N6 acceptance approve"})
        if str(approved.get("review_status")) != "approved":
            raise AcceptanceError("case approval response was not approved")
        admin_client.request("GET", f"/case-reviews/{case_id}/history")
        recorder.add("case-review", "passed", "case submitted, approved and review history was readable")

        suite = admin_client.request(
            "POST",
            "/suites",
            {"name": "N6 acceptance suite", "project_id": project_id, "case_ids": [{"case_id": case_id, "sort": 0}]},
        )
        suite_id = _resource_id(suite)
        report["resources"]["suite_id"] = suite_id
        recorder.add("suite-create", "passed", f"created suite id={suite_id}")

        plan = admin_client.request(
            "POST",
            "/plans",
            {
                "name": "N6 acceptance plan",
                "project_id": project_id,
                "suite_ids": [{"suite_id": suite_id, "sort": 0}],
                "schedule_type": "manual",
                "is_enabled": True,
            },
        )
        plan_id = _resource_id(plan)
        report["resources"]["plan_id"] = plan_id
        recorder.add("plan-create", "passed", f"created plan id={plan_id}")

        if not args.execute:
            recorder.add(
                "execution-report", "skipped", "pass --execute to trigger a read-only run and verify the report"
            )
            recorder.add("defect-link", "skipped", "requires an execution record; no defect was created")
        else:
            plan_run = admin_client.request("POST", f"/plans/{plan_id}/run", {"extra_vars": {}})
            plan_run_id = _resource_id(plan_run)
            report["resources"]["plan_run_id"] = plan_run_id
            deadline = time.monotonic() + max(args.run_timeout, 1.0)
            latest = plan_run
            while time.monotonic() < deadline:
                latest = admin_client.request("GET", f"/plan-runs/{plan_run_id}")
                if str(latest.get("status")) in TERMINAL_RUN_STATUSES:
                    break
                time.sleep(max(args.poll_interval, 0.1))
            final_status = str(latest.get("status"))
            if final_status not in TERMINAL_RUN_STATUSES:
                raise AcceptanceError("plan run did not reach a terminal status before timeout")
            recorder.add(
                "execution-report", "passed", f"plan run id={plan_run_id} reached terminal status={final_status}"
            )

            defect = admin_client.request(
                "POST",
                "/defects",
                {
                    "project_id": project_id,
                    "case_id": case_id,
                    "title": "N6 acceptance linked defect",
                    "description": "Temporary defect link for N6 acceptance; removed with project.",
                    "run_links": [{"run_type": "plan", "run_id": plan_run_id}],
                },
            )
            defect_payload = defect.get("defect") if isinstance(defect, dict) else None
            defect_id = _resource_id(defect_payload)
            report["resources"]["defect_id"] = defect_id
            admin_client.request("GET", f"/defects/{defect_id}")
            recorder.add("defect-link", "passed", f"created defect id={defect_id} linked to plan run id={plan_run_id}")

        viewer_username, viewer_password = _credentials("VIEWER")
        if not viewer_username or not viewer_password:
            if args.require_role_matrix:
                recorder.add("role-matrix", "failed", "viewer credentials are required by --require-role-matrix")
            else:
                recorder.add(
                    "role-matrix",
                    "skipped",
                    "set ATP_VIEWER_USERNAME/ATP_VIEWER_PASSWORD to verify ordinary-role isolation",
                )
        else:
            viewer_client = ApiClient(args.base_url, timeout=args.timeout)
            viewer_client.login(viewer_username, viewer_password)
            viewer_me = viewer_client.request("GET", "/auth/me")
            if isinstance(viewer_me, dict) and viewer_me.get("role") == "admin":
                raise AcceptanceError("role-matrix account must not be a global admin")
            viewer_id = _resource_id(viewer_me)
            admin_client.request("POST", f"/projects/{project_id}/members", {"user_id": viewer_id, "role": "viewer"})
            viewer_client.request("GET", f"/projects/{project_id}")
            viewer_client.request("GET", f"/cases?project_id={project_id}")
            try:
                viewer_client.request("POST", "/cases", _case_payload(module_id, target_url))
            except AcceptanceError as exc:
                if "HTTP 403" not in str(exc):
                    raise
            else:
                raise AcceptanceError("viewer unexpectedly created a case")
            recorder.add(
                "role-matrix", "passed", "viewer could read the project but mutation was rejected with HTTP 403"
            )
    except (AcceptanceError, ValueError) as exc:
        recorder.add("acceptance-execution", "failed", str(exc))
    finally:
        if admin_client is not None and project_id is not None:
            try:
                if viewer_id is not None:
                    admin_client.request("DELETE", f"/projects/{project_id}/members/{viewer_id}")
                admin_client.request("DELETE", f"/projects/{project_id}")
                admin_client.assert_not_found(f"/projects/{project_id}")
                recorder.add("cleanup", "passed", f"temporary project id={project_id} deleted")
            except AcceptanceError as exc:
                recorder.add("cleanup", "failed", str(exc))
    _set_overall_status(report)
    return report


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    report = run_acceptance(args)
    _write_report(args.report, report)
    print(f"N6 project asset acceptance: {report['status']}; evidence={args.report}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
