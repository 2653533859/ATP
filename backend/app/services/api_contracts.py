"""OpenAPI/Swagger and JSON Schema compatibility comparison."""

from __future__ import annotations

from typing import Any


class _LocalRefResolver:
    """Resolve local JSON Pointer references without fetching remote documents."""

    def __init__(self, document: dict[str, Any], warnings: list[dict[str, str]]) -> None:
        self.document = document
        self.warnings = warnings

    def resolve(self, value: Any) -> Any:
        if not isinstance(value, dict) or "$ref" not in value:
            return value
        current = value
        visited: set[str] = set()
        while isinstance(current, dict) and "$ref" in current:
            reference = current.get("$ref")
            if not isinstance(reference, str) or not reference.startswith("#/"):
                _add(
                    self.warnings, str(reference), "仅支持项目内 JSON Pointer $ref，外部引用已跳过", severity="warning"
                )
                return {key: item for key, item in current.items() if key != "$ref"}
            if reference in visited:
                _add(self.warnings, reference, "检测到循环 $ref，已停止展开", severity="warning")
                return {key: item for key, item in current.items() if key != "$ref"}
            visited.add(reference)
            target = self._pointer(reference)
            if not isinstance(target, dict):
                _add(self.warnings, reference, "未找到可比较的 $ref 目标", severity="warning")
                return {key: item for key, item in current.items() if key != "$ref"}
            merged = dict(target)
            merged.update({key: item for key, item in current.items() if key != "$ref"})
            current = merged
        return current

    def _pointer(self, reference: str) -> Any:
        value: Any = self.document
        for part in reference[2:].split("/"):
            part = part.replace("~1", "/").replace("~0", "~")
            if not isinstance(value, dict):
                return None
            value = value.get(part)
        return value


