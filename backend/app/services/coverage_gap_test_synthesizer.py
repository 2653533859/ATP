"""缺失用例场景反向合成与测试输入推导器服务 (T2.2)

依据未覆盖高危分支的条件表达式与上下文，反向推导边界测试输入并生成可落地的用例草稿:
1. 分支条件边界参数自动推演引擎 (Boundary Inputs Deduction: 数值边界、空值校验、权限反例、HTTP异常桩);
2. 缺失用例场景草稿逆向生成 (SuggestedTestCaseDraft: 入参、前置Mock、预期断言与测试代码);
3. 预估覆盖率收益精算 (Estimated Coverage Gain %);
4. 结构化补测计划报告输出 (CoverageGapSynthesisPlan)。
"""

from __future__ import annotations

import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.services.uncovered_branch_risk_analyzer import (
    BranchRiskSeverity,
    UncoveredBranchAnalysisReport,
    UncoveredBranchCategory,
    UncoveredBranchItem,
)


@dataclass
class SuggestedTestCaseDraft:
    draft_id: str
    target_branch_id: str
    file_path: str
    target_lines: str
    case_title: str
    test_type: str  # api | unit | scenario
    severity: BranchRiskSeverity
    category: UncoveredBranchCategory
    recommended_inputs: Dict[str, Any]
    expected_assertion: str
    mock_prerequisites: List[str]
    suggested_test_code: str

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["severity"] = self.severity.value
        d["category"] = self.category.value
        return d


@dataclass
class CoverageGapSynthesisPlan:
    plan_id: str
    diff_report_id: str
    total_synthesized_cases: int
    p0_cases_count: int
    p1_cases_count: int
    p2_cases_count: int
    estimated_coverage_gain_pct: float
    cases: List[SuggestedTestCaseDraft]
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "diff_report_id": self.diff_report_id,
            "total_synthesized_cases": self.total_synthesized_cases,
            "p0_cases_count": self.p0_cases_count,
            "p1_cases_count": self.p1_cases_count,
            "p2_cases_count": self.p2_cases_count,
            "estimated_coverage_gain_pct": round(self.estimated_coverage_gain_pct, 1),
            "cases": [c.to_dict() for c in self.cases],
            "generated_at": self.generated_at,
        }


def _deduce_boundary_inputs_from_condition(
    condition_expr: str,
    category: UncoveredBranchCategory,
    code_snippet: str = "",
) -> tuple[Dict[str, Any], str, List[str]]:
    """根据分支条件与代码片段反向推导边界入参、断言与 Mock 依赖"""
    _ = code_snippet
    inputs: Dict[str, Any] = {}
    assertions = "assert response.status_code == 200"
    mocks: List[str] = []

    cond = condition_expr.strip()

    # 1. 资金支付类条件推导
    if category == UncoveredBranchCategory.PAYMENT_FINANCIAL:
        # e.g. amount <= 0 / amount < 0
        if re.search(r"amount\s*<=\s*0", cond) or re.search(r"amount\s*<\s*0", cond):
            inputs["amount"] = -10.0
            assertions = "assert response.status_code == 400 and 'InvalidAmount' in response.text"
        elif re.search(r"amount\s*>\s*(\d+)", cond):
            m = re.search(r"amount\s*>\s*(\d+)", cond)
            val = float(m.group(1)) if m else 1000.0
            inputs["amount"] = val + 1.0
            assertions = "assert response.status_code == 200 and 'discount' in response.json()"
        else:
            inputs["amount"] = 99999.0
            inputs["currency"] = "CNY"
            assertions = "assert response.status_code in (200, 400)"
        mocks.append("Mock: payment_gateway_service (准备测试账号及充足预存款)")

    # 2. 安全鉴权类条件推导
    elif category == UncoveredBranchCategory.AUTH_SECURITY:
        if "token" in cond:
            if "not" in cond or "none" in cond.lower():
                inputs["authorization_header"] = None
                assertions = "assert response.status_code == 401"
            else:
                inputs["authorization_header"] = "Bearer EXPIRED_OR_FORGED_JWT_TOKEN"
                assertions = "assert response.status_code == 403"
        elif "role" in cond or "permission" in cond:
            inputs["user_role"] = "guest_anonymous"
            assertions = "assert response.status_code == 403 and 'PermissionDenied' in response.text"
        else:
            inputs["access_key"] = "invalid_credential_probe"
            assertions = "assert response.status_code in (401, 403)"
        mocks.append("Mock: auth_service (模拟未授权或越权用户上下文)")

    # 3. 异常回滚与超时抛错
    elif category == UncoveredBranchCategory.EXCEPTION_ROLLBACK:
        inputs["trigger_fault_scenario"] = True
        inputs["mock_failure_type"] = "DatabaseTimeoutException"
        assertions = "assert 'rollback' in audit_log and response.status_code == 500"
        mocks.append("Mock: db_session (模拟事务操作抛出异常并触发 rollback)")

    # 4. 熔断与降级
    elif category == UncoveredBranchCategory.CIRCUIT_BREAKER_FALLBACK:
        inputs["simulate_downstream_latency_ms"] = 3000
        assertions = "assert response.status_code == 200 and response.json().get('is_fallback') is True"
        mocks.append("Mock: circuit_breaker (模拟下游超时触发断路器 OPEN 并走只读降级旁路)")

    # 5. 常规业务分支
    else:
        # 尝试从简单的比较表达式提取
        comp_m = re.search(r"(\w+)\s*(==|!=|>|<|>=|<=)\s*([\"'\w\d]+)", cond)
        if comp_m:
            var_name = comp_m.group(1)
            op = comp_m.group(2)
            val_str = comp_m.group(3).strip("\"'")
            if op == "==":
                inputs[var_name] = val_str
            elif op == "!=":
                inputs[var_name] = f"not_{val_str}"
            elif op in (">", ">="):
                try:
                    inputs[var_name] = float(val_str) + 1.0
                except ValueError:
                    inputs[var_name] = val_str
            elif op in ("<", "<="):
                try:
                    inputs[var_name] = float(val_str) - 1.0
                except ValueError:
                    inputs[var_name] = val_str
        else:
            inputs["test_flag"] = True
        assertions = "assert response.status_code == 200"

    return inputs, assertions, mocks


