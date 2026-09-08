#!/usr/bin/env python3
"""Verify the ATP workbench with admin, engineer, and viewer credentials.

Credentials are read from ``ATP_<ROLE>_TOKEN`` or the matching username and
password environment variables. Reports contain role names, counts, IDs, and
redacted paths only. The default flow is read-only; denial POST checks require
``--verify-denials`` and are expected to fail before command creation.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any


ROLES = ("admin", "engineer", "viewer")
TASK_TYPES = ("case", "suite", "plan", "android", "performance")
FAILURE_STATUSES = {"failed", "error", "stopped", "cancelled"}
SAFE_SCHEMES = {"http", "https"}


class AcceptanceError(RuntimeError):
    """A redacted acceptance failure."""


class ApiHttpError(AcceptanceError):
    def __init__(self, method: str, path: str, status: int):
        super().__init__(f"{method} {path} returned HTTP {status}")
        self.status = status


@dataclass
class Recorder:
    checks: list[dict[str, Any]] = field(default_factory=list)

    def add(self, name: str, status: str, details: str, **evidence: Any) -> None:
        item: dict[str, Any] = {"name": name, "status": status, "details": details[:500]}
        item.update(evidence)
        self.checks.append(item)


class ApiClient:
    def __init__(self, base_url: str, *, timeout: float = 20.0, token: str | None = None):
        parsed = urllib.parse.urlsplit(base_url.strip())
        try:
            parsed.port
        except ValueError:
            raise ValueError("base URL contains an invalid port") from None
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

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        if not path.startswith("/") or "#" in path:
            raise ValueError("acceptance paths must be absolute and fragment-free")
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            method=method,
            headers=self.headers,
        )
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                raw = response.read(2 * 1024 * 1024)
                return json.loads(raw.decode("utf-8")) if raw else {}
        except urllib.error.HTTPError as exc:
            exc.read()
            raise ApiHttpError(method, path, exc.code) from None
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, UnicodeDecodeError):
            raise AcceptanceError(f"{method} {path}: request failed") from None

    def login(self, username: str, password: str) -> None:
        response = self.request("POST", "/auth/login", {"username": username, "password": password})
        if isinstance(response, dict) and isinstance(response.get("access_token"), str):
            self.headers["Authorization"] = f"Bearer {response['access_token']}"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.getenv("ATP_ACCEPTANCE_BASE_URL") or os.getenv("ATP_BASE_URL"))
    parser.add_argument("--project-id", type=int, required=True)
    parser.add_argument("--foreign-project-id", type=int)
    parser.add_argument("--require-five-domains", action="store_true")
    parser.add_argument("--verify-denials", action="store_true")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--report", type=Path, default=Path("docs/evidence/b1-workbench-role-matrix.json"))
    return parser.parse_args(argv)


def _credentials(role: str) -> tuple[str | None, str | None, str | None]:
    prefix = f"ATP_{role.upper()}"
    return os.getenv(f"{prefix}_TOKEN"), os.getenv(f"{prefix}_USERNAME"), os.getenv(f"{prefix}_PASSWORD")


def _client_for_role(base_url: str, timeout: float, role: str) -> ApiClient:
    token, username, password = _credentials(role)
    if not token and (not username or not password):
        raise AcceptanceError(
            f"missing {role} credentials; set ATP_{role.upper()}_TOKEN or username/password environment variables"
        )
    client = ApiClient(base_url, timeout=timeout, token=token)
    if not token:
        client.login(username or "", password or "")
    return client


def _require_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AcceptanceError(f"{label} response was not an object")
    return value


def _task_page(
    client: ApiClient,
    project_id: int,
    task_type: str | None = None,
    *,
    limit: int = 200,
    offset: int = 0,
) -> dict[str, Any]:
    suffix = f"&task_type={task_type}" if task_type else ""
    page = _require_dict(
        client.request("GET", f"/workbench/tasks?project_id={project_id}&limit={limit}&offset={offset}{suffix}"),
        "workbench tasks",
    )
    if not isinstance(page.get("items"), list) or not isinstance(page.get("total"), int):
        raise AcceptanceError("workbench task page omitted items or total")
    return page


def _expect_status(client: ApiClient, method: str, path: str, expected: int, payload: dict | None = None) -> None:
    try:
        client.request(method, path, payload)
    except ApiHttpError as exc:
        if exc.status == expected:
            return
        raise AcceptanceError(f"{method} {path} returned HTTP {exc.status}, expected HTTP {expected}") from None
    raise AcceptanceError(f"{method} {path} unexpectedly succeeded; expected HTTP {expected}")


def _member_roles(admin: ApiClient, project_id: int) -> dict[int, str]:
    payload = admin.request("GET", f"/projects/{project_id}/members")
    if not isinstance(payload, list):
        raise AcceptanceError("project members response was not a list")
    return {
        item["user_id"]: item["role"]
        for item in payload
        if isinstance(item, dict) and isinstance(item.get("user_id"), int) and isinstance(item.get("role"), str)
    }


def run_acceptance(args: argparse.Namespace) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": _safe_url(args.base_url or ""),
        "project_id": args.project_id,
        "status": "failed",
        "checks": [],
    }
    recorder = Recorder(report["checks"])
    if not args.base_url:
        recorder.add("configuration", "failed", "--base-url or ATP_ACCEPTANCE_BASE_URL is required")
        return report

    try:
        clients = {role: _client_for_role(args.base_url, args.timeout, role) for role in ROLES}
        identities = {
            role: _require_dict(client.request("GET", "/auth/me"), f"{role} identity")
            for role, client in clients.items()
        }
        if identities["admin"].get("role") != "admin":
            raise AcceptanceError("admin credential is not a global admin")
        if identities["engineer"].get("role") != "engineer":
            raise AcceptanceError("engineer credential is not a global engineer")
        if identities["viewer"].get("role") not in {"tester", "viewer"}:
            raise AcceptanceError("viewer credential is not a global tester/viewer")
        identity_ids = {identity.get("id") for identity in identities.values()}
        if None in identity_ids or len(identity_ids) != len(ROLES):
            raise AcceptanceError("three distinct role accounts are required")
        recorder.add(
            "authentication", "passed", "three distinct global roles authenticated; credentials were not recorded"
        )

        member_roles = _member_roles(clients["admin"], args.project_id)
        engineer_id = identities["engineer"].get("id")
        viewer_id = identities["viewer"].get("id")
        if member_roles.get(engineer_id) not in {"owner", "editor"}:
            raise AcceptanceError("engineer is not an owner/editor of the selected project")
        if member_roles.get(viewer_id) != "viewer":
            raise AcceptanceError("viewer does not have the viewer role in the selected project")
        recorder.add(
            "project-membership", "passed", "engineer is writable and viewer is read-only in the selected project"
        )

        pages: dict[str, dict[str, Any]] = {}
        for role, client in clients.items():
            overview = _require_dict(
                client.request("GET", f"/workbench/overview?project_id={args.project_id}"),
                f"{role} overview",
            )
            if not isinstance(overview.get("counts"), dict):
                raise AcceptanceError(f"{role} overview omitted counts")
            pages[role] = _task_page(client, args.project_id)
        for role, page in pages.items():
            if any(item.get("project_id") != args.project_id for item in page["items"] if isinstance(item, dict)):
                raise AcceptanceError(f"{role} task page leaked another project")
        if any(
            item.get("can_retry") or item.get("can_stop") for item in pages["viewer"]["items"] if isinstance(item, dict)
        ):
            raise AcceptanceError("viewer received an actionable workbench task")
        recorder.add(
            "workbench-read",
            "passed",
            "all roles read project-scoped task pages; viewer action flags were disabled",
            returned={role: len(page["items"]) for role, page in pages.items()},
        )

        domain_counts: dict[str, int] = {}
        for task_type in TASK_TYPES:
            first_page = _task_page(clients["admin"], args.project_id, task_type, limit=1)
            if any(item.get("task_type") != task_type for item in first_page["items"] if isinstance(item, dict)):
                raise AcceptanceError(f"{task_type} filter returned another task domain")
            domain_counts[task_type] = first_page["total"]
            if first_page["total"] > 1:
                second_page = _task_page(clients["admin"], args.project_id, task_type, limit=1, offset=1)
                first_ids = {item.get("id") for item in first_page["items"] if isinstance(item, dict)}
                second_ids = {item.get("id") for item in second_page["items"] if isinstance(item, dict)}
                if not second_ids or first_ids & second_ids:
                    raise AcceptanceError(f"{task_type} pagination repeated or omitted the second item")
        missing_domains = [task_type for task_type, count in domain_counts.items() if count == 0]
        if missing_domains and args.require_five_domains:
            raise AcceptanceError(f"selected project has no runs for domains: {','.join(missing_domains)}")
        recorder.add(
            "five-domain-pagination",
            "partial" if missing_domains else "passed",
            "domain filters and bounded paging were valid"
            if not missing_domains
            else "some domains had no real run evidence",
            counts=domain_counts,
        )

        failed_item = next(
            (
                item
                for item in pages["admin"]["items"]
                if isinstance(item, dict) and item.get("status") in FAILURE_STATUSES
            ),
            None,
        )
        if failed_item:
            path = f"/workbench/tasks/{failed_item['task_type']}/{failed_item['run_id']}/failure-diagnosis"
            for client in clients.values():
                _require_dict(client.request("POST", path), "failure diagnosis")
            recorder.add("failure-diagnosis", "passed", "all roles read the same project-scoped failure diagnosis")
        else:
            recorder.add("failure-diagnosis", "partial", "selected project had no failed run to diagnose")

        if args.foreign_project_id:
            for role in ("engineer", "viewer"):
                _expect_status(
                    clients[role],
                    "GET",
                    f"/workbench/tasks?project_id={args.foreign_project_id}&limit=1",
                    403,
                )
            recorder.add("cross-project", "passed", "non-member engineer and viewer were denied with HTTP 403")
        else:
            recorder.add("cross-project", "partial", "--foreign-project-id was not supplied")

        actionable = next(
            (
                item
                for item in pages["admin"]["items"]
                if isinstance(item, dict) and (item.get("can_retry") or item.get("can_stop"))
            ),
            None,
        )
        if args.verify_denials and actionable:
            action = "retry" if actionable.get("can_retry") else "stop"
            _expect_status(
                clients["viewer"],
                "POST",
                f"/workbench/tasks/{actionable['task_type']}/{actionable['run_id']}/{action}",
                403,
            )
            recorder.add("viewer-write-denial", "passed", "viewer action was rejected before dispatch with HTTP 403")
        else:
            recorder.add(
                "viewer-write-denial",
                "partial",
                "enable --verify-denials and provide an actionable run to execute the denial probe",
            )
    except (AcceptanceError, ValueError) as exc:
        recorder.add("acceptance", "failed", str(exc))

    statuses = {item["status"] for item in report["checks"]}
    report["status"] = "failed" if "failed" in statuses else "partial" if "partial" in statuses else "passed"
    return report


def _safe_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value.strip())
    if parsed.scheme not in SAFE_SCHEMES or not parsed.hostname:
        return "<invalid-url>"
    host = parsed.hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    try:
        port = parsed.port
    except ValueError:
        return "<invalid-url>"
    netloc = f"{host}:{port}" if port is not None else host
    return urllib.parse.urlunsplit((parsed.scheme, netloc, parsed.path.rstrip("/") or "/", "", ""))


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    report = run_acceptance(args)
    _write_report(args.report, report)
    print(f"B1 workbench role matrix: {report['status']} ({len(report['checks'])} checks)")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