def compare_contracts(baseline: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    breaking: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    baseline_refs = _LocalRefResolver(baseline, warnings)
    current_refs = _LocalRefResolver(current, warnings)
    if _is_openapi(baseline) or _is_openapi(current):
        _compare_openapi(baseline, current, breaking, warnings, baseline_refs, current_refs)
    else:
        _compare_schema(baseline, current, "$", breaking, warnings, baseline_refs, current_refs)

    return {
        "compatible": not breaking,
        "breaking_changes": breaking,
        "warnings": warnings,
        "summary": "未发现破坏性变化" if not breaking else f"发现 {len(breaking)} 项破坏性变化",
    }


def _is_openapi(document: dict[str, Any]) -> bool:
    return isinstance(document, dict) and ("openapi" in document or "swagger" in document or "paths" in document)


def _compare_openapi(
    baseline: dict[str, Any],
    current: dict[str, Any],
    breaking: list[dict[str, str]],
    warnings: list[dict[str, str]],
    baseline_refs: _LocalRefResolver,
    current_refs: _LocalRefResolver,
) -> None:
    old_paths = baseline.get("paths", {})
    new_paths = current.get("paths", {})
    if not isinstance(old_paths, dict) or not isinstance(new_paths, dict):
        return
    for path, raw_old_item in old_paths.items():
        old_item = baseline_refs.resolve(raw_old_item)
        new_item = current_refs.resolve(new_paths.get(path))
        if not isinstance(old_item, dict):
            continue
        if new_item is None:
            _add(breaking, path, "接口路径已删除")
            continue
        if not isinstance(new_item, dict):
            _add(breaking, path, "接口路径定义无效")
            continue
        for method, raw_old_operation in old_item.items():
            if method.lower() not in _HTTP_METHODS:
                continue
            old_operation = baseline_refs.resolve(raw_old_operation)
            new_operation = current_refs.resolve(new_item.get(method))
            location = f"{method.upper()} {path}"
            if not isinstance(old_operation, dict):
                continue
            if not isinstance(new_operation, dict):
                _add(breaking, location, "接口操作已删除")
                continue
            _compare_parameters(old_operation, new_operation, location, breaking, warnings, baseline_refs, current_refs)
            _compare_request_body(old_operation, new_operation, location, breaking, baseline_refs, current_refs)
            _compare_responses(old_operation, new_operation, location, breaking, warnings, baseline_refs, current_refs)


def _parameter_map(raw_parameters: Any, resolver: _LocalRefResolver) -> dict[tuple[Any, Any], dict[str, Any]]:
    result: dict[tuple[Any, Any], dict[str, Any]] = {}
    for raw_item in raw_parameters if isinstance(raw_parameters, list) else []:
        item = resolver.resolve(raw_item)
        if isinstance(item, dict):
            result[(item.get("in"), item.get("name"))] = item
    return result


def _compare_parameters(
    old: dict[str, Any],
    new: dict[str, Any],
    location: str,
    breaking: list[dict[str, str]],
    warnings: list[dict[str, str]],
    old_refs: _LocalRefResolver,
    new_refs: _LocalRefResolver,
) -> None:
    old_params = _parameter_map(old.get("parameters"), old_refs)
    new_params = _parameter_map(new.get("parameters"), new_refs)
    for key, old_param in old_params.items():
        if key not in new_params:
            _add(breaking, f"{location} parameter {key[0]} {key[1]}", "请求参数已删除")
        elif not old_param.get("required", False) and new_params[key].get("required", False):
            _add(breaking, f"{location} parameter {key[0]} {key[1]}", "可选请求参数变为必填")
    for key, new_param in new_params.items():
        if key not in old_params and new_param.get("required", False):
            _add(warnings, f"{location} parameter {key[0]} {key[1]}", "新增必填请求参数", severity="warning")


def _compare_request_body(
    old: dict[str, Any],
    new: dict[str, Any],
    location: str,
    breaking: list[dict[str, str]],
    old_refs: _LocalRefResolver,
    new_refs: _LocalRefResolver,
) -> None:
    old_body = old_refs.resolve(old.get("requestBody", {}))
    new_body = new_refs.resolve(new.get("requestBody", {}))
    if not isinstance(old_body, dict) or not isinstance(new_body, dict):
        return
    if old_body and not new_body:
        _add(breaking, f"{location} requestBody", "请求体已删除")
    elif old_body and new_body and not old_body.get("required", False) and new_body.get("required", False):
        _add(breaking, f"{location} requestBody", "可选请求体变为必填")


def _compare_responses(
    old: dict[str, Any],
    new: dict[str, Any],
    location: str,
    breaking: list[dict[str, str]],
    warnings: list[dict[str, str]],
    old_refs: _LocalRefResolver,
    new_refs: _LocalRefResolver,
) -> None:
    old_responses = old.get("responses", {})
    new_responses = new.get("responses", {})
    if not isinstance(old_responses, dict) or not isinstance(new_responses, dict):
        return
    for status, raw_old_response in old_responses.items():
        if status not in new_responses and status != "default":
            _add(breaking, f"{location} response {status}", "响应状态码已删除")
            continue
        old_response = old_refs.resolve(raw_old_response)
        new_response = new_refs.resolve(new_responses.get(status))
        if not isinstance(old_response, dict) or not isinstance(new_response, dict):
            continue
        old_schema = _response_schema(old_response, old_refs)
        new_schema = _response_schema(new_response, new_refs)
        if old_schema and new_schema:
            _compare_schema(
                old_schema,
                new_schema,
                f"{location} response {status}",
                breaking,
                warnings,
                old_refs,
                new_refs,
            )


def _response_schema(response: dict[str, Any], resolver: _LocalRefResolver) -> dict[str, Any] | None:
    content = response.get("content", {})
    if isinstance(content, dict):
        for media in content.values():
            if isinstance(media, dict):
                schema = resolver.resolve(media.get("schema"))
                if isinstance(schema, dict):
                    return schema
    schema = resolver.resolve(response.get("schema"))
    return schema if isinstance(schema, dict) else None


def _compare_schema(
    old: Any,
    new: Any,
    location: str,
    breaking: list[dict[str, str]],
    warnings: list[dict[str, str]],
    old_refs: _LocalRefResolver | None = None,
    new_refs: _LocalRefResolver | None = None,
) -> None:
    if old_refs is not None:
        old = old_refs.resolve(old)
    if new_refs is not None:
        new = new_refs.resolve(new)
    if not isinstance(old, dict) or not isinstance(new, dict):
        return
    if old.get("type") and new.get("type") and old["type"] != new["type"]:
        _add(breaking, location, f"类型从 {old['type']} 变更为 {new['type']}")
        return
    old_required = set(old.get("required", []))
    new_required = set(new.get("required", []))
    for name in sorted(old_required - new_required):
        _add(breaking, f"{location}.{name}", "必填字段变为可选")
    for name in sorted(new_required - old_required):
        _add(warnings, f"{location}.{name}", "新增必填字段，可能影响旧客户端", severity="warning")
    old_properties = old.get("properties", {})
    new_properties = new.get("properties", {})
    if not isinstance(old_properties, dict) or not isinstance(new_properties, dict):
        return
    for name, old_property in old_properties.items():
        if name not in new_properties:
            _add(breaking, f"{location}.{name}", "字段已删除")
        else:
            _compare_schema(
                old_property,
                new_properties[name],
                f"{location}.{name}",
                breaking,
                warnings,
                old_refs,
                new_refs,
            )


def _add(target: list[dict[str, str]], location: str, message: str, *, severity: str = "breaking") -> None:
    target.append({"severity": severity, "location": location, "message": message})


_HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}
