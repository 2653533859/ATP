"""双端功能差异与缺失控件侦测器服务 (T2.2)

基于双端 UI 状态树对齐矩阵深度侦测多端业务功能不对等与潜在漏测缺陷:
1. 核心关键控件单端缺失识别 (MISSING_CORE_CONTROL: 支付、退款、登录等核心业务入口);
2. 业务文案与参数语义漂移探针 (SEMANTIC_TEXT_DRIFT: 文案不一致、金额/规则描述冲突);
3. 跨端交互能力不对等侦测 (ACTION_CAPABILITY_MISMATCH: 可交互输入框退化为纯文本);
4. 差异严重度定级 (CRITICAL | HIGH | MEDIUM | LOW) 与修复建议生成。
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from app.services.parity_alignment_analyzer import (
    AlignmentMatchType,
    ParityAlignmentMatrix,
    ParityNode,
)

# 核心高危业务关键词 (一旦单端缺失，判定为 CRITICAL 致命漏测)
CORE_BUSINESS_KEYWORDS: Set[str] = {
    "支付",
    "付款",
    "结算",
    "购买",
    "提交",
    "下单",
    "退款",
    "售后",
    "登录",
    "注册",
    "密码",
    "实名",
    "充值",
    "提现",
    "转账",
    "确认收货",
    "pay",
    "checkout",
    "submit",
    "refund",
    "login",
    "register",
}


class ParityGapType(str, enum.Enum):
    MISSING_CORE_CONTROL = "MISSING_CORE_CONTROL"  # 单端核心功能入口缺失 (致命)
    MISSING_OPTIONAL_CONTROL = "MISSING_OPTIONAL_CONTROL"  # 单端次要功能/展示控件缺失
    SEMANTIC_TEXT_DRIFT = "SEMANTIC_TEXT_DRIFT"  # 双端文案或参数语义漂移
    ACTION_CAPABILITY_MISMATCH = "ACTION_CAPABILITY_MISMATCH"  # 交互属性/控件角色不对等
    LAYOUT_ORIENTATION_DIFF = "LAYOUT_ORIENTATION_DIFF"  # 布局空间相对颠倒错位


class GapSeverity(str, enum.Enum):
    CRITICAL = "CRITICAL"  # 核心业务漏测/功能缺失
    HIGH = "HIGH"  # 关键差异，影响业务闭环
    MEDIUM = "MEDIUM"  # 普通次要差异
    LOW = "LOW"  # 提示性微小差异


@dataclass
class ParityGapItem:
    gap_id: str
    gap_type: ParityGapType
    severity: GapSeverity
    title: str
    description: str
    source_node: Optional[Dict[str, Any]] = None
    target_node: Optional[Dict[str, Any]] = None
    suggested_fix: str = ""
    detected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["gap_type"] = self.gap_type.value
        d["severity"] = self.severity.value
        return d


@dataclass
class ParityDiscrepancyReport:
    report_id: str
    matrix_id: str
    screen_name: str
    source_platform: str
    target_platform: str
    total_gaps_count: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    gaps: List[ParityGapItem]
    analyzed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "matrix_id": self.matrix_id,
            "screen_name": self.screen_name,
            "source_platform": self.source_platform,
            "target_platform": self.target_platform,
            "total_gaps_count": self.total_gaps_count,
            "critical_count": self.critical_count,
            "high_count": self.high_count,
            "medium_count": self.medium_count,
            "low_count": self.low_count,
            "gaps": [g.to_dict() for g in self.gaps],
            "analyzed_at": self.analyzed_at,
        }


def is_core_business_node(node: ParityNode) -> bool:
    """判定控件是否属于高危核心业务逻辑入口"""
    text = (node.text or "").lower()
    ident = (node.identifier or "").lower()

    # 包含核心业务关键词且为操作控件 (button/input/link)
    if node.role in ("button", "input", "link"):
        if any(kw in text for kw in CORE_BUSINESS_KEYWORDS):
            return True
        if any(kw in ident for kw in CORE_BUSINESS_KEYWORDS):
            return True
    return False


def detect_parity_gaps(matrix: ParityAlignmentMatrix) -> ParityDiscrepancyReport:
    """基于双端对齐矩阵深度侦测功能缺失、语义漂移与交互不对等差异缺陷"""
    report_id = f"prep_{uuid.uuid4().hex[:12]}"
    gaps: List[ParityGapItem] = []

    # 1. 检查源端独有控件 (目标端缺失)
    for src_node in matrix.source_only_nodes:
        gid = f"gap_src_{uuid.uuid4().hex[:8]}"
        is_core = is_core_business_node(src_node)
        if is_core:
            gap = ParityGapItem(
                gap_id=gid,
                gap_type=ParityGapType.MISSING_CORE_CONTROL,
                severity=GapSeverity.CRITICAL,
                title=f"目标端 [{matrix.target_platform}] 缺失核心业务入口: [{src_node.text or src_node.identifier}]",
                description=(
                    f"源端 [{matrix.source_platform}] 包含核心业务控件 [ID: {src_node.node_id}, 文案: '{src_node.text}']，"
                    f"但在目标端未找到对应对齐节点，可能存在严重功能不对等或遗漏实现风险。"
                ),
                source_node=src_node.to_dict(),
                suggested_fix=f"请开发在目标端 [{matrix.target_platform}] 补齐对应的 [{src_node.text}] 功能实现。",
            )
        else:
            gap = ParityGapItem(
                gap_id=gid,
                gap_type=ParityGapType.MISSING_OPTIONAL_CONTROL,
                severity=GapSeverity.MEDIUM,
                title=f"目标端未发现展示控件: [{src_node.text or src_node.identifier or src_node.node_id}]",
                description=f"次要展示或交互控件在 [{matrix.target_platform}] 端未发现对应元素。",
                source_node=src_node.to_dict(),
                suggested_fix="评估是否为平台特定差异设计，如无需对齐可忽略。",
            )
        gaps.append(gap)

    # 2. 检查目标端独有控件 (源端未覆盖)
    for tgt_node in matrix.target_only_nodes:
        gid = f"gap_tgt_{uuid.uuid4().hex[:8]}"
        is_core = is_core_business_node(tgt_node)
        gap = ParityGapItem(
            gap_id=gid,
            gap_type=ParityGapType.MISSING_CORE_CONTROL if is_core else ParityGapType.MISSING_OPTIONAL_CONTROL,
            severity=GapSeverity.HIGH if is_core else GapSeverity.LOW,
            title=f"源端 [{matrix.source_platform}] 未覆盖目标端专有功能: [{tgt_node.text or tgt_node.identifier}]",
            description=f"目标端 [{matrix.target_platform}] 独有控件在源端用例中未被测试用例覆盖，存在回归盲区。",
            target_node=tgt_node.to_dict(),
            suggested_fix="补充跨端对等测试用例，覆盖该专属业务链路。",
        )
        gaps.append(gap)

    # 3. 检查已对齐节点对中的语义漂移与角色冲突
    for pair in matrix.aligned_pairs:
        s_node = pair.source_node
        t_node = pair.target_node

        # 3.1 角色不对等 (如一端是 input 另一端是 label)
        if s_node.role != t_node.role:
            gid = f"gap_role_{uuid.uuid4().hex[:8]}"
            gaps.append(
                ParityGapItem(
                    gap_id=gid,
                    gap_type=ParityGapType.ACTION_CAPABILITY_MISMATCH,
                    severity=GapSeverity.HIGH,
                    title=f"控件交互属性不一致: [{s_node.role}] vs [{t_node.role}]",
                    description=(
                        f"控件在 [{matrix.source_platform}] 为 '{s_node.role}'，但在 [{matrix.target_platform}] "
                        f"为 '{t_node.role}'，可能导致自动化脚本手势无法直接复用或交互能力缺失。"
                    ),
                    source_node=s_node.to_dict(),
                    target_node=t_node.to_dict(),
                    suggested_fix="统一双端交互设计，或在用例中配置平台特定适配手势。",
                )
            )

        # 3.2 语义文案严重漂移 (部分匹配且得分偏低)
        elif pair.match_type == AlignmentMatchType.PARTIAL or pair.alignment_score < 0.75:
            gid = f"gap_drift_{uuid.uuid4().hex[:8]}"
            gaps.append(
                ParityGapItem(
                    gap_id=gid,
                    gap_type=ParityGapType.SEMANTIC_TEXT_DRIFT,
                    severity=GapSeverity.MEDIUM,
                    title=f"双端业务文案语义存在漂移: '{s_node.text}' vs '{t_node.text}'",
                    description=(
                        f"对齐置信度仅为 {round(pair.alignment_score * 100, 1)}%，"
                        f"源端文案为 '{s_node.text}'，目标端文案为 '{t_node.text}'，可能导致用户感知不一致。"
                    ),
                    source_node=s_node.to_dict(),
                    target_node=t_node.to_dict(),
                    suggested_fix="核对产品多端文案规范，排查是否存在多版本文案配置不同步问题。",
                )
            )

    # 统计分类严重度数量
    crit_count = sum(1 for g in gaps if g.severity == GapSeverity.CRITICAL)
    high_count = sum(1 for g in gaps if g.severity == GapSeverity.HIGH)
    med_count = sum(1 for g in gaps if g.severity == GapSeverity.MEDIUM)
    low_count = sum(1 for g in gaps if g.severity == GapSeverity.LOW)

    return ParityDiscrepancyReport(
        report_id=report_id,
        matrix_id=matrix.matrix_id,
        screen_name=matrix.screen_name,
        source_platform=matrix.source_platform,
        target_platform=matrix.target_platform,
        total_gaps_count=len(gaps),
        critical_count=crit_count,
        high_count=high_count,
        medium_count=med_count,
        low_count=low_count,
        gaps=gaps,
    )
