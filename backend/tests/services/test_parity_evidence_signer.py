"""双端一致性与跨端迁移证据 64 位 SHA-256 存证签名服务单测 (T4.2)"""

from __future__ import annotations

import pytest

from app.services.cross_platform_action_mapper import (
    ActionMappingResult,
    PlatformType,
    SemanticActionStep,
    SemanticActionType,
    SemanticLocator,
)
from app.services.parity_evidence_signer import (
    ParityArtifactType,
    ParityVerificationVerdict,
    clear_parity_certificates,
    get_parity_certificate,
    list_parity_certificates,
    sign_case_migration_evidence,
    sign_parity_report_evidence,
    verify_parity_certificate,
)
from app.services.parity_scoring_engine import (
    ParityAuditReport,
    ParityGrade,
    ParityScoreBreakdown,
    ReleaseGateVerdict,
)


@pytest.fixture(autouse=True)
def clean_store():
    clear_parity_certificates()
    yield
    clear_parity_certificates()


def test_sign_case_migration_evidence_and_verify():
    mapping = ActionMappingResult(
        mapping_id="map_evidence_test_01",
        source_platform=PlatformType.WEB,
        target_platform=PlatformType.ANDROID,
        total_steps=2,
        mapped_steps_count=2,
        average_confidence=0.92,
        mapped_steps=[
            SemanticActionStep(
                step_id="s1",
                action_type=SemanticActionType.TAP,
                source_platform=PlatformType.WEB,
                target_platform=PlatformType.ANDROID,
                source_locator=SemanticLocator("id", "btn_login", element_text="登录"),
                target_locator=SemanticLocator("resource_id", "com.app:id/btn_login", element_text="登录"),
                parameters={},
                confidence=0.95,
            ),
        ],
    )

    cert = sign_case_migration_evidence(mapping)
    assert cert.certificate_id.startswith("cert_mig_")
    assert cert.artifact_type == ParityArtifactType.CASE_MIGRATION
    assert cert.artifact_id == "map_evidence_test_01"
    assert len(cert.evidence_sha256) == 64
    assert len(cert.hmac_signature) == 64

    # 在线验签通过
    verdict, reason = verify_parity_certificate(cert.certificate_id)
    assert verdict == ParityVerificationVerdict.VALID
    assert "无篡改" in reason


def test_sign_parity_report_evidence_and_verify():
    report = ParityAuditReport(
        report_id="parrep_evidence_test_02",
        screen_name="商品收银台",
        source_platform="ios",
        target_platform="android",
        composite_score=88.5,
        grade=ParityGrade.GRADE_B,
        verdict=ReleaseGateVerdict.PASS,
        scores=ParityScoreBreakdown(85.0, 90.0, 90.0, 100.0, 88.5),
        matrix_summary={"total": 5, "aligned": 4},
        discrepancy_summary={"total_gaps": 1},
        gaps=[],
        executive_summary="双端一致性达到合格标准",
    )

    cert = sign_parity_report_evidence(report)
    assert cert.certificate_id.startswith("cert_parrep_")
    assert cert.artifact_type == ParityArtifactType.PARITY_REPORT
    assert cert.artifact_id == "parrep_evidence_test_02"
    assert len(cert.evidence_sha256) == 64

    verdict, _ = verify_parity_certificate(cert.certificate_id)
    assert verdict == ParityVerificationVerdict.VALID


def test_tamper_detection_on_canonical_payload():
    report = ParityAuditReport(
        report_id="parrep_tamper_03",
        screen_name="原始页面",
        source_platform="web",
        target_platform="ios",
        composite_score=95.0,
        grade=ParityGrade.GRADE_A,
        verdict=ReleaseGateVerdict.PASS,
        scores=ParityScoreBreakdown(95.0, 95.0, 95.0, 95.0, 95.0),
        matrix_summary={},
        discrepancy_summary={},
        gaps=[],
        executive_summary="合格",
    )

    cert = sign_parity_report_evidence(report)

    # 模拟外部恶意篡改证书中的载荷字段
    cert.canonical_payload["composite_score"] = 60.0

    verdict, reason = verify_parity_certificate(cert.certificate_id)
    assert verdict == ParityVerificationVerdict.TAMPERED_INVALID
    assert "存证指纹被篡改" in reason


def test_tamper_detection_on_hmac_signature():
    report = ParityAuditReport(
        report_id="parrep_sig_tamper_04",
        screen_name="页面",
        source_platform="web",
        target_platform="ios",
        composite_score=90.0,
        grade=ParityGrade.GRADE_A,
        verdict=ReleaseGateVerdict.PASS,
        scores=ParityScoreBreakdown(90.0, 90.0, 90.0, 90.0, 90.0),
        matrix_summary={},
        discrepancy_summary={},
        gaps=[],
        executive_summary="合格",
    )

    cert = sign_parity_report_evidence(report)

    # 篡改 HMAC 防伪签名
    cert.hmac_signature = "bad" + cert.hmac_signature[3:]

    verdict, reason = verify_parity_certificate(cert.certificate_id)
    assert verdict == ParityVerificationVerdict.TAMPERED_INVALID
    assert "防伪数字签名校验失败" in reason


def test_certificate_not_found_and_listing():
    verdict, _ = verify_parity_certificate("cert_non_existent")
    assert verdict == ParityVerificationVerdict.CERTIFICATE_NOT_FOUND

    assert get_parity_certificate("cert_non_existent") is None
    assert isinstance(list_parity_certificates(), list)
