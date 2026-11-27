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
    AIScenarioBatchStepSuggestion,
    AIScenarioBatchSuggestOut,
)
from app.services.ai_case.llm_client import LLMRequest, call_llm
from app.services.ai_case.outbound_sanitizer import (
    OutboundSanitizer,
    build_safe_response_schema_summary,
    is_business_result_path,
    is_dynamic_field_path,
)
from app.services.ai_governance import check_and_incr_daily_limit, llm_extra_params

logger = logging.getLogger(__name__)

MAX_SUGGESTIONS_DEFAULT = 6
MAX_SUGGESTIONS_WITH_GOAL = 8


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


def _response_path(body: Any, expression: str) -> tuple[bool, Any]:
    """Resolve the simple JSON paths supported by ATP's scenario editor."""
    if expression == "$":
        return True, body
    if not expression.startswith("$.") and not expression.startswith("$["):
        return False, None
    parts = re.findall(r"[^.\[\]]+|\[\d+\]", expression[1:])
    if not parts:
        return False, None
    current = body
    for part in parts:
        if part.startswith("["):
            index = int(part[1:-1])
            if not isinstance(current, list) or index >= len(current):
                return False, None
            current = current[index]
        elif isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return False, None
    return True, current


def _suggestion_matches_response(suggestion: AIAssertionSuggestion, body: AIAssertionSuggestIn) -> bool:
    found: bool = False
    actual: Any = None
    if suggestion.target == "status_code":
        found, actual = body.status_code is not None, body.status_code
    elif suggestion.target == "header":
        headers = {key.lower(): value for key, value in (body.response_headers or {}).items()}
        found = suggestion.expression.lower() in headers
        actual = headers.get(suggestion.expression.lower())
    elif suggestion.target == "body":
        if suggestion.expression:
            found, actual = _response_path(_sanitize_json(body.response_body), suggestion.expression)
        else:
            found, actual = body.response_body is not None, body.response_body
    else:
        return False
    if not found:
        return False
    if suggestion.operator == "exists":
        return actual is not None and actual != ""
    if isinstance(actual, (dict, list)):
        return False
    actual_text = str(actual).lower() if isinstance(actual, bool) else str(actual)
    expected = suggestion.expected
    if suggestion.operator == "eq":
        return actual_text == expected
    if suggestion.operator == "ne":
        return actual_text != expected
    if suggestion.operator == "contains":
        return expected in actual_text and bool(expected)
    if suggestion.operator in {"gt", "lt"}:
        try:
            actual_number, expected_number = float(actual_text), float(expected)
        except ValueError:
            return False
        return actual_number > expected_number if suggestion.operator == "gt" else actual_number < expected_number
    return False


def _extraction_matches_response(suggestion: AIExtractionSuggestion, body: AIAssertionSuggestIn) -> bool:
    if suggestion.type == "jsonpath":
        found, value = _response_path(_sanitize_json(body.response_body), suggestion.expression)
        return found and value is not None
    if suggestion.type == "header":
        return suggestion.expression.lower() in {key.lower() for key in (body.response_headers or {})}
    if suggestion.type == "regex":
        try:
            return re.search(suggestion.expression, str(body.response_body or "")) is not None
        except re.error:
            return False
    return False


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
请仅根据以下已脱敏的接口响应结构元数据（不含任何业务明文值、URL、Header 或 Cookie）以及可选业务目标，推荐最核心的测试断言（Assertions）与变量提取（Extractions）。

【接口方法】{method}
【HTTP 状态码】{status_code}
【业务目标】{business_goal}
【下游依赖字段】{downstream_refs}
【响应字段结构元数据（仅路径与类型）】
{schema_summary}

请输出严格的 JSON 对象，必须包含 assertions 和 extractions 两个数组，格式如下：
{{
  "assertions": [
    {{
      "target": "status_code" | "body",
      "operator": "eq" | "ne" | "contains" | "exists",
      "expected": "期望值字符串（exists 留空）",
      "expression": "定位表达式，body 用 JSONPath 如 $.code 或 $.data.token",
      "description": "说明该断言的业务目的"
    }}
  ],
  "extractions": [
    {{
      "variable": "变量名称如 token / userId / orderId",
      "type": "jsonpath",
      "expression": "JSONPath 定位表达式如 $.data.token",
      "description": "说明该变量提取的用途"
    }}
  ]
}}

