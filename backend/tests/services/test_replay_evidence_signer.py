"""流量回放与 Diff 报告 64 位 SHA-256 存证证书器单测 (T4.2)"""

from __future__ import annotations

import pytest

from app.services.replay_evidence_signer import (
    ReplayArtifactType,
    ReplayVerificationVerdict,
    canonicalize_payload,
    clear_replay_certificates,
    compute_evidence_sha256,
    get_replay_certificate,
    list_replay_certificates,
    sign_diff_report_certificate,
    sign_replay_evaluation_certificate,
    sign_traffic_record_certificate,
    verify_replay_certificate,
)


@pytest.fixture(autouse=True)
def clean_certs():
    clear_replay_certificates()
    yield
    clear_replay_certificates()


def test_canonicalize_payload():
    payload_a = {"y": "world", "a": 1, "m": {"c": 3, "a": 2}}
    payload_b = {"a": 1, "m": {"a": 2, "c": 3}, "y": "world"}

    s_a = canonicalize_payload(payload_a)
    s_b = canonicalize_payload(payload_b)
    assert s_a == s_b
    assert s_a == '{"a":1,"m":{"a":2,"c":3},"y":"world"}'

    sha = compute_evidence_sha256(s_a)
    assert len(sha) == 64


def test_sign_traffic_record_and_verify():
    mock_record = {
        "record_id": "trf_order_888",
        "trace_id": "trace_abc_123",
        "method": "POST",
        "path": "/api/v1/orders/checkout",
        "status_code": 200,
        "is_sanitized": True,
        "request_body": {"amount": 100},
        "response_body": {"order_id": "OD_888"},
    }

    cert = sign_traffic_record_certificate(mock_record)
    assert cert.certificate_id.startswith("cert_trf_")
    assert cert.artifact_type == ReplayArtifactType.TRAFFIC_RECORD
    assert cert.artifact_id == "trf_order_888"
    assert len(cert.evidence_sha256) == 64
    assert len(cert.hmac_signature) == 64

    verdict, msg = verify_replay_certificate(cert.certificate_id)
    assert verdict == ReplayVerificationVerdict.VALID
    assert "密码学验签通过" in msg

    fetched = get_replay_certificate(cert.certificate_id)
    assert fetched is not None
    assert fetched.certificate_id == cert.certificate_id


def test_sign_diff_report_certificate():
    mock_diff = {
        "report_id": "diff_rep_001",
        "record_id": "trf_order_888",
        "baseline_status_code": 200,
        "replayed_status_code": 200,
        "is_identical": False,
        "has_critical_breaking": False,
        "diff_count": 1,
    }

    cert = sign_diff_report_certificate(mock_diff)
    assert cert.certificate_id.startswith("cert_diff_")
    assert cert.artifact_type == ReplayArtifactType.DIFF_REPORT
    assert cert.artifact_id == "diff_rep_001"

    verdict, _ = verify_replay_certificate(cert.certificate_id)
    assert verdict == ReplayVerificationVerdict.VALID


def test_sign_replay_evaluation_certificate():
    mock_eval = {
        "evaluation_id": "eval_rpl_001",
        "record_id": "trf_order_888",
        "consistency_score": 95.0,
        "impact_level": "NON_BREAKING",
        "verdict": "WARN_PERMISSIVE",
        "is_deployable": True,
    }

    cert = sign_replay_evaluation_certificate(mock_eval)
    assert cert.certificate_id.startswith("cert_eval_")
    assert cert.artifact_type == ReplayArtifactType.REPLAY_EVALUATION
    assert cert.artifact_id == "eval_rpl_001"

    verdict, _ = verify_replay_certificate(cert.certificate_id)
    assert verdict == ReplayVerificationVerdict.VALID


def test_tamper_detection_fails_verification():
    mock_record = {
        "record_id": "trf_tamper",
        "method": "POST",
        "path": "/api/test",
        "status_code": 200,
    }

    cert = sign_traffic_record_certificate(mock_record)

    # 恶意篡改已签名载荷中的状态码
    cert.canonical_payload["status_code"] = 500

    verdict, msg = verify_replay_certificate(cert.certificate_id)
    assert verdict == ReplayVerificationVerdict.TAMPERED_INVALID
    assert "指纹不匹配" in msg or "篡改" in msg


def test_certificate_not_found():
    verdict, msg = verify_replay_certificate("cert_not_exist")
    assert verdict == ReplayVerificationVerdict.CERTIFICATE_NOT_FOUND
    assert "未找到存证证书" in msg


def test_list_replay_certificates():
    cert1 = sign_traffic_record_certificate({"record_id": "r1"})
    cert2 = sign_diff_report_certificate({"report_id": "d1"})

    all_certs = list_replay_certificates()
    assert len(all_certs) == 2

    records_certs = list_replay_certificates(artifact_type=ReplayArtifactType.TRAFFIC_RECORD)
    assert len(records_certs) == 1
    assert records_certs[0].certificate_id == cert1.certificate_id

    diff_certs = list_replay_certificates(artifact_type=ReplayArtifactType.DIFF_REPORT)
    assert len(diff_certs) == 1
    assert diff_certs[0].certificate_id == cert2.certificate_id
