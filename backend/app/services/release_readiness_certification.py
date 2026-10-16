"""Automated Release Readiness Certification & Digital Anti-Counterfeit Seal Service (C4.3).

Provides:
1. Synthesis of multi-dimensional quality metrics (C4.1) and quality gate evaluation (C4.2) into an immutable Release Readiness Certificate.
2. Cryptographic HMAC-SHA256 digital security seal generation over release metadata, commit SHA, and gate verdict.
3. Tamper-evident authenticity verification ensuring release certificates cannot be forged or manipulated.
4. Exportable compliance audit payload for enterprise change control board (CCB) and automated CI/CD gating.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import hmac
import json
import logging
from typing import Any
import uuid

from app.services.quality_gate_engine import (
    GateEvaluationResult,
    evaluate_quality_gate,
)
from app.services.quality_metrics_engine import (
    QualityHealthReport,
    compute_quality_health_report,
)

logger = logging.getLogger(__name__)

DEFAULT_CERTIFICATE_SECRET = "atp_release_cert_signing_key_2026_enterprise"


@dataclass
class ReleaseCertificate:
    certificate_id: str
    project_id: int
    release_version: str
    commit_sha: str
    target_environment: str
    verdict: str  # "APPROVED" | "REJECTED"
    quality_score: float
    quality_grade: str
    issued_at: str
    digital_seal_signature: str
    certificate_hash: str
    quality_report: dict[str, Any]
    gate_result: dict[str, Any]
    rejection_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "certificate_id": self.certificate_id,
            "project_id": self.project_id,
            "release_version": self.release_version,
            "commit_sha": self.commit_sha,
            "target_environment": self.target_environment,
            "verdict": self.verdict,
            "quality_score": round(self.quality_score, 1),
            "quality_grade": self.quality_grade,
            "issued_at": self.issued_at,
            "digital_seal_signature": self.digital_seal_signature,
            "certificate_hash": self.certificate_hash,
            "rejection_reasons": self.rejection_reasons,
            "quality_report": self.quality_report,
            "gate_result": self.gate_result,
        }


# In-memory registry of issued certificates
_CERTIFICATES: dict[str, ReleaseCertificate] = {}


def compute_certificate_signature(
    certificate_id: str,
    release_version: str,
    commit_sha: str,
    verdict: str,
    quality_score: float,
    issued_at: str,
    *,
    signing_key: str = DEFAULT_CERTIFICATE_SECRET,
) -> str:
    """Compute HMAC-SHA256 digital security seal over core release credentials."""
    canonical_material = f"{certificate_id}|{release_version}|{commit_sha}|{verdict}|{quality_score:.1f}|{issued_at}"
    return hmac.new(
        signing_key.encode("utf-8"),
        canonical_material.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def generate_release_certificate(
    project_id: int,
    release_version: str,
    commit_sha: str,
    *,
    target_environment: str = "production",
    gate_profile_id: str = "gate_prod_release",
    metrics_override: dict[str, Any] | None = None,
    signing_key: str = DEFAULT_CERTIFICATE_SECRET,
) -> ReleaseCertificate:
    """Synthesize metrics and quality gate into a digitally-signed Release Readiness Certificate."""
    cert_id = f"CERT-RELEASE-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Compute Quality Health Report (C4.1)
    if metrics_override:
        q_report: QualityHealthReport = compute_quality_health_report(
            project_id=project_id,
            total_cases=int(metrics_override.get("total_cases", 100)),
            automated_cases=int(metrics_override.get("automated_cases", 85)),
            internal_defects=int(metrics_override.get("internal_defects", 40)),
            prod_escapes=int(metrics_override.get("prod_escapes", 2)),
            total_runs=int(metrics_override.get("total_runs", 50)),
            flaky_runs=int(metrics_override.get("flaky_runs", 2)),
            mttr_hours=float(metrics_override.get("mttr_hours", 3.5)),
        )
    else:
        q_report = compute_quality_health_report(project_id=project_id)

    # 2. Evaluate CI/CD Quality Gate (C4.2)
    pass_rate = max(0.0, 100.0 - q_report.dimensions.flaky_ratio_pct)
    gate_metrics: dict[str, Any] = {
        "pass_rate_pct": pass_rate,
        "automation_coverage_pct": q_report.dimensions.coverage_pct,
        "p0_pass_rate_pct": 100.0 if q_report.dimensions.production_escape_defects == 0 else 95.0,
        "open_blocker_defects": q_report.dimensions.production_escape_defects,
        "composite_health_score": q_report.composite_health_score,
        "defect_escape_rate_pct": q_report.dimensions.escape_rate_pct,
    }
    if metrics_override:
        gate_metrics.update(metrics_override)

    gate_result: GateEvaluationResult = evaluate_quality_gate(gate_profile_id, gate_metrics)

    # 3. Determine Final Verdict
    reasons: list[str] = []
    if gate_result.status == "BLOCKED" or gate_result.exit_code != 0:
        verdict = "REJECTED"
        reasons.extend(gate_result.blocked_reasons)
    elif q_report.composite_health_score < 70.0:
        verdict = "REJECTED"
        reasons.append(f"综合质量健康分过低 ({q_report.composite_health_score:.1f} < 70.0)，不满足准入基线")
    else:
        verdict = "APPROVED"

    # 4. Generate Digital Signature Seal & Hash
    digital_signature = compute_certificate_signature(
        cert_id,
        release_version,
        commit_sha,
        verdict,
        q_report.composite_health_score,
        now_iso,
        signing_key=signing_key,
    )

    cert_payload_bytes = json.dumps(
        {
            "cert_id": cert_id,
            "project_id": project_id,
            "version": release_version,
            "commit": commit_sha,
            "verdict": verdict,
            "score": round(q_report.composite_health_score, 1),
            "sig": digital_signature,
        },
        sort_keys=True,
    ).encode("utf-8")
    cert_hash = hashlib.sha256(cert_payload_bytes).hexdigest()

    certificate = ReleaseCertificate(
        certificate_id=cert_id,
        project_id=project_id,
        release_version=release_version,
        commit_sha=commit_sha,
        target_environment=target_environment,
        verdict=verdict,
        quality_score=q_report.composite_health_score,
        quality_grade=q_report.grade,
        issued_at=now_iso,
        digital_seal_signature=digital_signature,
        certificate_hash=cert_hash,
        rejection_reasons=reasons,
        quality_report=q_report.to_dict(),
        gate_result=gate_result.to_dict(),
    )

    _CERTIFICATES[cert_id] = certificate
    logger.info("Issued release certificate %s: %s (Score: %s)", cert_id, verdict, q_report.composite_health_score)
    return certificate


def verify_certificate_authenticity(
    certificate_id: str,
    release_version: str,
    commit_sha: str,
    verdict: str,
    quality_score: float,
    issued_at: str,
    digital_seal_signature: str,
    *,
    signing_key: str = DEFAULT_CERTIFICATE_SECRET,
) -> dict[str, Any]:
    """Verify that a certificate's digital seal signature matches and has not been forged."""
    expected_sig = compute_certificate_signature(
        certificate_id,
        release_version,
        commit_sha,
        verdict,
        quality_score,
        issued_at,
        signing_key=signing_key,
    )

    is_authentic = hmac.compare_digest(expected_sig, digital_seal_signature)

    return {
        "certificate_id": certificate_id,
        "is_authentic": is_authentic,
        "verdict": verdict,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_message": "证书数字防伪签名验签一致，真实有效！"
        if is_authentic
        else "数字验签不匹配，证书可能遭到篡改或伪造！",
    }


def get_certificate(certificate_id: str) -> ReleaseCertificate | None:
    return _CERTIFICATES.get(certificate_id)
