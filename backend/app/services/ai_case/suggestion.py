"""AI-driven and heuristic suggestion generator for test case assertions and extractions."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.models.ai_llm_config import AILLMConfig
from app.schemas.ai_case import (
    AIAssertionSuggestIn,
    AIAssertionSuggestOut,
    AIAssertionSuggestion,
    AIExtractionSuggestion,
)
from app.services.ai_case.llm_client import LLMRequest, call_llm
from app.services.ai_governance import check_and_incr_daily_limit, llm_extra_params

logger = logging.getLogger(__name__)


def _sanitize_json(val: Any) -> Any:
    if val is None or isinstance(val, (int, float, bool, list, dict)):
        return val
    if isinstance(val, str):
        val = val.strip()
        if (val.startswith("{") and val.endswith("}")) or (val.startswith("[") and val.endswith("]")):
            try:
                return json.loads(val)
            except Exception:
                pass
    return val


def heuristic_suggestions(
    method: str,
    url: str,
    status_code: int | None,
    response_body: Any,
) -> tuple[list[AIAssertionSuggestion], list[AIExtractionSuggestion]]:
    """Heuristic rule engine to derive high-precision assertions and extractions from actual API data."""
    assertions: list[AIAssertionSuggestion] = []
    extractions: list[AIExtractionSuggestion] = []
    method_upper = (method or "GET").upper()
    url_lower = (url or "").lower()
    sc = status_code if status_code and 100 <= status_code <= 599 else 200
    assertions.append(
        AIAssertionSuggestion(
            target="status_code",
            operator="eq",
            expected=str(sc),
            expression="",
            description=f"校验 HTTP 状态码为 {sc}",
        )
    )

    body = _sanitize_json(response_body)

    if isinstance(body, dict):
        # 2. Check top-level business status fields
        for field, desc in [
            ("code", "业务响应码为预期值"),
            ("status", "业务状态标识"),
            ("success", "业务执行成功标识"),
            ("errorCode", "错误代码"),
            ("errcode", "接口响应码"),
        ]:
            if field in body and not isinstance(body[field], (dict, list)):
                val = body[field]
                expected_str = str(val).lower() if isinstance(val, bool) else str(val)
                assertions.append(
                    AIAssertionSuggestion(
                        target="body",
                        operator="eq",
                        expected=expected_str,
                        expression=f"$.{field}",
                        description=f"校验 {desc}",
                    )
                )

        # 3. Check message / msg fields
        for msg_field in ["message", "msg", "detail", "description"]:
            if msg_field in body and isinstance(body[msg_field], str) and body[msg_field].strip():
                assertions.append(
                    AIAssertionSuggestion(
                        target="body",
                        operator="contains",
                        expected=body[msg_field].strip()[:30],
                        expression=f"$.{msg_field}",
                        description="校验返回提示文本包含关键信息",
                    )
                )

        # 4. Deep search for token & business ID fields for extraction & existence assertion
        def walk(obj: Any, prefix: str, depth: int) -> None:
            if depth > 4 or not isinstance(obj, dict):
                return
            for k, v in obj.items():
                current_path = f"{prefix}.{k}" if prefix else k

                # Token-like fields -> Extract & Assert
                if re.search(r"(?i)(token|jwt|ticket|auth_token|access_token|session_id)$", str(k)):
                    if isinstance(v, (str, int)) and str(v).strip():
                        extractions.append(
                            AIExtractionSuggestion(
                                variable=k,
                                type="jsonpath",
                                expression=f"$.{current_path}",
                                description="提取认证 Token 供下游接口鉴权依赖",
                            )
                        )
                        assertions.append(
                            AIAssertionSuggestion(
                                target="body",
                                operator="exists",
                                expected="",
                                expression=f"$.{current_path}",
                                description="校验认证 Token 字段存在且非空",
                            )
                        )

                # ID-like fields -> Extract & Assert
                elif re.search(r"(?i)(id|uuid|user_id|userId|order_id|orderId|trade_no|tradeNo)$", str(k)):
                    if isinstance(v, (str, int)) and str(v).strip():
                        extractions.append(
                            AIExtractionSuggestion(
                                variable=k,
                                type="jsonpath",
                                expression=f"$.{current_path}",
                                description=f"提取业务标识 {k} 供后续链路依赖",
                            )
                        )
                        assertions.append(
                            AIAssertionSuggestion(
                                target="body",
                                operator="exists",
                                expected="",
                                expression=f"$.{current_path}",
                                description=f"校验关键业务标识 {k} 存在",
                            )
                        )

                # List-like data -> Assert exists
                elif isinstance(v, list) and k in ("data", "list", "items", "records", "results", "rows"):
                    assertions.append(
                        AIAssertionSuggestion(
                            target="body",
                            operator="exists",
                            expected="",
                            expression=f"$.{current_path}",
                            description=f"校验数据列表 {k} 存在",
                        )
                    )
                    # Check first element of list
                    if v and isinstance(v[0], dict):
                        walk(v[0], f"{current_path}[0]", depth + 1)
                elif isinstance(v, dict):
                    walk(v, current_path, depth + 1)

        walk(body, "", 1)

    elif isinstance(body, list) and body and isinstance(body[0], dict):
        assertions.append(
            AIAssertionSuggestion(
                target="body",
                operator="exists",
                expected="",
                expression="$[0]",
                description="校验返回列表数据非空",
            )
        )

    # Deduplicate assertions by (target, expression, operator)
    seen_assert: set[tuple[str, str, str]] = set()
    deduped_assertions: list[AIAssertionSuggestion] = []
    for a in assertions:
        key = (a.target, a.expression, a.operator)
        if key not in seen_assert:
            seen_assert.add(key)
            deduped_assertions.append(a)

    # Deduplicate extractions by variable
    seen_vars: set[str] = set()
    deduped_extractions: list[AIExtractionSuggestion] = []
    for e in extractions:
        if e.variable not in seen_vars:
            seen_vars.add(e.variable)
            deduped_extractions.append(e)

    return deduped_assertions, deduped_extractions


_LLM_SUGGESTION_PROMPT = """你是一个资深的 API 自动化测试专家。
请根据以下接口信息和真实响应内容，分析并推荐最核心的测试断言（Assertions）与变量提取（Extractions）。

