"""解析 OpenAPI / Postman Collection / cURL / 接口样例文本为统一接口清单。

对外只暴露 ``parse_schema(source_type, content) -> ParseResult``。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Literal
from urllib.parse import parse_qsl, urlparse

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
    base_url: str | None = None
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


ExternalRefPolicy = Literal["warn", "reject"]


class _OpenApiResolver:
    """Resolve local OpenAPI/Swagger JSON pointers without fetching remote files."""

    def __init__(
        self,
        document: dict[str, Any],
        warnings: list[str],
        *,
        external_ref_policy: ExternalRefPolicy = "warn",
    ) -> None:
        self.document = document
        self.warnings = warnings
        self.external_ref_policy = external_ref_policy

    def resolve(self, value: Any) -> Any:
        if not isinstance(value, dict) or "$ref" not in value:
            return value
        current = value
        visited: set[str] = set()
        while isinstance(current, dict) and "$ref" in current:
            reference = current.get("$ref")
            if not isinstance(reference, str) or not reference.startswith("#/"):
                if self.external_ref_policy == "reject":
                    raise ValueError(f"发布安全模式禁止外部 OpenAPI $ref: {reference}")
                self.warnings.append(f"暂不解析外部 OpenAPI $ref: {reference}")
                return {key: item for key, item in current.items() if key != "$ref"}
            if reference in visited:
                self.warnings.append(f"检测到循环 OpenAPI $ref: {reference}")
                return {key: item for key, item in current.items() if key != "$ref"}
            visited.add(reference)
            target = self._pointer(reference)
            if target is None:
                self.warnings.append(f"未找到 OpenAPI $ref: {reference}")
                return {key: item for key, item in current.items() if key != "$ref"}
            if not isinstance(target, dict):
                self.warnings.append(f"OpenAPI $ref 目标不是对象: {reference}")
                return target
            merged = dict(target)
            merged.update({key: item for key, item in current.items() if key != "$ref"})
            current = merged
        return current

    def _pointer(self, reference: str) -> Any:
        value: Any = self.document
        for part in reference[2:].split("/"):
            part = part.replace("~1", "/").replace("~0", "~")
            if isinstance(value, dict):
                value = value.get(part)
            elif isinstance(value, list) and part.isdigit():
                index = int(part)
                value = value[index] if index < len(value) else None
            else:
                return None
        return value


def _example_from_schema(schema: dict | None, resolver: _OpenApiResolver | None = None) -> Any:
    if not isinstance(schema, dict):
        return None
    if resolver is not None:
        schema = resolver.resolve(schema)
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
        return [_example_from_schema(schema.get("items"), resolver)]
    if type_ == "object" or schema.get("properties"):
        return {name: _example_from_schema(sub, resolver) for name, sub in (schema.get("properties") or {}).items()}
    all_of = schema.get("allOf")
    if isinstance(all_of, list):
        example: dict[str, Any] = {}
        for item in all_of:
            nested = _example_from_schema(item, resolver)
            if isinstance(nested, dict):
                example.update(nested)
        return example or None
    return None


def _example_from_media(media: dict[str, Any], resolver: _OpenApiResolver) -> Any:
    """Return an explicit media example, including valid falsy JSON values."""
    if "example" in media:
        return media["example"]
    examples = media.get("examples")
    if isinstance(examples, dict):
        for item in examples.values():
            if isinstance(item, dict) and "value" in item:
                return item["value"]
    return _example_from_schema(media.get("schema"), resolver)


def parse_openapi(content: str, *, external_ref_policy: ExternalRefPolicy = "warn") -> ParseResult:
    if external_ref_policy not in {"warn", "reject"}:
        raise ValueError(f"不支持的外部 OpenAPI $ref 策略: {external_ref_policy}")
    doc = _coerce_doc(content)
    if not isinstance(doc, dict):
        raise ValueError("OpenAPI 文档需要是对象")
    paths = doc.get("paths")
    if not isinstance(paths, dict):
        return ParseResult(endpoints=[], warnings=["未找到 paths 字段"])

    endpoints: list[Endpoint] = []
    warnings: list[str] = []
    resolver = _OpenApiResolver(doc, warnings, external_ref_policy=external_ref_policy)
    valid_methods = {"get", "post", "put", "delete", "patch", "options", "head"}
    servers = doc.get("servers") or []
    base_url = servers[0].get("url") if servers and isinstance(servers[0], dict) else None
    if not base_url and doc.get("host"):
        schemes = doc.get("schemes") or ["http"]
        base_url = f"{schemes[0]}://{doc['host']}{doc.get('basePath', '')}"

    for path, item in paths.items():
        if not isinstance(item, dict):
            continue
        common_params = item.get("parameters") or []
        for method, op in item.items():
            if method.lower() not in valid_methods or not isinstance(op, dict):
                continue
            params: list[EndpointParameter] = []
            for raw in common_params + (op.get("parameters") or []):
                if not isinstance(raw, dict):
                    continue
                raw = resolver.resolve(raw)
                if not isinstance(raw, dict):
                    continue
                schema = raw.get("schema") or {}
                schema = resolver.resolve(schema)
                params.append(
                    EndpointParameter(
                        name=raw.get("name", ""),
                        location=raw.get("in", "query"),
                        required=bool(raw.get("required", False)),
                        schema_type=schema.get("type"),
                        description=raw.get("description"),
                        example=(raw["example"] if "example" in raw else _example_from_schema(schema, resolver)),
                    )
                )

            body_example: Any = None
            body = op.get("requestBody")
            if isinstance(body, dict):
                body = resolver.resolve(body)
                content_map = body.get("content") or {}
                json_media = content_map.get("application/json") or {}
                if isinstance(json_media, dict):
                    json_media = resolver.resolve(json_media)
                    body_example = _example_from_media(json_media, resolver)

            resp_example: Any = None
            responses = op.get("responses") or {}
            for code in ("200", "201", "default"):
                resp = responses.get(code)
                if isinstance(resp, dict):
                    resp = resolver.resolve(resp)
                    content_map = resp.get("content") or {}
                    json_media = content_map.get("application/json") or {}
                    if isinstance(json_media, dict):
                        json_media = resolver.resolve(json_media)
                        resp_example = _example_from_media(json_media, resolver)
                        if resp_example is not None:
                            break

            endpoints.append(
                Endpoint(
                    method=method.upper(),
                    path=path,
                    base_url=base_url,
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
            base_url = None
            host = url.get("host") or []
            protocol = url.get("protocol") or "http"
            if host:
                base_url = f"{protocol}://{'.'.join(host) if isinstance(host, list) else host}"
        else:
            parsed = urlparse(str(url or ""))
            path = parsed.path or "/"
            query_items = [{"key": key, "value": value} for key, value in parse_qsl(parsed.query, keep_blank_values=True)]
            base_url = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else None

        params: list[EndpointParameter] = []
        for q in query_items:
            if isinstance(q, dict) and not q.get("disabled") and q.get("key"):
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
            if isinstance(h, dict) and not h.get("disabled") and h.get("key"):
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
        if isinstance(body, dict):
            if body.get("mode") == "raw":
                raw = body.get("raw") or ""
                try:
                    body_example = json.loads(raw)
                except (TypeError, ValueError):
                    body_example = raw
            elif body.get("mode") in {"urlencoded", "formdata"}:
                fields = body.get(body["mode"]) or []
                body_example = {
                    field.get("key"): field.get("value")
                    for field in fields
                    if isinstance(field, dict) and not field.get("disabled") and field.get("key")
                }

        accumulator.append(
            Endpoint(
                method=method,
                path=path,
                base_url=base_url,
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
    base_url = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else None

    method = "GET"
    if m := _CURL_METHOD_RE.search(raw):
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
    if m := _CURL_DATA_RE.search(raw):
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
                base_url=base_url,
                summary=f"{method} {path}",
                parameters=params,
                request_body_example=body_example,
            )
        ]
    )


# ──────────────────────────── 接口样例 ─────────────────────────────


_SAMPLE_METHOD_PATH_RE = re.compile(
    r"\b(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)\s+((?:https?://)?[^\s]+)",
    re.IGNORECASE,
)


def _try_load_json(value: str) -> Any | None:
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return None


def _extract_json_blocks(text: str) -> list[Any]:
    """Best-effort 提取文本中的顶层 JSON object/array 块。"""
    blocks: list[Any] = []
    stack: list[str] = []
    start: int | None = None
    in_string = False
    escape = False
    pairs = {"{": "}", "[": "]"}

    for idx, char in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char in pairs:
            if not stack:
                start = idx
            stack.append(pairs[char])
            continue
        if stack and char == stack[-1]:
            stack.pop()
            if not stack and start is not None:
                payload = text[start : idx + 1]
                parsed = _try_load_json(payload)
                if parsed is not None:
                    blocks.append(parsed)
                start = None
    return blocks


def _endpoint_from_sample_object(obj: dict) -> Endpoint:
    method = str(obj.get("method") or obj.get("http_method") or "POST").upper()
    raw_path = str(obj.get("path") or obj.get("url") or obj.get("endpoint") or "/")
    parsed = urlparse(raw_path)
    path = parsed.path or raw_path or "/"
    base_url = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else None

    params: list[EndpointParameter] = []
    raw_headers = obj.get("headers") or obj.get("header")
    if isinstance(raw_headers, dict):
        for name, value in raw_headers.items():
            params.append(EndpointParameter(name=str(name), location="header", example=value))
    raw_query = obj.get("query") or obj.get("query_params") or obj.get("params")
    if isinstance(raw_query, dict):
        for name, value in raw_query.items():
            params.append(EndpointParameter(name=str(name), location="query", example=value))

    request_example = (
        obj.get("request_body")
        if "request_body" in obj
        else obj.get("request")
        if "request" in obj
        else obj.get("body")
        if "body" in obj
        else None
    )
    response_example = (
        obj.get("response_body") if "response_body" in obj else obj.get("response") if "response" in obj else None
    )
    return Endpoint(
        method=method,
        path=path,
        base_url=base_url,
        summary=obj.get("name") or obj.get("summary") or f"{method} {path}",
        description=obj.get("description"),
        parameters=params,
        request_body_example=request_example,
        response_example=response_example,
    )


def parse_sample(content: str) -> ParseResult:
    """解析接口样例文本。

    支持：
    - JSON object/list：含 method/path/request/response 等字段。
    - HTTP/cURL 风格片段：`POST /api/login` 后跟请求/响应 JSON。
    - 纯 JSON 样例：作为 request_body_example，用需求补足接口语义。
    """
    text = content.strip()
    if not text:
        raise ValueError("接口样例为空")

    loaded = _try_load_json(text)
    if isinstance(loaded, list):
        endpoints = [_endpoint_from_sample_object(item) for item in loaded if isinstance(item, dict)]
        if endpoints:
            return ParseResult(endpoints=endpoints)
    if isinstance(loaded, dict):
        if any(key in loaded for key in ("method", "path", "url", "endpoint", "request", "response", "body")):
            return ParseResult(endpoints=[_endpoint_from_sample_object(loaded)])
        return ParseResult(
            endpoints=[
                Endpoint(
                    method="POST",
                    path="/sample-endpoint",
                    base_url=None,
                    summary="接口样例",
                    request_body_example=loaded,
                )
            ],
            warnings=["未识别到 method/path，已将 JSON 作为请求样例"],
        )

    method = "POST"
    path = "/sample-endpoint"
    summary = "接口样例"
    if match := _SAMPLE_METHOD_PATH_RE.search(text):
        method = match.group(1).upper()
        raw_path = match.group(2)
        parsed = urlparse(raw_path)
        path = parsed.path or raw_path or "/"
        summary = f"{method} {path}"

    blocks = _extract_json_blocks(text)
    request_example = blocks[0] if blocks else None
    response_example = blocks[1] if len(blocks) > 1 else None
    warnings: list[str] = []
    if request_example is None and response_example is None:
        request_example = text[:2000]
        warnings.append("未识别到 JSON 块，已将样例文本作为请求说明")

    return ParseResult(
        endpoints=[
            Endpoint(
                method=method,
                path=path,
                summary=summary,
                description=text[:500],
                request_body_example=request_example,
                response_example=response_example,
            )
        ],
        warnings=warnings,
    )


# ──────────────────────────── 入口 ────────────────────────────────


def parse_schema(
    source_type: str,
    content: str,
    *,
    external_ref_policy: ExternalRefPolicy = "warn",
) -> ParseResult:
    """根据 source_type 路由到对应解析器。"""
    if source_type == "openapi":
        return parse_openapi(content, external_ref_policy=external_ref_policy)
    if source_type == "postman":
        return parse_postman(content)
    if source_type == "curl":
        return parse_curl(content)
    if source_type == "sample":
        return parse_sample(content)
    raise ValueError(f"不支持的 source_type: {source_type}")
