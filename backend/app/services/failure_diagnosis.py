"""Run-level failure diagnosis for execution details.

The diagnosis is generated on demand from failed/error steps, run error text,
request/response payloads, and screenshot references. It prefers the project's
LLM config when available and falls back to a deterministic rule summary.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.ai_llm_config import AILLMConfig
from app.models.case import RunStatus, StepResult, TestCase, TestRun
from app.models.project import Module, Project
from app.services.ai_case.outbound_sanitizer import OutboundSanitizer
from app.services.ai_governance import (
    check_and_incr_daily_limit,
    fallback_enabled,
    llm_extra_params,
    resolve_system_prompt,
)

logger = logging.getLogger(__name__)

_MAX_TEXT = 1200
_FAILURE_DIAGNOSIS_SYSTEM_PROMPT = (
    "你是资深测试诊断助手，请基于执行日志、断言、请求响应和截图线索，"
    "输出简明、可执行、不过度放宽断言的失败原因总结。"
)


def _truncate(value: Any, limit: int = _MAX_TEXT) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        try:
            text = json.dumps(value, ensure_ascii=False)
        except Exception:
            text = str(value)
    else:
        text = str(value)
    return text if len(text) <= limit else text[:limit] + " ...(truncated)"


def _problem_steps(run: TestRun) -> list[StepResult]:
    return [step for step in run.steps if step.status in (RunStatus.failed, RunStatus.error)]


def _guess_category(text: str, has_screenshot: bool) -> str:
    lower = text.lower()
    if any(word in lower for word in ("assert", "断言", "expected", "actual", "不匹配", "mismatch")):
        return "断言或响应内容不符合预期"
    if any(word in lower for word in ("timeout", "timed out", "超时", "deadline")):
        return "依赖服务、页面加载或设备操作超时"
    if any(word in lower for word in ("connection", "connect", "network", "dns", "网络", "连接")):
        return "环境或网络连接异常"
    if any(word in lower for word in ("401", "403", "unauthorized", "forbidden", "鉴权", "权限")):
        return "鉴权、权限或测试账号状态异常"
    if any(word in lower for word in ("404", "not found", "不存在")):
        return "测试数据、路由或资源不存在"
    if has_screenshot:
        return "页面/设备截图显示的状态可能与预期不一致"
    return "失败集中在执行步骤错误信息，需要结合日志继续定位"


def _extract_status_code(response_data: Any) -> int | None:
    if not isinstance(response_data, dict):
        return None
    for key in ("status_code", "status", "code"):
        value = response_data.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def build_repair_suggestions(failed_steps: list[StepResult]) -> list[dict[str, Any]]:
    """Build structured case repair suggestions for failed API/assertion steps."""
    suggestions: list[dict[str, Any]] = []
    for step in failed_steps[:5]:
        error_text = step.error_message or ""
        response_text = _truncate(step.response_data, 600)
        joined = f"{error_text}\n{response_text}".lower()
        status_code = _extract_status_code(step.response_data)

        if any(token in joined for token in ("assert", "断言", "expected", "actual", "不匹配", "mismatch")):
            suggestion_type = "update_assertion"
            target = "expected_result"
            suggested_change = (
                "根据实际响应字段、状态码或错误码更新该步骤断言；保留核心业务不变量，" "避免只断言完整响应文本。"
            )
        elif status_code in (401, 403) or any(
            token in joined for token in ("unauthorized", "forbidden", "鉴权", "权限")
        ):
            suggestion_type = "update_request"
            target = "test_data"
            suggested_change = "检查 token、账号权限、Header 与环境变量；必要时更新前置登录步骤或请求头配置。"
        elif status_code == 404 or any(token in joined for token in ("not found", "不存在")):
            suggestion_type = "update_request"
            target = "test_data"
            suggested_change = "确认接口路径、资源 ID 与测试数据是否仍有效；必要时改为动态创建测试数据后再断言。"
        elif status_code and status_code >= 500:
            suggestion_type = "investigate_environment"
            target = "preconditions"
            suggested_change = "优先确认服务端依赖、Mock/环境配置与测试数据状态，暂不直接放宽断言。"
        else:
            suggestion_type = "update_step"
            target = "steps"
            suggested_change = "复核该步骤动作、请求参数和断言点；若接口契约已变更，同步更新步骤说明和预期结果。"

        evidence_parts = []
        if status_code is not None:
            evidence_parts.append(f"status_code={status_code}")
        if error_text:
            evidence_parts.append(_truncate(error_text, 180))
        elif response_text:
            evidence_parts.append(_truncate(response_text, 180))

        suggestions.append(
            {
                "step_index": step.step_index,
                "step_name": step.name,
                "suggestion_type": suggestion_type,
                "target": target,
                "suggested_change": suggested_change,
                "evidence": "；".join(evidence_parts) or "该步骤状态为失败/异常",
                "confidence": 0.78 if suggestion_type in {"update_assertion", "update_request"} else 0.62,
            }
        )
    return suggestions


def build_rule_diagnosis(run: TestRun, failed_steps: list[StepResult]) -> str:
    if not failed_steps and run.status not in (RunStatus.failed, RunStatus.error):
        return "当前执行未发现失败或异常步骤，暂无需要诊断的失败原因。"

    first_error = next((step.error_message for step in failed_steps if step.error_message), None)
    combined_error = first_error or run.error_message or ""
    screenshot_count = sum(1 for step in failed_steps if step.screenshot_url)
    category = _guess_category(combined_error, screenshot_count > 0)
    first_step = failed_steps[0] if failed_steps else None
    step_hint = f"首个异常步骤为 #{first_step.step_index + 1} {first_step.name}" if first_step else "运行级错误"

    lines = [
        f"最可能原因：{category}。",
        f"关键线索：{step_hint}；异常步骤 {len(failed_steps)} 个，关联截图 {screenshot_count} 张。",
    ]
    if combined_error:
        lines.append(f"错误摘要：{_truncate(combined_error, 280)}")
    lines.append("建议优先核对失败步骤的请求/响应、断言预期、测试数据与环境连通性，再复跑确认。")
    return "\n".join(lines)


def build_deterministic_facts(run: TestRun, failed_steps: list[StepResult]) -> list[dict[str, Any]]:
    """Build deterministic, scrubbed fact entries with stable F1..Fn IDs so LLM causes stay grounded."""
    sanitizer = OutboundSanitizer(
        documents=[step.request_data for step in failed_steps] + [step.response_data for step in failed_steps]
    )
    facts: list[dict[str, Any]] = []
    idx = 1

    if run.error_message and not failed_steps:
        facts.append(
            {
                "id": f"F{idx}",
                "step_index": None,
                "step_name": "运行级异常",
                "category": _guess_category(run.error_message, False),
                "field_path": None,
                "status_code": None,
                "summary": sanitizer.scrub_text(run.error_message, limit=260),
            }
        )
        return facts

    for step in failed_steps[:8]:
        status_code = _extract_status_code(step.response_data)
        resp_dict = step.response_data if isinstance(step.response_data, dict) else {}
        failed_assertions = [
            a for a in (resp_dict.get("assertions") or []) if isinstance(a, dict) and not a.get("passed", True)
        ]
        if failed_assertions:
            for item in failed_assertions[:3]:
                field_path = str(item.get("expression") or item.get("target") or "") or None
                msg = sanitizer.scrub_text(item.get("message") or step.error_message or "断言未通过", limit=240)
                facts.append(
                    {
                        "id": f"F{idx}",
                        "step_index": step.step_index,
                        "step_name": step.name,
                        "category": "assertion_mismatch",
                        "field_path": field_path,
                        "status_code": status_code,
                        "summary": f"步骤 #{step.step_index + 1}「{step.name}」断言失败：{msg}",
                    }
                )
                idx += 1
        else:
            err_text = sanitizer.scrub_text(step.error_message or "步骤执行异常", limit=240)
            category = (
                "response_error"
                if (status_code and status_code >= 400)
                else _guess_category(err_text, bool(step.screenshot_url))
            )
            facts.append(
                {
                    "id": f"F{idx}",
                    "step_index": step.step_index,
                    "step_name": step.name,
                    "category": category,
                    "field_path": None,
                    "status_code": status_code,
                    "summary": f"步骤 #{step.step_index + 1}「{step.name}」({status_code or step.status.value})：{err_text}",
                }
            )
            idx += 1
    return facts


def _parse_grounded_llm_diagnosis(
    raw_text: str,
    valid_fact_ids: set[str],
) -> tuple[str, list[dict[str, Any]], list[str]]:
    """Parse structured JSON diagnosis and strip any hallucinated fact_id references."""
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        import re as _re

        cleaned = _re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
        cleaned = _re.sub(r"\n?```$", "", cleaned).strip()
    try:
        parsed = json.loads(cleaned)
    except Exception:
        return raw_text.strip(), [], []
    if not isinstance(parsed, dict):
        return raw_text.strip(), [], []

    summary = str(parsed.get("summary") or "").strip()
    causes: list[dict[str, Any]] = []
    for item in parsed.get("possible_causes") or []:
        if not isinstance(item, dict):
            continue
        cause_text = str(item.get("cause") or "").strip()
        raw_ids = [str(fid).strip() for fid in (item.get("fact_ids") or []) if str(fid).strip() in valid_fact_ids]
        if cause_text and (raw_ids or not valid_fact_ids):
            causes.append(
                {
                    "cause": cause_text,
                    "fact_ids": raw_ids,
                    "confidence": float(item.get("confidence", 0.7)),
                }
            )
    next_steps = [str(s).strip() for s in (parsed.get("next_steps") or []) if str(s).strip()][:5]
    return summary or raw_text.strip(), causes, next_steps


def build_failure_diagnosis_prompt(
    *,
    case: TestCase | None,
    run: TestRun,
    failed_steps: list[StepResult],
    fallback_summary: str,
    facts: list[dict[str, Any]] | None = None,
) -> str:
    case_type = (
        case.case_type.value if case and hasattr(case.case_type, "value") else str(case.case_type) if case else "-"
    )
    fact_list = facts if facts is not None else build_deterministic_facts(run, failed_steps)
    parts = [
        "# 任务",
        "请仅基于下方服务端提取的已脱敏事实（facts），输出结构化 JSON 失败归因诊断。",
        "# 严格约束",
        '1. 每条 possible_causes 必须引用上方真实存在的 fact_ids（如 ["F1"]），禁止编造未出现的事实。',
        '2. 输出纯 JSON：{"summary": "200字以内中文总结", "possible_causes": [{"cause": "...", "fact_ids": ["F1"], "confidence": 0.8}], "next_steps": ["..."]}',
        "# 执行元数据",
        f"run_id: {run.id}",
        f"run_status: {run.status.value if hasattr(run.status, 'value') else run.status}",
        f"case_name: {case.name if case else '-'}",
        f"case_type: {case_type}",
        f"rule_fallback: {_truncate(fallback_summary, 300)}",
        "# 确定性事实列表 (facts)",
        json.dumps(fact_list, ensure_ascii=False),
    ]
    sanitizer = OutboundSanitizer(
        documents=[step.request_data for step in failed_steps] + [step.response_data for step in failed_steps]
    )
    for step in failed_steps[:8]:
        req_meta = (
            {"method": step.request_data.get("method"), "action": step.request_data.get("action")}
            if isinstance(step.request_data, dict)
            else "-"
        )
        resp_meta = (
            {"status_code": _extract_status_code(step.response_data)} if isinstance(step.response_data, dict) else "-"
        )
        parts.extend(
            [
                f"\n## 失败步骤 #{step.step_index + 1} {step.name}",
                f"status: {step.status.value if hasattr(step.status, 'value') else step.status}",
                f"error: {sanitizer.scrub_text(step.error_message, limit=300)}",
                f"request_or_action: {_truncate(req_meta, 200)}",
                f"response_or_assertion: {_truncate(resp_meta, 200)}",
                f"screenshot_url: {step.screenshot_url or '-'}",
            ]
        )
    return "\n".join(parts)


async def _resolve_case_and_project(db: AsyncSession, run: TestRun) -> tuple[TestCase | None, Project | None]:
    case = await db.get(TestCase, run.case_id)
    if case is None:
        return None, None
    module = await db.get(Module, case.module_id)
    project = await db.get(Project, module.project_id) if module else None
    return case, project


async def generate_failure_diagnosis(db: AsyncSession, run_id: int) -> dict[str, Any] | None:
    result = await db.execute(select(TestRun).where(TestRun.id == run_id).options(selectinload(TestRun.steps)))
    run = result.scalar_one_or_none()
    if run is None:
        return None

    failed_steps = _problem_steps(run)
    case, project = await _resolve_case_and_project(db, run)
    facts = build_deterministic_facts(run, failed_steps)
    valid_fact_ids = {f["id"] for f in facts}
    fallback = build_rule_diagnosis(run, failed_steps)
    source = "rule"
    summary = fallback
    possible_causes: list[dict[str, Any]] = [
        {"cause": f["summary"], "fact_ids": [f["id"]], "confidence": 0.75} for f in facts[:3]
    ]
    next_steps: list[str] = ["优先核对首个异常步骤的响应字段、断言预期与环境连通性，再复跑验证。"] if facts else []

    if project and project.ai_llm_config_id and settings.AI_HEALING_ENABLED:
        config = await db.get(AILLMConfig, project.ai_llm_config_id)
        if config and config.enabled:
            try:
                if not await check_and_incr_daily_limit(config=config, capability="failure_diagnosis"):
                    raise ValueError("daily-limit-reached")
                from app.core.encryption import decrypt
                from app.services.ai_case.llm_client import LLMRequest, call_llm

                prompt = build_failure_diagnosis_prompt(
                    case=case,
                    run=run,
                    failed_steps=failed_steps,
                    fallback_summary=fallback,
                    facts=facts,
                )
                response = await call_llm(
                    LLMRequest(
                        provider=config.provider,
                        api_key=(
                            ""
                            if getattr(config, "provider", None) == "ollama" and not config.api_key_encrypted
                            else decrypt(config.api_key_encrypted)
                        ),
                        model_name=config.model_name,
                        prompt=prompt,
                        endpoint=config.endpoint,
                        system_prompt=resolve_system_prompt(
                            config,
                            "failure_diagnosis",
                            _FAILURE_DIAGNOSIS_SYSTEM_PROMPT,
                        ),
                        timeout_seconds=float(settings.AI_HEALING_TIMEOUT_SECONDS),
                        extra_params=llm_extra_params(config),
                    )
                )
                llm_text = (response.text or "").strip()
                if llm_text:
                    parsed_summary, parsed_causes, parsed_next = _parse_grounded_llm_diagnosis(llm_text, valid_fact_ids)
                    summary = parsed_summary
                    if parsed_causes:
                        possible_causes = parsed_causes
                    if parsed_next:
                        next_steps = parsed_next
                    source = "llm"
            except Exception as exc:
                logger.warning("Failure diagnosis LLM call failed for run_id=%s: %s", run_id, exc)
                if fallback_enabled(config):
                    source = "rule_fallback"
                else:
                    summary = f"LLM 调用失败且当前配置关闭规则兜底：{exc}"
                    source = "rule_fallback"

    payload = {
        "status": "done" if failed_steps or run.status in (RunStatus.failed, RunStatus.error) else "skipped",
        "source": source,
        "summary": summary,
        "at": datetime.now(timezone.utc).isoformat(),
        "failed_step_count": len(failed_steps),
        "screenshot_count": sum(1 for step in failed_steps if step.screenshot_url),
        "facts": facts,
        "possible_causes": possible_causes,
        "next_steps": next_steps,
        "repair_suggestions": build_repair_suggestions(failed_steps),
        "error_samples": [
            {
                "step_index": step.step_index,
                "name": step.name,
                "error_message": _truncate(step.error_message, 300),
                "screenshot_url": step.screenshot_url,
            }
            for step in failed_steps[:5]
        ],
    }
    run.result_summary = {
        **dict(run.result_summary or {}),
        "failure_diagnosis": payload,
    }
    await db.commit()
    return payload