【接口方法】{method}
【接口URL】{url}
【状态码】{status_code}
【响应内容预览】
{response_body}

请输出严格的 JSON 对象，必须包含 assertions 和 extractions 两个数组，格式如下：
{{
  "assertions": [
    {{
      "target": "status_code" | "body" | "header",
      "operator": "eq" | "contains" | "exists",
      "expected": "期望值字符串",
      "expression": "定位表达式，body用JSONPath如 $.code 或 $.data.token",
      "description": "说明该断言的业务目的"
    }}
  ],
  "extractions": [
    {{
      "variable": "变量名称如 token / userId / orderId",
      "type": "jsonpath",
      "expression": "JSONPath定位表达式如 $.data.token",
      "description": "说明该变量提取的用途"
    }}
  ]
}}

要求：
1. 断言必须精准、关键，覆盖状态码、业务返回码和核心数据。
2. 变量提取必须聚焦于后续接口可能依赖的 token、ID、凭证、订单号等关键字段。
3. 只能输出纯 JSON，严禁输出任何 Markdown 标记或多余解释文字。
"""


async def suggest_assertions_and_extractions(
    body: AIAssertionSuggestIn,
    config: AILLMConfig | None,
    api_key: str,
) -> AIAssertionSuggestOut:
    """Combines heuristic analysis with optional LLM reasoning to produce assertion and extraction recommendations."""
    # 1. Base heuristic suggestions from real data
    h_assertions, h_extractions = heuristic_suggestions(
        method=body.method,
        url=body.url,
        status_code=body.status_code,
        response_body=body.response_body,
    )

    if not config or not config.enabled:
        return AIAssertionSuggestOut(
            assertions=h_assertions,
            extractions=h_extractions,
            source="heuristic",
        )

    # 2. Try LLM enhancement
    try:
        if not await check_and_incr_daily_limit(config=config, capability="ai_case_suggest"):
            return AIAssertionSuggestOut(assertions=h_assertions, extractions=h_extractions, source="heuristic")

        body_preview = ""
        if body.response_body is not None:
            if isinstance(body.response_body, (dict, list)):
                body_preview = json.dumps(body.response_body, ensure_ascii=False)[:3000]
            else:
                body_preview = str(body.response_body)[:3000]

        prompt = _LLM_SUGGESTION_PROMPT.format(
            method=body.method,
            url=body.url,
            status_code=body.status_code or 200,
            response_body=body_preview or "（无响应体）",
        )

        resp = await call_llm(
            LLMRequest(
                provider=config.provider,
                api_key=api_key,
                model_name=config.model_name,
                prompt=prompt,
                endpoint=config.endpoint,
                system_prompt="你是一个输出严格 JSON 数据的 API 测试专家。",
                timeout_seconds=30.0,
                extra_params=llm_extra_params(config),
            )
        )

        clean_text = resp.text.strip()
        if clean_text.startswith("```"):
            clean_text = re.sub(r"^```[a-zA-Z]*\n?", "", clean_text)
            clean_text = re.sub(r"\n?```$", "", clean_text).strip()

        data = json.loads(clean_text)
        if isinstance(data, dict):
            llm_assertions: list[AIAssertionSuggestion] = []
            for item in data.get("assertions") or []:
                if isinstance(item, dict) and item.get("operator"):
                    llm_assertions.append(
                        AIAssertionSuggestion(
                            target=item.get("target") or "body",
                            operator=item.get("operator") or "eq",
                            expected=str(item.get("expected") or ""),
                            expression=str(item.get("expression") or ""),
                            description=str(item.get("description") or ""),
                        )
                    )

            llm_extractions: list[AIExtractionSuggestion] = []
            for item in data.get("extractions") or []:
                if isinstance(item, dict) and item.get("variable"):
                    llm_extractions.append(
                        AIExtractionSuggestion(
                            variable=str(item.get("variable")),
                            type=item.get("type") or "jsonpath",
                            expression=str(item.get("expression") or ""),
                            description=str(item.get("description") or ""),
                        )
                    )

            if llm_assertions or llm_extractions:
                # Merge: ensure status_code is retained
                if not any(a.target == "status_code" for a in llm_assertions) and h_assertions:
                    llm_assertions.insert(0, h_assertions[0])

                return AIAssertionSuggestOut(
                    assertions=llm_assertions or h_assertions,
                    extractions=llm_extractions or h_extractions,
                    source="llm",
                )
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM assertion suggestion failed, falling back to heuristic: error=%s", type(exc).__name__)

    return AIAssertionSuggestOut(
        assertions=h_assertions,
        extractions=h_extractions,
        source="heuristic",
    )
