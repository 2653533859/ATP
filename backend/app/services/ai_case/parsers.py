"""解析 OpenAPI / Postman Collection / cURL 文本为统一接口清单。

对外只暴露 ``parse_schema(source_type, content) -> ParseResult``。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import yaml


@dataclass
class EndpointParameter:
    name: str
    location: str  # path / query / header / body
    required: bool = False
    schema_type: str | None = None
    description: str | None = None
    example: Any | None = None


@dataclass
class Endpoint:
    method: str
    path: str
    summary: str | None = None
    description: str | None = None
    operation_id: str | None = None
    tags: list[str] = field(default_factory=list)
    parameters: list[EndpointParameter] = field(default_factory=list)
    request_body_example: Any | None = None
    response_example: Any | None = None


@dataclass
class ParseResult:
    endpoints: list[Endpoint]
    warnings: list[str] = field(default_factory=list)


# ──────────────────────────── OpenAPI ─────────────────────────────


def _coerce_doc(content: str) -> dict:
    text = content.strip()
    if not text:
        raise ValueError("内容为空")
    if text[0] in "{[":
        return json.loads(text)
    return yaml.safe_load(text)


def _example_from_schema(schema: dict | None) -> Any:
    if not isinstance(schema, dict):
        return None
    if "example" in schema:
        return schema["example"]
    if "default" in schema:
        return schema["default"]
    enum = schema.get("enum")
    if isinstance(enum, list) and enum:
        return enum[0]
    type_ = schema.get("type")
    if type_ == "string":
        return ""
    if type_ in ("integer", "number"):
        return 0
    if type_ == "boolean":
        return False
    if type_ == "array":
        return [_example_from_schema(schema.get("items"))]
    if type_ == "object" or schema.get("properties"):
        return {
            name: _example_from_schema(sub)
            for name, sub in (schema.get("properties") or {}).items()
        }
    return None


def parse_openapi(content: str) -> ParseResult:
    doc = _coerce_doc(content)
    if not isinstance(doc, dict):
        raise ValueError("OpenAPI 文档需要是对象")
    paths = doc.get("paths")
    if not isinstance(paths, dict):
        return ParseResult(endpoints=[], warnings=["未找到 paths 字段"])

    endpoints: list[Endpoint] = []
    warnings: list[str] = []
    valid_methods = {"get", "post", "put", "delete", "patch", "options", "head"}

    for path, item in paths.items():
        if not isinstance(item, dict):
            continue
        common_params = item.get("parameters") or []
        for method, op in item.items():
            if method.lower() not in valid_methods or not isinstance(op, dict):
                continue
            params: list[EndpointParameter] = []
            for raw in (common_params + (op.get("parameters") or [])):
                if not isinstance(raw, dict):
                    continue
                schema = raw.get("schema") or {}
                params.append(
                    EndpointParameter(
                        name=raw.get("name", ""),
                        location=raw.get("in", "query"),
                        required=bool(raw.get("required", False)),
                        schema_type=schema.get("type"),
                        description=raw.get("description"),
                        example=raw.get("example") or _example_from_schema(schema),
                    )
                )

            body_example: Any = None
            body = op.get("requestBody")
            if isinstance(body, dict):
                content_map = body.get("content") or {}
                json_media = content_map.get("application/json") or {}
                if isinstance(json_media, dict):
                    body_example = json_media.get("example") or _example_from_schema(
                        json_media.get("schema")
                    )

            resp_example: Any = None
            responses = op.get("responses") or {}
            for code in ("200", "201", "default"):
                resp = responses.get(code)
                if isinstance(resp, dict):
                    content_map = resp.get("content") or {}
                    json_media = content_map.get("application/json") or {}
                    if isinstance(json_media, dict):
                        resp_example = json_media.get("example") or _example_from_schema(
                            json_media.get("schema")
                        )
                        if resp_example is not None:
                            break

            endpoints.append(
                Endpoint(
                    method=method.upper(),
                    path=path,
                    summary=op.get("summary"),
                    description=op.get("description"),
                    operation_id=op.get("operationId"),
                    tags=list(op.get("tags") or []),
                    parameters=params,
                    request_body_example=body_example,
                    response_example=resp_example,
                )
            )

    if not endpoints:
        warnings.append("paths 中未识别到任何接口")
    return ParseResult(endpoints=endpoints, warnings=warnings)


# ──────────────────────────── Postman ─────────────────────────────


def _walk_postman_items(items: list, accumulator: list[Endpoint]) -> None:
    for entry in items:
        if not isinstance(entry, dict):
            continue
        if "item" in entry:
            _walk_postman_items(entry["item"], accumulator)
            continue
        request = entry.get("request")
        if not isinstance(request, dict):
            continue
        method = (request.get("method") or "GET").upper()
        url = request.get("url")
        if isinstance(url, dict):
            path = "/" + "/".join(url.get("path") or [])
            query_items = url.get("query") or []
        else:
            parsed = urlparse(str(url or ""))
            path = parsed.path or "/"
            query_items = []

        params: list[EndpointParameter] = []
        for q in query_items:
            if isinstance(q, dict):
                params.append(
                    EndpointParameter(
                        name=q.get("key", ""),
                        location="query",
                        required=False,
                        description=q.get("description"),
                        example=q.get("value"),
                    )
                )
        for h in request.get("header") or []:
            if isinstance(h, dict):
                params.append(
                    EndpointParameter(
                        name=h.get("key", ""),
                        location="header",
                        required=False,
                        description=h.get("description"),
                        example=h.get("value"),
                    )
                )

        body_example: Any = None
        body = request.get("body")
        if isinstance(body, dict) and body.get("mode") == "raw":
            raw = body.get("raw") or ""
            try:
                body_example = json.loads(raw)
            except (TypeError, ValueError):
                body_example = raw

        accumulator.append(
            Endpoint(
                method=method,
                path=path,
                summary=entry.get("name"),
                description=(request.get("description") or None)
                if isinstance(request.get("description"), str)
                else None,
                tags=[],
                parameters=params,
                request_body_example=body_example,
            )
        )


def parse_postman(content: str) -> ParseResult:
    doc = _coerce_doc(content)
    if not isinstance(doc, dict):
        raise ValueError("Postman Collection 需要是对象")
    items = doc.get("item")
    if not isinstance(items, list):
        return ParseResult(endpoints=[], warnings=["未找到 item 字段"])
    endpoints: list[Endpoint] = []
    _walk_postman_items(items, endpoints)
    warnings: list[str] = []
    if not endpoints:
        warnings.append("item 中未识别到任何接口")
    return ParseResult(endpoints=endpoints, warnings=warnings)


# ──────────────────────────── cURL ────────────────────────────────


_CURL_METHOD_RE = re.compile(r"-X\s+([A-Z]+)", re.IGNORECASE)
# 用反向引用匹配同种引号，避免 JSON 内嵌引号截断
_CURL_HEADER_RE = re.compile(r"""-H\s+(['"])([^'"]+)\1""")
_CURL_DATA_RE = re.compile(r"""--data(?:-raw)?\s+(['"])([\s\S]+?)\1""")
_CURL_URL_RE = re.compile(r"curl\s+(?:[^ ]+\s+)*?['\"]?(https?://[^\s'\"]+)")


def parse_curl(content: str) -> ParseResult:
    """支持单条 cURL 命令。多行 \\ 续行会被合并。"""
    raw = " ".join(line.strip().rstrip("\\") for line in content.splitlines()).strip()
    if not raw:
        raise ValueError("cURL 命令为空")

    url_match = _CURL_URL_RE.search(raw)
    if not url_match:
        raise ValueError("未找到 URL")
    url = url_match.group(1)
    parsed = urlparse(url)
    path = parsed.path or "/"

    method = "GET"
    if (m := _CURL_METHOD_RE.search(raw)):
        method = m.group(1).upper()

    params: list[EndpointParameter] = []
    for _quote, header in _CURL_HEADER_RE.findall(raw):
        key, _, value = header.partition(":")
        params.append(
            EndpointParameter(
                name=key.strip(),
                location="header",
                example=value.strip() or None,
            )
        )

    body_example: Any = None
    if (m := _CURL_DATA_RE.search(raw)):
        body_raw = m.group(2)
        method = method if method != "GET" else "POST"
        try:
            body_example = json.loads(body_raw)
        except (TypeError, ValueError):
            body_example = body_raw

    return ParseResult(
        endpoints=[
            Endpoint(
                method=method,
                path=path,
                summary=f"{method} {path}",
                parameters=params,
                request_body_example=body_example,
            )
        ]
    )


# ──────────────────────────── 入口 ────────────────────────────────


def parse_schema(source_type: str, content: str) -> ParseResult:
    """根据 source_type 路由到对应解析器。"""
    if source_type == "openapi":
        return parse_openapi(content)
    if source_type == "postman":
        return parse_postman(content)
    if source_type == "curl":
        return parse_curl(content)
    raise ValueError(f"不支持的 source_type: {source_type}")
