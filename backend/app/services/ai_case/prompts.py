"""AI 用例生成 prompt 模板。

设计：构造一段 system + user prompt，要求 LLM 输出 **严格 JSON 数组**，
便于后续解析为 AICaseDraft。
"""

from __future__ import annotations

import json
from typing import Any

SYSTEM_PROMPT = (
    "你是资深的软件测试工程师，擅长基于 OpenAPI、接口样例和自然语言需求产出可执行的接口测试用例。"
    "请按用户提供的接口定义、请求/响应样例与业务需求生成多条可编辑用例草稿，并严格按 JSON 数组格式输出，"
    "数组每个元素是一个用例。除 JSON 外，不要输出任何解释、Markdown 围栏或多余文字。"
)


_USER_TEMPLATE = (
    "## 任务背景\n"
    "我需要基于以下接口定义/接口样例/自然语言需求生成 {max_cases} 条测试用例草稿（含正向、异常、边界）。\n\n"
    "## 业务需求（可能为空）\n{user_requirement}\n\n"
    "## 接口清单\n{endpoints_block}\n\n"
    "## 已选择的测试数据集（内容已脱敏，可用字段请优先生成 {{{{字段名}}}} 占位符）\n{dataset_block}\n\n"
    "## 已选择的 Mock 服务规则（可用于生成请求路径、响应断言和异常场景）\n{mock_block}\n\n"
    "## 输出规范\n"
    "- 输出一个 JSON 数组，元素为对象，字段：name, summary, description, "
    "case_type, priority, case_level, tags, preconditions, postconditions, steps, config\n"
    "- steps 是数组，每个元素含 action（必填）, test_data, expected_result, is_key_step, remarks\n"
    "- 如果只提供自然语言需求，也要补全可编辑步骤，并在 action/test_data/expected_result 中写清接口动作、关键参数和断言\n"
    "- 如果提供请求/响应样例，优先从样例提取字段、状态码、边界值、错误码和断言点\n"
    "- 如果提供测试数据集上下文，API 请求中的可变字段优先使用 {{{{字段名}}}} 占位符，并保持字段名与数据集一致\n"
    "- 如果提供 Mock 规则上下文，优先使用其 method/path/status_code/response_body 生成请求和断言；不要臆造未提供的密钥\n"
    "- 上下文中的 [已脱敏] 只能作为占位提示，禁止还原或猜测真实敏感值\n"
    '- case_type 必须是 "{case_type}"\n'
    '- priority 必须是 "{priority}"\n'
    '- case_level 必须是 "{case_level}"\n'
    "- 用例名 name 要求简短可读，描述测试意图\n"
    "- 不要在 JSON 外输出任何其它内容\n"
)


def _format_endpoint(endpoint: dict) -> str:
    method = endpoint.get("method", "GET")
    path = endpoint.get("path", "/")
    summary = endpoint.get("summary") or ""
    parts = [f"- `{method} {path}`"]
    if summary:
        parts.append(f"  - 描述: {summary}")
    params = endpoint.get("parameters") or []
    if params:
        parts.append("  - 参数:")
        for p in params:
            required = "必填" if p.get("required") else "可选"
            parts.append(
                f"    - [{p.get('location', '?')}] {p.get('name', '')} ({required})" f" - {p.get('description') or ''}"
            )
    if endpoint.get("request_body_example") is not None:
        example = json.dumps(endpoint["request_body_example"], ensure_ascii=False)
        if len(example) > 400:
            example = example[:400] + "…"
        parts.append(f"  - 请求体示例: {example}")
    if endpoint.get("response_example") is not None:
        example = json.dumps(endpoint["response_example"], ensure_ascii=False)
        if len(example) > 400:
            example = example[:400] + "…"
        parts.append(f"  - 响应示例: {example}")
    return "\n".join(parts)


def build_user_prompt(
    *,
    endpoints: list[dict],
    user_requirement: str,
    case_type: str,
    priority: str,
    case_level: str,
    max_cases: int,
    dataset_context: dict[str, Any] | None = None,
    mock_context: list[dict[str, Any]] | None = None,
) -> str:
    """生成提交给 LLM 的用户 prompt。"""
    if not endpoints:
        endpoints_block = "(未提供接口，仅根据需求生成)"
    else:
        endpoints_block = "\n".join(_format_endpoint(e) for e in endpoints)
    dataset_block = json.dumps(dataset_context, ensure_ascii=False, indent=2) if dataset_context else "(未选择)"
    mock_block = json.dumps(mock_context, ensure_ascii=False, indent=2) if mock_context else "(未选择)"
    return _USER_TEMPLATE.format(
        max_cases=max_cases,
        user_requirement=(user_requirement or "(无)").strip(),
        endpoints_block=endpoints_block,
        dataset_block=dataset_block,
        mock_block=mock_block,
        case_type=case_type,
        priority=priority,
        case_level=case_level,
    )


def parse_llm_json_array(text: str) -> list[dict[str, Any]]:
    """从 LLM 输出文本中提取 JSON 数组。

    宽容处理：去除 Markdown 围栏，截取第一个 [ 到最后一个 ]。
    解析失败时抛出 ValueError。
    """
    if not text:
        raise ValueError("LLM 返回为空")
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("LLM 输出中未找到 JSON 数组")
    payload = cleaned[start : end + 1]
    parsed = json.loads(payload)
    if not isinstance(parsed, list):
        raise ValueError("LLM 输出 JSON 不是数组")
    return parsed
