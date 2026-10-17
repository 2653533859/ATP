"""覆盖率评估报告与染色结果 64 位 SHA-256 存证证书器服务 (T4.2)

为覆盖率全流程产物（统一覆盖率报告、Diff 增量染色数据、高危分支分析、准入裁决结果）提供密码学不可篡改存证:
1. 确定性 Canonical JSON 规范化序列化 (Canonicalization: sorted keys, compact separators);
2. 64 字符十六进制 SHA-256 存证指纹计算;
3. 平台权威防伪数字签名 (HMAC-SHA256);
4. 证书签发与在线合规验签防篡改探针 (CoverageEvidenceCertificate: VALID | TAMPERED_INVALID)。
"""

from __future__ import annotations

import enum
import hashlib
import hmac
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.services.coverage_report_ingestor import UnifiedCoverageReport
from app.services.diff_coverage_staining_engine import DiffCoverageReport
from app.services.incremental_coverage_gate_evaluator import IncrementalCoverageGateVerdict


class CoverageArtifactType(str, enum.Enum):
    UNIFIED_COVERAGE_REPORT = "UNIFIED_COVERAGE_REPORT"  # 多源统一覆盖率报告
    DIFF_STAINING_REPORT = "DIFF_STAINING_REPORT"  # Git Diff 增量逐行染色报告
    UNCOVERED_BRANCH_RISK = "UNCOVERED_BRANCH_RISK"  # 未覆盖高危分支漏洞分析
    COVERAGE_GATE_VERDICT = "COVERAGE_GATE_VERDICT"  # 准入卡点与发布阻断裁决


class CoverageVerificationVerdict(str, enum.Enum):
    VALID = "VALID"  # 验签合规通过，未篡改
    TAMPERED_INVALID = "TAMPERED_INVALID"  # 验签失败，数据或签名被恶意篡改
    CERTIFICATE_NOT_FOUND = "CERTIFICATE_NOT_FOUND"  # 证书未找到


@dataclass
class CoverageEvidenceCertificate:
    certificate_id: str
    artifact_type: CoverageArtifactType
    artifact_id: str
    project_id: str
    commit_id: str
    signer_identity: str
    algorithm: str  # SHA-256/HMAC-SHA256
    evidence_sha256: str  # 64 位十六进制 SHA-256 摘要
    hmac_signature: str
    canonical_payload: Dict[str, Any]
    summary: Dict[str, Any]
    issued_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


_COVERAGE_CERT_STORE: Dict[str, CoverageEvidenceCertificate] = {}
_DEFAULT_COVERAGE_SECRET = b"atp-v5-9-0-code-coverage-evidence-secret-2026"


def clear_coverage_certificates() -> None:
    """清空存证证书内存库（测试隔离使用）"""
    _COVERAGE_CERT_STORE.clear()


def canonicalize_payload(payload: Dict[str, Any]) -> str:
    """对产物字典执行确定性规范化 JSON 序列化（键排序、剔除冗余空格）"""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def compute_evidence_sha256(canonical_json: str) -> str:
    """计算规范化 JSON 数据的 64 位 SHA-256 哈希指纹"""
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def compute_hmac_signature(evidence_sha256: str, secret_key: bytes = _DEFAULT_COVERAGE_SECRET) -> str:
    """对 SHA-256 哈希指纹生成平台权威防伪 HMAC 签名"""
    return hmac.new(secret_key, evidence_sha256.encode("utf-8"), hashlib.sha256).hexdigest()


def sign_coverage_artifact(
    artifact_type: CoverageArtifactType,
    artifact_id: str,
    project_id: str,
    commit_id: str,
    payload: Dict[str, Any],
    summary: Dict[str, Any],
    signer_identity: str = "ATP-COVERAGE-EVIDENCE-AUTHORITY-v5.9.0",
    secret_key: bytes = _DEFAULT_COVERAGE_SECRET,
) -> CoverageEvidenceCertificate:
    """通用代码覆盖率产物存证证书签发"""
    cert_id = f"cert_cov_{uuid.uuid4().hex[:12]}"
    canonical_json = canonicalize_payload(payload)
    sha256_hash = compute_evidence_sha256(canonical_json)
    signature = compute_hmac_signature(sha256_hash, secret_key=secret_key)

    cert = CoverageEvidenceCertificate(
        certificate_id=cert_id,
        artifact_type=artifact_type,
        artifact_id=artifact_id,
        project_id=project_id,
        commit_id=commit_id,
        signer_identity=signer_identity,
        algorithm="SHA-256/HMAC-SHA256",
        evidence_sha256=sha256_hash,
        hmac_signature=signature,
        canonical_payload=payload,
        summary=summary,
    )
    _COVERAGE_CERT_STORE[cert_id] = cert
    return cert


