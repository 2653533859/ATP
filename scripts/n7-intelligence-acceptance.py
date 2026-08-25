#!/usr/bin/env python3
"""Run the safe N7 intelligence-hub acceptance flow.

The command creates a temporary project, requirement, knowledge entry and case,
checks requirement parsing, Hermes retrieval and source navigation, then removes
the project in a finally block. AI draft generation and ordinary-role isolation
are explicit gates so a local run cannot silently claim a full environment
acceptance.
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


class AcceptanceError(RuntimeError):
    """An expected, redacted acceptance failure."""


@dataclass
class CheckRecorder:
    checks: list[dict[str, str]] = field(default_factory=list)

    def add(self, name: str, status: str, details: str) -> None:
        self.checks.append({"name": name, "status": status, "details": details[:500]})


def _safe_url(value: str) -> str:
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
    return urllib.parse.urlunsplit((parsed.scheme, netloc, parsed.path.rstrip("/") or "/", "", ""))


class ApiClient:
    """Small cookie-aware JSON client whose errors never echo response bodies."""

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
                return json.loads(raw.decode("utf-8")) if raw else {}
        except urllib.error.HTTPError as exc:
            exc.read()
            raise AcceptanceError(f"{method} {path} returned HTTP {exc.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, UnicodeDecodeError):
            raise AcceptanceError(f"{method} {path}: request failed") from None

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
    parser.add_argument("--report", type=Path, default=Path("docs/evidence/n7-intelligence-acceptance.json"))
    parser.add_argument("--allow-mutations", action="store_true", help="required before creating or deleting data")
    parser.add_argument("--require-ai", action="store_true", help="require a real model to return editable case drafts")
    parser.add_argument(
        "--llm-config-id",
        type=int,
        help="saved AI LLM configuration to exercise; defaults to ATP_LLM_CONFIG_ID",
    )
    parser.add_argument(
        "--require-vision",
        action="store_true",
        help="require the selected saved configuration to advertise vision support",
    )
    parser.add_argument(
        "--require-thinking",
        action="store_true",
        help="require the selected saved configuration to contain a supported thinking parameter",
    )
    parser.add_argument("--require-role-matrix", action="store_true", help="fail if viewer credentials are absent")
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args(argv)
    if (args.require_vision or args.require_thinking) and not args.require_ai:
        parser.error("--require-vision and --require-thinking require --require-ai")
    return args


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


def _resource_id(payload: Any, key: str = "id") -> int:
    if not isinstance(payload, dict) or not isinstance(payload.get(key), int) or payload[key] < 1:
        raise AcceptanceError(f"response did not contain a valid {key}")
    return payload[key]


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


def _thinking_parameter_keys(default_params: Any) -> list[str]:
    if not isinstance(default_params, dict):
        return []
    return [key for key in ("thinking", "enable_thinking", "reasoning_effort") if key in default_params]


def _llm_config_id(args: argparse.Namespace) -> int:
    value = args.llm_config_id
    if value is None:
        raw = os.getenv("ATP_LLM_CONFIG_ID") or os.getenv("ATP_AI_CONFIG_ID")
        try:
            value = int(raw or "")
        except ValueError:
            value = None
    if not isinstance(value, int) or value < 1:
        raise AcceptanceError("--require-ai needs --llm-config-id or ATP_LLM_CONFIG_ID")
    return value


def _load_and_check_ai_config(client: ApiClient, args: argparse.Namespace) -> dict[str, Any]:
    config_id = _llm_config_id(args)
    configs = client.request("GET", "/ai/llm-configs")
    if not isinstance(configs, list):
        raise AcceptanceError("AI configuration response was not a list")
    config = next((item for item in configs if isinstance(item, dict) and item.get("id") == config_id), None)
    if config is None:
        raise AcceptanceError(f"saved AI configuration id={config_id} was not found")
    if config.get("enabled") is not True:
        raise AcceptanceError("selected AI configuration is disabled")
    provider = str(config.get("provider") or "")
    model_name = str(config.get("model_name") or "").strip()
    if not provider or not model_name:
        raise AcceptanceError("selected AI configuration is missing provider or model")
    supports_vision = config.get("supports_vision") is True
    thinking_keys = _thinking_parameter_keys(config.get("default_params"))
    if args.require_vision and not supports_vision:
        raise AcceptanceError("selected AI configuration does not advertise vision support")
    if args.require_thinking and not thinking_keys:
        raise AcceptanceError("selected AI configuration has no thinking parameter")

    models = client.request("POST", "/ai/llm-configs/models", {"config_id": config_id, "provider": provider})
    model_options = models.get("models") if isinstance(models, dict) else None
    if not isinstance(model_options, list) or not model_options:
        raise AcceptanceError("AI model discovery returned no models")
    discovered = next(
        (item for item in model_options if isinstance(item, dict) and item.get("id") == model_name),
        None,
    )
    if discovered is None:
        raise AcceptanceError("saved AI model was not present in the discovered model list")
    if args.require_vision and discovered.get("supports_vision") is not True:
        raise AcceptanceError("discovered AI model did not explicitly declare vision support")
    if args.require_thinking and discovered.get("supports_reasoning") is not True:
        raise AcceptanceError("discovered AI model did not explicitly declare reasoning support")

    connection = client.request("POST", "/ai/llm-configs/test-connection", {"config_id": config_id})
    if not isinstance(connection, dict) or connection.get("response_received") is not True:
        raise AcceptanceError("AI connection test did not confirm a response")
    if connection.get("model_name") != model_name:
        raise AcceptanceError("AI connection test used an unexpected model")
    return {
        "id": config_id,
        "provider": provider,
        "model_name": model_name,
        "supports_vision": supports_vision,
        "thinking_parameter_keys": thinking_keys,
        "discovered_model_count": len(model_options),
    }


def _ensure_module(client: ApiClient, project_id: int) -> tuple[int, bool]:
    modules = client.request("GET", f"/projects/{project_id}/modules")
    if isinstance(modules, list) and not modules:
        created = client.request(
            "POST",
            "/modules",
            {"project_id": project_id, "name": "N7 acceptance module", "module_code": "N7_ACCEPTANCE"},
        )
        return _resource_id(created), True
    return _first_module_id(modules), False


def _credentials(name: str) -> tuple[str | None, str | None]:
    return os.getenv(f"ATP_{name}_USERNAME"), os.getenv(f"ATP_{name}_PASSWORD")


def _case_payload(module_id: int, marker: str) -> dict[str, Any]:
    return {
        "name": f"N7 acceptance case {marker}",
        "description": "Temporary case for Hermes source retrieval.",
        "summary": f"验证 {marker} 登录主流程",
        "case_type": "api",
        "module_id": module_id,
        "priority": "P2",
        "case_level": "smoke",
        "automation_status": "auto",
        "tags": ["n7-acceptance", marker],
        "steps": [{"step_no": 1, "action": "读取临时检索数据", "test_data": marker}],
        "config": {},
    }


def _assert_source_types(payload: Any, marker: str, project_id: int) -> None:
    if not isinstance(payload, dict) or payload.get("mode") != "project_retrieval":
        raise AcceptanceError("Hermes did not return a project retrieval result")
    sources = payload.get("sources")
    if not isinstance(sources, list):
        raise AcceptanceError("Hermes response did not contain sources")
    expected_types = {"knowledge", "requirement", "case"}
    source_types = {item.get("source_type") for item in sources if isinstance(item, dict)}
    if not expected_types.issubset(source_types):
        raise AcceptanceError("Hermes source result did not include requirement, knowledge and case")
    matched_types: set[str] = set()
    expected_paths = {
        "knowledge": "/knowledge",
        "requirement": "/requirements",
        "case": "/cases",
    }
    for item in sources:
        if not isinstance(item, dict):
            continue
        searchable = str(item.get("excerpt", "")) + str(item.get("title", ""))
        source_type = item.get("source_type")
        if source_type not in expected_types or marker not in searchable:
            continue
        path = item.get("path")
        if not isinstance(path, str) or not path.startswith(f"{expected_paths[source_type]}?"):
            raise AcceptanceError("Hermes source did not contain a project-scoped navigation path")
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(path).query)
        if query.get("project_id") != [str(project_id)]:
            raise AcceptanceError("Hermes source navigation path escaped the temporary project")
        if not item.get("source_ref"):
            raise AcceptanceError("Hermes source did not contain a traceable source reference")
        matched_types.add(source_type)
    if matched_types != expected_types:
        raise AcceptanceError("Hermes did not return marker-bearing sources for all three source types")


def run_acceptance(args: argparse.Namespace) -> dict[str, Any]:
    recorder = CheckRecorder()
    report: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "N5/N7 AI model, Hermes, requirement and knowledge retrieval",
        "status": "failed",
        "endpoint": _safe_url(args.base_url or ""),
        "checks": recorder.checks,
        "resources": {},
    }
    project_id: int | None = None
    admin_client: ApiClient | None = None
    viewer_id: int | None = None
    ai_config: dict[str, Any] | None = None

    try:
        if not args.base_url:
            recorder.add("configuration", "failed", "--base-url or ATP_ACCEPTANCE_BASE_URL is required")
            return report
        if not args.allow_mutations:
            recorder.add(
                "mutation-safety", "failed", "pass --allow-mutations before creating or deleting acceptance data"
            )
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
        role = str(me.get("role")) if isinstance(me, dict) else ""
        if role not in {"admin", "engineer"}:
            raise AcceptanceError("authenticated account must be admin or engineer")
        if args.require_ai and role != "admin":
            raise AcceptanceError("--require-ai needs a global admin account for saved-model checks")
        recorder.add("authentication", "passed", f"authenticated as {role}; credentials were not recorded")

        if args.require_ai:
            assert admin_client is not None
            ai_config = _load_and_check_ai_config(admin_client, args)
            recorder.add(
                "ai-model-preflight",
                "passed",
                "saved AI configuration, model discovery and connection passed "
                f"(config_id={ai_config['id']}, provider={ai_config['provider']}, "
                f"model={ai_config['model_name']}, discovered={ai_config['discovered_model_count']}, "
                f"vision={ai_config['supports_vision']}, "
                f"thinking_keys={','.join(ai_config['thinking_parameter_keys']) or 'none'})",
            )

        marker = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        project = admin_client.request(
            "POST",
            "/projects",
            {
                "name": f"ATP N7 acceptance {marker}",
                "description": "temporary N7 intelligence project",
                "ai_llm_config_id": ai_config["id"] if ai_config else None,
                "template": "blank",
            },
        )
        project_id = _resource_id(project)
        report["resources"]["project_id"] = project_id
        recorder.add("project-create", "passed", f"created temporary project id={project_id}")

        module_id, module_created = _ensure_module(admin_client, project_id)
        report["resources"]["module_id"] = module_id
        if module_created:
            recorder.add("module-create", "passed", f"created temporary module id={module_id}")
        requirement = admin_client.request(
            "POST",
            "/requirements",
            {
                "project_id": project_id,
                "title": f"{marker} 登录需求",
                "description": f"用户使用邮箱完成 {marker} 登录",
                "status": "draft",
                "priority": "P1",
                "source": "n7-acceptance",
                "acceptance_criteria": [{"id": "AC-1", "text": f"{marker} 登录成功进入首页"}],
            },
        )
        requirement_id = _resource_id(requirement)
        report["resources"]["requirement_id"] = requirement_id
        knowledge = admin_client.request(
            "POST",
            "/knowledge",
            {
                "project_id": project_id,
                "source_type": "runbook",
                "title": f"{marker} 登录排查手册",
                "summary": "临时来源，仅用于 N7 验收",
                "content": f"{marker} 先检查认证服务，再检查 Redis；不要记录任何真实密钥。",
                "source_ref": f"N7-SOP-{marker}",
                "tags": ["n7-acceptance", marker],
                "status": "published",
            },
        )
        knowledge_id = _resource_id(knowledge, "document_id")
        report["resources"]["knowledge_id"] = knowledge_id
        case = admin_client.request("POST", "/cases", _case_payload(module_id, marker))
        case_id = _resource_id(case)
        report["resources"]["case_id"] = case_id
        recorder.add("temporary-data-create", "passed", "created one requirement, knowledge entry and case")

        parsed = admin_client.request(
            "POST",
            "/requirements/parse",
            {"project_id": project_id, "text": f"{marker} 登录\n- {marker} 登录成功进入首页"},
        )
        if not isinstance(parsed, dict) or not parsed.get("acceptance_criteria"):
            raise AcceptanceError("requirement parser did not return an editable acceptance draft")
        requirement_detail = admin_client.request("GET", f"/requirements/{requirement_id}")
        if _resource_id(requirement_detail) != requirement_id:
            raise AcceptanceError("temporary requirement detail was not retrievable")
        listed_requirement = admin_client.request("GET", f"/requirements?project_id={project_id}&keyword={marker}")
        if not isinstance(listed_requirement, dict) or not listed_requirement.get("items"):
            raise AcceptanceError("temporary requirement was not retrievable by project and keyword")
        knowledge_detail = admin_client.request("GET", f"/knowledge/{knowledge_id}")
        if _resource_id(knowledge_detail, "document_id") != knowledge_id:
            raise AcceptanceError("temporary knowledge detail was not retrievable")
        listed_knowledge = admin_client.request("GET", f"/knowledge?project_id={project_id}&keyword={marker}")
        if not isinstance(listed_knowledge, dict) or not listed_knowledge.get("items"):
            raise AcceptanceError("temporary knowledge was not retrievable by project and keyword")
        case_detail = admin_client.request("GET", f"/cases/{case_id}")
        if _resource_id(case_detail) != case_id:
            raise AcceptanceError("temporary case detail was not retrievable")
        recorder.add(
            "editable-retrieval",
            "passed",
            "requirement parsing and project-scoped requirement/knowledge/case detail retrieval passed",
        )

        hermes_result = admin_client.request(
            "POST",
            "/hermes/query",
            {"project_id": project_id, "query": marker, "limit": 8},
        )
        _assert_source_types(hermes_result, marker, project_id)
        recorder.add(
            "hermes-sources", "passed", "Hermes returned project-scoped requirement, knowledge and case citations"
        )

        if args.require_ai:
            generated = admin_client.request(
                "POST",
                "/ai/cases/generate",
                {
                    "project_id": project_id,
                    "module_id": module_id,
                    "user_requirement": f"根据 {marker} 需求生成可编辑的登录用例草稿",
                    "case_type": "api",
                    "priority": "P2",
                    "case_level": "regression",
                    "max_cases": 3,
                },
            )
            if not isinstance(generated, dict) or not isinstance(generated.get("drafts"), list):
                raise AcceptanceError("AI generation did not return editable drafts")
            recorder.add("ai-draft", "passed", f"real model returned {len(generated['drafts'])} editable case drafts")
        else:
            recorder.add(
                "ai-draft", "skipped", "pass --require-ai to verify a controlled real model and editable case drafts"
            )

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
            viewer_result = viewer_client.request(
                "POST",
                "/hermes/query",
                {"project_id": project_id, "query": marker, "limit": 8},
            )
            _assert_source_types(viewer_result, marker, project_id)
            try:
                viewer_client.request(
                    "POST",
                    "/requirements",
                    {"project_id": project_id, "title": f"{marker} viewer mutation", "status": "draft"},
                )
            except AcceptanceError as exc:
                if "HTTP 403" not in str(exc):
                    raise
            else:
                raise AcceptanceError("viewer unexpectedly created a requirement")
            recorder.add(
                "role-matrix",
                "passed",
                "viewer could query project sources but requirement mutation was rejected with HTTP 403",
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
    print(f"N7 intelligence acceptance: {report['status']}; evidence={args.report}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
