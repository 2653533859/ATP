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
                "根据实际响应字段、状态码或错误码更新该步骤断言；保留核心业务不变量，"
                "避免只断言完整响应文本。"
            )
        elif status_code in (401, 403) or any(token in joined for token in ("unauthorized", "forbidden", "鉴权", "权限")):
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


def build_failure_diagnosis_prompt(
    *,
    case: TestCase | None,
    run: TestRun,
    failed_steps: list[StepResult],
    fallback_summary: str,
) -> str:
    case_type = case.case_type.value if case and hasattr(case.case_type, "value") else str(case.case_type) if case else "-"
    parts = [
        "# 任务",
        "请基于测试执行详情生成简明失败原因诊断，面向测试工程师，中文回答，控制在 220 字以内。",
        "# 输出要求",
        "包含：最可能原因、关键证据、下一步排查/修复建议。避免泛泛而谈。",
        "# 执行上下文",
        f"run_id: {run.id}",
        f"run_status: {run.status.value if hasattr(run.status, 'value') else run.status}",
        f"case_name: {case.name if case else '-'}",
        f"case_type: {case_type}",
        f"run_error: {_truncate(run.error_message, 500)}",
        f"rule_fallback: {_truncate(fallback_summary, 500)}",
    ]
    for step in failed_steps[:8]:
        parts.extend(
            [
                f"\n## 失败步骤 #{step.step_index + 1} {step.name}",
                f"status: {step.status.value if hasattr(step.status, 'value') else step.status}",
                f"error: {_truncate(step.error_message, 700)}",
                f"request_or_action: {_truncate(step.request_data, 700)}",
                f"response_or_assertion: {_truncate(step.response_data, 700)}",
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
    result = await db.execute(
        select(TestRun).where(TestRun.id == run_id).options(selectinload(TestRun.steps))
    )
    run = result.scalar_one_or_none()
    if run is None:
        return None

    failed_steps = _problem_steps(run)
    case, project = await _resolve_case_and_project(db, run)
    fallback = build_rule_diagnosis(run, failed_steps)
    source = "rule"
    summary = fallback

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
                )
                response = await call_llm(
                    LLMRequest(
                        provider=config.provider,
                        api_key=decrypt(config.api_key_encrypted),
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
                    summary = llm_text
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
