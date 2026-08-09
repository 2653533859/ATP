"""AI 用例生成高层入口：调用 LLM + 解析输出。

对外只暴露 ``generate_case_drafts(config, request)``，由 API 层调用。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.core.encryption import decrypt
from app.models.ai_llm_config import AILLMConfig
from app.services.ai_governance import (
    check_and_incr_daily_limit,
    llm_extra_params,
    resolve_system_prompt,
)
from app.services.ai_case.llm_client import LLMRequest, call_llm
from app.services.ai_case.prompts import (
    SYSTEM_PROMPT,
    build_user_prompt,
    parse_llm_json_array,
)

logger = logging.getLogger(__name__)


@dataclass
class GenerationResult:
    drafts: list[dict[str, Any]]
    raw_text: str
    warnings: list[str]


def _coerce_step(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {"action": str(item) if item is not None else ""}
    return {
        "action": str(item.get("action") or "").strip(),
        "test_data": item.get("test_data"),
        "expected_result": item.get("expected_result"),
        "is_key_step": bool(item.get("is_key_step", False)),
        "remarks": item.get("remarks"),
    }


def _coerce_draft(
    item: dict[str, Any],
    *,
    default_case_type: str,
    default_priority: str,
    default_case_level: str,
    dataset_id: int | None = None,
    dataset_version: int | None = None,
) -> dict[str, Any]:
    name = (item.get("name") or "").strip() or "AI 生成用例"
    steps_raw = item.get("steps") or []
    if not isinstance(steps_raw, list):
        steps_raw = []
    return {
        "name": name,
        "summary": item.get("summary") or name,
        "description": item.get("description"),
        "case_type": item.get("case_type") or default_case_type,
        "priority": item.get("priority") or default_priority,
        "case_level": item.get("case_level") or default_case_level,
        "tags": list(item.get("tags") or []),
        "preconditions": list(item.get("preconditions") or []),
        "postconditions": list(item.get("postconditions") or []),
        "steps": [_coerce_step(s) for s in steps_raw if s is not None],
        "config": item.get("config") or {},
        "dataset_id": dataset_id,
        "dataset_version": dataset_version,
    }


async def generate_case_drafts(
    *,
    config: AILLMConfig,
    endpoints: list[dict[str, Any]],
    user_requirement: str,
    case_type: str,
    priority: str,
    case_level: str,
    max_cases: int,
    dataset_context: dict[str, Any] | None = None,
    mock_context: list[dict[str, Any]] | None = None,
    dataset_id: int | None = None,
    dataset_version: int | None = None,
) -> GenerationResult:
    """调用 LLM 并返回归一化后的用例草稿列表。"""
    if not config.enabled:
        raise ValueError("AI 配置已禁用")
    try:
        api_key = decrypt(config.api_key_encrypted)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("API Key 解密失败，请重新录入") from exc

    if not await check_and_incr_daily_limit(config=config, capability="ai_case_generation"):
        raise ValueError("AI 用例生成已达今日调用上限")

    user_prompt = build_user_prompt(
        endpoints=endpoints,
        user_requirement=user_requirement,
        case_type=case_type,
        priority=priority,
        case_level=case_level,
        max_cases=max_cases,
        dataset_context=dataset_context,
        mock_context=mock_context,
    )

    request = LLMRequest(
        provider=config.provider,
        api_key=api_key,
        model_name=config.model_name,
        prompt=user_prompt,
        endpoint=config.endpoint,
        system_prompt=resolve_system_prompt(config, "ai_case_generation", SYSTEM_PROMPT),
        extra_params=llm_extra_params(config),
    )
    response = await call_llm(request)

    warnings: list[str] = []
    try:
        items = parse_llm_json_array(response.text)
    except ValueError as exc:
        logger.warning("LLM 输出 JSON 解析失败: %s", exc)
        warnings.append(f"LLM 输出解析失败: {exc}")
        items = []

    drafts = [
        _coerce_draft(
            item,
            default_case_type=case_type,
            default_priority=priority,
            default_case_level=case_level,
            dataset_id=dataset_id,
            dataset_version=dataset_version,
        )
        for item in items
        if isinstance(item, dict)
    ][:max_cases]

    if not drafts:
        warnings.append("LLM 未生成有效用例")

    return GenerationResult(drafts=drafts, raw_text=response.text, warnings=warnings)
