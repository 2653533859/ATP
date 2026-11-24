"""AI-driven and heuristic assertion suggestion generator for Web UI lowcode steps."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.models.ai_llm_config import AILLMConfig
from app.schemas.ai_case import (
    AIWebAssertionSuggestIn,
    AIWebAssertionSuggestOut,
    WebAssertionStepIn,
    WebAssertionSuggestion,
)
from app.services.ai_case.llm_client import LLMRequest, call_llm
from app.services.ai_governance import check_and_incr_daily_limit, llm_extra_params, redact_llm_text
from app.services.sensitive_data_redactor import mask_pii_text

logger = logging.getLogger(__name__)

_SENSITIVE_FIELD_RE = re.compile(r"(password|passwd|pwd|secret|token|pin|验证码|密码)", re.IGNORECASE)
_SUCCESS_TEXT_RE = re.compile(
    r"(成功|完成|保存|提交|欢迎|工作台|仪表盘|首页|退出|登出|列表|详情|success|welcome|dashboard|saved|created|logout)",
    re.IGNORECASE,
)

_WEB_ASSERTION_PROMPT = """你是一名资深 Web UI 自动化测试专家。请根据已录制的 Web 操作步骤与页面上下文，为该测试用例推荐 1 到 4 条最关键、最稳定、具有业务验证价值的页面断言。

页面上下文：
- 起始 URL: {start_url}
- 当前 URL: {current_url}
- 页面标题: {page_title}
- 当前页面可见文本摘要:
{dom_summary}

已录制步骤（按顺序）：
{steps_json}

严格约束：
1. 只能使用以下两种执行器原生支持的 action：
   - "assert_text": 验证页面可见文本存在，params 必须为 {{"text": "页面中实际出现的简短可见文本"}}
   - "assert_visible": 验证页面元素可见，params 必须为 {{"selector": "稳定的 Playwright/CSS 选择器"}}
