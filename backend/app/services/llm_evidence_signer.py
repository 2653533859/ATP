"""大模型评测结论与红蓝攻防验收 64 位 SHA-256 存证证书器服务 (T4.2)

为大模型与 RAG 智能体评测全流程产物提供密码学不可篡改存证:
1. 确定性 Canonical JSON 规范化序列化 (Canonicalization: sorted keys, compact separators);
2. 64 字符十六进制 SHA-256 存证防伪指纹计算;
3. 平台权威防伪数字签名 (HMAC-SHA256);
4. 证书签发、存储检索与在线合规验签防篡改探针 (LlmEvidenceCertificate: VALID | TAMPERED_INVALID)。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import enum
import hashlib
import hmac
import json
from typing import Any, Dict, List, Optional, Tuple
import uuid

from app.services.llm_eval_safety_boundary_guard import LlmSafetyAdmissionVerdict
from app.services.llm_hallucination_detector import HallucinationAuditReport
from app.services.llm_rag_triad_evaluator import RagTriadEvaluationReport
from app.services.llm_red_teaming_attacker import RedTeamSummaryReport


class LlmArtifactType(str, enum.Enum):
    """大模型质效评测存证产物类型"""

    RAG_TRIAD_EVALUATION = "RAG_TRIAD_EVALUATION"  # RAG 三元组质量评测报告
    HALLUCINATION_AUDIT_REPORT = "HALLUCINATION_AUDIT_REPORT"  # 事实一致性与幻觉检出报告
    RED_TEAM_ROBUSTNESS_REPORT = "RED_TEAM_ROBUSTNESS_REPORT"  # 红蓝越狱对抗渗透报告
    LLM_SAFETY_ADMISSION_VERDICT = "LLM_SAFETY_ADMISSION_VERDICT"  # 生产模型线上接入安全强准入裁决


class LlmVerificationVerdict(str, enum.Enum):
    """防篡改验签状态"""

    VALID = "VALID"  # 验签合规通过，未发生任何篡改
    TAMPERED_INVALID = "TAMPERED_INVALID"  # 验签失败，数据或签名被恶意篡改
    CERTIFICATE_NOT_FOUND = "CERTIFICATE_NOT_FOUND"  # 证书未找到


@dataclass
class LlmEvidenceCertificate:
    """不可篡改大模型质效评测证据证书"""

    certificate_id: str
    artifact_type: LlmArtifactType
    artifact_id: str
    target_model: str
    signer_identity: str
    algorithm: str  # SHA-256/HMAC-SHA256
    evidence_sha256: str  # 64 位十六进制 SHA-256 摘要
    hmac_signature: str  # 64 位平台权威数字签名
    canonical_payload: Dict[str, Any]
    summary: Dict[str, Any]
    issued_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


_LLM_CERT_STORE: Dict[str, LlmEvidenceCertificate] = {}
_DEFAULT_LLM_SECRET = b"atp-v6-3-0-llm-eval-evidence-secret-2026"


def clear_llm_certificates() -> None:
    """清空大模型存证证书内存库（测试隔离使用）"""
    _LLM_CERT_STORE.clear()


def compute_canonical_json(data: Dict[str, Any]) -> str:
    """确定性规范化 JSON 序列化 (键排序、紧凑分隔符、UTF-8 保真)"""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_evidence_sha256(canonical_json: str) -> str:
    """计算 64 字符全小写十六进制 SHA-256 散列指纹"""
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def compute_hmac_signature(canonical_json: str, secret: bytes = _DEFAULT_LLM_SECRET) -> str:
    """使用平台秘钥生成 HMAC-SHA256 防伪签名"""
    return hmac.new(secret, canonical_json.encode("utf-8"), hashlib.sha256).hexdigest()


def _issue_and_store_certificate(
    artifact_type: LlmArtifactType,
    artifact_id: str,
    target_model: str,
    canonical_payload: Dict[str, Any],
    summary: Dict[str, Any],
    signer_identity: str = "ATP_LLM_EVAL_PLATFORM_V6_3_0",
    secret: bytes = _DEFAULT_LLM_SECRET,
) -> LlmEvidenceCertificate:
    """内部通用签发流水线"""
    canonical_json = compute_canonical_json(canonical_payload)
    sha256_digest = compute_evidence_sha256(canonical_json)
    signature = compute_hmac_signature(canonical_json, secret=secret)

    cert_id = f"llm_cert_{uuid.uuid4().hex[:12]}"
    cert = LlmEvidenceCertificate(
        certificate_id=cert_id,
        artifact_type=artifact_type,
        artifact_id=artifact_id,
        target_model=target_model,
        signer_identity=signer_identity,
        algorithm="SHA-256/HMAC-SHA256",
        evidence_sha256=sha256_digest,
        hmac_signature=signature,
        canonical_payload=canonical_payload,
        summary=summary,
    )
    _LLM_CERT_STORE[cert_id] = cert
    return cert


def sign_rag_triad_report(
    report: RagTriadEvaluationReport,
    target_model: str = "qwen-2.5-72b",
    secret: bytes = _DEFAULT_LLM_SECRET,
) -> LlmEvidenceCertificate:
    """为 RAG 核心三元组质量评测报告签发存证证书"""
    payload = report.to_dict()
    summary = {
        "evaluation_id": report.evaluation_id,
        "query": report.query,
        "composite_score": report.composite_score,
        "grade": report.grade,
        "context_relevance": report.context_relevance,
        "groundedness": report.groundedness,
        "answer_relevance": report.answer_relevance,
        "chunks_count": len(report.chunks),
    }
    return _issue_and_store_certificate(
        artifact_type=LlmArtifactType.RAG_TRIAD_EVALUATION,
        artifact_id=report.evaluation_id,
        target_model=target_model,
        canonical_payload=payload,
        summary=summary,
        secret=secret,
    )


def sign_hallucination_report(
    report: HallucinationAuditReport,
    target_model: str = "qwen-2.5-72b",
    secret: bytes = _DEFAULT_LLM_SECRET,
) -> LlmEvidenceCertificate:
    """为事实一致性与幻觉检出报告签发存证证书"""
    payload = report.to_dict()
    summary = {
        "audit_id": report.audit_id,
        "verdict": report.verdict.value,
        "hallucination_rate_pct": report.hallucination_rate_pct,
        "factual_consistency_score": report.factual_consistency_score,
        "total_claims_count": report.total_claims_count,
        "hallucinated_claims_count": report.hallucinated_claims_count,
        "findings_count": len(report.findings),
    }
    return _issue_and_store_certificate(
        artifact_type=LlmArtifactType.HALLUCINATION_AUDIT_REPORT,
        artifact_id=report.audit_id,
        target_model=target_model,
        canonical_payload=payload,
        summary=summary,
        secret=secret,
    )


def sign_red_team_report(
    report: RedTeamSummaryReport,
    secret: bytes = _DEFAULT_LLM_SECRET,
) -> LlmEvidenceCertificate:
    """为红蓝越狱对抗渗透评估报告签发存证证书"""
    payload = report.to_dict()
    summary = {
        "report_id": report.report_id,
        "target_model": report.target_model,
        "total_attacks": report.total_attacks,
        "defended_count": report.defended_count,
        "breached_critical_count": report.breached_critical_count,
        "defense_rate_pct": report.defense_rate_pct,
        "robustness_score": report.robustness_score,
    }
    return _issue_and_store_certificate(
        artifact_type=LlmArtifactType.RED_TEAM_ROBUSTNESS_REPORT,
        artifact_id=report.report_id,
        target_model=report.target_model,
        canonical_payload=payload,
        summary=summary,
        secret=secret,
    )


def sign_safety_admission_verdict(
    verdict: LlmSafetyAdmissionVerdict,
    secret: bytes = _DEFAULT_LLM_SECRET,
) -> LlmEvidenceCertificate:
    """为大模型生产安全强准入放行裁决签发存证证书"""
    payload = verdict.to_dict()
    summary = {
        "verdict_id": verdict.verdict_id,
        "verdict_code": verdict.verdict_code.value,
        "is_admitted": verdict.is_admitted,
        "model_name": verdict.model_name,
        "environment": verdict.environment,
        "reason": verdict.reason,
    }
    return _issue_and_store_certificate(
        artifact_type=LlmArtifactType.LLM_SAFETY_ADMISSION_VERDICT,
        artifact_id=verdict.verdict_id,
        target_model=verdict.model_name,
        canonical_payload=payload,
        summary=summary,
        secret=secret,
    )


def get_llm_certificate(certificate_id: str) -> Optional[LlmEvidenceCertificate]:
    """根据证书唯一标识查询存证"""
    return _LLM_CERT_STORE.get(certificate_id)


def list_llm_certificates(
    artifact_type: Optional[LlmArtifactType] = None,
) -> List[LlmEvidenceCertificate]:
    """列出当前内存库中的所有存证证书（可按类型过滤）"""
    all_certs = list(_LLM_CERT_STORE.values())
    if artifact_type:
        return [c for c in all_certs if c.artifact_type == artifact_type]
    return all_certs


def verify_llm_certificate(
    certificate_id: str,
    secret: bytes = _DEFAULT_LLM_SECRET,
) -> Tuple[LlmVerificationVerdict, Optional[str]]:
    """在线校验大模型存证证书指纹与 HMAC 防伪签名

    返回: (LlmVerificationVerdict, 诊断线索说明)
    """
    cert = _LLM_CERT_STORE.get(certificate_id)
    if not cert:
        return (
            LlmVerificationVerdict.CERTIFICATE_NOT_FOUND,
            f"未检索到证书标识为 [{certificate_id}] 的存证记录",
        )

    # 1. 重新计算 Canonical JSON
    recomputed_canonical = compute_canonical_json(cert.canonical_payload)

    # 2. 校验 64 位 SHA-256 摘要
    recomputed_sha256 = compute_evidence_sha256(recomputed_canonical)
    if not hmac.compare_digest(recomputed_sha256, cert.evidence_sha256):
        return (
            LlmVerificationVerdict.TAMPERED_INVALID,
            f"SHA-256 指纹不匹配！原始存证: {cert.evidence_sha256}，重新推导: {recomputed_sha256}",
        )

    # 3. 校验 HMAC 数字签名
    recomputed_signature = compute_hmac_signature(recomputed_canonical, secret=secret)
    if not hmac.compare_digest(recomputed_signature, cert.hmac_signature):
        return (
            LlmVerificationVerdict.TAMPERED_INVALID,
            f"HMAC 防伪签名失效或平台秘钥不匹配！当前签名: {cert.hmac_signature}",
        )

    return (
        LlmVerificationVerdict.VALID,
        f"存证证书 [{certificate_id}] 64 位 SHA-256 指纹与防伪签名校验合规，无篡改痕迹！",
    )