def _generate_test_code_draft(
    branch: UncoveredBranchItem,
    inputs: Dict[str, Any],
    assertions: str,
) -> str:
    """自动生成标准的 pytest 补测用例函数模板代码"""
    fn_name = f"test_cover_{branch.category.value.lower()}_line_{branch.line_start}"

    return f"""def {fn_name}(client):
    # 自动合成用例: 补齐 [{branch.file_path}] 第 {branch.line_start}~{branch.line_end} 行未覆盖高危分支
    # 针对条件: {branch.condition_expr}
    payload = {{{', '.join(f'"{k}": {repr(v)}' for k, v in inputs.items())}}}

    # 执行目标接口/业务调用
    response = client.post("/api/v1/business-call", json=payload)

    # 期望断言校验
    {assertions}
"""


def synthesize_coverage_gap_test_cases(
    uncovered_report: UncoveredBranchAnalysisReport,
) -> CoverageGapSynthesisPlan:
    """针对所有挖掘出的未覆盖分支，反向合成补测用例草稿与预期输入参数"""
    plan_id = f"plan_gap_{uuid.uuid4().hex[:10]}"
    drafts: List[SuggestedTestCaseDraft] = []

    for branch in uncovered_report.branches:
        inputs, assertions, mocks = _deduce_boundary_inputs_from_condition(
            condition_expr=branch.condition_expr,
            category=branch.category,
            code_snippet=branch.code_snippet,
        )

        test_code = _generate_test_code_draft(branch, inputs, assertions)
        title = f"【补测】覆盖 {branch.file_path}:{branch.line_start} {branch.category.value} 高危分支"

        drafts.append(
            SuggestedTestCaseDraft(
                draft_id=f"draft_{uuid.uuid4().hex[:8]}",
                target_branch_id=branch.branch_id,
                file_path=branch.file_path,
                target_lines=f"{branch.line_start}-{branch.line_end}",
                case_title=title,
                test_type="api",
                severity=branch.severity,
                category=branch.category,
                recommended_inputs=inputs,
                expected_assertion=assertions,
                mock_prerequisites=mocks,
                suggested_test_code=test_code,
            )
        )

    p0 = sum(1 for d in drafts if d.severity == BranchRiskSeverity.P0_BLOCKING)
    p1 = sum(1 for d in drafts if d.severity == BranchRiskSeverity.P1_CRITICAL)
    p2 = sum(1 for d in drafts if d.severity == BranchRiskSeverity.P2_MAJOR)

    # 预估补齐增量覆盖率收益（每补齐 1 个分支预估提升 4.5% 覆盖率，最高 100%）
    gain_pct = min(40.0, len(drafts) * 4.5)

    return CoverageGapSynthesisPlan(
        plan_id=plan_id,
        diff_report_id=uncovered_report.diff_report_id,
        total_synthesized_cases=len(drafts),
        p0_cases_count=p0,
        p1_cases_count=p1,
        p2_cases_count=p2,
        estimated_coverage_gain_pct=gain_pct,
        cases=drafts,
    )
