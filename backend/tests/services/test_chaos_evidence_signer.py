"""混沌实验结论与韧性得分 64 位 SHA-256 存证证书器单测 (T4.2)"""

from __future__ import annotations

import pytest

from app.services.architecture_weakness_radar import (
    ArchitectureResilienceRadarReport,
    ResilienceDimensionScore,
)
from app.services.chaos_evidence_signer import (
    ChaosArtifactType,
    ChaosVerificationVerdict,
    canonicalize_payload,
    clear_chaos_certificates,
    compute_evidence_sha256,
    get_chaos_certificate,
    list_chaos_certificates,
    sign_chaos_artifact,
    sign_radar_hardening_report,
    sign_resilience_rto_evaluation,
    sign_steady_state_baseline,
    verify_chaos_certificate,
)
from app.services.chaos_steady_state_evaluator import (
    ChaosExperimentSession,
    ChaosExperimentState,
    SteadyStateHypothesis,
)
from app.services.resilience_rto_evaluator import ResilienceGrade, ResilienceRTOEvaluation


@pytest.fixture(autouse=True)
def setup_certs():
    clear_chaos_certificates()
    yield
    clear_chaos_certificates()


def test_canonicalize_and_sha256():
    payload_a = {"b": 2, "a": 1, "c": [1, 2, 3]}
    payload_b = {"a": 1, "c": [1, 2, 3], "b": 2}
    c_a = canonicalize_payload(payload_a)
    c_b = canonicalize_payload(payload_b)
    assert c_a == c_b == '{"a":1,"b":2,"c":[1,2,3]}'

    hash_val = compute_evidence_sha256(c_a)
    assert len(hash_val) == 64
    assert hash_val.islower()


def test_sign_and_verify_steady_state_baseline():
    hypo = SteadyStateHypothesis(
        hypothesis_id="hypo_01",
        target_service="payment-service",
        min_success_rate_pct=99.0,
        max_p99_latency_ms=250.0,
    )
    exp = ChaosExperimentSession(
        experiment_id="exp_pay_test",
        name="收银台高延迟演练",
        target_service="payment-service",
        active_fault_id="fault_lat_01",
        hypothesis=hypo,
        state=ChaosExperimentState.CREATED,
    )

    cert = sign_steady_state_baseline(exp)
    assert cert.certificate_id.startswith("cert_chaos_")
    assert cert.artifact_type == ChaosArtifactType.STEADY_STATE_BASELINE
    assert cert.experiment_id == "exp_pay_test"
    assert len(cert.evidence_sha256) == 64
    assert len(cert.hmac_signature) == 64

    # 验证存证证书
    verdict, msg = verify_chaos_certificate(cert.certificate_id)
    assert verdict == ChaosVerificationVerdict.VALID
    assert "验签成功" in msg


def test_sign_resilience_rto_evaluation():
    rto_eval = ResilienceRTOEvaluation(
        evaluation_id="eval_test_01",
        experiment_id="exp_order_rto",
        target_service="order-service",
        circuit_breaker_trip_time_ms=240.0,
        fallback_takeover_rate_pct=100.0,
        recovery_time_objective_seconds=3.2,
        recovery_point_objective_seconds=0.0,
        resilience_grade=ResilienceGrade.GRADE_A_RESILIENT,
        is_slo_compliant=True,
    )

    cert = sign_resilience_rto_evaluation(rto_eval)
    assert cert.artifact_type == ChaosArtifactType.RESILIENCE_RTO_EVALUATION
    assert cert.summary["resilience_grade"] == "GRADE_A_RESILIENT"

    verdict, _ = verify_chaos_certificate(cert.certificate_id)
    assert verdict == ChaosVerificationVerdict.VALID


def test_sign_radar_hardening_report():
    radar = ArchitectureResilienceRadarReport(
        report_id="rad_order_01",
        experiment_id="exp_order_rto",
        target_service="order-service",
        composite_resilience_score=94.5,
        dimension_scores={"fault_isolation": 95.0, "circuit_tripping_speed": 98.0},
        radar_dimensions=[ResilienceDimensionScore("fault_isolation", "故障隔离性", 95.0, "EXCELLENT", "良好隔离")],
        identified_weaknesses_count=0,
        recommendations=[],
    )

    cert = sign_radar_hardening_report(radar)
    assert cert.artifact_type == ChaosArtifactType.RADAR_HARDENING_REPORT
    assert cert.summary["composite_resilience_score"] == 94.5

    verdict, _ = verify_chaos_certificate(cert.certificate_id)
    assert verdict == ChaosVerificationVerdict.VALID


def test_verify_detects_tampering_of_payload():
    cert = sign_chaos_artifact(
        artifact_type=ChaosArtifactType.FAULT_INJECTION_RECORD,
        artifact_id="flt_rec_01",
        experiment_id="exp_hack",
        payload={"injected_fault": "LATENCY", "latency_ms": 300},
        summary={"fault": "LATENCY"},
    )

    # 恶意篡改数据
    cert.canonical_payload["latency_ms"] = 9999

    verdict, msg = verify_chaos_certificate(cert.certificate_id)
    assert verdict == ChaosVerificationVerdict.TAMPERED_INVALID
    assert "指纹不匹配" in msg


def test_verify_detects_tampering_of_signature():
    cert = sign_chaos_artifact(
        artifact_type=ChaosArtifactType.FAULT_INJECTION_RECORD,
        artifact_id="flt_rec_02",
        experiment_id="exp_hack",
        payload={"test": 123},
        summary={},
    )

    # 伪造签名
    cert.hmac_signature = "0" * 64

    verdict, msg = verify_chaos_certificate(cert.certificate_id)
    assert verdict == ChaosVerificationVerdict.TAMPERED_INVALID
    assert "HMAC 数字签名无效" in msg


def test_verify_nonexistent_certificate():
    verdict, msg = verify_chaos_certificate("cert_not_exist_999")
    assert verdict == ChaosVerificationVerdict.CERTIFICATE_NOT_FOUND
    assert "未检索到" in msg


def test_list_and_get_certificates():
    sign_chaos_artifact(
        artifact_type=ChaosArtifactType.FAULT_INJECTION_RECORD,
        artifact_id="a1",
        experiment_id="exp_01",
        payload={"k": 1},
        summary={},
    )
    cert2 = sign_chaos_artifact(
        artifact_type=ChaosArtifactType.FAULT_INJECTION_RECORD,
        artifact_id="a2",
        experiment_id="exp_02",
        payload={"k": 2},
        summary={},
    )

    all_certs = list_chaos_certificates()
    assert len(all_certs) == 2

    exp1_certs = list_chaos_certificates(experiment_id="exp_01")
    assert len(exp1_certs) == 1

    fetched = get_chaos_certificate(cert2.certificate_id)
    assert fetched is not None
    assert fetched.artifact_id == "a2"
