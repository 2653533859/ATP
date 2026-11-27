"""Unit tests for AI whitelist outbound sanitizer, self-verified dynamic-field guard, and grounded failure diagnosis."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.models.case import RunStatus
from app.schemas.ai_case import AIAssertionSuggestIn
from app.services.ai_case.outbound_sanitizer import OutboundSanitizer, build_safe_response_schema_summary
from app.services.ai_case import suggestion as suggestion_mod
from app.services.failure_diagnosis import build_deterministic_facts, _parse_grounded_llm_diagnosis


def test_outbound_sanitizer_short_secret_does_not_hide_user_id_and_schema_omits_values():
    sanitizer = OutboundSanitizer(
        secrets=["id", "super_secret_token_999"],
        documents=[{"authorization": "Bearer live_jwt_xyz"}],
    )
    assert sanitizer.allowed_field_name("user_id") is True
    assert sanitizer.allowed_field_name("access_token") is False
    assert "super_secret_token_999" not in sanitizer.scrub_text("leak super_secret_token_999 here")

    summary = build_safe_response_schema_summary(
        200,
        {
            "code": 0,
            "user_id": 42,
            "order_secret_value": "TOP_SECRET_VALUE",
            "password": "my_password",
            "memo": "CONFIDENTIAL_BUSINESS_TEXT",
        },
        sanitizer,
    )
    serialized = json.dumps(summary, ensure_ascii=False)
    assert "CONFIDENTIAL_BUSINESS_TEXT" not in serialized
    assert "TOP_SECRET_VALUE" not in serialized
    assert "my_password" not in serialized
    assert "$.user_id" in serialized
    assert "$.password" not in serialized


def test_suggest_assertions_guards_dynamic_fields_uses_whitelist_prompt_and_ranks_downstream_refs(monkeypatch):
    captured_prompts = []

    async def fake_call_llm(req):
        captured_prompts.append(req.prompt)
        return SimpleNamespace(
            text=json.dumps(
                {
                    "assertions": [
                        # Dynamic field eq -> must be downgraded to exists!
                        {
                            "target": "body",
                            "operator": "eq",
                            "expected": "ORD-20261127-999",
                            "expression": "$.data.order_id",
                            "description": "校验订单号",
                        },
                        # Arbitrary non-status text eq without business_goal -> must be filtered!
                        {
                            "target": "body",
                            "operator": "eq",
                            "expected": "VIP客户备注",
                            "expression": "$.data.remark",
                            "description": "校验备注",
                        },
                        # Mismatch on real response -> must be filtered!
                        {
                            "target": "body",
                            "operator": "eq",
                            "expected": "999",
                            "expression": "$.code",
                            "description": "错误预期",
                        },
                        # Valid business result -> keep
                        {
                            "target": "body",
                            "operator": "eq",
                            "expected": "0",
                            "expression": "$.code",
                            "description": "业务码为 0",
                        },
                    ],
                    "extractions": [],
                }
            )
        )

    monkeypatch.setattr(suggestion_mod, "call_llm", fake_call_llm)
    monkeypatch.setattr(suggestion_mod, "check_and_incr_daily_limit", AsyncMock(return_value=True))

    cfg = SimpleNamespace(
        enabled=True,
        provider="openai",
        model_name="gpt-4o-mini",
        endpoint=None,
        default_params={},
    )
    body = AIAssertionSuggestIn(
        method="POST",
        url="https://internal.corp.local/secret-path/orders",
        status_code=200,
        response_body={
            "code": 0,
            "data": {
                "order_id": "ORD-20261127-999",
                "remark": "VIP客户备注",
            },
        },
        downstream_referenced_paths=["$.data.order_id"],
    )

    out = asyncio.run(suggestion_mod.suggest_assertions_and_extractions(body, cfg, "sk-test"))
    assert out.source == "llm"
    # Whitelist check: neither raw URL nor raw business values left in LLM prompt
    assert captured_prompts
    assert "internal.corp.local" not in captured_prompts[0]
    assert "VIP客户备注" not in captured_prompts[0]
    assert "ORD-20261127-999" not in captured_prompts[0]

    # Dynamic field downgraded to exists and ranked first among body assertions because it is downstream-referenced
    order_rule = next(a for a in out.assertions if a.expression == "$.data.order_id")
    assert order_rule.operator == "exists"
    assert order_rule.expected == ""
    body_assertions = [a for a in out.assertions if a.target == "body"]
    assert body_assertions[0].expression == "$.data.order_id"
    # Arbitrary remark eq filtered out
    assert all(a.expression != "$.data.remark" for a in out.assertions)
    assert out.filtered_count >= 2


def test_grounded_failure_diagnosis_extracts_facts_and_strips_hallucinated_fact_ids():
    step = SimpleNamespace(
        step_index=1,
        name="创建订单",
        status=RunStatus.failed,
        error_message="断言失败: Bearer secret_token_12345",
        screenshot_url=None,
        request_data={"headers": {"Authorization": "Bearer secret_token_12345"}},
        response_data={
            "status_code": 200,
            "assertions": [
                {"target": "body", "expression": "$.code", "passed": False, "message": "expected 0 got 4001"}
            ],
        },
    )
    run = SimpleNamespace(id=55, status=RunStatus.failed, error_message=None, steps=[step])
    facts = build_deterministic_facts(run, [step])
    assert len(facts) == 1
    assert facts[0]["id"] == "F1"
    assert facts[0]["field_path"] == "$.code"
    assert "secret_token_12345" not in facts[0]["summary"]

    raw_llm = json.dumps(
        {
            "summary": "订单创建返回业务错误码 4001",
            "possible_causes": [
                {"cause": "库存不足导致返回 4001", "fact_ids": ["F1", "F999"], "confidence": 0.85},
                {"cause": "幻觉原因", "fact_ids": ["F888"], "confidence": 0.5},
            ],
            "next_steps": ["检查库存数据"],
        }
    )
    summary, causes, next_steps = _parse_grounded_llm_diagnosis(raw_llm, {"F1"})
    assert summary == "订单创建返回业务错误码 4001"
    assert len(causes) == 1
    assert causes[0]["fact_ids"] == ["F1"]
    assert next_steps == ["检查库存数据"]
