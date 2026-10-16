"""CI/CD Intelligent Quality Gate Rule Engine & Blocking Decision Point (C4.2).

Provides:
1. Flexible gate rule definitions (pass_rate_pct, open_blocker_defects, composite_health_score, etc.).
2. Operator comparisons (gte, lte, eq, gt, lt) with blocker vs warning severity tiers.
3. Automated CI/CD blocking gate evaluation returning exit_code (0 = Pass, 1 = Block).
4. Predefined enterprise quality gate profiles (Production Release Gate, PR Merge Gate, Nightly Gate).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import Any
import uuid

logger = logging.getLogger(__name__)


@dataclass
class QualityGateRule:
    metric_key: str
    operator: str  # "gte" | "lte" | "eq" | "gt" | "lt"
    threshold: float
    severity: str = "blocker"  # "blocker" | "warning"
    description: str = ""

    def evaluate(self, actual_value: float | int | None) -> tuple[bool, str]:
        """Evaluate rule against actual metric value.

        Returns:
            tuple[bool, str]: (passed, message)
        """
        if actual_value is None:
            return False, f"指标缺少真实数值: {self.metric_key}"

        val = float(actual_value)
        thresh = float(self.threshold)
        passed = False

        if self.operator == "gte":
            passed = val >= thresh
            symbol = ">="
        elif self.operator == "lte":
            passed = val <= thresh
            symbol = "<="
        elif self.operator == "eq":
            passed = abs(val - thresh) < 1e-4
            symbol = "=="
        elif self.operator == "gt":
            passed = val > thresh
            symbol = ">"
        elif self.operator == "lt":
            passed = val < thresh
            symbol = "<"
        else:
            return False, f"未知的操作符: {self.operator}"

        if passed:
            msg = f"达标: {self.metric_key} 实际值 {val} {symbol} 阈值 {thresh}"
        else:
            msg = f"未达标: {self.metric_key} 实际值 {val} 不满足 {symbol} 阈值 {thresh}"

        return passed, msg

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_key": self.metric_key,
            "operator": self.operator,
            "threshold": self.threshold,
            "severity": self.severity,
            "description": self.description,
        }


@dataclass
class QualityGateProfile:
    profile_id: str
    name: str
    description: str
    rules: list[QualityGateRule]
    block_on_failure: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "name": self.name,
            "description": self.description,
            "rules": [r.to_dict() for r in self.rules],
            "block_on_failure": self.block_on_failure,
        }


@dataclass
class GateEvaluationResult:
    decision_id: str
    profile_id: str
    status: str  # "PASSED" | "WARNING" | "BLOCKED"
    exit_code: int  # 0 for Passed / Warning, 1 for Blocked
    evaluated_at: str
    total_rules_checked: int
    passed_rules_count: int
    failed_blockers_count: int
    failed_warnings_count: int
    rule_results: list[dict[str, Any]]
    blocked_reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "profile_id": self.profile_id,
            "status": self.status,
            "exit_code": self.exit_code,
            "evaluated_at": self.evaluated_at,
            "total_rules_checked": self.total_rules_checked,
            "passed_rules_count": self.passed_rules_count,
            "failed_blockers_count": self.failed_blockers_count,
            "failed_warnings_count": self.failed_warnings_count,
            "rule_results": self.rule_results,
            "blocked_reasons": self.blocked_reasons,
        }


# Standard enterprise quality gate baseline profiles
_DEFAULT_PROFILES: dict[str, QualityGateProfile] = {
    "gate_prod_release": QualityGateProfile(
        profile_id="gate_prod_release",
        name="生产环境上线准入标准门禁",
        description="严格检验用例通过率、严重阻塞缺陷与综合质量得分",
        rules=[
            QualityGateRule("pass_rate_pct", "gte", 99.0, "blocker", "测试用例通过率必须 >= 99.0%"),
            QualityGateRule("open_blocker_defects", "lte", 0.0, "blocker", "严禁存在任何未关闭的 Block/Critical 缺陷"),
            QualityGateRule("composite_health_score", "gte", 80.0, "blocker", "全生命周期综合质量健康得分必须 >= 80.0"),
            QualityGateRule("defect_escape_rate_pct", "lte", 5.0, "warning", "建议线上缺陷逃逸率 <= 5.0%"),
        ],
        block_on_failure=True,
    ),
    "gate_pr_check": QualityGateProfile(
        profile_id="gate_pr_check",
        name="CI 代码提交与 Pull Request 合并门禁",
        description="核心 P0 冒烟用例 100% 通过与零阻塞缺陷",
        rules=[
            QualityGateRule("p0_pass_rate_pct", "gte", 100.0, "blocker", "P0 核心场景必须 100% 通过"),
            QualityGateRule("open_blocker_defects", "lte", 0.0, "blocker", "不得引入未解决的阻塞缺陷"),
            QualityGateRule("p95_latency_ms", "lte", 500.0, "warning", "建议 API P95 耗时 <= 500ms"),
        ],
        block_on_failure=True,
    ),
}

_CUSTOM_PROFILES: dict[str, QualityGateProfile] = {}


def register_gate_profile(profile: QualityGateProfile) -> None:
    _CUSTOM_PROFILES[profile.profile_id] = profile


def get_gate_profile(profile_id: str) -> QualityGateProfile | None:
    return _CUSTOM_PROFILES.get(profile_id) or _DEFAULT_PROFILES.get(profile_id)


def list_gate_profiles() -> list[QualityGateProfile]:
    all_profiles = dict(_DEFAULT_PROFILES)
    all_profiles.update(_CUSTOM_PROFILES)
    return list(all_profiles.values())


def evaluate_quality_gate(
    profile_id: str,
    metrics: dict[str, Any],
) -> GateEvaluationResult:
    """Evaluate quality gate profile rules against runtime test & quality metrics."""
    profile = get_gate_profile(profile_id)
    if not profile:
        raise ValueError(f"质量门禁配置策略不存在: {profile_id}")

    decision_id = f"gate_eval_{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    passed_count = 0
    failed_blockers = 0
    failed_warnings = 0
    rule_results: list[dict[str, Any]] = []
    blocked_reasons: list[str] = []

    for rule in profile.rules:
        actual_val = metrics.get(rule.metric_key)
        passed, msg = rule.evaluate(actual_val)

        status_str = "PASSED" if passed else ("FAILED" if rule.severity == "blocker" else "WARN")

        if passed:
            passed_count += 1
        else:
            if rule.severity == "blocker":
                failed_blockers += 1
                blocked_reasons.append(f"阻塞卡点 [{rule.description or rule.metric_key}]: {msg}")
            else:
                failed_warnings += 1

        rule_results.append(
            {
                "metric_key": rule.metric_key,
                "status": status_str,
                "severity": rule.severity,
                "actual_value": actual_val,
                "operator": rule.operator,
                "threshold": rule.threshold,
                "description": rule.description,
                "message": msg,
            }
        )

    # Determine overall status and exit code
    if failed_blockers > 0:
        overall_status = "BLOCKED"
        exit_code = 1 if profile.block_on_failure else 0
        logger.warning(
            "Quality gate %s BLOCKED: %s blocker violations",
            profile_id,
            failed_blockers,
        )
    elif failed_warnings > 0:
        overall_status = "WARNING"
        exit_code = 0
    else:
        overall_status = "PASSED"
        exit_code = 0

    return GateEvaluationResult(
        decision_id=decision_id,
        profile_id=profile_id,
        status=overall_status,
        exit_code=exit_code,
        evaluated_at=now_iso,
        total_rules_checked=len(profile.rules),
        passed_rules_count=passed_count,
        failed_blockers_count=failed_blockers,
        failed_warnings_count=failed_warnings,
        rule_results=rule_results,
        blocked_reasons=blocked_reasons,
    )
