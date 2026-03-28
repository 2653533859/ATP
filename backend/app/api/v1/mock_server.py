import asyncio
import json
import re
from collections import deque
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.redis_client import (
    delete_json_cache,
    delete_json_cache_pattern,
    get_json_cache,
    set_json_cache,
)
from app.models.mock import MockRule, MockMethod

router = APIRouter(tags=["mock-server"])

_MAX_LOGS = 50
_MAX_RECORDED_SAMPLES = 20
_request_logs: dict[int, deque] = {}


def _get_logs(project_id: int) -> deque:
    if project_id not in _request_logs:
        _request_logs[project_id] = deque(maxlen=_MAX_LOGS)
    return _request_logs[project_id]


def get_mock_logs(project_id: int) -> list[dict]:
    return list(_get_logs(project_id))


def _normalize_path(path: str) -> str:
    return "/" + path.lstrip("/")


def _candidate_methods(method: str) -> list[MockMethod]:
    if method == "HEAD":
        return [MockMethod.GET, MockMethod.ANY]
    if method == "OPTIONS":
        return [MockMethod.ANY]
    return [MockMethod(method), MockMethod.ANY]


def _path_matches_template(template: str, actual: str) -> bool:
    pattern_parts: list[str] = []
    cursor = 0

    for match in re.finditer(r"\{[^/{}]+\}", template):
        pattern_parts.append(re.escape(template[cursor:match.start()]))
        pattern_parts.append(r"[^/]+")
        cursor = match.end()

    pattern_parts.append(re.escape(template[cursor:]))
    pattern = "^" + "".join(pattern_parts) + "$"
    return re.fullmatch(pattern, actual) is not None


def _build_rule_stmt(project_id: int, candidate_methods: list[MockMethod]):
    return (
        select(MockRule)
        .where(
            MockRule.project_id == project_id,
            MockRule.is_enabled.is_(True),
            MockRule.method.in_(candidate_methods),
        )
        .order_by(MockRule.method == MockMethod.ANY, MockRule.id.desc())
    )


def _match_conditions(rule: MockRule, request_data: dict) -> bool:
    conditions = rule.match_conditions or {}
    for source_key, actual_data in (
        ("query", request_data.get("query", {})),
        ("headers", request_data.get("headers", {})),
        ("body", request_data.get("body", {})),
    ):
        expected = conditions.get(source_key) or {}
        for key, value in expected.items():
            actual_value = actual_data.get(key)
            if str(actual_value) != str(value):
                return False
    return True


def _render_template_text(template: str | None, request_data: dict) -> str:
    if not template:
        return ""

    def replacer(match: re.Match[str]) -> str:
        source = match.group(1)
        key = match.group(2)
        return str((request_data.get(source) or {}).get(key, ""))

    return re.sub(r"\{\{\s*(query|headers|body)\.([\w.-]+)\s*\}\}", replacer, template)


def _cache_key(project_id: int, normalized: str, candidate_methods: list[MockMethod], request_data: dict) -> str:
    return (
        f"atp:mock:{project_id}:{candidate_methods[0].value}:{normalized}:"
        f"{json.dumps(request_data, sort_keys=True, ensure_ascii=False)}"
    )


def _rule_matches_request(
    rule: MockRule | None,
    normalized: str,
    candidate_methods: list[MockMethod],
    request_data: dict,
) -> bool:
    if rule is None or not rule.is_enabled or rule.method not in candidate_methods:
        return False
    path_matches = (
        _path_matches_template(rule.path, normalized)
        if "{" in rule.path
        else rule.path == normalized
    )
    return path_matches and _match_conditions(rule, request_data)


async def invalidate_mock_cache(project_id: int) -> None:
    await delete_json_cache_pattern(f"atp:mock:{project_id}:*")


async def _record_sample(rule_id: int, request_data: dict, response_payload: dict):
    async with AsyncSessionLocal() as db:
        rule = await db.get(MockRule, rule_id)
        if not rule or not rule.record_requests:
            return
        samples = list(rule.recorded_samples or [])
        samples.insert(0, {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request": request_data,
            "response": response_payload,
        })
        rule.recorded_samples = samples[:_MAX_RECORDED_SAMPLES]
        await db.commit()


async def _find_matching_rule(project_id: int, normalized: str, candidate_methods: list[MockMethod], request_data: dict):
    cache_key = _cache_key(project_id, normalized, candidate_methods, request_data)
    cached = await get_json_cache(cache_key)
    if cached is not None and cached.get("rule_id"):
        async with AsyncSessionLocal() as db:
            cached_rule = await db.get(MockRule, cached.get("rule_id"))
            if _rule_matches_request(cached_rule, normalized, candidate_methods, request_data):
                return cached_rule
        await delete_json_cache(cache_key)

    async with AsyncSessionLocal() as db:
        exact_stmt = (
            select(MockRule)
            .where(
                MockRule.project_id == project_id,
                MockRule.is_enabled.is_(True),
                MockRule.path == normalized,
                MockRule.method.in_(candidate_methods),
            )
            .order_by(MockRule.method == MockMethod.ANY, MockRule.id.desc())
        )
        result = await db.execute(exact_stmt)
        for rule in result.scalars().all():
            if _match_conditions(rule, request_data):
                await set_json_cache(cache_key, {"rule_id": rule.id}, ttl_seconds=180)
                return rule

        tmpl_stmt = _build_rule_stmt(project_id, candidate_methods)
        result = await db.execute(tmpl_stmt)
        for rule in result.scalars().all():
            if "{" in rule.path and _path_matches_template(rule.path, normalized) and _match_conditions(rule, request_data):
                await set_json_cache(cache_key, {"rule_id": rule.id}, ttl_seconds=180)
                return rule

    return None


@router.api_route(
    "/mock/{project_id}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
)
async def mock_endpoint(project_id: int, path: str, request: Request):
    method = request.method.upper()
    normalized = _normalize_path(path)
    body_data = {}
    try:
        body_bytes = await request.body()
        if body_bytes:
            body_data = json.loads(body_bytes.decode())
    except Exception:
        body_data = {}

    request_data = {
        "query": dict(request.query_params),
        "headers": {k.lower(): v for k, v in request.headers.items()},
        "body": body_data if isinstance(body_data, dict) else {},
    }

    rule = await _find_matching_rule(project_id, normalized, _candidate_methods(method), request_data)

    log_entry = {
        "method": method,
        "path": normalized,
        "matched": rule is not None,
        "rule_name": rule.name if rule else None,
        "status_code": rule.status_code if rule else 404,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _get_logs(project_id).appendleft(log_entry)

    if rule is None:
        return JSONResponse(
            status_code=404,
            content={"detail": f"No mock rule matched: {method} {normalized}"},
        )

    if rule.delay_ms > 0:
        await asyncio.sleep(rule.delay_ms / 1000.0)

    headers = {k: str(v) for k, v in (rule.response_headers or {}).items()}
    content_type = headers.pop("Content-Type", headers.pop("content-type", None))
    body = _render_template_text(rule.response_body, request_data) if rule.render_template else (rule.response_body or "")

    response_payload = {
        "status_code": rule.status_code,
        "headers": headers,
        "body": body,
    }
    if rule.record_requests:
        await _record_sample(rule.id, request_data, response_payload)

    if content_type and "json" not in content_type:
        return PlainTextResponse(
            content=body,
            status_code=rule.status_code,
            headers=headers,
            media_type=content_type,
        )

    return Response(
        content=body,
        status_code=rule.status_code,
        headers=headers,
        media_type=content_type or "application/json",
    )
