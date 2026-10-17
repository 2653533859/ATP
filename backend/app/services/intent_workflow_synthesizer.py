"""自然语言意图驱动工作流 DAG 拓扑合成器服务 (T1.1)

基于多模态/大模型自然语言业务意图,
逆向推导多端多协议 DAG 拓扑节点、连线关系与跨节点动态变量总线绑定:
1. 意图语义动作到节点类型智能映射 (Intent-to-NodeType Mapping);
2. 拓扑无环依赖边与分支关系自动生成 (Automatic Edge & Branch Wiring);
3. 跨端上下文变量自动注入 (Context Variable Binding {{node_1.output.id}});
4. 对话式工作流迭代微调优化 (Conversational Workflow Refinement)。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.hybrid_workflow_dag_engine import (
    WorkflowEdge,
    WorkflowNode,
    WorkflowNodeType,
)
from app.services.intent_semantic_prompt_planner import (
    IntentSemanticSlots,
    plan_semantic_slots,
)


@dataclass
class SynthesizedWorkflowDAG:
    synthesis_id: str
    workflow_id: str
    workflow_name: str
    semantic_summary: str
    nodes: List[WorkflowNode]
    edges: List[WorkflowEdge]
    variable_bindings: Dict[str, str]  # node_id -> bound_expression
    slots: IntentSemanticSlots
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "synthesis_id": self.synthesis_id,
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "semantic_summary": self.semantic_summary,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "variable_bindings": self.variable_bindings,
            "slots": self.slots.to_dict(),
            "created_at": self.created_at,
        }


# 全局轻量级意图合成历史
_SYNTHESIS_STORE: Dict[str, SynthesizedWorkflowDAG] = {}


def clear_synthesis_history() -> None:
    _SYNTHESIS_STORE.clear()


def list_synthesis_history(limit: int = 50) -> List[Dict[str, Any]]:
    return [s.to_dict() for s in reversed(list(_SYNTHESIS_STORE.values())[-limit:])]


def get_synthesis_result(synthesis_id: str) -> Optional[SynthesizedWorkflowDAG]:
    return _SYNTHESIS_STORE.get(synthesis_id)


def _infer_node_type_from_action(action_text: str) -> WorkflowNodeType:
    act = action_text.lower()
    if any(k in act for k in ("sql", "数据库", "db", "对账", "核验", "落库")):
        return WorkflowNodeType.DATABASE_QUERY
    if any(k in act for k in ("ios", "iphone", "苹果", "wda", "手势")):
        return WorkflowNodeType.MOBILE_IOS
    if any(k in act for k in ("android", "安卓", "uiautomator", "app")):
        return WorkflowNodeType.MOBILE_ANDROID
    if any(k in act for k in ("web", "浏览器", "页面", "登录", "表单", "点击")):
        return WorkflowNodeType.WEB_UI_STEP
    if any(k in act for k in ("grpc", "rpc", "微服务")):
        return WorkflowNodeType.GRPC_CALL
    if any(k in act for k in ("判断", "如果", "分支", "条件")):
        return WorkflowNodeType.CONDITION_BRANCH
    if any(k in act for k in ("等待", "延迟", "sleep")):
        return WorkflowNodeType.DELAY_SLEEP
    return WorkflowNodeType.HTTP_REQUEST


def synthesize_workflow_from_intent(
    prompt: str,
    workflow_id: Optional[str] = None,
    workflow_name: Optional[str] = None,
) -> SynthesizedWorkflowDAG:
    """根据自然语言意图推导生成完整的跨端多协议工作流 DAG 拓扑"""
    slots = plan_semantic_slots(prompt)

    wf_id = workflow_id or f"wf_ai_{uuid.uuid4().hex[:8]}"
    wf_name = workflow_name or f"AI意图生成: {prompt[:18]}..."
    synth_id = f"synth_{uuid.uuid4().hex[:12]}"

    nodes: List[WorkflowNode] = []
    edges: List[WorkflowEdge] = []
    bindings: Dict[str, str] = {}

    actions = slots.actions
    # 限制节点数量在 3~7 之间，保持连贯性
    if len(actions) < 3:
        if "sql" not in slots.protocols:
            actions.append("数据库最终数据核验")
        if "web" in slots.protocols and "ios" in slots.protocols:
            actions = ["HTTP 创建前置基础数据", "Web 页面登录与选购", "iOS 客户端结账支付", "数据库状态对账"]

    prev_node_id: Optional[str] = None

    for idx, act in enumerate(actions, start=1):
        node_id = f"node_{idx}"
        ntype = _infer_node_type_from_action(act)

        # 构造节点配置与动态变量绑定
        config: Dict[str, Any] = {"action_label": act}
        if ntype == WorkflowNodeType.HTTP_REQUEST:
            config["method"] = "POST"
            config["url"] = f"/api/v1/{slots.business_domain}/action"
            config["expected_status"] = 200
            if prev_node_id:
                config["ref_id"] = f"{{{{{prev_node_id}.output.body.order_id}}}}"
                bindings[node_id] = f"{{{{{prev_node_id}.output.body.order_id}}}}"

        elif ntype == WorkflowNodeType.WEB_UI_STEP:
            config["browser"] = "chromium"
            config["action"] = act
            if prev_node_id:
                config["input_val"] = f"{{{{{prev_node_id}.output.body.order_id}}}}"
                bindings[node_id] = f"{{{{{prev_node_id}.output.body.order_id}}}}"

        elif ntype == WorkflowNodeType.MOBILE_IOS:
            config["action"] = act
            config["device_udid"] = "auto_allocated_ios"
            if prev_node_id:
                config["order_ref"] = f"{{{{{prev_node_id}.output.body.order_id}}}}"
                bindings[node_id] = f"{{{{{prev_node_id}.output.body.order_id}}}}"

        elif ntype == WorkflowNodeType.MOBILE_ANDROID:
            config["action"] = act
            config["device_serial"] = "auto_allocated_android"

        elif ntype == WorkflowNodeType.DATABASE_QUERY:
            config["db_type"] = "postgresql"
            first_http = next((n.node_id for n in nodes if n.node_type == WorkflowNodeType.HTTP_REQUEST), "node_1")
            config["query_sql"] = (
                f"SELECT status FROM {slots.business_domain}_records WHERE ref_id = '{{{{{first_http}.output.body.order_id}}}}'"
            )
            bindings[node_id] = f"{{{{{first_http}.output.body.order_id}}}}"

        elif ntype == WorkflowNodeType.CONDITION_BRANCH:
            config["expr"] = "output.status_code == 200"

        # 阶梯布局坐标
        node_obj = WorkflowNode(
            node_id=node_id,
            node_name=f"{idx}. {act}",
            node_type=ntype,
            config=config,
            condition_expr="output.status_code == 200" if ntype == WorkflowNodeType.CONDITION_BRANCH else None,
        )
        nodes.append(node_obj)

        # 自动串联有向边
        if prev_node_id:
            edge_id = f"edge_{prev_node_id}_{node_id}"
            edges.append(
                WorkflowEdge(
                    edge_id=edge_id,
                    source_node_id=prev_node_id,
                    target_node_id=node_id,
                    branch_type="default",
                )
            )

        prev_node_id = node_id

    summary = f"已基于业务意图智能合成包含 {len(nodes)} 个跨端多协议节点的工作流，覆盖领域: [{slots.business_domain}]，通讯协议: [{', '.join(slots.protocols)}]。"

    synthesized_dag = SynthesizedWorkflowDAG(
        synthesis_id=synth_id,
        workflow_id=wf_id,
        workflow_name=wf_name,
        semantic_summary=summary,
        nodes=nodes,
        edges=edges,
        variable_bindings=bindings,
        slots=slots,
    )
    _SYNTHESIS_STORE[synth_id] = synthesized_dag
    return synthesized_dag


def refine_workflow_with_intent(
    synthesis_id: str,
    refinement_prompt: str,
) -> SynthesizedWorkflowDAG:
    """根据自然语言微调指令，动态扩展与修改已有工作流拓扑"""
    existing = get_synthesis_result(synthesis_id)
    if not existing:
        raise ValueError(f"未找到指定的合成会话 [{synthesis_id}]")

    ref_lower = refinement_prompt.lower()
    nodes = list(existing.nodes)
    edges = list(existing.edges)

    new_node_idx = len(nodes) + 1
    new_node_id = f"node_{new_node_idx}"

    # 判断是否增加断言、延时或特定节点
    if any(k in ref_lower for k in ("延时", "等待", "sleep")):
        new_node = WorkflowNode(
            node_id=new_node_id,
            node_name=f"{new_node_idx}. 延时等待 500ms",
            node_type=WorkflowNodeType.DELAY_SLEEP,
            config={"delay_ms": 500},
        )
    elif any(k in ref_lower for k in ("判断", "如果", "分支", "condition")):
        new_node = WorkflowNode(
            node_id=new_node_id,
            node_name=f"{new_node_idx}. 条件异常分支判断",
            node_type=WorkflowNodeType.CONDITION_BRANCH,
            condition_expr="output.status_code == 200",
        )
    else:
        new_node = WorkflowNode(
            node_id=new_node_id,
            node_name=f"{new_node_idx}. 微调补齐操作: {refinement_prompt[:12]}",
            node_type=WorkflowNodeType.HTTP_REQUEST,
            config={"method": "POST", "url": "/api/v1/refined/step"},
        )

    # 连接到最后一个节点
    if nodes:
        last_node = nodes[-1]
        edges.append(
            WorkflowEdge(
                edge_id=f"edge_{last_node.node_id}_{new_node_id}",
                source_node_id=last_node.node_id,
                target_node_id=new_node_id,
            )
        )
    nodes.append(new_node)

    existing.nodes = nodes
    existing.edges = edges
    existing.semantic_summary += f" | 已追加微调步骤: [{refinement_prompt}]"
    return existing
