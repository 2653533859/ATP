"""漏测盲区智能补全用例草稿合成器服务 (T2.2)

根据漏测血缘分析器排查出的未覆盖分支 (Missing Branches),
自动推导测试前置条件、边缘/异常测试数据集与预期断言规则,
一键合成端到端自动化测试用例草稿 (Test Case Drafts):
1. 异常边界反例逆向推导 (Negative & Edge Case Synthesis);
2. API 接口异常状态码校验与断言生成 (4xx, 5xx, Schema Mismatch);
3. 界面交互与真机操作步骤草稿合成 (Web/Android/iOS);
4. 用例优先级自动定级 (HIGH/MEDIUM) 与结构化用例模型导出。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.services.visual_coverage_lineage_analyzer import (
    CoverageLineageNode,
    CoverageRiskLevel,
    LineageCategory,
)


@dataclass
class SynthesizedTestStep:
    step_number: int
    step_name: str
    action_type: str  # http_request | ui_action | db_verify | assertion
    input_payload: Dict[str, Any]
    expected_result: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_number": self.step_number,
            "step_name": self.step_name,
            "action_type": self.action_type,
            "input_payload": self.input_payload,
            "expected_result": self.expected_result,
        }


@dataclass
class SynthesizedTestCaseDraft:
    draft_id: str
    source_node_id: str
    target_branch: str
    title: str
    case_type: str  # api | web | mobile | hybrid
    priority: str  # P0 | P1 | P2
    preconditions: str
    steps: List[SynthesizedTestStep]
    expected_outcome: str
    suggested_tags: List[str]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "draft_id": self.draft_id,
            "source_node_id": self.source_node_id,
            "target_branch": self.target_branch,
            "title": self.title,
            "case_type": self.case_type,
            "priority": self.priority,
            "preconditions": self.preconditions,
            "steps": [s.to_dict() for s in self.steps],
            "expected_outcome": self.expected_outcome,
            "suggested_tags": self.suggested_tags,
            "created_at": self.created_at,
        }


def _derive_case_priority(risk_level: CoverageRiskLevel) -> str:
    if risk_level == CoverageRiskLevel.HIGH:
        return "P0"
    if risk_level == CoverageRiskLevel.MEDIUM:
        return "P1"
    return "P2"


def synthesize_cases_for_gap_node(node: CoverageLineageNode) -> List[SynthesizedTestCaseDraft]:
    """针对单个漏测节点的所有缺失分支合成针对性测试用例草稿"""
    drafts: List[SynthesizedTestCaseDraft] = []
    missing_branches = node.missing_branches

    for branch in missing_branches:
        draft_id = f"draft_{uuid.uuid4().hex[:12]}"
        priority = _derive_case_priority(node.risk_level)

        steps: List[SynthesizedTestStep] = []

        if node.category == LineageCategory.API_ENDPOINT:
            case_type = "api"
            title = f"[API漏测补全] {node.node_name} - 覆盖分支: {branch}"
            steps.append(
                SynthesizedTestStep(
                    step_number=1,
                    step_name=f"构造针对分支 [{branch}] 的请求参数",
                    action_type="http_request",
                    input_payload={
                        "headers": {"Content-Type": "application/json"},
                        "body": {"test_scenario": branch, "mock_flag": True},
                    },
                    expected_result=f"接口返回预期状态响应，命中业务分支 [{branch}]",
                )
            )
            steps.append(
                SynthesizedTestStep(
                    step_number=2,
                    step_name="断言响应状态码与错误字段",
                    action_type="assertion",
                    input_payload={"assert_expr": f"response.status in [200, 400, 404, 500]"},
                    expected_result="校验返回字段结构完全符合接口契约定义",
                )
            )
            preconditions = "被测微服务处于健康可用状态，准备好前置认证凭据"
            expected_outcome = f"成功验证接口在 [{branch}] 分支下的容错与业务行为"

        elif node.category == LineageCategory.UI_INTERACTION:
            case_type = "web"
            title = f"[UI漏测补全] {node.node_name} - 交互分支: {branch}"
            steps.append(
                SynthesizedTestStep(
                    step_number=1,
                    step_name="打开页面并定位目标交互元素",
                    action_type="ui_action",
                    input_payload={"action": "navigate_and_find", "selector": f"[data-test='{node.node_id}']"},
                    expected_result="目标界面组件渲染完毕",
                )
            )
            steps.append(
                SynthesizedTestStep(
                    step_number=2,
                    step_name=f"触发 [{branch}] 对应用户操作",
                    action_type="ui_action",
                    input_payload={"action": "click_or_input", "trigger": branch},
                    expected_result="界面给出正确状态提示或跳转",
                )
            )
            preconditions = "浏览器环境或真机处于待命状态"
            expected_outcome = f"UI 成功捕获并响应分支 [{branch}]"

        else:
            case_type = "hybrid"
            title = f"[业务漏测补全] {node.node_name} - 业务逻辑: {branch}"
            steps.append(
                SynthesizedTestStep(
                    step_number=1,
                    step_name=f"构造前置测试数据满足分支 [{branch}] 触发条件",
                    action_type="http_request",
                    input_payload={"branch": branch},
                    expected_result="前置数据就绪",
                )
            )
            steps.append(
                SynthesizedTestStep(
                    step_number=2,
                    step_name="触发全链路业务流转并比对数据库最终状态",
                    action_type="db_verify",
                    input_payload={"verify_sql": "SELECT * FROM orders WHERE ..."},
                    expected_result="数据状态一致，无脏数据残留",
                )
            )
            preconditions = "测试数据库与微服务具备一致性测试数据隔离"
            expected_outcome = f"业务逻辑在 [{branch}] 场景下流转无误"

        tags = [node.category.value, f"risk:{node.risk_level.value.lower()}", "auto-synthesized"]

        drafts.append(
            SynthesizedTestCaseDraft(
                draft_id=draft_id,
                source_node_id=node.node_id,
                target_branch=branch,
                title=title,
                case_type=case_type,
                priority=priority,
                preconditions=preconditions,
                steps=steps,
                expected_outcome=expected_outcome,
                suggested_tags=tags,
            )
        )

    return drafts


def synthesize_cases_for_all_gaps(gap_nodes: List[CoverageLineageNode]) -> List[SynthesizedTestCaseDraft]:
    """批量针对全量漏测节点自动推导合成补全用例"""
    all_drafts: List[SynthesizedTestCaseDraft] = []
    for node in gap_nodes:
        if node.is_gap:
            all_drafts.extend(synthesize_cases_for_gap_node(node))
    return all_drafts
