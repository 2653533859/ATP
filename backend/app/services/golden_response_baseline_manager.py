"""接口黄金响应基线版本化管理与回归偏离判定器服务 (T2.3)。

为接口重构回归与影子流量比对提供官方认证的黄金基线生命周期管理：
1. 黄金响应基线版本化打标 (v1.0-prod-gold, v2.0-rc 等)；
2. 设定各接口自适应容差阈值 (默认 ≥95% 相似度)；
3. 联动 T2.2 traffic_diff_comparator 执行字段级去噪精准比对；
4. 捕获核心字段删除与类型漂移，判定回归偏离报警等级 (NORMAL / WARNING / CRITICAL)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
import logging
import re
from typing import Any
import uuid

from app.services.traffic_diff_comparator import (
    NoiseFilterConfig,
    compare_traffic_responses,
)

logger = logging.getLogger(__name__)


class DriftAlertLevel(str, Enum):
    NORMAL = "NORMAL"  # 正常: 相似度达标且无核心阻断差异
    WARNING = "WARNING"  # 警告: 相似度接近临界线或存在非核心字段变更
    CRITICAL = "CRITICAL"  # 严重阻断: 相似度低于容差阈值，或出现字段删除/类型漂移


@dataclass
class GoldenBaselineItem:
    baseline_id: str
    endpoint: str  # 如 POST /api/v1/orders/checkout
    protocol: str  # HTTP | GRPC
    version_tag: str  # 如 v1.0-prod-gold
    description: str
    golden_request_body: str
    golden_response_status: int
    golden_response_body: str
    tolerance_threshold_pct: float = 95.0
    is_active: bool = True
    tags: dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_id": self.baseline_id,
            "endpoint": self.endpoint,
            "protocol": self.protocol,
            "version_tag": self.version_tag,
            "description": self.description,
            "golden_request_body": self.golden_request_body,
            "golden_response_status": self.golden_response_status,
            "golden_response_body": self.golden_response_body,
            "tolerance_threshold_pct": self.tolerance_threshold_pct,
            "is_active": self.is_active,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class BaselineVerificationResult:
    verification_id: str
    baseline_id: str
    version_tag: str
    endpoint: str
    actual_status_code: int
    similarity_score_pct: float
    tolerance_threshold_pct: float
    passed: bool
    diff_report_id: str
    critical_diffs_count: int
    warning_diffs_count: int
    alert_level: DriftAlertLevel
    summary: str
    verified_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "verification_id": self.verification_id,
            "baseline_id": self.baseline_id,
            "version_tag": self.version_tag,
            "endpoint": self.endpoint,
            "actual_status_code": self.actual_status_code,
            "similarity_score_pct": round(self.similarity_score_pct, 2),
            "tolerance_threshold_pct": self.tolerance_threshold_pct,
            "passed": self.passed,
            "diff_report_id": self.diff_report_id,
            "critical_diffs_count": self.critical_diffs_count,
            "warning_diffs_count": self.warning_diffs_count,
            "alert_level": self.alert_level.value,
            "summary": self.summary,
            "verified_at": self.verified_at.isoformat(),
        }


@dataclass
class BatchVerificationReport:
    batch_id: str
    total_verified: int
    passed_count: int
    drifted_count: int
    pass_rate_pct: float
    results: list[BaselineVerificationResult]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "total_verified": self.total_verified,
            "passed_count": self.passed_count,
            "drifted_count": self.drifted_count,
            "pass_rate_pct": round(self.pass_rate_pct, 2),
            "results": [r.to_dict() for r in self.results],
            "created_at": self.created_at.isoformat(),
        }


# 全局内存基线与批次报告仓库
_GOLDEN_BASELINES: dict[str, GoldenBaselineItem] = {}
_BATCH_VERIFICATIONS: dict[str, BatchVerificationReport] = {}


def create_or_update_golden_baseline(
    endpoint: str,
    golden_response_body: str | dict[str, Any],
    golden_response_status: int = 200,
    golden_request_body: str = "",
    protocol: str = "HTTP",
    version_tag: str = "v1.0-prod-gold",
    description: str = "",
    tolerance_threshold_pct: float = 95.0,
    is_active: bool = True,
    baseline_id: str | None = None,
    tags: dict[str, str] | None = None,
) -> GoldenBaselineItem:
    """创建或更新黄金响应基线快照。"""
    resp_body_str = (
        json.dumps(golden_response_body, ensure_ascii=False)
        if isinstance(golden_response_body, (dict, list))
        else str(golden_response_body)
    )

    b_id = baseline_id or f"gbl_{uuid.uuid4().hex[:10]}"
    now = datetime.now(timezone.utc)

    item = GoldenBaselineItem(
        baseline_id=b_id,
        endpoint=endpoint.strip(),
        protocol=protocol.upper(),
        version_tag=version_tag.strip(),
        description=description or f"针对接口 {endpoint} 的官方黄金响应基线快照",
        golden_request_body=golden_request_body,
        golden_response_status=golden_response_status,
        golden_response_body=resp_body_str,
        tolerance_threshold_pct=float(tolerance_threshold_pct),
        is_active=is_active,
        tags=tags or {},
        created_at=now,
        updated_at=now,
    )

    _GOLDEN_BASELINES[b_id] = item
    logger.info("黄金响应基线已录入 [%s]: %s (版本: %s)", b_id, endpoint, version_tag)
    return item


def get_golden_baseline(baseline_id: str) -> GoldenBaselineItem | None:
    """根据 ID 获取黄金响应基线。"""
    return _GOLDEN_BASELINES.get(baseline_id)


def get_golden_baseline_by_endpoint(endpoint: str, version_tag: str | None = None) -> GoldenBaselineItem | None:
    """根据接口端点 (及可选的版本标签) 获取生效的黄金基线。"""
    endpoint_clean = endpoint.strip()
    candidates = [b for b in _GOLDEN_BASELINES.values() if b.is_active and b.endpoint.lower() == endpoint_clean.lower()]
    if not candidates:
        return None

    if version_tag:
        tag_match = next((b for b in candidates if b.version_tag == version_tag), None)
        if tag_match:
            return tag_match

    # 默认返回最新创建/更新的基线
    candidates.sort(key=lambda b: b.updated_at, reverse=True)
    return candidates[0]


def list_golden_baselines(
    endpoint_pattern: str | None = None,
    version_tag: str | None = None,
    is_active: bool | None = None,
) -> list[GoldenBaselineItem]:
    """多维检索黄金响应基线列表。"""
    items = list(_GOLDEN_BASELINES.values())

    if endpoint_pattern:
        try:
            reg = re.compile(endpoint_pattern, re.IGNORECASE)
            items = [b for b in items if reg.search(b.endpoint)]
        except re.error:
            items = [b for b in items if endpoint_pattern.lower() in b.endpoint.lower()]

    if version_tag:
        items = [b for b in items if b.version_tag == version_tag]

    if is_active is not None:
        items = [b for b in items if b.is_active == is_active]

    items.sort(key=lambda b: b.updated_at, reverse=True)
    return items


def delete_golden_baseline(baseline_id: str) -> bool:
    """删除指定黄金基线。"""
    if baseline_id in _GOLDEN_BASELINES:
        del _GOLDEN_BASELINES[baseline_id]
        return True
    return False


def verify_response_against_baseline(
    baseline_id_or_item: str | GoldenBaselineItem,
    actual_response_body: str | dict[str, Any],
    actual_status_code: int = 200,
    custom_tolerance_pct: float | None = None,
    noise_config: NoiseFilterConfig | None = None,
) -> BaselineVerificationResult:
    """对比实测/回放响应与指定黄金基线，判定是否发生显著回归偏离并评定报警级别。"""
    if isinstance(baseline_id_or_item, str):
        baseline = get_golden_baseline(baseline_id_or_item)
        if not baseline:
            raise ValueError(f"未找到黄金响应基线: {baseline_id_or_item}")
    else:
        baseline = baseline_id_or_item

    tolerance = custom_tolerance_pct if custom_tolerance_pct is not None else baseline.tolerance_threshold_pct

    # 调用 T2.2 traffic_diff_comparator
    diff_report = compare_traffic_responses(
        baseline_response_body=baseline.golden_response_body,
        replayed_response_body=actual_response_body,
        baseline_status_code=baseline.golden_response_status,
        replayed_status_code=actual_status_code,
        config=noise_config,
    )

    similarity = diff_report.similarity_score_pct
    crit_count = diff_report.critical_diffs_count
    warn_count = diff_report.warning_diffs_count

    # 偏离判定逻辑
    passed = (similarity >= tolerance) and (crit_count == 0)

    if passed:
        alert_level = DriftAlertLevel.NORMAL
        summary = (
            f"回归校验通过！实测相似度 {similarity:.1f}% 达到基线阈值 ({tolerance}%)，" f"且无关键字段缺失或业务篡改。"
        )
    elif crit_count > 0:
        alert_level = DriftAlertLevel.CRITICAL
        summary = (
            f"【严重回归阻断】实测相似度 {similarity:.1f}%，检出 {crit_count} 处阻断级核心差异"
            f"(字段删除/类型漂移/核心值篡改)，严禁直接合流上线！"
        )
    else:
        alert_level = DriftAlertLevel.WARNING
        summary = (
            f"【回归偏离告警】实测相似度 {similarity:.1f}% 低于容差基线 ({tolerance}%)，"
            f"存在 {warn_count} 处次要差异，建议人工核验新逻辑。"
        )

    verif_id = f"vrf_{uuid.uuid4().hex[:10]}"
    res = BaselineVerificationResult(
        verification_id=verif_id,
        baseline_id=baseline.baseline_id,
        version_tag=baseline.version_tag,
        endpoint=baseline.endpoint,
        actual_status_code=actual_status_code,
        similarity_score_pct=similarity,
        tolerance_threshold_pct=tolerance,
        passed=passed,
        diff_report_id=diff_report.report_id,
        critical_diffs_count=crit_count,
        warning_diffs_count=warn_count,
        alert_level=alert_level,
        summary=summary,
    )
    return res


def batch_verify_against_baselines(
    actual_items: list[dict[str, Any]],
    default_version_tag: str | None = None,
    noise_config: NoiseFilterConfig | None = None,
) -> BatchVerificationReport:
    """批量校验一组实测/回放响应并输出全景偏离汇总报告。"""
    batch_id = f"bvr_{uuid.uuid4().hex[:12]}"
    results: list[BaselineVerificationResult] = []
    passed_count = 0
    drifted_count = 0

    for it in actual_items:
        endpoint_raw = str(it.get("endpoint", "") or it.get("path_or_endpoint", "")).strip()
        parts = endpoint_raw.split(maxsplit=1)
        if len(parts) == 2 and parts[0].upper() in ("GET", "POST", "PUT", "DELETE", "PATCH", "GRPC"):
            full_endpoint = f"{parts[0].upper()} {parts[1]}"
        else:
            method = str(it.get("method", "GET")).upper()
            full_endpoint = f"{method} {endpoint_raw}"

        baseline_id = it.get("baseline_id")
        baseline = None
        if baseline_id:
            baseline = get_golden_baseline(str(baseline_id))
        if not baseline:
            baseline = get_golden_baseline_by_endpoint(full_endpoint, default_version_tag)

        if not baseline:
            logger.warning("未找到匹配的黄金基线，跳过此条目: %s", full_endpoint)
            continue

        actual_resp = it.get("response_body", "")
        actual_status = int(it.get("response_status_code", it.get("status_code", 200)))
        custom_tol = float(it["tolerance_threshold_pct"]) if "tolerance_threshold_pct" in it else None

        v_res = verify_response_against_baseline(
            baseline_id_or_item=baseline,
            actual_response_body=actual_resp,
            actual_status_code=actual_status,
            custom_tolerance_pct=custom_tol,
            noise_config=noise_config,
        )
        results.append(v_res)
        if v_res.passed:
            passed_count += 1
        else:
            drifted_count += 1

    total = len(results)
    pass_rate = (passed_count / total * 100.0) if total > 0 else 0.0

    report = BatchVerificationReport(
        batch_id=batch_id,
        total_verified=total,
        passed_count=passed_count,
        drifted_count=drifted_count,
        pass_rate_pct=pass_rate,
        results=results,
    )
    _BATCH_VERIFICATIONS[batch_id] = report
    return report


def get_batch_verification_report(batch_id: str) -> BatchVerificationReport | None:
    """获取指定批次黄金基线回归偏离报告。"""
    return _BATCH_VERIFICATIONS.get(batch_id)


def list_batch_verification_reports() -> list[BatchVerificationReport]:
    """查询历史黄金基线批量回归验证报告。"""
    reports = list(_BATCH_VERIFICATIONS.values())
    reports.sort(key=lambda r: r.created_at, reverse=True)
    return reports


def clear_golden_baselines() -> int:
    """清空黄金响应基线与验证报告缓存。"""
    count = len(_GOLDEN_BASELINES)
    _GOLDEN_BASELINES.clear()
    _BATCH_VERIFICATIONS.clear()
    return count
