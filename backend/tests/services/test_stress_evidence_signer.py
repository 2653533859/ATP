"""容量基线推演结论与压测验收 64 位 SHA-256 存证证书器单测 (T4.2)"""

from __future__ import annotations

import pytest

from app.services.capacity_knee_point_deductor import CapacityKneePointReport
from app.services.shadow_data_pollution_cleaner import ShadowDataCleanReport
from app.services.stress_evidence_signer import (
    StressArtifactType,
    StressVerificationVerdict,
    canonicalize_payload,
    clear_stress_certificates,
    compute_evidence_sha256,
    compute_hmac_signature,
    get_stress_certificate,
    list_stress_certificates,
    sign_capacity_knee_point_report,
    sign_shadow_data_clean_report,
    sign_stress_overload_guard_verdict,
    sign_stress_safety_admission_verdict,
    verify_stress_certificate,
)
from app.services.stress_safety_boundary_guard import (
    StressAdmissionVerdictCode,
    StressSafetyAdmissionVerdict,
)
from app.services.stress_safety_overload_guard import (
    OverloadGuardAction,
    ProductionHealthSnapshot,
    StressOverloadGuardVerdict,
)


@pytest.fixture(autouse=True)
def setup_stress_certs():
    clear_stress_certificates()
    yield
    clear_stress_certificates()


def test_canonical_json_and_sha256_generation():
    d1 = {"y": 100, "x": 10, "arr": [3, 2, 1]}
    d2 = {"x": 10, "arr": [3, 2, 1], "y": 100}
    c1 = canonicalize_payload(d1)
    c2 = canonicalize_payload(d2)
    assert c1 == c2
    assert c1 == '{"arr":[3,2,1],"x":10,"y":100}'

    sha = compute_evidence_sha256(c1)
    assert len(sha) == 64
    assert all(c in "0123456789abcdef" for c in sha)

    sig = compute_hmac_signature(sha)
    assert len(sig) == 64


def test_sign_and_verify_capacity_report():
    report = CapacityKneePointReport(
        report_id="rep_usl_01",
        target_service="payment-service",
        gamma_efficiency=18.5,
        sigma_contention=0.035,
        kappa_coherency=0.00012,
        knee_point_vu=4200,
        knee_point_tps=14800.0,
        saturation_vu=7500,
        peak_tps_ceiling=16200.0,
        recommended_safe_concurrency=3360,
        r_squared_fit=0.96,
        deduction_summary="USL 拟合优良",
        samples_count=8,
    )

    cert = sign_capacity_knee_point_report(report)
    assert cert.certificate_id.startswith("cert_str_")
    assert cert.artifact_type == StressArtifactType.CAPACITY_KNEE_POINT_DEDUCTION
    assert cert.target_service == "payment-service"
    assert len(cert.evidence_sha256) == 64
    assert len(cert.hmac_signature) == 64

    # 在线验签验证
    verdict, msg = verify_stress_certificate(cert.certificate_id)
    assert verdict == StressVerificationVerdict.VALID
    assert msg is not None and "未发生任何篡改" in msg


def test_sign_and_verify_overload_verdict():
    snap = ProductionHealthSnapshot(
        target_service="order-service",
        measured_tps=15000.0,
        measured_error_rate_pct=2.1,
        measured_p99_latency_ms=280.0,
        measured_cpu_pct=88.0,
    )
    verdict_obj = StressOverloadGuardVerdict(
        guard_verdict_id="g_ovl_01",
        target_service="order-service",
        is_tripped=True,
        action=OverloadGuardAction.TRIGGERED_CIRCUIT_BREAK,
        tripped_reasons=["错误率突破红线 2.1%"],
        disabled_rules_count=2,
        health_snapshot=snap,
        policy_thresholds={},
        verdict_message="紧急熔断泄压完成",
    )

    cert = sign_stress_overload_guard_verdict(verdict_obj)
    assert cert.artifact_type == StressArtifactType.STRESS_OVERLOAD_CIRCUIT_BREAK
    assert cert.target_service == "order-service"

    verdict, _ = verify_stress_certificate(cert.certificate_id)
    assert verdict == StressVerificationVerdict.VALID