2. 不要重复已存在于步骤中的相同断言，也不要断言密码、Token 等敏感输入值。
3. 优先验证操作流程结束后的业务结果（如成功提示、跳转后的核心标题/导航/列表/关键按钮），不要编造页面中不存在的选择器。
4. 只输出严格 JSON 对象，不要附加解释文字或 Markdown 代码块，格式如下：
{{
  "assertions": [
    {{
      "action": "assert_text",
      "name": "断言登录成功跳转工作台",
      "params": {{"text": "工作台"}},
      "reason": "验证登录提交后已进入系统主界面"
    }}
  ]
}}
"""


def _is_sensitive_step(step: WebAssertionStepIn) -> bool:
    haystack = " ".join(
        [
            step.name or "",
            str(step.params.get("selector") or ""),
            str(step.params.get("label") or ""),
        ]
    )
    return bool(_SENSITIVE_FIELD_RE.search(haystack))


def _sanitize_steps_for_prompt(steps: list[WebAssertionStepIn]) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    sensitive_mask_needed = False
    for index, step in enumerate(steps[:40], start=1):
        params = dict(step.params or {})
        sensitive_mask_needed = _is_sensitive_step(step)
        if sensitive_mask_needed and "value" in params:
            params["value"] = "***"
        elif isinstance(params.get("value"), str):
            params["value"] = redact_llm_text(mask_pii_text(params["value"]), limit=120)
        if isinstance(params.get("text"), str):
            params["text"] = redact_llm_text(mask_pii_text(params["text"]), limit=120)
        if isinstance(params.get("url"), str):
            params["url"] = redact_llm_text(mask_pii_text(params["url"]), limit=240)
        sanitized.append(
            {
                "index": index,
                "action": step.action,
                "name": redact_llm_text(mask_pii_text(step.name or step.action), limit=120),
                "params": params,
            }
        )
    return sanitized


def _existing_assertion_signatures(steps: list[WebAssertionStepIn]) -> set[tuple[str, str]]:
    signatures: set[tuple[str, str]] = set()
    for step in steps:
        if step.action == "assert_text":
            text = str(step.params.get("text") or "").strip().lower()
            if text:
                signatures.add(("assert_text", text))
        elif step.action == "assert_visible":
            selector = str(step.params.get("selector") or "").strip()
            if selector:
                signatures.add(("assert_visible", selector))
    return signatures


def _normalize_candidate(
    raw: dict[str, Any],
    existing: set[tuple[str, str]],
) -> WebAssertionSuggestion | None:
    action = str(raw.get("action") or "").strip()
    if action not in {"assert_text", "assert_visible"}:
        return None
    maybe_params = raw.get("params")
    raw_params: dict[str, Any] = maybe_params if isinstance(maybe_params, dict) else {}
    reason = str(raw.get("reason") or "").strip()[:200]
    name = str(raw.get("name") or "").strip()[:120]

    if action == "assert_text":
        text = str(raw_params.get("text") or raw.get("text") or "").strip()
        if not text or len(text) > 120:
            return None
        sig = ("assert_text", text.lower())
        if sig in existing:
            return None
        existing.add(sig)
        return WebAssertionSuggestion(
            action="assert_text",
            name=name or f"断言文本 {text[:30]}",
            params={"text": text},
            reason=reason or "验证页面包含关键可见文本",
        )

    selector = str(raw_params.get("selector") or raw.get("selector") or "").strip()
    if not selector or len(selector) > 200:
        return None
    sig = ("assert_visible", selector)
    if sig in existing:
        return None
    existing.add(sig)
    return WebAssertionSuggestion(
        action="assert_visible",
        name=name or f"断言可见 {selector[:40]}",
        params={"selector": selector},
        reason=reason or "验证关键页面元素可见",
    )


def _heuristic_web_assertions(body: AIWebAssertionSuggestIn) -> list[WebAssertionSuggestion]:
    """Build deterministic fallback assertions from page summary and recorded steps."""
    existing = _existing_assertion_signatures(body.steps)
    suggestions: list[WebAssertionSuggestion] = []

    summary_lines = [line.strip() for line in (body.dom_summary or "").splitlines() if 2 <= len(line.strip()) <= 60]
    prioritized_lines = [line for line in summary_lines if _SUCCESS_TEXT_RE.search(line)]
    candidate_lines = prioritized_lines or summary_lines

    for line in candidate_lines:
        item = _normalize_candidate(
            {
                "action": "assert_text",
                "name": f"断言可见文本「{line[:24]}」",
                "params": {"text": line},
                "reason": "基于当前页面核心可见文本生成的兜底断言",
            },
            existing,
        )
        if item is not None:
            suggestions.append(item)
            if len(suggestions) >= 2:
                break

    if not suggestions:
        for step in reversed(body.steps):
            if step.action in {"click", "select", "press"} and not _is_sensitive_step(step):
                selector = str(step.params.get("selector") or "").strip()
                if selector:
                    item = _normalize_candidate(
                        {
                            "action": "assert_visible",
                            "name": f"断言操作元素可见 {selector[:30]}",
                            "params": {"selector": selector},
                            "reason": "未获取到页面文本摘要，基于最近交互元素生成的可见性断言",
                        },
                        existing,
                    )
                    if item is not None:
                        suggestions.append(item)
                        break

    return suggestions


def _extract_json_object(raw_text: str) -> dict[str, Any] | None:
    clean_text = (raw_text or "").strip()
    if clean_text.startswith("```"):
        clean_text = re.sub(r"^```[a-zA-Z]*\n?", "", clean_text)
        clean_text = re.sub(r"\n?```$", "", clean_text).strip()
    try:
        parsed = json.loads(clean_text)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        match = re.search(r"\{[\s\S]*\}", clean_text)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None


async def suggest_web_assertions(
    body: AIWebAssertionSuggestIn,
    config: AILLMConfig | None,
    api_key: str = "",
) -> AIWebAssertionSuggestOut:
    """Generate Web UI assertion suggestions using LLM with deterministic heuristic fallback."""
    heuristics = _heuristic_web_assertions(body)

    if config is None or (not api_key and config.provider != "ollama"):
        return AIWebAssertionSuggestOut(assertions=heuristics, source="heuristic")

    try:
        if not await check_and_incr_daily_limit(config=config, capability="ai_case_suggest"):
            return AIWebAssertionSuggestOut(assertions=heuristics, source="heuristic")

        safe_steps = _sanitize_steps_for_prompt(body.steps)
        prompt = _WEB_ASSERTION_PROMPT.format(
            start_url=redact_llm_text(mask_pii_text(body.start_url or ""), limit=240) or "（未知）",
            current_url=redact_llm_text(mask_pii_text(body.current_url or ""), limit=240) or "（未知）",
            page_title=redact_llm_text(mask_pii_text(body.page_title or ""), limit=120) or "（未知）",
            dom_summary=redact_llm_text(mask_pii_text(body.dom_summary or ""), limit=1500) or "（无页面可见文本摘要）",
            steps_json=json.dumps(safe_steps, ensure_ascii=False, indent=2) if safe_steps else "[]",
        )

        resp = await call_llm(
            LLMRequest(
                provider=config.provider,
                api_key=api_key,
                model_name=config.model_name,
                prompt=prompt,
                endpoint=config.endpoint,
                system_prompt="你是一个只输出严格 JSON 的 Web UI 自动化测试专家。",
                timeout_seconds=30.0,
                extra_params=llm_extra_params(config),
            )
        )

        data = _extract_json_object(resp.text)
        if data:
            existing = _existing_assertion_signatures(body.steps)
            llm_assertions: list[WebAssertionSuggestion] = []
            for raw_item in data.get("assertions") or []:
                if not isinstance(raw_item, dict):
                    continue
                normalized = _normalize_candidate(raw_item, existing)
                if normalized is not None:
                    llm_assertions.append(normalized)
                if len(llm_assertions) >= 5:
                    break

            if llm_assertions:
                return AIWebAssertionSuggestOut(assertions=llm_assertions, source="llm")
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM web assertion suggestion failed, falling back to heuristic: error=%s", type(exc).__name__)

    return AIWebAssertionSuggestOut(assertions=heuristics, source="heuristic")