要求：
1. 对 ID/UUID/Token/时间戳/订单号等每次运行变化的动态字段，严禁使用 eq 固定值，必须使用 exists。
2. 未提供业务目标时，不要猜测普通业务字段的固定文本值，优先校验状态码、业务状态字段与关键结构存在性。
3. 最多输出 {max_suggestions} 条最有价值的断言，只能输出纯 JSON，严禁输出 Markdown 标记或额外文字。
"""


def _filter_existing_rules(
    assertions: list[AIAssertionSuggestion],
    extractions: list[AIExtractionSuggestion],
    existing_assertions: list[dict[str, Any]] | None,
    existing_extractions: list[dict[str, Any]] | None,
) -> tuple[list[AIAssertionSuggestion], list[AIExtractionSuggestion]]:
    if not existing_assertions and not existing_extractions:
        return assertions, extractions

    filtered_assertions = assertions
    if existing_assertions:
        filtered_assertions = []
        for a in assertions:
            is_dup = False
            for ex in existing_assertions:
                if not isinstance(ex, dict):
                    continue
                t = ex.get("target") or "body"
                exp = str(ex.get("expression") or ex.get("property") or "")
                raw_expected = ex.get("expected") if "expected" in ex else ex.get("value")
                expected_str = str(raw_expected) if raw_expected is not None else ""
                if (
                    t == "status_code"
                    and a.target == "status_code"
                    and (raw_expected is None or expected_str == a.expected)
                ):
                    is_dup = True
                    break
                if (
                    t == a.target
                    and exp == a.expression
                    and (
                        (a.operator == "exists" and (ex.get("operator") or "") == "exists")
                        or raw_expected is None
                        or expected_str == a.expected
                    )
                ):
                    is_dup = True
                    break
            if not is_dup:
                filtered_assertions.append(a)

    filtered_extractions = extractions
    if existing_extractions:
        existing_vars = {
            str(ex.get("variable") or ex.get("name") or "") for ex in existing_extractions if isinstance(ex, dict)
        }
        filtered_extractions = [e for e in extractions if e.variable not in existing_vars]

    return filtered_assertions, filtered_extractions


def _assertion_priority_score(
    item: AIAssertionSuggestion,
    downstream_refs: set[str],
) -> tuple[int, int]:
    """Higher score = higher value: downstream referenced > status_code > business result > shallow depth."""
    expr = item.expression or ""
    depth = expr.count(".") + expr.count("[") if expr else 0
    if expr and expr in downstream_refs:
        return (100, -depth)
    if item.target == "status_code":
        return (85, 0)
    if item.target == "body" and is_business_result_path(expr):
        return (80, -depth)
    return (max(10, 40 - depth * 5), -depth)


def _guard_verify_and_rank_assertions(
    candidates: list[AIAssertionSuggestion],
    body: AIAssertionSuggestIn,
    *,
    has_goal: bool,
) -> tuple[list[AIAssertionSuggestion], int, list[str], int]:
    """Deterministically verify candidates against real response, guard dynamic fields, merge & cap."""
    filtered_reasons: list[str] = []
    filtered_count = 0
    verified: list[AIAssertionSuggestion] = []

    for item in candidates:
        candidate = item.model_copy()
        # 1. Dynamic field guard: disallow fixed eq/contains on dynamic per-run identifiers/timestamps
        if (
            candidate.target == "body"
            and is_dynamic_field_path(candidate.expression)
            and candidate.operator in {"eq", "contains"}
        ):
            downgraded = candidate.model_copy(
                update={
                    "operator": "exists",
                    "expected": "",
                    "description": f"{candidate.description or '校验动态字段存在'}（动态字段自动转为存在性校验）",
                }
            )
            if _suggestion_matches_response(downgraded, body):
                filtered_reasons.append(f"字段 {candidate.expression} 为动态值，已将固定等值自动改为 exists 校验")
                candidate = downgraded
            else:
                filtered_count += 1
                filtered_reasons.append(f"已过滤动态字段 {candidate.expression} 的固定值建议")
                continue

        # 2. Without explicit business goal, disallow fixed text assertions on arbitrary non-business-result fields
        if (
            not has_goal
            and candidate.target == "body"
            and candidate.operator in {"eq", "contains"}
            and not is_business_result_path(candidate.expression)
        ):
            filtered_count += 1
            filtered_reasons.append(f"未指定业务目标，已过滤非状态字段 {candidate.expression} 的固定值建议")
            continue

        # 3. Deterministic self-verification against real response
        if not _suggestion_matches_response(candidate, body):
            filtered_count += 1
            filtered_reasons.append(
                f"建议 [{candidate.target}:{candidate.expression or candidate.operator}] 在当前真实响应上未通过，已过滤"
            )
            continue

        verified.append(candidate)

    # 4. Merge same-field rules (prefer stronger eq/contains over exists on the same expression)
    by_field: dict[tuple[str, str], AIAssertionSuggestion] = {}
    for item in verified:
        field_key = (item.target, item.expression)
        prev = by_field.get(field_key)
        if prev is None:
            by_field[field_key] = item
        elif prev.operator == "exists" and item.operator != "exists":
            by_field[field_key] = item

    downstream_refs = {str(p).strip() for p in (body.downstream_referenced_paths or []) if str(p).strip()}
    ranked = sorted(
        by_field.values(),
        key=lambda a: _assertion_priority_score(a, downstream_refs),
        reverse=True,
    )

    cap = MAX_SUGGESTIONS_WITH_GOAL if has_goal else MAX_SUGGESTIONS_DEFAULT
    truncated_count = max(0, len(ranked) - cap)
    if truncated_count > 0:
        filtered_reasons.append(f"按价值排序保留前 {cap} 条建议，已折叠 {truncated_count} 条低优先级建议")
    return ranked[:cap], filtered_count, filtered_reasons[:10], truncated_count


async def suggest_assertions_and_extractions(
    body: AIAssertionSuggestIn,
    config: AILLMConfig | None,
    api_key: str,
) -> AIAssertionSuggestOut:
    """Combines heuristic analysis with whitelist-sanitized LLM reasoning and deterministic self-verification."""
    has_goal = bool((body.business_goal or "").strip())

    # 1. Base heuristic suggestions from real data
    raw_h_assertions, raw_h_extractions = heuristic_suggestions(
        method=body.method,
        url=body.url,
        status_code=body.status_code,
        response_body=body.response_body,
    )
    h_assertions, h_filtered, h_reasons, h_truncated = _guard_verify_and_rank_assertions(
        raw_h_assertions,
        body,
        has_goal=has_goal,
    )
    before_h_len = len(h_assertions)
    h_assertions, h_extractions = _filter_existing_rules(
        h_assertions, raw_h_extractions, body.existing_assertions, body.existing_extractions
    )
    h_exists_cnt = max(0, before_h_len - len(h_assertions))

    if not config or not config.enabled:
        return AIAssertionSuggestOut(
            assertions=h_assertions,
            extractions=h_extractions,
            source="heuristic",
            filtered_count=h_filtered,
            filtered_reasons=h_reasons,
            already_exists_count=h_exists_cnt,
            truncated_count=h_truncated,
        )

    # 2. Try LLM enhancement with strict WHITELIST outbound schema metadata (zero raw JSON values / URL / headers)
    try:
        if not await check_and_incr_daily_limit(config=config, capability="ai_case_suggest"):
            return AIAssertionSuggestOut(
                assertions=h_assertions,
                extractions=h_extractions,
                source="heuristic",
                filtered_count=h_filtered,
                filtered_reasons=h_reasons,
                already_exists_count=h_exists_cnt,
                truncated_count=h_truncated,
            )

        sanitizer = OutboundSanitizer(
            secrets=body.secret_values or [],
            documents=[body.response_body, body.request_body, body.response_headers],
        )
        parsed_body = _sanitize_json(body.response_body)
        if parsed_body is None:
            schema_summary_text = "（无响应体）"
        elif isinstance(parsed_body, (dict, list)):
            schema_summary = build_safe_response_schema_summary(body.status_code, parsed_body, sanitizer)
            schema_summary_text = json.dumps(schema_summary, ensure_ascii=False)[:4000]
        else:
            schema_summary_text = sanitizer.scrub_text(parsed_body, limit=500)

        safe_goal = sanitizer.scrub_text(body.business_goal, limit=400) if has_goal else "（未提供，仅校验状态与结构）"
        safe_downstream = [
            p
            for p in (body.downstream_referenced_paths or [])
            if isinstance(p, str) and sanitizer.allowed_field_name(p.rsplit(".", 1)[-1])
        ]
        max_cap = MAX_SUGGESTIONS_WITH_GOAL if has_goal else MAX_SUGGESTIONS_DEFAULT

        prompt = _LLM_SUGGESTION_PROMPT.format(
            method=(body.method or "GET").upper(),
            status_code=body.status_code or 200,
            business_goal=safe_goal,
            downstream_refs=", ".join(safe_downstream) if safe_downstream else "无",
            schema_summary=schema_summary_text,
            max_suggestions=max_cap,
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

            verified_a, filtered_cnt, reasons, truncated_cnt = _guard_verify_and_rank_assertions(
                llm_assertions,
                body,
                has_goal=has_goal,
            )
            verified_e = [item for item in llm_extractions if _extraction_matches_response(item, body)]

            if verified_a or verified_e:
                sc_rule = next((a for a in h_assertions if a.target == "status_code"), None)
                if sc_rule and not any(a.target == "status_code" for a in verified_a):
                    verified_a.insert(0, sc_rule)
                base_a = verified_a or h_assertions
                final_a, final_e = _filter_existing_rules(
                    base_a,
                    verified_e or h_extractions,
                    body.existing_assertions,
                    body.existing_extractions,
                )
                exists_cnt = max(0, len(base_a) - len(final_a))
                return AIAssertionSuggestOut(
                    assertions=final_a,
                    extractions=final_e,
                    source="llm",
                    filtered_count=filtered_cnt,
                    filtered_reasons=reasons,
                    already_exists_count=exists_cnt,
                    truncated_count=truncated_cnt,
                )
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM assertion suggestion failed, falling back to heuristic: error=%s", type(exc).__name__)

    return AIAssertionSuggestOut(
        assertions=h_assertions,
        extractions=h_extractions,
        source="heuristic",
        filtered_count=h_filtered,
        filtered_reasons=h_reasons,
        already_exists_count=h_exists_cnt,
        truncated_count=h_truncated,
    )


def _classify_step_failure_kind(step_result: dict[str, Any] | None, cached_response: dict[str, Any] | None) -> str:
    """Deterministically classify whether a step failed due to response_error vs assertion_mismatch."""
    if not step_result:
        return "not_executed"
    status = str(step_result.get("status") or "")
    if status == "error" or cached_response is None:
        return "response_error"
    sc = cached_response.get("status_code")
    resp_body = cached_response.get("body")
    if isinstance(sc, int) and sc >= 400:
        return "response_error"
    if not isinstance(resp_body, (dict, list)):
        return "response_error"
    if status == "failed":
        return "assertion_mismatch"
    return "none"


def _collect_downstream_extracted_paths(steps: list[dict[str, Any]], step_index: int) -> list[str]:
    """Identify JSONPaths extracted in step_index that are actually referenced in later steps."""
    step = steps[step_index]
    extracted_map: dict[str, str] = {}
    for ex in step.get("extractions") or []:
        if isinstance(ex, dict) and ex.get("variable") and ex.get("expression"):
            extracted_map[str(ex["variable"])] = str(ex["expression"])
    if not extracted_map:
        return []
    later_blob = json.dumps(steps[step_index + 1 :], ensure_ascii=False, default=str)
    return [expr for var, expr in extracted_map.items() if f"{{{{{var}}}}}" in later_blob]


async def suggest_scenario_batch_assertions(
    *,
    debug_session: Any,
    steps: list[dict[str, Any]],
    project_id: int,
    business_goal: str,
    config: AILLMConfig | None,
    api_key: str,
) -> AIScenarioBatchSuggestOut:
    """Generate per-step assertion suggestions across a debug session collected in 'collect' mode."""
    items: list[AIScenarioBatchStepSuggestion] = []
    overall_source: str = "heuristic"

    for idx, step in enumerate(steps):
        uid = str(step.get("uid") or step.get("id") or f"step_{idx + 1}")
        step_name = str(step.get("name") or f"Step {idx + 1}")
        step_res = debug_session.results.get(uid)
        cached_resp = debug_session.responses.get(uid)
        failure_kind = _classify_step_failure_kind(step_res, cached_resp)

        if failure_kind == "not_executed":
            items.append(
                AIScenarioBatchStepSuggestion(
                    step_uid=uid,
                    step_index=idx,
                    step_name=step_name,
                    failure_kind="not_executed",
                    note="未执行：前序步骤未成功获取响应",
                )
            )
            continue

        if failure_kind == "response_error":
            items.append(
                AIScenarioBatchStepSuggestion(
                    step_uid=uid,
                    step_index=idx,
                    step_name=step_name,
                    failure_kind="response_error",
                    note="响应异常（HTTP ≥ 400、非 JSON 或连接错误），不生成断言建议，请先确认接口或转用失败诊断",
                )
            )
            continue

        suggest_in = AIAssertionSuggestIn(
            project_id=project_id,
            method=str(step.get("method") or "GET"),
            url=str(step.get("url") or ""),
            status_code=cached_resp.get("status_code") if cached_resp else None,
            response_body=cached_resp.get("body") if cached_resp else None,
            response_headers=cached_resp.get("headers") if cached_resp else None,
            existing_assertions=step.get("assertions") or [],
            existing_extractions=step.get("extractions") or [],
            business_goal=business_goal,
            downstream_referenced_paths=_collect_downstream_extracted_paths(steps, idx),
        )
        out = await suggest_assertions_and_extractions(suggest_in, config, api_key)
        if out.source == "llm":
            overall_source = "llm"
        note = "当前校验失败，已按真实响应给出修正建议" if failure_kind == "assertion_mismatch" else ""
        items.append(
            AIScenarioBatchStepSuggestion(
                step_uid=uid,
                step_index=idx,
                step_name=step_name,
                failure_kind=failure_kind,  # type: ignore[arg-type]
                note=note,
                assertions=out.assertions,
                extractions=out.extractions,
                filtered_count=out.filtered_count,
                filtered_reasons=out.filtered_reasons,
                already_exists_count=out.already_exists_count,
            )
        )

    return AIScenarioBatchSuggestOut(
        debug_session_id=debug_session.session_id,
        items=items,
        source="llm" if overall_source == "llm" else "heuristic",
    )