def test_sign_and_verify_shadow_clean_report():
    clean_rep = ShadowDataCleanReport(
        clean_job_id="cln_job_01",
        target_service="payment-service",
        is_dry_run=False,
        cleaned_resources_count=2,
        total_purged_records=170000,
        reclaimed_space_mb=263.5,
        purged_details=[],
        rejected_attempts=[],
    )

    cert = sign_shadow_data_clean_report(clean_rep)
    assert cert.artifact_type == StressArtifactType.SHADOW_DATA_CLEAN_AUDIT

    verdict, _ = verify_stress_certificate(cert.certificate_id)
    assert verdict == StressVerificationVerdict.VALID


def test_sign_and_verify_safety_admission():
    adm_verdict = StressSafetyAdmissionVerdict(
        verdict_id="adm_01",
        is_admitted=True,
        verdict_code=StressAdmissionVerdictCode.ADMITTED_PASS,
        target_service="order-service",
        environment="production",
        planned_peak_vu=10000,
        reasons=["三要素合规"],
    )

    cert = sign_stress_safety_admission_verdict(adm_verdict)
    assert cert.artifact_type == StressArtifactType.STRESS_SAFETY_ADMISSION_VERDICT

    verdict, _ = verify_stress_certificate(cert.certificate_id)
    assert verdict == StressVerificationVerdict.VALID


def test_detect_tampering_attack():
    clean_rep = ShadowDataCleanReport(
        clean_job_id="cln_safe_01",
        target_service="payment-service",
        is_dry_run=False,
        cleaned_resources_count=1,
        total_purged_records=10000,
        reclaimed_space_mb=20.0,
        purged_details=[],
        rejected_attempts=[],
    )
    cert = sign_shadow_data_clean_report(clean_rep)

    # 1. 模拟恶意篡改 payload 字段 (如篡改清理记录数)
    cert.canonical_payload["total_purged_records"] = 999999
    verdict, msg = verify_stress_certificate(cert.certificate_id)
    assert verdict == StressVerificationVerdict.TAMPERED_INVALID
    assert msg is not None and "SHA-256 指纹不匹配" in msg

    # 2. 模拟伪造签名
    cert_good = sign_shadow_data_clean_report(clean_rep)
    cert_good.hmac_signature = "fake_signature_0000000000000000000000000000000000000000000000000000"
    verdict_sig, msg_sig = verify_stress_certificate(cert_good.certificate_id)
    assert verdict_sig == StressVerificationVerdict.TAMPERED_INVALID
    assert msg_sig is not None and "HMAC 签名校验失败" in msg_sig

    # 3. 证书不存在
    verdict_nf, _ = verify_stress_certificate("cert_not_exist")
    assert verdict_nf == StressVerificationVerdict.CERTIFICATE_NOT_FOUND


def test_list_and_query_certificates():
    clean_rep = ShadowDataCleanReport(
        clean_job_id="cln_query_01",
        target_service="payment-service",
        is_dry_run=False,
        cleaned_resources_count=1,
        total_purged_records=5000,
        reclaimed_space_mb=10.0,
        purged_details=[],
        rejected_attempts=[],
    )
    c1 = sign_shadow_data_clean_report(clean_rep)

    adm_verdict = StressSafetyAdmissionVerdict(
        verdict_id="adm_query_02",
        is_admitted=True,
        verdict_code=StressAdmissionVerdictCode.ADMITTED_PASS,
        target_service="order-service",
        environment="production",
        planned_peak_vu=5000,
        reasons=[],
    )
    c2 = sign_stress_safety_admission_verdict(adm_verdict)
    assert c2.certificate_id.startswith("cert_str_")

    assert get_stress_certificate(c1.certificate_id) == c1
    assert len(list_stress_certificates()) == 2
    assert len(list_stress_certificates(target_service="payment-service")) == 1
    assert len(list_stress_certificates(target_service="order-service")) == 1

    d = c1.to_dict()
    assert d["certificate_id"] == c1.certificate_id
    assert d["evidence_sha256"] == c1.evidence_sha256
