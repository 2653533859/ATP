"""金丝雀健康度结论与放行准入 64 位 SHA-256 存证证书器单测 (T4.2)"""

from __future__ import annotations

import pytest

from app.services.canary_auto_rollback_guard import (
    CanaryGuardAction,
    CanaryRollbackGuardVerdict,
)
from app.services.canary_data_isolation_inspector import (
    CanaryDataIsolationReport,
    IsolationLeakSeverity,
)
from app.services.canary_evidence_signer import (
    CanaryArtifactType,
    CanaryVerificationVerdict,
    canonicalize_payload,
    clear_canary_certificates,
    compute_evidence_sha256,
    compute_hmac_signature,
    get_canary_certificate,
    list_canary_certificates,
    sign_canary_data_isolation,
    sign_canary_rollback_verdict,
    sign_canary_safety_admission,
    sign_canary_stepping_decision,
    verify_canary_certificate,
)
from app.services.canary_health_scoring_stepper import (
    CanaryHealthDimensionScore,
    CanaryHealthScoreReport,
    CanaryStepStage,
    CanaryStepperAction,
    CanarySteppingDecision,
)
from app.services.canary_safety_boundary_guard import (
    CanaryAdmissionVerdictCode,
    CanarySafetyAdmissionVerdict,
)


@pytest.fixture(autouse=True)
def setup_certs():
    clear_canary_certificates()
    yield
    clear_canary_certificates()


def test_canonical_json_and_sha256():
    # 验证键无序时生成的确定性规范 JSON 及其 64 位 SHA-256 摘要
    d1 = {"b": 2, "a": 1, "c": [1, 2]}
    d2 = {"a": 1, "c": [1, 2], "b": 2}
    c1 = canonicalize_payload(d1)
    c2 = canonicalize_payload(d2)
    assert c1 == c2
    assert c1 == '{"a":1,"b":2,"c":[1,2]}'

    sha = compute_evidence_sha256(c1)
    assert len(sha) == 64
    assert all(c in "0123456789abcdef" for c in sha)

    sig = compute_hmac_signature(sha)
    assert len(sig) == 64


def test_sign_and_verify_stepping_decision():
    dim = CanaryHealthDimensionScore("error", "错误率", 95.0, 0.3, "PASS")
    hs = CanaryHealthScoreReport(93.5, "EXCELLENT", [dim])
    decision = CanarySteppingDecision(
        decision_id="dec_test_01",
        target_service="payment-service",
        canary_version="v1.2.0-canary",
        current_stage=CanaryStepStage.STAGE_1_5PCT,
        current_weight_pct=5.0,
        recommended_action=CanaryStepperAction.PROMOTE_NEXT_STAGE,
        next_recommended_weight_pct=10.0,
        health_score=hs,
        evaluation_summary="健康度达标",
    )

    cert = sign_canary_stepping_decision(decision)
    assert cert.certificate_id.startswith("cert_can_")
    assert cert.artifact_type == CanaryArtifactType.CANARY_HEALTH_SCORE_EVALUATION
    assert cert.target_service == "payment-service"
    assert len(cert.evidence_sha256) == 64
    assert len(cert.hmac_signature) == 64

    # 在线验签合规
    verdict, msg = verify_canary_certificate(cert.certificate_id)
    assert verdict == CanaryVerificationVerdict.VALID
    assert msg is not None and "未发生任何篡改" in msg


def test_sign_and_verify_rollback_verdict():
    verdict_obj = CanaryRollbackGuardVerdict(
        guard_verdict_id="g_test_01",
        target_service="order-service",
        canary_version="v2.0.0-canary",
        is_tripped=True,
        action=CanaryGuardAction.TRIGGERED_AUTO_ROLLBACK,
        tripped_rules=["错误率突增 > 2.0%"],
        disabled_rules_count=2,
        verdict_message="紧急熔断切流完成",
    )

    cert = sign_canary_rollback_verdict(verdict_obj)
    assert cert.artifact_type == CanaryArtifactType.CANARY_ROLLBACK_GUARD_VERDICT
    assert cert.target_service == "order-service"

    verdict, _ = verify_canary_certificate(cert.certificate_id)
    assert verdict == CanaryVerificationVerdict.VALID


