"""业务分支与契约多维漏测血缘分析器服务 (T2.1)

对齐业务需求 (Requirement)、API 接口契约、页面交互与测试用例覆盖矩阵:
1. 构建 4 层血缘依赖图谱 (Requirement ➔ Endpoint ➔ Business Branch ➔ Test Case);
2. 计算路径覆盖率与分支覆盖率 (Branch Coverage Rate);
3. 智能标定漏测盲区节点 (Coverage Gap / 未覆盖红斑) 与风险定级 (HIGH/MEDIUM/LOW);
4. 输出多级层级树与全网拓扑数据供前端可视化渲染。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class CoverageRiskLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NONE = "NONE"


class LineageCategory(str, Enum):
    REQUIREMENT = "requirement"
    API_ENDPOINT = "api_endpoint"
    UI_INTERACTION = "ui_interaction"
    BUSINESS_BRANCH = "business_branch"


@dataclass
class CoverageLineageNode:
    node_id: str
    node_name: str
    category: LineageCategory
    expected_branches: List[str]
    covered_branches: List[str]
    linked_case_ids: List[str] = field(default_factory=list)
    risk_level: CoverageRiskLevel = CoverageRiskLevel.LOW
    description: str = ""

    @property
    def coverage_rate(self) -> float:
        if not self.expected_branches:
            return 1.0
        return round(len(self.covered_branches) / len(self.expected_branches), 3)

    @property
    def is_gap(self) -> bool:
        return self.coverage_rate < 1.0

    @property
    def missing_branches(self) -> List[str]:
        covered_set = set(self.covered_branches)
        return [b for b in self.expected_branches if b not in covered_set]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_name": self.node_name,
            "category": self.category.value,
            "expected_branches": self.expected_branches,
            "covered_branches": self.covered_branches,
            "missing_branches": self.missing_branches,
            "coverage_rate": self.coverage_rate,
            "is_gap": self.is_gap,
            "risk_level": self.risk_level.value,
            "linked_case_ids": self.linked_case_ids,
            "description": self.description,
        }


@dataclass
class CoverageLineageEdge:
    edge_id: str
    source_id: str
    target_id: str
    relationship: str  # implements | triggers | validates

    def to_dict(self) -> Dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relationship": self.relationship,
        }


@dataclass
class CoverageLineageReport:
    report_id: str
    project_id: str
    total_nodes_count: int
    gap_nodes_count: int
    overall_coverage_rate: float
    high_risk_gaps_count: int
    nodes: List[CoverageLineageNode]
    edges: List[CoverageLineageEdge]
    tree_hierarchy: List[Dict[str, Any]]
    analyzed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "project_id": self.project_id,
            "total_nodes_count": self.total_nodes_count,
            "gap_nodes_count": self.gap_nodes_count,
            "overall_coverage_rate": self.overall_coverage_rate,
            "high_risk_gaps_count": self.high_risk_gaps_count,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "tree_hierarchy": self.tree_hierarchy,
            "analyzed_at": self.analyzed_at,
        }


# 全局轻量级漏测分析报告字典
_COVERAGE_REPORT_STORE: Dict[str, CoverageLineageReport] = {}


def clear_coverage_reports() -> None:
    _COVERAGE_REPORT_STORE.clear()


def get_coverage_report(report_id: str) -> Optional[CoverageLineageReport]:
    return _COVERAGE_REPORT_STORE.get(report_id)


def list_coverage_reports(limit: int = 50) -> List[Dict[str, Any]]:
    return [r.to_dict() for r in reversed(list(_COVERAGE_REPORT_STORE.values())[-limit:])]


def analyze_coverage_lineage(
    project_id: str,
    nodes: List[CoverageLineageNode],
    edges: List[CoverageLineageEdge],
) -> CoverageLineageReport:
    """计算业务分支与测试用例覆盖矩阵，标定漏测盲区与层级树"""
    report_id = f"covrep_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')[:17]}"

    # 1. 判定风险定级
    high_risk_count = 0
    gap_count = 0
    total_expected = 0
    total_covered = 0

    for n in nodes:
        total_expected += len(n.expected_branches)
        total_covered += len(n.covered_branches)

        if n.is_gap:
            gap_count += 1
            # 若缺失分支为异常/安全/支付关键，评定为 HIGH
            missing_text = " ".join(n.missing_branches).lower()
            if any(
                k in missing_text
                for k in ("error", "fail", "timeout", "pay", "auth", "exception", "超时", "异常", "失败", "鉴权")
            ):
                n.risk_level = CoverageRiskLevel.HIGH
                high_risk_count += 1
            elif n.coverage_rate < 0.5:
                n.risk_level = CoverageRiskLevel.HIGH
                high_risk_count += 1
            else:
                n.risk_level = CoverageRiskLevel.MEDIUM
        else:
            n.risk_level = CoverageRiskLevel.NONE

    overall_rate = round(total_covered / max(1, total_expected), 3)

    # 2. 构建层级树形结构 (从顶层需求到叶子分支)
    node_map = {n.node_id: n for n in nodes}
    children_map: Dict[str, List[str]] = {n.node_id: [] for n in nodes}
    in_degrees: Dict[str, int] = {n.node_id: 0 for n in nodes}

    for e in edges:
        if e.source_id in node_map and e.target_id in node_map:
            children_map[e.source_id].append(e.target_id)
            in_degrees[e.target_id] += 1

    root_ids = [nid for nid, deg in in_degrees.items() if deg == 0]
    if not root_ids and nodes:
        root_ids = [nodes[0].node_id]

    def _build_tree(cur_id: str, depth: int) -> Dict[str, Any]:
        node = node_map[cur_id]
        child_trees = [_build_tree(cid, depth + 1) for cid in children_map.get(cur_id, [])]
        data = node.to_dict()
        data["depth"] = depth
        data["children"] = child_trees
        return data

    hierarchy = [_build_tree(rid, 1) for rid in root_ids]

    report = CoverageLineageReport(
        report_id=report_id,
        project_id=project_id,
        total_nodes_count=len(nodes),
        gap_nodes_count=gap_count,
        overall_coverage_rate=overall_rate,
        high_risk_gaps_count=high_risk_count,
        nodes=nodes,
        edges=edges,
        tree_hierarchy=hierarchy,
    )
    _COVERAGE_REPORT_STORE[report_id] = report
    return report
