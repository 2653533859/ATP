"""Unit tests for C4.3 Automated Release Readiness Certification & Digital Anti-Counterfeit Seal.

Tests:
1. generate_release_certificate produces APPROVED certificate with HMAC-SHA256 signature seal
2. verify_certificate_authenticity verifies valid digital seal
3. verify_certificate_authenticity catches forged or tampered certificate verdict
4. generate_release_certificate marks REJECTED when quality gate blockers fail
5. get_certificate retrieves issued certificate record
"""

from __future__ import annotations

import pytest

from app.services.release_readiness_certification import (
    _CERTIFICATES,
    generate_release_certificate,
    get_certificate,
    verify_certificate_authenticity,
)


@pytest.fixture(autouse=True)
def clean_certs():
    _CERTIFICATES.clear()
    yield
    _CERTIFICATES.clear()


def test_generate_compliant_release_certificate():
    cert = generate_release_certificate(
        project_id=1,
        release_version="v3.2.0",
        commit_sha="a6c65e54",
        target_environment="production",
        gate_profile_id="gate_prod_release",
        metrics_override={
            "total_cases": 150,
            "automated_cases": 140,
            "internal_defects": 30,
            "prod_escapes": 0,  # 0 escapes -> 100% P0 pass, 0 blockers
            "total_runs": 100,
            "flaky_runs": 0,
            "mttr_hours": 2.0,
        },
    )

    assert cert.certificate_id.startswith("CERT-RELEASE-")
    assert cert.release_version == "v3.2.0"
    assert cert.commit_sha == "a6c65e54"
    assert cert.verdict == "APPROVED"
    assert cert.quality_score >= 85.0
    assert len(cert.digital_seal_signature) == 64  # HMAC-SHA256 hex
    assert len(cert.certificate_hash) == 64
    assert len(cert.rejection_reasons) == 0

    # Retrieve from registry
    cached = get_certificate(cert.certificate_id)
    assert cached is not None
    assert cached.certificate_id == cert.certificate_id


def test_verify_certificate_authenticity_valid():
    cert = generate_release_certificate(
        project_id=1,
        release_version="v3.2.0",
        commit_sha="a6c65e54",
    )

    verif = verify_certificate_authenticity(
        certificate_id=cert.certificate_id,
        release_version=cert.release_version,
        commit_sha=cert.commit_sha,
        verdict=cert.verdict,
        quality_score=cert.quality_score,
        issued_at=cert.issued_at,
        digital_seal_signature=cert.digital_seal_signature,
    )

    assert verif["is_authentic"] is True
    assert "真实有效" in verif["diagnostic_message"]


def test_verify_certificate_authenticity_detects_forgery():
    cert = generate_release_certificate(
        project_id=1,
        release_version="v3.2.0",
        commit_sha="a6c65e54",
    )

    # Malicious attacker attempts to forge verdict from REJECTED to APPROVED or alters version
    tampered_verif = verify_certificate_authenticity(
        certificate_id=cert.certificate_id,
        release_version="v3.9.9",  # Tampered version
        commit_sha=cert.commit_sha,
        verdict=cert.verdict,
        quality_score=cert.quality_score,
        issued_at=cert.issued_at,
        digital_seal_signature=cert.digital_seal_signature,
    )

    assert tampered_verif["is_authentic"] is False
    assert "可能遭到篡改或伪造" in tampered_verif["diagnostic_message"]


def test_generate_rejected_release_certificate():
    cert_bad = generate_release_certificate(
        project_id=2,
        release_version="v3.2.0-rc1",
        commit_sha="bad00000",
        gate_profile_id="gate_prod_release",
        metrics_override={
            "pass_rate_pct": 80.0,
            "open_blocker_defects": 3,  # Blocker violation
            "composite_health_score": 60.0,
            "defect_escape_rate_pct": 20.0,
        },
    )

    assert cert_bad.verdict == "REJECTED"
    assert len(cert_bad.rejection_reasons) >= 1
    assert any("阻塞卡点" in r for r in cert_bad.rejection_reasons)
