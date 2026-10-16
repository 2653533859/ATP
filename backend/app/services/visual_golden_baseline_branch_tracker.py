"""多版本视觉黄金基线快照管理与跨分支差异演变追踪器 (T1.3)。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class BaselineEvolutionType(str, Enum):
    """基线演化变更分类。"""

    INTENTIONAL_REDESIGN = "INTENTIONAL_REDESIGN"  # 预期内的品牌样式改版
    UNINTENDED_REGRESSION = "UNINTENDED_REGRESSION"  # 潜在非预期视觉回归
    NEW_PAGE_BASELINE = "NEW_PAGE_BASELINE"  # 全新页面初始基线建立
    IDENTICAL_BASELINE = "IDENTICAL_BASELINE"  # 与主干基准完全一致


@dataclass
class VisualBaselineSnapshot:
    """单个版本的页面视觉基线快照。"""

    baseline_id: str
    page_route: str
    branch_name: str
    version_tag: str
    viewport_snapshots: dict[str, str]  # viewport -> snapshot_hash (如 DESKTOP: sha256_xxx)
    approved_by: str = "system"
    is_active_golden: bool = False
    changelog: str = "初始创建视觉基线"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_id": self.baseline_id,
            "page_route": self.page_route,
            "branch_name": self.branch_name,
            "version_tag": self.version_tag,
            "viewport_snapshots": self.viewport_snapshots,
            "approved_by": self.approved_by,
            "is_active_golden": self.is_active_golden,
            "changelog": self.changelog,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class CrossBranchBaselineDiffReport:
    """跨分支基线差异演化比对报告。"""

    report_id: str
    page_route: str
    source_branch: str
    target_branch: str
    evolution_type: BaselineEvolutionType
    source_version: str
    target_version: str
    has_viewport_drifts: bool
    drifted_viewports: list[str]
    audit_recommendation: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "page_route": self.page_route,
            "source_branch": self.source_branch,
            "target_branch": self.target_branch,
            "evolution_type": self.evolution_type.value,
            "source_version": self.source_version,
            "target_version": self.target_version,
            "has_viewport_drifts": self.has_viewport_drifts,
            "drifted_viewports": self.drifted_viewports,
            "audit_recommendation": self.audit_recommendation,
            "created_at": self.created_at.isoformat(),
        }


# 全局视觉基线仓库
_BASELINES_STORE: dict[str, VisualBaselineSnapshot] = {}
_CROSS_BRANCH_REPORTS: dict[str, CrossBranchBaselineDiffReport] = {}


def clear_baseline_tracker_store() -> None:
    """清空基线仓库（单测专用）。"""
    _BASELINES_STORE.clear()
    _CROSS_BRANCH_REPORTS.clear()


def register_visual_baseline(
    page_route: str,
    branch_name: str,
    version_tag: str,
    viewport_snapshots: dict[str, str],
    approved_by: str = "tester",
    is_active_golden: bool = False,
    changelog: str = "提交视觉基线更新",
) -> VisualBaselineSnapshot:
    """登记新的页面多视口视觉基线快照。"""
    # 若标记为 active golden，先将同页面同分支的其他基线取消激活
    if is_active_golden:
        for b in _BASELINES_STORE.values():
            if b.page_route == page_route and b.branch_name == branch_name:
                b.is_active_golden = False

    clean_route = page_route.replace("/", "_").strip("_")
    clean_branch = branch_name.replace("/", "_").strip("_")
    clean_version = version_tag.replace("/", "_").strip("_")
    b_id = f"base_{clean_route}_{clean_branch}_{clean_version}_{uuid.uuid4().hex[:6]}"

    snapshot = VisualBaselineSnapshot(
        baseline_id=b_id,
        page_route=page_route,
        branch_name=branch_name,
        version_tag=version_tag,
        viewport_snapshots=viewport_snapshots,
        approved_by=approved_by,
        is_active_golden=is_active_golden,
        changelog=changelog,
    )
    _BASELINES_STORE[b_id] = snapshot
    return snapshot


def promote_baseline_to_golden(
    baseline_id: str,
    approver: str,
) -> dict[str, Any]:
    """将候选基线审批提升为当前分支的生效黄金基线。"""
    target = _BASELINES_STORE.get(baseline_id)
    if not target:
        return {"success": False, "message": f"基线快照 [{baseline_id}] 不存在"}

    # 取消同路由同分支旧基线激活态
    for b in _BASELINES_STORE.values():
        if b.page_route == target.page_route and b.branch_name == target.branch_name:
            b.is_active_golden = False

    target.is_active_golden = True
    target.approved_by = approver
    return {
        "success": True,
        "message": f"页面 [{target.page_route}] 分支 [{target.branch_name}] 基线版本 [{target.version_tag}] 已由 [{approver}] 成功提升为黄金基线。",
        "baseline": target.to_dict(),
    }


def compare_cross_branch_baselines(
    page_route: str,
    source_branch: str,
    target_branch: str = "main",
) -> CrossBranchBaselineDiffReport:
    """比对来源特性分支与主干分支的生效黄金基线，评估演化差异。"""
    # 查找两分支的黄金基线（若无则取最新）
    src_candidates = [
        b for b in _BASELINES_STORE.values() if b.page_route == page_route and b.branch_name == source_branch
    ]
    tgt_candidates = [
        b for b in _BASELINES_STORE.values() if b.page_route == page_route and b.branch_name == target_branch
    ]

    src_base = next((b for b in src_candidates if b.is_active_golden), src_candidates[-1] if src_candidates else None)
    tgt_base = next((b for b in tgt_candidates if b.is_active_golden), tgt_candidates[-1] if tgt_candidates else None)

    now = datetime.now(timezone.utc)
    report_id = f"cb_diff_{page_route.replace('/', '_').strip('_')}_{int(now.timestamp())}"

    if not src_base and not tgt_base:
        rep = CrossBranchBaselineDiffReport(
            report_id=report_id,
            page_route=page_route,
            source_branch=source_branch,
            target_branch=target_branch,
            evolution_type=BaselineEvolutionType.NEW_PAGE_BASELINE,
            source_version="none",
            target_version="none",
            has_viewport_drifts=False,
            drifted_viewports=[],
            audit_recommendation="两分支均未建立基线，建议完成设计评审后建立主干初始黄金基线。",
            created_at=now,
        )
        _CROSS_BRANCH_REPORTS[report_id] = rep
        return rep

    if not tgt_base and src_base:
        rep = CrossBranchBaselineDiffReport(
            report_id=report_id,
            page_route=page_route,
            source_branch=source_branch,
            target_branch=target_branch,
            evolution_type=BaselineEvolutionType.NEW_PAGE_BASELINE,
            source_version=src_base.version_tag,
            target_version="none",
            has_viewport_drifts=True,
            drifted_viewports=list(src_base.viewport_snapshots.keys()),
            audit_recommendation=f"来源分支 [{source_branch}] 引入全新页面，合入主干前需由 UI 设计师完成初次设计核验。",
            created_at=now,
        )
        _CROSS_BRANCH_REPORTS[report_id] = rep
        return rep

    assert src_base is not None and tgt_base is not None
    drifted_vps = []
    all_vps = sorted(set(src_base.viewport_snapshots.keys()) | set(tgt_base.viewport_snapshots.keys()))

    for vp in all_vps:
        src_hash = src_base.viewport_snapshots.get(vp)
        tgt_hash = tgt_base.viewport_snapshots.get(vp)
        if src_hash != tgt_hash:
            drifted_vps.append(vp)

    has_drift = len(drifted_vps) > 0
    if not has_drift:
        evo_type = BaselineEvolutionType.IDENTICAL_BASELINE
        rec = "两分支视口基线完全一致，无视觉层冲突。"
    elif "重构" in src_base.changelog or "改版" in src_base.changelog or "redesign" in src_base.changelog.lower():
        evo_type = BaselineEvolutionType.INTENTIONAL_REDESIGN
        rec = f"分支 [{source_branch}] 进行了主动页面改版，合入主干后应自动提升为新一代黄金基线。"
    else:
        evo_type = BaselineEvolutionType.UNINTENDED_REGRESSION
        rec = f"检测到 {len(drifted_vps)} 个视口存在未在 Changelog 明确声明的视觉差异，需人工复核是否为意外引入的布局错位。"

    rep = CrossBranchBaselineDiffReport(
        report_id=report_id,
        page_route=page_route,
        source_branch=source_branch,
        target_branch=target_branch,
        evolution_type=evo_type,
        source_version=src_base.version_tag,
        target_version=tgt_base.version_tag,
        has_viewport_drifts=has_drift,
        drifted_viewports=drifted_vps,
        audit_recommendation=rec,
        created_at=now,
    )
    _CROSS_BRANCH_REPORTS[report_id] = rep
    return rep


def get_visual_baseline(baseline_id: str) -> VisualBaselineSnapshot | None:
    """按 ID 查询基线快照。"""
    return _BASELINES_STORE.get(baseline_id)


def list_visual_baselines(page_route: str | None = None, branch_name: str | None = None) -> list[dict[str, Any]]:
    """查询基线列表（支持按页面和分支过滤）。"""
    items = list(_BASELINES_STORE.values())
    if page_route:
        items = [b for b in items if b.page_route == page_route]
    if branch_name:
        items = [b for b in items if b.branch_name == branch_name]
    return [b.to_dict() for b in reversed(items)]
