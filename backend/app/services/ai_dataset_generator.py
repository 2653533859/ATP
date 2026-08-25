"""Generate synthetic dataset rows through the configured project LLM.

The service deliberately returns rows for user review instead of writing to the
database.  This keeps AI output reversible and lets the dataset editor apply
its normal schema validation and versioning path.
"""

from __future__ import annotations

import json
from typing import Any

from app.core.encryption import decrypt
from app.models.ai_llm_config import AILLMConfig
from app.services.ai_case.llm_client import LLMRequest, call_llm
from app.services.ai_governance import (
    check_and_incr_daily_limit,
    llm_extra_params,
    resolve_system_prompt,
)

_MAX_ROWS_BYTES = 256 * 1024

_DEFAULT_SYSTEM_PROMPT = (
    "你是测试数据生成器。根据字段定义和业务要求生成安全的合成测试数据。"
    "必须只输出 JSON 数组，数组每个元素都是对象；不要输出 Markdown、解释、真实个人信息、密钥或令牌。"
)


def _schema_text(schema_fields: list[dict[str, Any]]) -> str:
    if not schema_fields:
        return "（未提供字段定义，请根据业务要求推断少量、稳定的字段）"
    return json.dumps(schema_fields, ensure_ascii=False, indent=2)


def _build_prompt(*, schema_fields: list[dict[str, Any]], requirement: str, row_count: int) -> str:
    return (
        f"请生成 {row_count} 行测试数据。\n\n"
        f"字段定义：\n{_schema_text(schema_fields)}\n\n"
        f"业务要求：\n{requirement.strip() or '生成适合接口测试的正常、边界和异常混合数据'}\n\n"
        "规则：\n"
        "1. 只返回 JSON 数组，不要包裹代码围栏。\n"
        "2. 每行必须是 JSON 对象；字段名保持一致。\n"
        "3. 遵循字段 type、required 和 default；无法满足时使用安全的合成值。\n"
        "4. 不要生成真实姓名、身份证号、银行卡号、密码、API Key、Cookie 或其他可识别个人信息。\n"
        "5. 输出行数不超过要求，内容应适合直接粘贴到测试数据集编辑器。"
    )


def _parse_rows(text: str, row_count: int) -> tuple[list[dict[str, Any]], list[str]]:
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
        # 兼容少数模型返回 {"rows": [...]} 的情况，但仍要求数组内容。
        start = cleaned.find("{")
        end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("AI 返回中未找到 JSON 数据")
    try:
        parsed = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(f"AI 返回不是合法 JSON: {exc.msg}") from exc
    if isinstance(parsed, dict) and isinstance(parsed.get("rows"), list):
        parsed = parsed["rows"]
    if not isinstance(parsed, list) or not all(isinstance(row, dict) for row in parsed):
        raise ValueError("AI 返回必须是对象数组")
    rows = [dict(row) for row in parsed[:row_count]]
    if not rows:
        raise ValueError("AI 未生成有效数据行")
    warnings: list[str] = []
    if len(parsed) > row_count:
        warnings.append(f"AI 返回了 {len(parsed)} 行，已按请求限制保留前 {row_count} 行")
    serialized = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
    if len(serialized.encode("utf-8")) > _MAX_ROWS_BYTES:
        raise ValueError("AI 生成结果超过 256KB，请减少行数或缩短业务要求")
    return rows, warnings


def _infer_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int) and not isinstance(value, bool):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "string"


def infer_schema_fields(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Infer a compact editor schema when the user did not provide one."""
    names: list[str] = []
    for row in rows:
        for name in row:
            if name not in names:
                names.append(name)
    fields: list[dict[str, Any]] = []
    for name in names:
        sample = next((row[name] for row in rows if row.get(name) is not None), None)
        fields.append({"name": name, "type": _infer_type(sample), "required": False, "default": None})
    return fields


async def generate_dataset_rows(
    *,
    config: AILLMConfig,
    schema_fields: list[dict[str, Any]],
    requirement: str,
    row_count: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    if not config.enabled:
        raise ValueError("AI 配置已禁用")
    try:
        api_key = (
            ""
            if getattr(config, "provider", None) == "ollama" and not config.api_key_encrypted
            else decrypt(config.api_key_encrypted)
        )
    except Exception as exc:  # noqa: BLE001
        raise ValueError("API Key 解密失败，请重新录入") from exc
    if not await check_and_incr_daily_limit(config=config, capability="ai_dataset_generation"):
        raise ValueError("AI 测试数据生成已达今日调用上限")

    response = await call_llm(
        LLMRequest(
            provider=config.provider,
            api_key=api_key,
            model_name=config.model_name,
            prompt=_build_prompt(schema_fields=schema_fields, requirement=requirement, row_count=row_count),
            endpoint=config.endpoint,
            system_prompt=resolve_system_prompt(config, "ai_dataset_generation", _DEFAULT_SYSTEM_PROMPT),
            extra_params=llm_extra_params(config),
        )
    )
    rows, warnings = _parse_rows(response.text, row_count)
    normalized_schema = schema_fields or infer_schema_fields(rows)
    return rows, normalized_schema, warnings
