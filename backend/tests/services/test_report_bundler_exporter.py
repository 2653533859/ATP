"""Unit tests for D4.1 Report Bundler Exporter Service."""

import io
import zipfile
import pytest

from app.services.report_bundler_exporter import (
    BundledReportPayload,
    ReportExportFormat,
    export_report_bundle,
    generate_excel_detailed_sheet,
    generate_html5_standalone_report,
    generate_pdf_compliance_summary,
    get_export_artifact,
    list_export_artifacts,
    reset_report_bundler_registry,
)


@pytest.fixture(autouse=True)
def clean_registry():
    reset_report_bundler_registry()
    yield
    reset_report_bundler_registry()


def _get_mock_payload() -> BundledReportPayload:
    return BundledReportPayload(
        run_id=101,
        title="2026 Q4 生产发布发版前置自动化质检验收",
        project_name="电商结算中台",
        environment_name="staging",
        total_cases=10,
        passed_cases=9,
        failed_cases=1,
        pass_rate_pct=90.0,
        duration_sec=42.5,
        executed_by="Release Bot",
        cases_summary=[
            {
                "case_id": 1,
                "name": "用户登录鉴权",
                "status": "passed",
                "duration_ms": 120,
            },
            {
                "case_id": 2,
                "name": "创建订单支付",
                "status": "failed",
                "duration_ms": 350,
                "error_message": "Timeout waiting for payment gateway",
            },
        ],
        digital_seal_signature="hmac_sha256_mock_sig_99aabbcc",
        quality_score=92.0,
        healed_cases_count=2,
    )


def test_generate_html5_standalone_report():
    payload = _get_mock_payload()
    html_bytes = generate_html5_standalone_report(payload)
    html_text = html_bytes.decode("utf-8")

    assert "<!DOCTYPE html>" in html_text
    assert "2026 Q4 生产发布发版前置自动化质检验收" in html_text
    assert "电商结算中台" in html_text
    assert "90.0%" in html_text
    assert "hmac_sha256_mock_sig_99aabbcc" in html_text
    assert "用户登录鉴权" in html_text


def test_generate_excel_detailed_sheet():
    payload = _get_mock_payload()
    excel_bytes = generate_excel_detailed_sheet(payload)
    excel_text = excel_bytes.decode("utf-8")

    # 验证 UTF-8 BOM 防乱码
    assert excel_text.startswith("\ufeff")
    assert "测试执行报告摘要" in excel_text
    assert "用例编号,用例名称,执行状态,执行耗时(ms),自愈标识,错误异常归因" in excel_text
    assert "1,用户登录鉴权,passed,120,NO,—" in excel_text
    assert "Timeout waiting for payment gateway" in excel_text


def test_generate_pdf_compliance_summary():
    payload = _get_mock_payload()
    pdf_bytes = generate_pdf_compliance_summary(payload)
    pdf_text = pdf_bytes.decode("utf-8")

    assert "%PDF-1.4" in pdf_text
    assert "ISO27001 (COMPLIANT)" in pdf_text
    assert "SOC2 (TYPE_II_AUDITED)" in pdf_text
    assert "hmac_sha256_mock_sig_99aabbcc" in pdf_text


def test_bundle_multimodal_archive_zip():
    payload = _get_mock_payload()
    artifact = export_report_bundle(payload, export_format=ReportExportFormat.MULTI_MODAL_ZIP)

    assert artifact.format == ReportExportFormat.MULTI_MODAL_ZIP
    assert artifact.filename.endswith(".zip")
    assert artifact.file_size_bytes > 500

    # 解压校验 ZIP 包含 4 个核心文件
    zip_buffer = io.BytesIO(artifact.data_bytes)
    with zipfile.ZipFile(zip_buffer, "r") as zf:
        namelist = zf.namelist()
        assert any(n.endswith(".html") for n in namelist)
        assert any(n.endswith(".csv") for n in namelist)
        assert any(n.endswith(".pdf") for n in namelist)
        assert any(n.endswith("_metadata.json") for n in namelist)


def test_export_report_bundle_lifecycle():
    payload = _get_mock_payload()

    # HTML 导出
    art_html = export_report_bundle(payload, export_format=ReportExportFormat.HTML5)
    assert art_html.filename.endswith(".html")
    assert art_html.content_type == "text/html; charset=utf-8"

    # 查询
    fetched = get_export_artifact(art_html.bundle_id)
    assert fetched is not None
    assert fetched.filename == art_html.filename

    all_arts = list_export_artifacts()
    assert len(all_arts) == 1
