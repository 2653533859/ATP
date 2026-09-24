#!/usr/bin/env python3
"""Prepare the fixed Hermes evaluation assets through APIs in a fresh database.

This script creates only new resources. It never updates or deletes existing
business assets, and it stops immediately when an expected first ID is not 1.
It does not submit the ten evaluation questions or call the answer model.
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
from datetime import datetime, timezone
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any
from uuid import uuid4


EVALUATION_SET_ID = "hermes-core-v2"
EVALUATION_SET_VERSION = "2026-09-23.1"
MODEL_PROVIDERS = {"deepseek", "claude", "openai", "openai_compatible", "qwen", "ollama"}
TERMINAL_RUN_STATUSES = {"passed", "failed", "error", "skipped", "cancelled"}


class SeedError(RuntimeError):
    """An error with no credentials or response body in its message."""


def _safe_url(value: str, *, api_base: bool = False, health_probe: bool = False) -> str:
    try:
        parsed = urllib.parse.urlsplit(value.strip())
    except ValueError:
        raise SeedError("URL has an invalid format") from None
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise SeedError("URL must be http(s) without credentials, query or fragment")
    try:
        port = parsed.port
    except ValueError:
        raise SeedError("URL has an invalid port") from None
    path = parsed.path.rstrip("/")
    if api_base and not path.endswith("/api/v1"):
        raise SeedError("API base URL must end in /api/v1")
    if health_probe and path != "/health":
        raise SeedError("probe URL must target the isolated Backend /health endpoint")
    host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    return f"{parsed.scheme}://{host}{f':{port}' if port is not None else ''}{path}"


def _secret(name: str) -> str | None:
    direct = os.getenv(name)
    filename = os.getenv(f"{name}_FILE")
    if direct and filename:
        raise SeedError(f"set only one of {name} and {name}_FILE")
    if filename:
        try:
            direct = Path(filename).read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError):
            raise SeedError(f"could not read {name}_FILE") from None
    return direct or None


class ApiClient:
    """Small JSON client that never includes response bodies in errors."""

    def __init__(self, base_url: str, *, timeout: float, token: str | None):
        self.base_url = _safe_url(base_url, api_base=True)
        self.timeout = timeout
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        if not path.startswith("/") or "#" in path:
            raise SeedError("invalid API path")
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        try:
            request = urllib.request.Request(self.base_url + path, data=data, method=method, headers=self.headers)
            with self.opener.open(request, timeout=self.timeout) as response:
                raw = response.read(2 * 1024 * 1024)
                return json.loads(raw.decode("utf-8")) if raw else {}
        except urllib.error.HTTPError as exc:
            exc.read()
            raise SeedError(f"{method} {path} returned HTTP {exc.code}") from None
        except (urllib.error.URLError, OSError, TimeoutError, ValueError, UnicodeError):
            raise SeedError(f"{method} {path} request failed") from None

    def login(self, username: str, password: str) -> None:
        response = self.request("POST", "/auth/login", {"username": username, "password": password})
        if not isinstance(response, dict) or not isinstance(response.get("access_token"), str):
            raise SeedError("login response did not contain an access token")
        self.headers["Authorization"] = f"Bearer {response['access_token']}"


def _id(payload: Any, field: str = "id", *, expected: int | None = None) -> int:
    value = payload.get(field) if isinstance(payload, dict) else None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise SeedError(f"response did not contain a valid {field}")
    if expected is not None and value != expected:
        raise SeedError(f"first {field} must equal {expected}; found {value}; stop without changing existing data")
    return value


def _empty_total(payload: Any, label: str) -> None:
    if not isinstance(payload, dict) or type(payload.get("total")) is not int:
        raise SeedError(f"{label} list response has an invalid shape")
    if payload["total"] != 0:
        raise SeedError(f"{label} already exist; use a new isolated database")


def _preflight(client: ApiClient) -> None:
    me = client.request("GET", "/auth/me")
    if not isinstance(me, dict) or me.get("role") != "admin":
        raise SeedError("fixture creation requires an admin account")
    evaluation_set = client.request("GET", "/hermes/governance/evaluation-set")
    if (
        not isinstance(evaluation_set, dict)
        or evaluation_set.get("id") != EVALUATION_SET_ID
        or evaluation_set.get("version") != EVALUATION_SET_VERSION
        or not isinstance(evaluation_set.get("questions"), list)
        or len(evaluation_set["questions"]) != 10
    ):
        raise SeedError("Backend Hermes evaluation set does not match the required version")
    projects = client.request("GET", "/projects")
    if not isinstance(projects, list):
        raise SeedError("project list response has an invalid shape")
    if projects:
        raise SeedError("projects already exist; use a new isolated database")
    _empty_total(client.request("GET", "/requirements?page_size=1"), "requirements")
    _empty_total(client.request("GET", "/knowledge?page_size=1"), "knowledge entries")
    _empty_total(client.request("GET", "/runs?page_size=1"), "case runs")


def _model_config(client: ApiClient, args: argparse.Namespace) -> int:
    configs = client.request("GET", "/ai/llm-configs")
    if not isinstance(configs, list):
        raise SeedError("model configuration list response has an invalid shape")
    if args.llm_config_id is not None:
        config = next(
            (item for item in configs if isinstance(item, dict) and item.get("id") == args.llm_config_id), None
        )
        if config is None or config.get("enabled") is not True:
            raise SeedError("selected model configuration does not exist or is disabled")
        return args.llm_config_id
    if configs:
        raise SeedError("model configurations already exist; select one by ID instead of creating another")
    provider = (os.getenv("ATP_HERMES_MODEL_PROVIDER") or "").strip()
    model_name = (os.getenv("ATP_HERMES_MODEL_NAME") or "").strip()
    endpoint = (os.getenv("ATP_HERMES_MODEL_ENDPOINT") or "").strip() or None
    api_key = _secret("ATP_HERMES_MODEL_API_KEY")
    if provider not in MODEL_PROVIDERS or not model_name:
        raise SeedError("set ATP_HERMES_MODEL_PROVIDER and ATP_HERMES_MODEL_NAME")
    if provider != "ollama" and not api_key:
        raise SeedError("set ATP_HERMES_MODEL_API_KEY or ATP_HERMES_MODEL_API_KEY_FILE")
    if provider == "openai_compatible" and not endpoint:
        raise SeedError("openai_compatible requires ATP_HERMES_MODEL_ENDPOINT")
    if endpoint is not None:
        endpoint = _safe_url(endpoint)
    created = client.request(
        "POST",
        "/ai/llm-configs",
        {
            "name": f"Hermes isolated evaluation {uuid4().hex[:8]}",
            "provider": provider,
            "api_key": api_key or "",
            "endpoint": endpoint,
            "model_name": model_name,
            "enabled": True,
        },
    )
    return _id(created)


def _failed_probe_run(run: Any, case_id: int) -> bool:
    if not isinstance(run, dict) or run.get("status") != "failed" or run.get("case_id") != case_id:
        return False
    steps = run.get("steps")
    if not isinstance(steps, list):
        return False
    for step in steps:
        if not isinstance(step, dict) or step.get("status") != "failed":
            continue
        response_data = step.get("response_data")
        if not isinstance(response_data, dict) or response_data.get("status_code") != 200:
            continue
        assertions = response_data.get("assertions")
        if isinstance(assertions, list) and any(
            isinstance(item, dict)
            and item.get("target") == "status_code"
            and item.get("expected") == 999
            and item.get("passed") is False
            for item in assertions
        ):
            return True
    return False


def _verify_tools(client: ApiClient, project_id: int) -> dict[str, str]:
    arguments = {
        "failed_tasks": {"task_type": "case", "limit": 1},
        "run_detail": {"task_type": "case", "run_id": 1},
        "quality_trend": {"days": 30, "aggregate": "daily"},
        "requirement_case_links": {"requirement_id": 1},
        "knowledge_detail": {"knowledge_id": 1},
    }
    statuses: dict[str, str] = {}
    for tool, tool_arguments in arguments.items():
        response = client.request(
            "POST",
            "/hermes/tools/execute",
            {
                "project_id": project_id,
                "conversation_id": f"hermes-seed-{uuid4().hex}",
                "tool": tool,
                "arguments": tool_arguments,
                "timeout_ms": 5_000,
            },
        )
        if not isinstance(response, dict) or response.get("tool") != tool:
            raise SeedError(f"{tool} returned an invalid response")
        status = response.get("status")
        evidence = response.get("evidence")
        if status != "ok" or not isinstance(evidence, list) or not evidence:
            raise SeedError(f"{tool} did not return ok with evidence")
        statuses[tool] = status
    return statuses


def run(client: ApiClient, args: argparse.Namespace, report: dict[str, Any]) -> None:
    report["stage"] = "preflight"
    _preflight(client)
    report["stage"] = "model_config"
    model_config_id = _model_config(client, args)
    report["resources"]["model_config_id"] = model_config_id
    report["stage"] = "project"
    project = client.request(
        "POST",
        "/projects",
        {
            "name": f"Hermes isolated evaluation {uuid4().hex[:8]}",
            "description": "Fixed Hermes evaluation assets in an isolated database",
            "template": "blank",
            "ai_llm_config_id": model_config_id,
        },
    )
    project_id = _id(project)
    if project.get("ai_llm_config_id") != model_config_id:
        raise SeedError("new project did not bind the selected model configuration")
    report["resources"]["project_id"] = project_id
    report["stage"] = "module"
    module = client.request(
        "POST",
        "/modules",
        {"project_id": project_id, "name": "Hermes evaluation module", "module_code": "HERMES_EVAL"},
    )
    module_id = _id(module)
    report["resources"]["module_id"] = module_id
    report["stage"] = "requirement_1"
    requirement = client.request(
        "POST",
        "/requirements",
        {
            "project_id": project_id,
            "title": "用户登录验收需求",
            "description": "用户使用测试账号登录后进入首页。",
            "status": "active",
            "priority": "P1",
            "source": "hermes-evaluation",
            "acceptance_criteria": [{"id": "AC-1", "text": "登录成功后进入首页"}],
        },
    )
    requirement_id = _id(requirement, expected=1)
    report["resources"]["requirement_id"] = requirement_id
    report["stage"] = "knowledge_1"
    knowledge = client.request(
        "POST",
        "/knowledge",
        {
            "project_id": project_id,
            "source_type": "runbook",
            "title": "隔离验收知识条目",
            "summary": "用于验证知识详情读取。",
            "content": "此条目只用于验证 Hermes 知识详情只读工具。",
            "source_ref": "HERMES-EVAL-KNOWLEDGE-1",
            "status": "published",
        },
    )
    knowledge_id = _id(knowledge, "document_id", expected=1)
    report["resources"]["knowledge_id"] = knowledge_id
    report["stage"] = "case"
    case = client.request(
        "POST",
        "/cases",
        {
            "name": "隔离验收 API 用例",
            "description": "通过只读健康检查生成可核查的失败运行。",
            "summary": "隔离环境运行状态夹具",
            "case_type": "api",
            "module_id": module_id,
            "automation_status": "auto",
            "steps": [{"step_no": 1, "action": "读取隔离 Backend 健康状态"}],
            "config": {
                "method": "GET",
                "url": args.probe_url,
                "headers": {},
                "timeout": 5,
                "assertions": [{"target": "status_code", "operator": "eq", "expected": 999}],
            },
        },
    )
    case_id = _id(case)
    report["resources"]["case_id"] = case_id
    report["stage"] = "case_approval"
    client.request("POST", f"/cases/{case_id}/submit-review", {"comment": "Hermes isolated evaluation"})
    approved = client.request("POST", f"/cases/{case_id}/approve", {"comment": "Hermes isolated evaluation"})
    if not isinstance(approved, dict) or approved.get("review_status") != "approved":
        raise SeedError("new case was not approved")
    report["stage"] = "requirement_case_link"
    link = client.request(
        "POST",
        "/requirements/1/case-links",
        {"case_id": case_id, "relation_type": "covers", "criterion_ids": ["AC-1"]},
    )
    report["resources"]["requirement_case_link_id"] = _id(link)
    report["stage"] = "run_1"
    triggered = client.request("POST", f"/cases/{case_id}/run", {"extra_vars": {}})
    run_id = _id(triggered, expected=1)
    report["resources"]["run_id"] = run_id
    deadline = time.monotonic() + args.run_timeout
    latest = triggered
    while time.monotonic() < deadline:
        latest = client.request("GET", "/runs/1")
        if isinstance(latest, dict) and latest.get("status") in TERMINAL_RUN_STATUSES:
            break
        time.sleep(args.poll_interval)
    if not _failed_probe_run(latest, case_id):
        raise SeedError("run 1 did not finish with a failed assertion against HTTP 200 /health")
    report["run_status"] = "failed"
    report["stage"] = "tool_evidence"
    report["tools"] = _verify_tools(client, project_id)
    report["stage"] = "complete"
    report["status"] = "passed"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="isolated Backend URL including /api/v1")
    parser.add_argument("--probe-url", required=True, help="Worker-reachable isolated Backend /health URL")
    parser.add_argument("--report", type=Path, default=Path(".local-run/hermes-evaluation-seed.json"))
    parser.add_argument("--allow-mutations", action="store_true", help="create new evaluation resources")
    parser.add_argument(
        "--confirm-isolated-db", action="store_true", help="confirm the API uses a fresh dedicated database"
    )
    model = parser.add_mutually_exclusive_group(required=True)
    model.add_argument(
        "--llm-config-id", type=int, help="reuse an enabled model configuration in the isolated database"
    )
    model.add_argument(
        "--create-model-config", action="store_true", help="create a model configuration from environment"
    )
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument("--run-timeout", type=float, default=120)
    parser.add_argument("--poll-interval", type=float, default=2)
    args = parser.parse_args(argv)
    if args.llm_config_id is not None and args.llm_config_id < 1:
        parser.error("--llm-config-id must be positive")
    if args.timeout <= 0 or args.run_timeout <= 0 or args.poll_interval <= 0:
        parser.error("timeouts and poll interval must be positive")

    report: dict[str, Any] = {
        "evidence_type": "hermes_evaluation_fixture_seed",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "evaluation_set": {"id": EVALUATION_SET_ID, "version": EVALUATION_SET_VERSION},
        "status": "failed",
        "stage": "configuration",
        "resources": {},
        "tools": {},
    }
    try:
        if not args.allow_mutations or not args.confirm_isolated_db:
            raise SeedError("both --allow-mutations and --confirm-isolated-db are required")
        args.probe_url = _safe_url(args.probe_url, health_probe=True)
        token = _secret("ATP_TOKEN")
        client = ApiClient(args.base_url, timeout=args.timeout, token=token)
        if not token:
            username = (os.getenv("ATP_USERNAME") or "").strip()
            password = _secret("ATP_PASSWORD")
            if not username or not password:
                raise SeedError("set ATP_TOKEN or ATP_USERNAME with ATP_PASSWORD / ATP_PASSWORD_FILE")
            client.login(username, password)
        run(client, args, report)
    except SeedError as exc:
        report["reason"] = str(exc)
    try:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError:
        print("Hermes evaluation seed: could not write report", file=sys.stderr)
        return 2
    print(f"Hermes evaluation seed: {report['status']}")
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    sys.exit(main())
