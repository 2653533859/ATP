"""覆盖率评估报告与染色结果 64 位 SHA-256 存证证书器单测 (T4.2)"""

from __future__ import annotations

import pytest

from app.services.coverage_evidence_signer import (
    CoverageArtifactType,
    CoverageVerificationVerdict,
    canonicalize_payload,
    clear_coverage_certificates,
    compute_evidence_sha256,
    get_coverage_certificate,
    list_coverage_certificates,
    sign_coverage_artifact,
    sign_coverage_gate_verdict,
    sign_diff_staining_report,
    sign_unified_coverage_report,
    verify_coverage_certificate,
)
from app.services.coverage_report_ingestor import UnifiedCoverageReport
from app.services.diff_coverage_staining_engine import DiffCoverageReport
from app.services.incremental_coverage_gate_evaluator import (
    CoverageGateVerdictAction,
    IncrementalCoverageGateVerdict,
)


@pytest.fixture(autouse=True)
def setup_certs():
    clear_coverage_certificates()
    yield
    clear_coverage_certificates()


def test_canonicalize_and_sha256():
    d1 = {"y": 20, "x": 10}
    d2 = {"x": 10, "y": 20}
    c1 = canonicalize_payload(d1)
    c2 = canonicalize_payload(d2)
    assert c1 == c2 == '{"x":10,"y":20}'

    sha = compute_evidence_sha256(c1)
    assert len(sha) == 64
    assert sha.islower()


def test_sign_and_verify_unified_coverage_report():
    rep = UnifiedCoverageReport(
        report_id="cov_rep_01",
        project_id="proj_atp",
        commit_id="git_hash_abc",
        total_files=2,
        overall_line_coverage_pct=91.5,
        overall_branch_coverage_pct=85.0,
        files={},
        sources_ingested=["Coverage.py"],
    )

    cert = sign_unified_coverage_report(rep)
    assert cert.certificate_id.startswith("cert_cov_")
    assert cert.artifact_type == CoverageArtifactType.UNIFIED_COVERAGE_REPORT
    assert cert.project_id == "proj_atp"
    assert len(cert.evidence_sha256) == 64
    assert len(cert.hmac_signature) == 64

    verdict, msg = verify_coverage_certificate(cert.certificate_id)
    assert verdict == CoverageVerificationVerdict.VALID
    assert "验签成功" in msg


def test_sign_diff_staining_report():
    diff_rep = DiffCoverageReport(
        diff_report_id="dcov_01",
        base_commit="main",
        target_commit="feat/cov",
        total_changed_files=3,
        overall_diff_line_coverage_pct=89.0,
        overall_diff_branch_coverage_pct=82.0,
        files={},
        total_changed_lines=50,
        total_uncovered_lines=5,
    )

    cert = sign_diff_staining_report(diff_rep, project_id="proj_atp")
    assert cert.artifact_type == CoverageArtifactType.DIFF_STAINING_REPORT
    assert cert.summary["total_changed_files"] == 3

    verdict, _ = verify_coverage_certificate(cert.certificate_id)
    assert verdict == CoverageVerificationVerdict.VALID


def test_sign_coverage_gate_verdict():
    gate_verdict = IncrementalCoverageGateVerdict(
        verdict_id="gate_01",
        diff_report_id="dcov_01",
        is_passed=True,
        action=CoverageGateVerdictAction.PASSED_CONFORMANT,
        actual_diff_line_coverage_pct=92.5,
        target_min_diff_line_coverage_pct=85.0,
        actual_diff_branch_coverage_pct=80.0,
        target_min_diff_branch_coverage_pct=70.0,
        p0_uncovered_count=0,
        uncovered_lines_count=3,
        breached_rules=[],
        remediation_suggestions=[],
    )

    cert = sign_coverage_gate_verdict(gate_verdict, project_id="proj_atp")
    assert cert.artifact_type == CoverageArtifactType.COVERAGE_GATE_VERDICT
    assert cert.summary["action"] == "PASSED_CONFORMANT"

    verdict, _ = verify_coverage_certificate(cert.certificate_id)
    assert verdict == CoverageVerificationVerdict.VALID


def test_verify_tampered_payload_detected():
    cert = sign_coverage_artifact(
        artifact_type=CoverageArtifactType.DIFF_STAINING_REPORT,
        artifact_id="art_1",
        project_id="proj_atp",
        commit_id="c1",
        payload={"coverage_pct": 88.0},
        summary={},
    )

    # 篡改数据
    cert.canonical_payload["coverage_pct"] = 99.9

    verdict, msg = verify_coverage_certificate(cert.certificate_id)
    assert verdict == CoverageVerificationVerdict.TAMPERED_INVALID
    assert "指纹不匹配" in msg


def test_verify_tampered_signature_detected():
    cert = sign_coverage_artifact(
        artifact_type=CoverageArtifactType.DIFF_STAINING_REPORT,
        artifact_id="art_2",
        project_id="proj_atp",
        commit_id="c2",
        payload={"k": "v"},
        summary={},
    )

    cert.hmac_signature = "bad" * 21 + "b"

    verdict, msg = verify_coverage_certificate(cert.certificate_id)
    assert verdict == CoverageVerificationVerdict.TAMPERED_INVALID
    assert "数字签名无效" in msg


def test_verify_certificate_not_found():
    verdict, msg = verify_coverage_certificate("cert_cov_not_exist_000")
    assert verdict == CoverageVerificationVerdict.CERTIFICATE_NOT_FOUND
    assert "未检索到" in msg


def test_list_and_get_certificates():
    sign_coverage_artifact(
        artifact_type=CoverageArtifactType.DIFF_STAINING_REPORT,
        artifact_id="a1",
        project_id="proj_1",
        commit_id="c1",
        payload={"x": 1},
        summary={},
    )
    cert2 = sign_coverage_artifact(
        artifact_type=CoverageArtifactType.DIFF_STAINING_REPORT,
        artifact_id="a2",
        project_id="proj_2",
        commit_id="c2",
        payload={"x": 2},
        summary={},
    )

    all_certs = list_coverage_certificates()
    assert len(all_certs) == 2

    p2_certs = list_coverage_certificates(project_id="proj_2")
    assert len(p2_certs) == 1

    fetched = get_coverage_certificate(cert2.certificate_id)
    assert fetched is not None
    assert fetched.artifact_id == "a2"
