"""Generate editable Mock rule drafts through the configured project LLM."""

from __future__ import annotations

import json
from typing import Any

from app.core.encryption import decrypt
from app.models.ai_llm_config import AILLMConfig
from app.models.mock import MockMethod
from app.services.ai_case.context import build_mock_rule_context
from app.services.ai_case.llm_client import LLMRequest, call_llm
from app.services.ai_governance import (
    check_and_incr_daily_limit,
    llm_extra_params,
    resolve_system_prompt,
)

_MAX_RULES_BYTES = 256 * 1024

_DEFAULT_SYSTEM_PROMPT = (
    "你是 Mock 服务规则生成器。根据接口规则和业务要求生成安全、可编辑的合成 Mock 规则。"
    "只输出 JSON 数组，不要输出 Markdown、解释、密钥、Cookie 或真实个人信息。"
)


def _build_prompt(*, rule_context: list[dict[str, Any]], requirement: str, rule_count: int) -> str:
    context = json.dumps(rule_context, ensure_ascii=False, indent=2)
    return (
        f"请生成 {rule_count} 条 Mock 规则。\n\n"
        f"已有规则参考（可能为空）：\n{context}\n\n"
        f"业务要求：\n{requirement.strip() or '生成覆盖成功、参数边界和常见异常的接口 Mock 响应'}\n\n"
        "输出要求：\n"
        "1. 只输出 JSON 数组，每个元素必须是对象。\n"
        "2. 每个对象包含 name、method、path、status_code、response_headers、response_body、"
        "match_conditions、delay_ms、is_enabled、render_template、record_requests。\n"
        "3. method 只能是 GET、POST、PUT、DELETE、PATCH 或 ANY；path 必须以 / 开头。\n"
        "4. response_body 使用 JSON 字符串；match_conditions 必须包含 query、headers、body 对象。\n"
        "5. 生成合成数据，不要使用真实姓名、身份证号、银行卡号、密码、API Key、Cookie 或 Token。\n"
        "6. 不要生成可执行脚本或模板表达式；render_template 默认 false。"
    )


def _parse_json_array(text: str, rule_count: int) -> list[dict[str, Any]]:
    if not text or not text.strip():
        raise ValueError("AI 返回为空")
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].lstrip()
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start < 0 or end <= start:
        raise ValueError("AI 返回中未找到 JSON 数组")
    try:
        parsed = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(f"AI 返回不是合法 JSON: {exc.msg}") from exc
    if not isinstance(parsed, list) or not all(isinstance(item, dict) for item in parsed):
        raise ValueError("AI 返回必须是对象数组")
    rules = [_coerce_rule(item) for item in parsed[:rule_count]]
    if not rules:
        raise ValueError("AI 未生成有效 Mock 规则")
    serialized = json.dumps(rules, ensure_ascii=False, separators=(",", ":"))
    if len(serialized.encode("utf-8")) > _MAX_RULES_BYTES:
        raise ValueError("AI 生成结果超过 256KB，请减少规则数量或缩短响应体")
    return rules


def _coerce_rule(item: dict[str, Any]) -> dict[str, Any]:
    method_value = str(item.get("method") or "GET").upper()
    if method_value not in {method.value for method in MockMethod}:
        method_value = MockMethod.GET.value
    path = str(item.get("path") or "/api/generated").strip() or "/api/generated"
    path = "/" + path.lstrip("/")
    response_body = item.get("response_body")
    if response_body is not None and not isinstance(response_body, str):
        response_body = json.dumps(response_body, ensure_ascii=False)
    match_conditions = item.get("match_conditions")
    if not isinstance(match_conditions, dict):
        match_conditions = {}

    def _string_dict(value: Any) -> dict[str, str]:
        if not isinstance(value, dict):
            return {}
        return {str(key): str(item_value) for key, item_value in value.items() if item_value is not None}

    match_conditions = {
        "query": _string_dict(match_conditions.get("query")),
        "headers": _string_dict(match_conditions.get("headers")),
        "body": _string_dict(match_conditions.get("body")),
    }
    headers = item.get("response_headers")
    if not isinstance(headers, dict):
        headers = {"Content-Type": "application/json"}
    else:
        headers = {str(key): str(item_value) for key, item_value in headers.items() if item_value is not None}

    def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
        try:
            return max(minimum, min(maximum, int(value)))
        except (TypeError, ValueError):
            return default

    return {
        "name": str(item.get("name") or "AI 生成 Mock 规则").strip()[:128] or "AI 生成 Mock 规则",
        "method": method_value,
        "path": path,
        "status_code": _bounded_int(item.get("status_code") or 200, 200, 100, 599),
        "response_headers": headers,
        "response_body": response_body,
        "match_conditions": match_conditions,
        "delay_ms": _bounded_int(item.get("delay_ms") or 0, 0, 0, 30_000),
        "is_enabled": bool(item.get("is_enabled", True)),
        "render_template": bool(item.get("render_template", False)),
        "record_requests": bool(item.get("record_requests", False)),
    }


async def generate_mock_rule_drafts(
    *,
    config: AILLMConfig,
    source_rules: list[Any],
    requirement: str,
    rule_count: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    if not config.enabled:
        raise ValueError("AI 配置已禁用")
    try:
        api_key = decrypt(config.api_key_encrypted)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("API Key 解密失败，请重新录入") from exc
    if not await check_and_incr_daily_limit(config=config, capability="ai_mock_generation"):
        raise ValueError("AI Mock 生成已达今日调用上限")

    response = await call_llm(
        LLMRequest(
            provider=config.provider,
            api_key=api_key,
            model_name=config.model_name,
            prompt=_build_prompt(
                rule_context=[build_mock_rule_context(rule) for rule in source_rules],
                requirement=requirement,
                rule_count=rule_count,
            ),
            endpoint=config.endpoint,
            system_prompt=resolve_system_prompt(config, "ai_mock_generation", _DEFAULT_SYSTEM_PROMPT),
            extra_params=llm_extra_params(config),
        )
    )
    rules = _parse_json_array(response.text, rule_count)
    warnings: list[str] = []
    if len(rules) < rule_count:
        warnings.append(f"AI 仅生成 {len(rules)} 条规则，少于请求的 {rule_count} 条")
    return rules, warnings
