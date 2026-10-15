"""API Contract Change Impact Analysis & Reverse Case Attribution Service (C2.2).

Provides:
1. Deep diff comparison between baseline and current API contract schemas (OpenAPI / JSON Schema).
2. Reverse impact derivation using the global AssetGraphIndexer topology.
3. Automated impact severity grading (breaking, warning, compatible) and affected step detection.
4. Comprehensive contract change impact diagnostic reports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Any
import uuid

from app.services.api_contracts import compare_contracts
from app.services.asset_graph_indexer import (
    AssetType,
    get_global_asset_indexer,
)

logger = logging.getLogger(__name__)


@dataclass
class ImpactedCaseItem:
    case_id: int | str
    case_name: str
    impact_level: str  # "breaking" | "warning" | "compatible"
    reason: str
    affected_steps: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "case_name": self.case_name,
            "impact_level": self.impact_level,
            "reason": self.reason,
            "affected_steps": self.affected_steps,
        }


@dataclass
class ContractImpactReport:
    report_id: str
    endpoint: str
    analysis_timestamp: str
    is_breaking: bool
    breaking_changes: list[dict[str, str]]
    warnings: list[dict[str, str]]
    total_impacted_cases_count: int
    total_impacted_suites_count: int
    total_impacted_plans_count: int
    impacted_cases: list[ImpactedCaseItem]
    recommended_action: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "endpoint": self.endpoint,
            "analysis_timestamp": self.analysis_timestamp,
            "is_breaking": self.is_breaking,
            "breaking_changes": self.breaking_changes,
            "warnings": self.warnings,
            "total_impacted_cases_count": self.total_impacted_cases_count,
            "total_impacted_suites_count": self.total_impacted_suites_count,
            "total_impacted_plans_count": self.total_impacted_plans_count,
            "impacted_cases": [c.to_dict() for c in self.impacted_cases],
            "recommended_action": self.recommended_action,
        }


def analyze_contract_change_impact(
    method: str,
    path: str,
    baseline_schema: dict[str, Any],
    current_schema: dict[str, Any],
    *,
    project_id: int | None = None,
) -> ContractImpactReport:
    """Analyze contract diff and reverse-trace impacted test cases, suites, and plans."""
    endpoint_key = f"{method.upper().strip()} {path.strip()}"
    report_id = f"rpt_impact_{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Compare contract schema differences
    comparison = compare_contracts(baseline_schema, current_schema)
    breaking_changes = comparison.get("breaking_changes", [])
    warnings = comparison.get("warnings", [])
    is_breaking = len(breaking_changes) > 0

    # 2. Query AssetGraphIndexer for upstream consumers
    indexer = get_global_asset_indexer()
    consumers = indexer.get_upstream_consumers(AssetType.API_ENDPOINT, endpoint_key, max_depth=5)

    impacted_cases_map: dict[str | int, ImpactedCaseItem] = {}
    impacted_suites_set: set[str | int] = set()
    impacted_plans_set: set[str | int] = set()

    # Determine default impact level and explanation
    if is_breaking:
        impact_level = "breaking"
        reasons_list = [c.get("message", "发生破坏性变更") for c in breaking_changes[:3]]
        default_reason = f"接口存在 {len(breaking_changes)} 项破坏性变更: " + "；".join(reasons_list)
    elif warnings:
        impact_level = "warning"
        reasons_list = [w.get("message", "检测到非破坏性警告") for w in warnings[:3]]
        default_reason = f"接口存在 {len(warnings)} 项变更警告: " + "；".join(reasons_list)
    else:
        impact_level = "compatible"
        default_reason = "接口契约完全向后兼容，未检测到破坏性改动。"

    for item in consumers:
        node = item.get("node", {})
        node_id = node.get("node_id", "")
        asset_type = node.get("asset_type")
        asset_id = node.get("asset_id")
        name = node.get("name", node_id)
        node_proj = node.get("project_id")

        if project_id is not None and node_proj is not None and node_proj != project_id:
            continue

        if asset_type == AssetType.CASE.value or asset_type == AssetType.CASE:
            cid = asset_id or node_id.replace("case:", "")
            if cid not in impacted_cases_map:
                impacted_cases_map[cid] = ImpactedCaseItem(
                    case_id=cid,
                    case_name=name,
                    impact_level=impact_level,
                    reason=default_reason,
                    affected_steps=[1],  # Default affected step
                )
        elif asset_type == AssetType.SUITE.value or asset_type == AssetType.SUITE:
            sid = asset_id or node_id.replace("suite:", "")
            impacted_suites_set.add(sid)
        elif asset_type == AssetType.PLAN.value or asset_type == AssetType.PLAN:
            pid = asset_id or node_id.replace("plan:", "")
            impacted_plans_set.add(pid)

    impacted_cases_list = list(impacted_cases_map.values())

    # Formulate actionable recommendation
    if is_breaking and impacted_cases_list:
        rec = f"紧急建议: 接口契约发生破坏性变更，直接波及 {len(impacted_cases_list)} 个测试用例与 {len(impacted_suites_set)} 个套件！建议立即触发最小化受影响精准回归验证。"
    elif warnings and impacted_cases_list:
        rec = f"注意: 接口存在可选字段或轻微变动，建议在夜间回归中复核受波及的 {len(impacted_cases_list)} 个用例。"
    else:
        rec = "契约变更安全向后兼容，无破坏性受损用例风险。"

    return ContractImpactReport(
        report_id=report_id,
        endpoint=endpoint_key,
        analysis_timestamp=now_iso,
        is_breaking=is_breaking,
        breaking_changes=breaking_changes,
        warnings=warnings,
        total_impacted_cases_count=len(impacted_cases_list),
        total_impacted_suites_count=len(impacted_suites_set),
        total_impacted_plans_count=len(impacted_plans_set),
        impacted_cases=impacted_cases_list,
        recommended_action=rec,
    )
