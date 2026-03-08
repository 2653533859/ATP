import asyncio
import re
from collections import deque
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.mock import MockRule, MockMethod

router = APIRouter(tags=["mock-server"])

# 内存存储最近 50 条 Mock 请求日志（按 project_id 分组）
_MAX_LOGS = 50
_request_logs: dict[int, deque] = {}


def _get_logs(project_id: int) -> deque:
    if project_id not in _request_logs:
        _request_logs[project_id] = deque(maxlen=_MAX_LOGS)
    return _request_logs[project_id]


def get_mock_logs(project_id: int) -> list[dict]:
    """供 API 端点调用，获取指定项目的请求日志"""
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
    """检查实际路径是否匹配模板路径（支持 {param} 占位符）"""
    pattern_parts: list[str] = []
    cursor = 0

    for match in re.finditer(r"\{[^/{}]+\}", template):
        pattern_parts.append(re.escape(template[cursor:match.start()]))
        pattern_parts.append(r"[^/]+")
        cursor = match.end()

    pattern_parts.append(re.escape(template[cursor:]))
    pattern = "^" + "".join(pattern_parts) + "$"
    return re.fullmatch(pattern, actual) is not None


def _build_rule_stmt(project_id: int, normalized: str, candidate_methods: list[MockMethod]):
    return (
        select(MockRule)
        .where(
            MockRule.project_id == project_id,
            MockRule.is_enabled.is_(True),
            MockRule.method.in_(candidate_methods),
        )
        .order_by(MockRule.method == MockMethod.ANY, MockRule.id.desc())
    )


async def _find_matching_rule(project_id: int, normalized: str, candidate_methods: list[MockMethod]):
    """先精确匹配，再模板匹配"""
    async with AsyncSessionLocal() as db:
        # 精确匹配
        exact_stmt = (
            select(MockRule)
            .where(
                MockRule.project_id == project_id,
                MockRule.is_enabled.is_(True),
                MockRule.path == normalized,
                MockRule.method.in_(candidate_methods),
            )
            .order_by(MockRule.method == MockMethod.ANY, MockRule.id.desc())
            .limit(1)
        )
        result = await db.execute(exact_stmt)
        rule = result.scalar_one_or_none()
        if rule:
            return rule

        # 模板匹配：查所有启用规则，逐一匹配
        tmpl_stmt = _build_rule_stmt(project_id, normalized, candidate_methods)
        result = await db.execute(tmpl_stmt)
        for rule in result.scalars().all():
            if "{" in rule.path and _path_matches_template(rule.path, normalized):
                return rule

    return None


@router.api_route(
    "/mock/{project_id}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
)
async def mock_endpoint(project_id: int, path: str, request: Request):
    """Mock 服务入口：根据 project_id + method + path 匹配规则并返回模拟响应"""
    method = request.method.upper()
    normalized = _normalize_path(path)

    rule = await _find_matching_rule(project_id, normalized, _candidate_methods(method))

    # 记录请求日志
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
    body = rule.response_body or ""

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
