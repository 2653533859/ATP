"""Bidirectional specification synchronization and test asset alignment service.

Compares OpenAPI/Swagger definitions with existing test cases to:
1. Detect new endpoints in spec (missing test cases) and generate TestCaseCreate draft patches.
2. Detect modified endpoints (parameter changes, schema shifts) and generate update patches.
3. Detect deprecated/removed endpoints in spec for review.
"""

from __future__ import annotations

import re
import hashlib
import json
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import CaseType, TestCase
from app.models.project import Module

HTTP_METHODS = {"get", "post", "put", "delete", "patch", "options", "head"}


def normalize_endpoint_path(path: str) -> str:
    """Normalize URL path by stripping queries, duplicate slashes, and trailing slashes."""
    if not path:
        return "/"
    raw = path.strip()
    parsed = urlparse(raw)
    p = parsed.path if parsed.scheme in {"http", "https"} and parsed.netloc else raw
    p = p.split("?", 1)[0].split("#", 1)[0]
    if not p.startswith("/"):
        p = "/" + p
    p = re.sub(r"/+", "/", p)
    if len(p) > 1 and p.endswith("/"):
        p = p[:-1]
    return p


def extract_spec_endpoints(spec: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    """Extract (METHOD, PATH) mapping from an OpenAPI / Swagger document."""
    paths_dict = spec.get("paths", {})
    if not isinstance(paths_dict, dict):
        return {}

    extracted: dict[tuple[str, str], dict[str, Any]] = {}
    for raw_path, path_item in paths_dict.items():
        if not isinstance(path_item, dict):
            continue
        norm_path = normalize_endpoint_path(str(raw_path))

        common_params = path_item.get("parameters", [])
        if not isinstance(common_params, list):
            common_params = []

        for method_name, op in path_item.items():
            if str(method_name).lower() not in HTTP_METHODS or not isinstance(op, dict):
                continue
            m = str(method_name).upper()

            op_params = op.get("parameters", [])
            all_params = [*common_params, *(op_params if isinstance(op_params, list) else [])]

            extracted[(m, norm_path)] = {
                "method": m,
                "path": norm_path,
                "raw_path": str(raw_path),
                "summary": str(op.get("summary") or op.get("operationId") or f"{m} {norm_path}"),
                "description": str(op.get("description") or ""),
                "parameters": all_params,
                "requestBody": op.get("requestBody") or {},
                "responses": op.get("responses") or {},
            }

    return extracted


def extract_case_endpoint(case: TestCase) -> tuple[str, str] | None:
    """Extract (METHOD, PATH) from a TestCase's config or first step."""
    cfg = getattr(case, "config", None) or {}
    method = str(cfg.get("method", "")).upper()
    url = str(cfg.get("url", "")).strip()

    if not method or not url:
        steps = cfg.get("steps")
        if isinstance(steps, list) and steps:
            first_step = steps[0]
            if isinstance(first_step, dict):
                method = str(first_step.get("method", "")).upper()
                url = str(first_step.get("url", "")).strip()

    if method and url:
        return method, normalize_endpoint_path(url)
    return None


def scenario_request_fingerprint(step: dict[str, Any]) -> str:
    """Fingerprint request fields only; avoid storing another copy of headers or body."""
    request = {
        "method": str(step.get("method") or "GET").upper(),
        "url": str(step.get("url") or ""),
        "headers": step.get("headers") or {},
        "params": step.get("params") or {},
        "cookies": step.get("cookies") or {},
        "body_type": step.get("body_type") or "none",
        "body": step.get("body") if step.get("body") is not None else "",
    }
    payload = json.dumps(request, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def case_request_fingerprint(case: TestCase) -> str:
    cfg = case.config or {}
    steps = cfg.get("steps")
    first = steps[0] if isinstance(steps, list) and steps and isinstance(steps[0], dict) else {}
    request = {key: first.get(key) or cfg.get(key) for key in ("method", "url", "body_type")}
    for key in ("headers", "params", "cookies"):
        request[key] = first[key] if isinstance(first.get(key), dict) else cfg.get(key)
    request["url"] = first.get("url") or cfg.get("url") or first.get("endpoint") or cfg.get("endpoint")
    request["body"] = first.get("body") if first.get("body") is not None else cfg.get("body")
    return scenario_request_fingerprint(request)


def generate_addition_patch(endpoint_meta: dict[str, Any], default_module_id: int) -> dict[str, Any]:
    """Build a draft TestCaseCreate payload for an unmapped spec endpoint."""
    method = endpoint_meta["method"]
    path = endpoint_meta["path"]
    summary = endpoint_meta["summary"]

    params_dict: dict[str, str] = {}
    headers_dict: dict[str, str] = {"Content-Type": "application/json"}

    for p in endpoint_meta.get("parameters", []):
        if not isinstance(p, dict):
            continue
        p_name = p.get("name")
        p_in = p.get("in")
        if not p_name:
            continue
        if p_in == "query":
            params_dict[str(p_name)] = "{{var}}" if p.get("required") else ""
        elif p_in == "header":
            headers_dict[str(p_name)] = ""

    config = {
        "method": method,
        "url": path,
        "params": params_dict,
        "headers": headers_dict,
        "assertions": [
            {
                "type": "status_code",
                "comparator": "eq",
                "expected": 200,
            }
        ],
    }

    return {
        "name": f"API - {summary}",
        "summary": summary,
        "case_type": "api",
        "module_id": default_module_id,
        "priority": "P2",
        "automation_status": "auto",
        "config": config,
    }


def compare_case_with_spec_endpoint(case: TestCase, endpoint_meta: dict[str, Any]) -> list[str]:
    """Identify modifications between existing case config and updated spec."""
    diffs: list[str] = []
    cfg = getattr(case, "config", None) or {}
    case_params = cfg.get("params") or {}
    if not isinstance(case_params, dict):
        case_params = {}

    for p in endpoint_meta.get("parameters", []):
        if not isinstance(p, dict):
            continue
        p_name = str(p.get("name") or "")
        p_in = p.get("in")
        is_required = bool(p.get("required"))

        if p_in == "query" and is_required and p_name not in case_params:
            diffs.append(f"新增必填 Query 参数: '{p_name}'")
        elif p_in == "header" and is_required and p_name not in (cfg.get("headers") or {}):
            diffs.append(f"新增必填 Header 参数: '{p_name}'")

    return diffs


async def sync_spec_with_cases(
    db: AsyncSession,
    project_id: int,
    spec: dict[str, Any],
    default_module_id: int | None = None,
    *,
    scenarios: list[dict[str, Any]] | None = None,
    baseline: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Analyze spec endpoints vs existing test cases and produce synchronization diffs."""
    spec_endpoints = extract_spec_endpoints(spec)

    modules_res = await db.execute(select(Module).where(Module.project_id == project_id))
    modules = modules_res.scalars().all()
    module_ids = [m.id for m in modules]

    if not default_module_id:
        default_module_id = module_ids[0] if module_ids else 1

    cases_res = await db.execute(
        select(TestCase).where(TestCase.module_id.in_(module_ids), TestCase.case_type == CaseType.api)
    )
    cases = cases_res.scalars().all()

    # Map existing cases by (method, path)
    case_by_endpoint: dict[tuple[str, str], list[TestCase]] = {}
    case_by_id = {case.id: case for case in cases}
    for c in cases:
        endpoint = extract_case_endpoint(c)
        if endpoint:
            case_by_endpoint.setdefault(endpoint, []).append(c)

    diffs: list[dict[str, Any]] = []
    draft_patches: list[dict[str, Any]] = []

    matched_spec_keys: set[tuple[str, str]] = set()

    # 1. Check spec endpoints for additions or modifications
    for (m, path), meta in spec_endpoints.items():
        matched_cases = case_by_endpoint.get((m, path))
        if not matched_cases:
            # Missing in test cases -> Addition
            patch = generate_addition_patch(meta, default_module_id)
            diffs.append(
                {
                    "endpoint": f"{m} {path}",
                    "change_type": "addition",
                    "case_id": None,
                    "case_name": None,
                    "details": [f"规格新增接口，当前项目缺少对应测试用例: {meta['summary']}"],
                    "patch_payload": patch,
                }
            )
            draft_patches.append({"action": "create_case", "payload": patch})
        else:
            matched_spec_keys.add((m, path))
            for case in matched_cases:
                mod_diffs = compare_case_with_spec_endpoint(case, meta)
                if mod_diffs:
                    diffs.append(
                        {
                            "endpoint": f"{m} {path}",
                            "change_type": "modification",
                            "case_id": case.id,
                            "case_name": case.name,
                            "details": mod_diffs,
                            "patch_payload": {"spec_summary": meta["summary"]},
                        }
                    )

    # 2. Check for cases whose endpoint no longer exists in spec -> Deprecation
    for (m, path), case_list in case_by_endpoint.items():
        if (m, path) not in spec_endpoints:
            for case in case_list:
                diffs.append(
                    {
                        "endpoint": f"{m} {path}",
                        "change_type": "deprecation",
                        "case_id": case.id,
                        "case_name": case.name,
                        "details": [f"规格已移除此接口: {m} {path}"],
                        "patch_payload": None,
                    }
                )

    if baseline is not None:
        old_endpoints = extract_spec_endpoints(baseline)
        existing_diff_endpoints = {diff["endpoint"] for diff in diffs}
        for (method, path), old_meta in old_endpoints.items():
            ep_key = f"{method} {path}"
            if ep_key in existing_diff_endpoints:
                continue
            current_meta = spec_endpoints.get((method, path))
            if current_meta is None:
                details = ["旧版规格中的接口已移除，需检查场景引用"]
                change_type = "deprecation"
            elif any(old_meta.get(key) != current_meta.get(key) for key in ("parameters", "requestBody", "responses")):
                details = ["规格请求或响应结构变化，需人工检查场景步骤"]
                change_type = "modification"
            else:
                continue
            diffs.append(
                {
                    "endpoint": ep_key,
                    "change_type": change_type,
                    "case_id": None,
                    "case_name": None,
                    "details": details,
                    "patch_payload": None,
                }
            )

    additions = sum(1 for d in diffs if d["change_type"] == "addition")
    modifications = sum(1 for d in diffs if d["change_type"] == "modification")
    deprecations = sum(1 for d in diffs if d["change_type"] == "deprecation")

    affected = {
        (method, normalize_endpoint_path(path)): diff
        for diff in diffs
        if diff["change_type"] != "addition"
        for method, path in [diff["endpoint"].split(" ", 1)]
    }
    affected_case_ids = {
        diff["case_id"]: diff for diff in diffs if diff["case_id"] is not None and diff["change_type"] != "addition"
    }
    scenario_impacts: list[dict[str, Any]] = []
    for scenario in scenarios or []:
        if scenario.get("project_id") != project_id or not isinstance(scenario.get("steps"), list):
            continue
        scenario_id = scenario.get("id")
        if not isinstance(scenario_id, int):
            continue
        for index, step in enumerate(scenario["steps"]):
            if not isinstance(step, dict):
                continue
            source_case_id = step.get("sourceCaseId")
            if not isinstance(source_case_id, int) or source_case_id not in affected_case_ids:
                source_case_id = None
            method = str(step.get("method") or "").upper()
            url = str(step.get("url") or "")
            endpoint = (method, normalize_endpoint_path(url)) if method and url else None
            diff = affected_case_ids.get(source_case_id) if source_case_id is not None else None
            if diff is None and endpoint is not None:
                diff = affected.get(endpoint)
            if diff is None:
                continue
            fingerprint = step.get("sourceCaseFingerprint")
            if source_case_id is not None and isinstance(fingerprint, str) and source_case_id in case_by_id:
                source_changed = fingerprint != case_request_fingerprint(case_by_id[source_case_id])
                local_override = fingerprint != scenario_request_fingerprint(step)
                reasons = []
                if source_changed:
                    reasons.append("来源用例请求已更新，存在版本冲突")
                if local_override:
                    reasons.append("场景步骤存在局部覆盖")
                review_reason = "；".join(reasons) if reasons else "来源与场景请求一致，请检查规格变更"
            else:
                review_reason = (
                    "来源用例版本与局部覆盖未记录，请逐项确认"
                    if source_case_id is not None
                    else "按请求地址匹配；未记录来源用例，请人工确认"
                )
            scenario_impacts.append(
                {
                    "scenario_id": scenario_id,
                    "scenario_name": str(scenario.get("name") or f"场景 {scenario_id}"),
                    "step_index": index,
                    "step_name": str(step.get("name") or f"步骤 {index + 1}"),
                    "endpoint": diff["endpoint"],
                    "source_case_id": source_case_id,
                    "review_reason": review_reason,
                }
            )

    return {
        "total_spec_endpoints": len(spec_endpoints),
        "total_cases": len(cases),
        "additions_count": additions,
        "modifications_count": modifications,
        "deprecations_count": deprecations,
        "diffs": diffs,
        "draft_patches": draft_patches,
        "scenario_impacts": scenario_impacts,
    }