def sign_unified_coverage_report(report: UnifiedCoverageReport) -> CoverageEvidenceCertificate:
    """为统一覆盖率报告签发存证证书"""
    payload = report.to_dict()
    summary = {
        "report_id": report.report_id,
        "total_files": report.total_files,
        "overall_line_coverage_pct": report.overall_line_coverage_pct,
        "overall_branch_coverage_pct": report.overall_branch_coverage_pct,
        "sources_ingested": report.sources_ingested,
    }
    return sign_coverage_artifact(
        artifact_type=CoverageArtifactType.UNIFIED_COVERAGE_REPORT,
        artifact_id=report.report_id,
        project_id=report.project_id,
        commit_id=report.commit_id,
        payload=payload,
        summary=summary,
    )


def sign_diff_staining_report(
    diff_report: DiffCoverageReport,
    project_id: str = "default_proj",
) -> CoverageEvidenceCertificate:
    """为 Git Diff 增量逐行染色报告签发存证证书"""
    payload = diff_report.to_dict()
    summary = {
        "diff_report_id": diff_report.diff_report_id,
        "base_commit": diff_report.base_commit,
        "target_commit": diff_report.target_commit,
        "total_changed_files": diff_report.total_changed_files,
        "overall_diff_line_coverage_pct": diff_report.overall_diff_line_coverage_pct,
        "overall_diff_branch_coverage_pct": diff_report.overall_diff_branch_coverage_pct,
        "total_uncovered_lines": diff_report.total_uncovered_lines,
    }
    return sign_coverage_artifact(
        artifact_type=CoverageArtifactType.DIFF_STAINING_REPORT,
        artifact_id=diff_report.diff_report_id,
        project_id=project_id,
        commit_id=diff_report.target_commit,
        payload=payload,
        summary=summary,
    )


def sign_coverage_gate_verdict(
    gate_verdict: IncrementalCoverageGateVerdict,
    project_id: str = "default_proj",
    commit_id: str = "head",
) -> CoverageEvidenceCertificate:
    """为增量覆盖率发布门禁裁决结果签发存证证书"""
    payload = gate_verdict.to_dict()
    summary = {
        "verdict_id": gate_verdict.verdict_id,
        "diff_report_id": gate_verdict.diff_report_id,
        "is_passed": gate_verdict.is_passed,
        "action": gate_verdict.action.value,
        "actual_diff_line_coverage_pct": gate_verdict.actual_diff_line_coverage_pct,
        "p0_uncovered_count": gate_verdict.p0_uncovered_count,
        "breached_rules_count": len(gate_verdict.breached_rules),
    }
    return sign_coverage_artifact(
        artifact_type=CoverageArtifactType.COVERAGE_GATE_VERDICT,
        artifact_id=gate_verdict.verdict_id,
        project_id=project_id,
        commit_id=commit_id,
        payload=payload,
        summary=summary,
    )


def verify_coverage_certificate(
    certificate_id: str,
    secret_key: bytes = _DEFAULT_COVERAGE_SECRET,
) -> Tuple[CoverageVerificationVerdict, str]:
    """验证代码覆盖率存证证书的 64 位 SHA-256 指纹完整性与 HMAC 数字签名防伪真实性"""
    cert = _COVERAGE_CERT_STORE.get(certificate_id)
    if not cert:
        return (
            CoverageVerificationVerdict.CERTIFICATE_NOT_FOUND,
            f"存证证书库中未检索到证书 ID [{certificate_id}]",
        )

    # 1. 重新计算当前 payload 的确定性 SHA-256 指纹
    current_canonical = canonicalize_payload(cert.canonical_payload)
    recalculated_sha256 = compute_evidence_sha256(current_canonical)

    if recalculated_sha256 != cert.evidence_sha256:
        return (
            CoverageVerificationVerdict.TAMPERED_INVALID,
            f"存证数据指纹不匹配: 原始 [{cert.evidence_sha256}] vs 当前计算 [{recalculated_sha256}]，数据已被篡改！",
        )

    # 2. 重新验证平台 HMAC-SHA256 签名真实性
    expected_sig = compute_hmac_signature(cert.evidence_sha256, secret_key=secret_key)
    if not hmac.compare_digest(expected_sig, cert.hmac_signature):
        return (
            CoverageVerificationVerdict.TAMPERED_INVALID,
            "平台 HMAC 数字签名无效或由非可信私钥伪造，判定为非法证书！",
        )

    return (
        CoverageVerificationVerdict.VALID,
        f"证书 [{certificate_id}] 验签成功：64 位 SHA-256 指纹与 HMAC 权威签名双重校验通过，覆盖率数据绝对真实未被篡改。",
    )


def get_coverage_certificate(certificate_id: str) -> Optional[CoverageEvidenceCertificate]:
    """获取指定存证证书"""
    return _COVERAGE_CERT_STORE.get(certificate_id)


def list_coverage_certificates(project_id: Optional[str] = None) -> List[CoverageEvidenceCertificate]:
    """列出存证证书列表，支持按项目 ID 过滤"""
    certs = list(_COVERAGE_CERT_STORE.values())
    if project_id:
        return [c for c in certs if c.project_id == project_id]
    return sorted(certs, key=lambda c: c.issued_at, reverse=True)
