"""Unit Tests for Self-Healing Audit Patch Pipeline (T4.3)。"""

from __future__ import annotations

import pytest

from app.services.self_healing_audit_patch_pipeline import (
    clear_pipeline_store,
    execute_self_healing_pipeline,
    get_pipeline_report,
    list_pipeline_reports,
    rollback_healed_patch,
)


@pytest.fixture(autouse=True)
def clean_store():
    clear_pipeline_store()
    yield
    clear_pipeline_store()


def test_api_assertion_self_healing_pipeline_flow():
    # 场景: 接口响应引入 data 外层包装，用例断言失效
    report = execute_self_healing_pipeline(
        case_id="case_api_auto_101",
        case_name="提交订单接口",
        console_logs="AssertionError: assert response['order_id'] == 888 failed, got KeyError: 'order_id'",
        http_status_code=200,
        http_response_payload={"code": 0, "message": "OK", "data": {"order_id": 888}},
        original_assertion="$.order_id == 888",
        auto_apply=True,
    )

    assert report.case_id == "case_api_auto_101"
    assert len(report.stages) == 4
    # 四阶段全部成功
    assert all(st.status.value in ("PASSED", "SKIPPED") for st in report.stages)
    assert report.stages[0].stage_name.startswith("多模态故障根因推导")
    assert report.stages[1].stage_name.startswith("候选自愈补丁智能合成")
    assert report.stages[2].stage_name.startswith("沙箱试跑试错检验")
    assert report.stages[3].stage_name.startswith("防篡改审计记录")

    assert report.dry_run_verified is True
    assert report.is_applied is True
    assert report.is_rolled_back is False
    assert len(report.diff_sha256) == 64  # SHA-256 哈希串
    assert "data.order_id" in report.healed_code


def test_ui_locator_self_healing_pipeline_flow():
    # 场景: 前端页面改版，DOM 元素定位器漂移失效
    logs = "selenium.common.exceptions.NoSuchElementException: Unable to locate element: //button[@id='old-checkout']"
    candidates = [
        {
            "candidate_id": "btn_c1",
            "tag_name": "button",
            "text_content": "结算支付",
            "attributes": {"class": "new-checkout-style"},
        }
    ]

    report = execute_self_healing_pipeline(
        case_id="case_ui_auto_202",
        case_name="结算支付",
        console_logs=logs,
        broken_locator="//button[@id='old-checkout']",
        dom_candidates=candidates,
        auto_apply=True,
    )

    assert report.failure_category == "UI_DOM_LOCATOR_DRIFT"
    assert report.patch_type == "UI_LOCATOR_HEAL"
    assert report.dry_run_verified is True
    assert report.is_applied is True
    assert "结算支付" in report.healed_code


def test_one_click_rollback_mechanism():
    report = execute_self_healing_pipeline(
        case_id="case_rollback_303",
        case_name="回滚测试用例",
        original_assertion="$.token == 'abc'",
        http_response_payload={"data": {"token": "abc"}},
        auto_apply=True,
    )

    assert report.is_applied is True
    assert report.is_rolled_back is False

    # 1. 执行一键原子回滚
    ok = rollback_healed_patch(report.pipeline_id)
    assert ok is True
    assert report.is_applied is False
    assert report.is_rolled_back is True
    assert "安全原子回滚" in report.verdict_summary

    # 2. 重复回滚防护
    re_ok = rollback_healed_patch(report.pipeline_id)
    assert re_ok is False


def test_review_required_mode_no_auto_apply():
    report = execute_self_healing_pipeline(
        case_id="case_manual_404",
        case_name="人工审核用例",
        original_assertion="$.price == 50",
        http_response_payload={"data": {"price": 50}},
        auto_apply=False,  # 仅推导试跑，不自动落盘
    )

    assert report.dry_run_verified is True
    assert report.is_applied is False  # 待审核
    assert report.is_rolled_back is False


def test_pipeline_reports_retrieval_and_clear():
    execute_self_healing_pipeline(
        case_id="c1",
        case_name="用例1",
        original_assertion="$.a == 1",
        http_response_payload={"data": {"a": 1}},
        auto_apply=True,
    )

    all_reports = list_pipeline_reports()
    assert len(all_reports) == 1

    applied_reports = list_pipeline_reports(applied_only=True)
    assert len(applied_reports) == 1

    stored = get_pipeline_report(all_reports[0].pipeline_id)
    assert stored is not None
    assert stored.case_id == "c1"
