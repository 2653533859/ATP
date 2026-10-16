"""接口契约与业务 Spec 驱动的端到端用例智能生成编排单元测试 (T3.1)。"""

from __future__ import annotations

import pytest
from app.services.llm_spec_to_e2e_case_synthesizer import (
    clear_synthesized_cases_store,
    get_synthesized_case,
    list_synthesized_cases,
    synthesize_e2e_test_flow,
)


@pytest.fixture(autouse=True)
def _reset_synthesizer_state():
    clear_synthesized_cases_store()
    yield
    clear_synthesized_cases_store()


def test_synthesize_e2e_test_flow_default_e2e():
    """测试基于默认典型电商闭环生成 3 步端到端用例流。"""
    case = synthesize_e2e_test_flow(
        spec_title="用户登录下单与支付闭环",
        business_flow_description="先登录获取 Token 和用户 ID，然后创建订单，最后完成收银支付。",
    )

    assert case.spec_title == "用户登录下单与支付闭环"
    assert case.steps_count == 3
    assert len(case.steps) == 3
    assert case.flow_completeness_score_pct >= 90.0

    # 验证步骤 1: 登录提取 Token 与 user_id
    step1 = case.steps[0]
    assert step1.endpoint == "/api/v1/auth/login"
    assert any("TOKEN" in k or "USER" in k for k in step1.extracted_variables)

    # 验证步骤 2: 订单创建消费 user_id 并导出 order_id
    step2 = case.steps[1]
    assert step2.endpoint == "/api/v1/orders/create"
    assert any("ORDER" in k for k in step2.extracted_variables)

    # 验证步骤 3: 支付结算消费 order_id
    step3 = case.steps[2]
    assert step3.endpoint == "/api/v1/payments/checkout"
    assert "${" in str(step3.request_payload)

    # 验证生成的 Python 代码格式
    assert "import pytest" in case.generated_python_script
    assert "import httpx" in case.generated_python_script
    assert "context_vars" in case.generated_python_script
    assert "test_e2e_" in case.generated_python_script

    # 验证持久化存储
    saved = get_synthesized_case(case.case_id)
    assert saved is not None
    assert saved.case_id == case.case_id


def test_synthesize_e2e_custom_endpoints():
    """测试基于自定义接口契约列表合成时序用例。"""
    custom_eps = [
        {
            "path": "/api/v1/accounts/register",
            "method": "POST",
            "summary": "新账号注册",
            "request_schema": {"properties": {"username": {"type": "string"}}},
            "response_schema": {"properties": {"data": {"properties": {"account_id": {"type": "string"}}}}},
        },
        {
            "path": "/api/v1/profiles/init",
            "method": "POST",
            "summary": "初始化用户资料",
            "request_schema": {"properties": {"account_id": {"type": "string"}, "nickname": {"type": "string"}}},
            "response_schema": {"properties": {"code": {"type": "integer"}}},
        },
    ]

    case = synthesize_e2e_test_flow(
        spec_title="新用户账号注册与档案初始化",
        endpoints=custom_eps,
    )

    assert case.steps_count == 2
    assert "account_id" in str(case.steps[1].request_payload)
    assert len(list_synthesized_cases()) == 1
