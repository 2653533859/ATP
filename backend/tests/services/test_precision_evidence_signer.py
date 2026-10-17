"""增量用例推荐与拓扑调度 64 位 SHA-256 存证证书器单测 (T4.2)"""

from __future__ import annotations

import pytest

from app.services.precision_evidence_signer import (
    PrecisionArtifactType,
    PrecisionVerificationVerdict,
    canonicalize_payload,
    clear_precision_certificates,
    compute_evidence_sha256,
    get_precision_certificate,
    list_precision_certificates,
    sign_dag_topology_certificate,
    sign_precision_recommendation_certificate,
    sign_wave_plan_certificate,
    verify_precision_certificate,
)


@pytest.fixture(autouse=True)
def clean_certs():
    clear_precision_certificates()
    yield
    clear_precision_certificates()


def test_canonicalize_payload_deterministic():
    payload_a = {"z": 99, "k": "val", "arr": [3, 2, 1]}
    payload_b = {"arr": [3, 2, 1], "k": "val", "z": 99}

    s_a = canonicalize_payload(payload_a)
    s_b = canonicalize_payload(payload_b)
    assert s_a == s_b
    assert s_a == '{"arr":[3,2,1],"k":"val","z":99}'

    sha = compute_evidence_sha256(s_a)
    assert len(sha) == 64


def test_sign_recommendation_and_verify():
    mock_rec = {
        "analysis_id": "prec_analysis_999",
        "changed_symbols": ["discount.calculate"],
        "impacted_endpoints": ["POST /api/v1/orders"],
        "impacted_cases_count": 3,
        "total_cases_in_suite": 100,
        "regression_reduction_ratio": 0.97,
        "estimated_time_saved_seconds": 970.0,
    }

    cert = sign_precision_recommendation_certificate(mock_rec)
    assert cert.certificate_id.startswith("cert_prec_")
    assert cert.artifact_type == PrecisionArtifactType.PRECISION_RECOMMENDATION
    assert cert.artifact_id == "prec_analysis_999"
    assert len(cert.evidence_sha256) == 64
    assert len(cert.hmac_signature) == 64

    verdict, msg = verify_precision_certificate(cert.certificate_id)
    assert verdict == PrecisionVerificationVerdict.VALID
    assert "密码学验签通过" in msg

    fetched = get_precision_certificate(cert.certificate_id)
    assert fetched is not None
    assert fetched.certificate_id == cert.certificate_id


def test_sign_dag_topology_certificate():
    mock_dag = {
        "dag_id": "dag_topology_001",
        "is_valid_dag": True,
        "nodes_count": 5,
        "edges_count": 4,
        "cycles": [],
    }

    cert = sign_dag_topology_certificate(mock_dag)
    assert cert.certificate_id.startswith("cert_dag_")
    assert cert.artifact_type == PrecisionArtifactType.DAG_TOPOLOGY
    assert cert.artifact_id == "dag_topology_001"

    verdict, _ = verify_precision_certificate(cert.certificate_id)
    assert verdict == PrecisionVerificationVerdict.VALID


def test_sign_wave_plan_certificate():
    mock_plan = {
        "plan_id": "wplan_001",
        "dag_id": "dag_topology_001",
        "total_waves_count": 3,
        "total_cases_count": 5,
        "concurrency_acceleration_ratio": 2.8,
    }

    cert = sign_wave_plan_certificate(mock_plan)
    assert cert.certificate_id.startswith("cert_wave_")
    assert cert.artifact_type == PrecisionArtifactType.WAVE_EXECUTION_PLAN
    assert cert.artifact_id == "wplan_001"

    verdict, _ = verify_precision_certificate(cert.certificate_id)
    assert verdict == PrecisionVerificationVerdict.VALID


def test_tamper_detection_fails_verification():
    mock_rec = {
        "analysis_id": "prec_tamper_test",
        "changed_symbols": ["auth"],
        "impacted_cases_count": 1,
    }

    cert = sign_precision_recommendation_certificate(mock_rec)

    # 恶意篡改已签名载荷中的用例数量
    cert.canonical_payload["impacted_cases_count"] = 999

    verdict, msg = verify_precision_certificate(cert.certificate_id)
    assert verdict == PrecisionVerificationVerdict.TAMPERED_INVALID
    assert "指纹不匹配" in msg or "篡改" in msg


def test_certificate_not_found():
    verdict, msg = verify_precision_certificate("cert_not_exist")
    assert verdict == PrecisionVerificationVerdict.CERTIFICATE_NOT_FOUND
    assert "未找到存证证书" in msg


def test_list_precision_certificates():
    cert1 = sign_precision_recommendation_certificate({"analysis_id": "p1"})
    cert2 = sign_dag_topology_certificate({"dag_id": "d1"})

    all_certs = list_precision_certificates()
    assert len(all_certs) == 2

    prec_certs = list_precision_certificates(artifact_type=PrecisionArtifactType.PRECISION_RECOMMENDATION)
    assert len(prec_certs) == 1
    assert prec_certs[0].certificate_id == cert1.certificate_id

    dag_certs = list_precision_certificates(artifact_type=PrecisionArtifactType.DAG_TOPOLOGY)
    assert len(dag_certs) == 1
    assert dag_certs[0].certificate_id == cert2.certificate_id
