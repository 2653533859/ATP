"""Unit tests for Shadow Traffic Replay Engine Service (T2.1)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock
import pytest

from app.services.shadow_traffic_replay_engine import (
    MockRuleConfig,
    ReplayJobConfig,
    WriteGuardMode,
    clear_replay_sessions,
    execute_shadow_replay,
    get_default_external_mock_rules,
    get_replay_session,
    list_replay_sessions,
)


@pytest.fixture(autouse=True)
def clean_sessions():
    clear_replay_sessions()
    yield
    clear_replay_sessions()


def test_write_guard_mode_block_writes():
    """验证 BLOCK_WRITES 模式下写操作被安全拦截，只读操作正常放行。"""
    records = [
        {
            "traffic_id": "trf_get",
            "protocol": "HTTP",
            "method": "GET",
            "path_or_endpoint": "/api/v1/products/100",
            "response_status_code": 200,
        },
        {
            "traffic_id": "trf_post",
            "protocol": "HTTP",
            "method": "POST",
            "path_or_endpoint": "/api/v1/orders/pay",
            "request_body": '{"order_id": 999, "amount": 100.0}',
            "response_status_code": 200,
        },
        {
            "traffic_id": "trf_delete",
            "protocol": "HTTP",
            "method": "DELETE",
            "path_or_endpoint": "/api/v1/users/888",
            "response_status_code": 204,
        },
    ]

    mock_requester = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = '{"product_id": 100, "name": "Item"}'
    mock_requester.return_value = mock_resp

    config = ReplayJobConfig(
        target_base_url="http://test-server:8000",
        write_guard_mode=WriteGuardMode.BLOCK_WRITES,
        rate_limit_qps=50.0,
    )

    report = execute_shadow_replay(records, config, _custom_http_requester=mock_requester)

    assert report.total_items == 3
    assert report.success_count == 3
    assert report.blocked_write_count == 2  # POST 和 DELETE 被安全阻断
    assert report.mocked_external_count == 0

    # 验证 GET 正常发起调用并被注入影子流量 Header
    mock_requester.assert_called_once()
    called_args, called_kwargs = mock_requester.call_args
    assert called_args[0] == "GET"
    assert "X-Shadow-Traffic" in called_kwargs["headers"]
    assert called_kwargs["headers"]["X-Shadow-Traffic"] == "true"

    # 验证 POST 结果标记为 was_write_blocked
    post_res = report.results[1]
    assert post_res.was_write_blocked is True
    assert "shadow_blocked" in post_res.replayed_response_body


def test_external_dependency_mock_interception():
    """验证命中第三方外部不可控依赖 (微信/支付宝/短信) 时被 Mock 代理拦截。"""
    records = [
        {
            "traffic_id": "trf_alipay",
            "protocol": "HTTP",
            "method": "POST",
            "path_or_endpoint": "https://api.alipay.com/gateway.do",
            "request_body": '{"trade_no": "20261016001"}',
            "response_status_code": 200,
        },
        {
            "traffic_id": "trf_sms",
            "protocol": "HTTP",
            "method": "POST",
            "path_or_endpoint": "http://sms.provider.com/send",
            "request_body": '{"mobile": "13800000000"}',
            "response_status_code": 200,
        },
    ]

    config = ReplayJobConfig(
        target_base_url="http://test-server:8000",
        write_guard_mode=WriteGuardMode.ALLOW_ALL,
        external_mock_rules=get_default_external_mock_rules(),
    )

    mock_requester = MagicMock()
    report = execute_shadow_replay(records, config, _custom_http_requester=mock_requester)

    # 外部依赖必须 100% 被 Mock 拦截，不得发出真实请求
    mock_requester.assert_not_called()
    assert report.total_items == 2
    assert report.mocked_external_count == 2
    assert report.results[0].was_mocked is True
    assert "第三方支付" in (report.results[0].mock_reason or "")
    assert report.results[1].was_mocked is True


def test_dry_run_mode():
    """验证 DRY_RUN 演练模式不发生任何实际网络通信。"""
    records = [
        {"traffic_id": "trf_dry_1", "method": "POST", "path_or_endpoint": "/api/v1/update"},
        {"traffic_id": "trf_dry_2", "method": "GET", "path_or_endpoint": "/api/v1/query"},
    ]

    config = ReplayJobConfig(
        write_guard_mode=WriteGuardMode.DRY_RUN,
    )

    mock_requester = MagicMock()
    report = execute_shadow_replay(records, config, _custom_http_requester=mock_requester)

    mock_requester.assert_not_called()
    assert report.total_items == 2
    assert report.success_count == 2
    assert report.write_guard_mode == "DRY_RUN"


def test_custom_mock_rules_and_session_persistence():
    """验证自定义 Mock 规则与回放批次检索持久化。"""
    custom_rule = MockRuleConfig(
        rule_id="mock_risk_engine",
        name="第三方风控引擎拦截",
        pattern=r".*risk-service.*",
        mock_status_code=200,
        mock_response_body=json.dumps({"risk_score": 10, "passed": True}),
    )

    records = [
        {"traffic_id": "trf_risk", "method": "GET", "path_or_endpoint": "/risk-service/score"},
    ]

    config = ReplayJobConfig(
        external_mock_rules=[custom_rule],
    )

    report = execute_shadow_replay(records, config)
    assert report.mocked_external_count == 1
    assert "第三方风控" in (report.results[0].mock_reason or "")

    # 验证批次报告检索
    fetched = get_replay_session(report.session_id)
    assert fetched is not None
    assert fetched.session_id == report.session_id
    assert len(list_replay_sessions()) == 1
