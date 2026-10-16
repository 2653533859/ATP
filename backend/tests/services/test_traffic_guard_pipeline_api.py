"""Unit tests for Traffic Guard Pipeline Service and CLI (T4.3)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock
import pytest

from app.services.traffic_guard_pipeline_api import (
    PipelineStageStatus,
    clear_pipeline_reports,
    execute_traffic_guard_pipeline,
    get_pipeline_report,
    list_pipeline_reports,
)


@pytest.fixture(autouse=True)
def clean_pipeline_state():
    clear_pipeline_reports()
    yield
    clear_pipeline_reports()


def test_execute_pipeline_success_exit_code_0():
    """验证四阶段全绿通过场景下的端到端编排与 Exit Code 0 裁决。"""
    mock_requester = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = json.dumps({"code": 0, "status": "SUCCESS", "order_id": 1001, "amount": 100.0})
    mock_requester.return_value = mock_resp

    report = execute_traffic_guard_pipeline(
        endpoint="POST /api/v1/orders/checkout",
        pipeline_name="CI-Test-Worker",
        write_guard_mode="DRY_RUN",
        simulate_chaos_resilience=True,
        _custom_requester=mock_requester,
    )

    assert report.exit_code == 0
    assert report.overall_status == PipelineStageStatus.PASSED
    assert len(report.stages) == 4
    assert len(report.remediation_actions) == 0

    # 验证控制台日志包含四阶段与退出码
    assert "[STAGE 1/4]" in report.console_log_output
    assert "[STAGE 2/4]" in report.console_log_output
    assert "[STAGE 3/4]" in report.console_log_output
    assert "[STAGE 4/4]" in report.console_log_output
    assert "[EXIT CODE]: 0 (SUCCESS)" in report.console_log_output


def test_execute_pipeline_blocked_exit_code_1():
    """验证当发生破坏性契约变更 (如删除字段或新增必填) 时，流水线拦截并输出 Exit Code 1。"""
    # 构造设计期基准契约包含 balance，而现网样本中缺失 balance (BREAKING)
    design_contract = {
        "endpoint": "POST /api/v1/orders/checkout",
        "request_schema": {
            "type": "object",
            "properties": {"order_id": {"type": "integer"}},
        },
        "response_schemas": {
            "200": {
                "type": "object",
                "properties": {
                    "code": {"type": "integer"},
                    "balance": {"type": "number"},  # 设计期包含，现网流量中被删除 -> BREAKING!
                },
            }
        },
    }

    report = execute_traffic_guard_pipeline(
        endpoint="POST /api/v1/orders/checkout",
        design_contract=design_contract,
        write_guard_mode="DRY_RUN",
        simulate_chaos_resilience=False,
    )

    assert report.exit_code == 1
    assert report.overall_status == PipelineStageStatus.BLOCKED
    assert report.stages[2].status == PipelineStageStatus.BLOCKED  # Stage 3 阻断
    assert len(report.remediation_actions) > 0
    assert "[EXIT CODE]: 1 (BLOCKED / FAILURE)" in report.console_log_output


def test_execute_pipeline_warning_exit_code_2():
    """验证当仅存在次要契约警告时，输出 Exit Code 2。"""
    # 现网响应新增了可选字段
    design_contract = {
        "endpoint": "POST /api/v1/orders/checkout",
        "request_schema": {
            "type": "object",
            "properties": {"order_id": {"type": "integer"}, "amount": {"type": "number"}, "phone": {"type": "string"}},
            "required": ["amount", "order_id", "phone"],
        },
        "response_schemas": {
            "200": {
                "type": "object",
                "properties": {
                    "code": {"type": "integer"},
                    "status": {"type": "string"},
                },  # 现网多了 order_id 和 amount -> WARNING
            }
        },
    }

    report = execute_traffic_guard_pipeline(
        endpoint="POST /api/v1/orders/checkout",
        design_contract=design_contract,
        write_guard_mode="DRY_RUN",
        simulate_chaos_resilience=False,
    )

    assert report.exit_code == 2
    assert report.overall_status == PipelineStageStatus.WARNING
    assert report.stages[2].status == PipelineStageStatus.WARNING
    assert "[EXIT CODE]: 2 (WARNING / CONDITIONAL)" in report.console_log_output


def test_report_persistence():
    """验证报告持久化存储与列表检索。"""
    report = execute_traffic_guard_pipeline(
        endpoint="POST /api/v1/orders/checkout",
        write_guard_mode="DRY_RUN",
        simulate_chaos_resilience=False,
    )

    fetched = get_pipeline_report(report.pipeline_run_id)
    assert fetched is not None
    assert fetched.pipeline_run_id == report.pipeline_run_id
    assert len(list_pipeline_reports()) == 1
