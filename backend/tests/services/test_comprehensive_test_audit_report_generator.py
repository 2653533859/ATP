"""端到端测试执行与质量合规全景审计报告单元测试 (T4.3)。"""

from __future__ import annotations

import pytest
from app.services.comprehensive_test_audit_report_generator import (
    clear_audit_report_store,
    export_report_as_markdown,
    generate_comprehensive_audit_report,
    get_comprehensive_audit_report,
    list_comprehensive_audit_reports,
    verify_audit_report_integrity,
)


@pytest.fixture(autouse=True)
def _reset_audit_state():
    clear_audit_report_store()
    yield
    clear_audit_report_store()


def test_generate_comprehensive_audit_report_and_verify():
    """测试组装全维度数据生成审计报告并验证 SHA-256 防篡改指纹。"""
    report = generate_comprehensive_audit_report(
        target_version="v4.2.0",
        project_name="ATP 自动化测试平台",
        generated_by="QualityCI",
        execution_data={"total_cases": 250, "passed_cases": 250, "failed_cases": 0, "pass_rate_pct": 100.0},
        health_data={"composite_score": 96.0, "grade": "A+"},
        gatekeeper_data={"verdict": "GO", "blocking_reasons": []},
    )

    assert report.target_version == "v4.2.0"
    assert report.overall_verdict == "GO"
    assert report.composite_health_score == 96.0
    assert report.health_grade == "A+"
    assert len(report.sha256_audit_fingerprint) == 64  # SHA-256 64 位字符

    # 验证完整性验签通过
    verify_res = verify_audit_report_integrity(report.report_id)
    assert verify_res["valid"] is True
    assert "保持完整性" in verify_res["message"]

    # 验证 Markdown 导出
    md = export_report_as_markdown(report.report_id)
    assert "# ATP 自动化测试平台 交付与发版质量全景审计报告" in md
    assert report.sha256_audit_fingerprint in md
    assert "GO" in md

    # 验证持久化
    saved = get_comprehensive_audit_report(report.report_id)
    assert saved is not None
    assert saved.report_id == report.report_id


def test_verify_tampered_report_fails():
    """测试当外部传入篡改数据时验签失败。"""
    report = generate_comprehensive_audit_report(target_version="v1.0")

    tampered_data = {
        "target_version": "v1.0",
        "verdict": "MALICIOUS_OVERRIDE_GO",
        "composite_score": 100.0,
    }

    verify_res = verify_audit_report_integrity(report.report_id, tampered_data=tampered_data)
    assert verify_res["valid"] is False
    assert "已被篡改" in verify_res["message"]


def test_list_and_clear_reports():
    """测试列表查询与清空。"""
    generate_comprehensive_audit_report(target_version="v2.0")
    assert len(list_comprehensive_audit_reports()) == 1

    clear_audit_report_store()
    assert len(list_comprehensive_audit_reports()) == 0