def test_sign_and_verify_data_isolation():
    iso_report = CanaryDataIsolationReport(
        report_id="iso_rep_01",
        target_service="payment-service",
        total_write_events=10,
        shadow_routed_count=10,
        leaked_master_writes_count=0,
        isolation_compliance_pct=100.0,
        leak_severity=IsolationLeakSeverity.CLEAN_ISOLATED,
        is_pollution_detected=False,
        leak_incidents=[],
    )

    cert = sign_canary_data_isolation(iso_report)
    assert cert.artifact_type == CanaryArtifactType.CANARY_DATA_ISOLATION_REPORT

    verdict, _ = verify_canary_certificate(cert.certificate_id)
    assert verdict == CanaryVerificationVerdict.VALID


def test_sign_and_verify_safety_admission():
    adm_verdict = CanarySafetyAdmissionVerdict(
        verdict_id="adm_01",
        is_admitted=True,
        verdict_code=CanaryAdmissionVerdictCode.ADMITTED_PASS,
        target_service="user-service",
        environment="production",
        proposed_weight_pct=10.0,
        reasons=["三要素合规"],
    )

    cert = sign_canary_safety_admission(adm_verdict)
    assert cert.artifact_type == CanaryArtifactType.CANARY_SAFETY_ADMISSION_VERDICT

    verdict, _ = verify_canary_certificate(cert.certificate_id)
    assert verdict == CanaryVerificationVerdict.VALID


def test_detect_tampering_attack():
    iso_report = CanaryDataIsolationReport(
        report_id="iso_rep_safe",
        target_service="payment-service",
        total_write_events=5,
        shadow_routed_count=5,
        leaked_master_writes_count=0,
        isolation_compliance_pct=100.0,
        leak_severity=IsolationLeakSeverity.CLEAN_ISOLATED,
        is_pollution_detected=False,
        leak_incidents=[],
    )
    cert = sign_canary_data_isolation(iso_report)

    # 1. 模拟恶意篡改 payload 内容 (如篡改合规率为 10%)
    cert.canonical_payload["isolation_compliance_pct"] = 10.0
    verdict, msg = verify_canary_certificate(cert.certificate_id)
    assert verdict == CanaryVerificationVerdict.TAMPERED_INVALID
    assert msg is not None and "SHA-256 指纹不匹配" in msg

    # 2. 模拟伪造签名
    cert_good = sign_canary_data_isolation(iso_report)
    cert_good.hmac_signature = "bad_signature_000000000000000000000000000000000000000000000000000000"
    verdict_sig, msg_sig = verify_canary_certificate(cert_good.certificate_id)
    assert verdict_sig == CanaryVerificationVerdict.TAMPERED_INVALID
    assert msg_sig is not None and "HMAC 签名校验失败" in msg_sig

    # 3. 证书不存在
    verdict_nf, _ = verify_canary_certificate("cert_not_exist")
    assert verdict_nf == CanaryVerificationVerdict.CERTIFICATE_NOT_FOUND


def test_list_and_query_certificates():
    iso_report = CanaryDataIsolationReport(
        report_id="iso_01",
        target_service="payment-service",
        total_write_events=1,
        shadow_routed_count=1,
        leaked_master_writes_count=0,
        isolation_compliance_pct=100.0,
        leak_severity=IsolationLeakSeverity.CLEAN_ISOLATED,
        is_pollution_detected=False,
        leak_incidents=[],
    )
    c1 = sign_canary_data_isolation(iso_report)

    adm_verdict = CanarySafetyAdmissionVerdict(
        verdict_id="adm_02",
        is_admitted=True,
        verdict_code=CanaryAdmissionVerdictCode.ADMITTED_PASS,
        target_service="order-service",
        environment="production",
        proposed_weight_pct=10.0,
        reasons=[],
    )
    c2 = sign_canary_safety_admission(adm_verdict)
    assert c2.certificate_id.startswith("cert_can_")

    assert get_canary_certificate(c1.certificate_id) == c1
    assert len(list_canary_certificates()) == 2
    assert len(list_canary_certificates(target_service="payment-service")) == 1
    assert len(list_canary_certificates(target_service="order-service")) == 1

    d = c1.to_dict()
    assert d["certificate_id"] == c1.certificate_id
    assert d["evidence_sha256"] == c1.evidence_sha256
