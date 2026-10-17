"""自愈补丁与断言演进 64 位 SHA-256 存证证书器单测 (T4.2)"""

from __future__ import annotations

import pytest

from app.services.healing_evidence_signer import (
    HealingArtifactType,
    HealingVerificationVerdict,
    canonicalize_payload,
    clear_healing_certificates,
    compute_evidence_sha256,
    get_healing_certificate,
    list_healing_certificates,
    sign_assertion_evolution_certificate,
    sign_healing_patch_certificate,
    verify_healing_certificate,
)


@pytest.fixture(autouse=True)
def clean_certs():
    clear_healing_certificates()
    yield
    clear_healing_certificates()


def test_canonicalize_payload_deterministic():
    payload_a = {"z": 100, "a": "hello", "b": [1, 2]}
    payload_b = {"a": "hello", "b": [1, 2], "z": 100}

    s_a = canonicalize_payload(payload_a)
    s_b = canonicalize_payload(payload_b)
    assert s_a == s_b
    assert s_a == '{"a":"hello","b":[1,2],"z":100}'

    sha = compute_evidence_sha256(s_a)
    assert len(sha) == 64


def test_sign_and_verify_patch_certificate():
    mock_patch = {
        "patch_id": "patch_heal_1001",
        "case_id": "case_ecommerce_01",
        "step_id": "step_click_cart",
        "status": "COMMITTED_PERMANENT",
        "confidence": 0.965,
        "broken_context": {"failed_locator_value": "#btn_legacy"},
        "best_candidate": {"recommended_locator_value": "button.btn-cart", "strategy_tier": "TIER_1_ID_VARIATION"},
    }

    cert = sign_healing_patch_certificate(mock_patch)
    assert cert.certificate_id.startswith("cert_patch_")
    assert cert.artifact_type == HealingArtifactType.LOCATOR_PATCH
    assert cert.artifact_id == "patch_heal_1001"
    assert len(cert.evidence_sha256) == 64
    assert len(cert.hmac_signature) == 64

    # 验证合规通过
    verdict, msg = verify_healing_certificate(cert.certificate_id)
    assert verdict == HealingVerificationVerdict.VALID
    assert "密码学验签通过" in msg

    # 查验存储查询
    fetched = get_healing_certificate(cert.certificate_id)
    assert fetched is not None
    assert fetched.certificate_id == cert.certificate_id


def test_sign_assertion_evolution_certificate():
    mock_snapshot = {
        "version_id": "ver_ast_2002",
        "case_id": "case_api_order",
        "step_id": "step_check_status",
        "original_assertion": 'assert res["order_id"] == 123',
        "current_assertion": 'assert res["data"]["orderId"] == 123',
        "confidence_score": 96.0,
        "risk_level": "LOW",
        "status": "ACTIVE",
    }

    cert = sign_assertion_evolution_certificate(mock_snapshot)
    assert cert.certificate_id.startswith("cert_evo_")
    assert cert.artifact_type == HealingArtifactType.ASSERTION_EVOLUTION
    assert cert.artifact_id == "ver_ast_2002"
    assert cert.summary["confidence_score"] == 96.0

    verdict, _ = verify_healing_certificate(cert.certificate_id)
    assert verdict == HealingVerificationVerdict.VALID


def test_tamper_detection_fails_verification():
    mock_patch = {
        "patch_id": "patch_tamper_test",
        "case_id": "case_security",
        "step_id": "step_auth",
        "status": "COMMITTED_PERMANENT",
        "confidence": 0.99,
    }

    cert = sign_healing_patch_certificate(mock_patch)

    # 恶意篡改载荷中的状态或置信度
    cert.canonical_payload["confidence"] = 0.50

    verdict, msg = verify_healing_certificate(cert.certificate_id)
    assert verdict == HealingVerificationVerdict.TAMPERED_INVALID
    assert "指纹不匹配" in msg or "篡改" in msg


def test_certificate_not_found():
    verdict, msg = verify_healing_certificate("cert_non_existent")
    assert verdict == HealingVerificationVerdict.CERTIFICATE_NOT_FOUND
    assert "未找到存证证书" in msg


def test_list_healing_certificates():
    cert1 = sign_healing_patch_certificate({"patch_id": "p1"})
    cert2 = sign_assertion_evolution_certificate({"version_id": "v1"})

    all_certs = list_healing_certificates()
    assert len(all_certs) == 2

    patch_certs = list_healing_certificates(artifact_type=HealingArtifactType.LOCATOR_PATCH)
    assert len(patch_certs) == 1
    assert patch_certs[0].certificate_id == cert1.certificate_id

    evo_certs = list_healing_certificates(artifact_type=HealingArtifactType.ASSERTION_EVOLUTION)
    assert len(evo_certs) == 1
    assert evo_certs[0].certificate_id == cert2.certificate_id
