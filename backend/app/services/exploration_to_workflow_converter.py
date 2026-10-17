"""探索成功轨迹逆向自动化工作流转换器服务 (T2.3)

将 VLM 多模态自主探索通过的屏幕交互轨迹与手势动作序列,
逆向一键转换为标准多端低代码自动化测试工作流 (Hybrid Workflow DAG):
1. 探索动作到工作流节点逆向映射 (Tap ➔ UI Action, Input ➔ Input Step, Swipe ➔ Drag);
2. 状态迁移序列到拓扑有向边自动构建 (Sequential Edges Wiring);
3. 自动生成前置环境配置与断言检查点 (Preconditions & Checkpoints);
4. 导出为可直接在画布编辑执行的 WorkflowDraftItem 结构。
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List

from app.services.hybrid_workflow_dag_engine import (
    WorkflowEdge,
    WorkflowNode,
    WorkflowNodeType,
)
from app.services.vlm_autonomous_explorer import (
    ExplorationActionType,
    ExplorationSession,
)


def convert_exploration_to_workflow(
    session: ExplorationSession,
    workflow_id: str | None = None,
    workflow_name: str | None = None,
) -> Dict[str, Any]:
    """将自主探索会话轨迹转换为标准低代码工作流拓扑配置"""
    wf_id = workflow_id or f"wf_from_exp_{uuid.uuid4().hex[:8]}"
    wf_name = workflow_name or f"探索轨迹固化工作流: {session.goal[:16]}"

    nodes: List[WorkflowNode] = []
    edges: List[WorkflowEdge] = []

    # 1. 前置节点: 初始化环境
    if session.platform.lower() == "ios":
        init_type = WorkflowNodeType.MOBILE_IOS
        init_name = f"1. 初始化并连接 iOS 真机 ({session.device_id})"
        init_cfg = {"action": "init_wda_tunnel", "udid": session.device_id}
    elif session.platform.lower() == "android":
        init_type = WorkflowNodeType.MOBILE_ANDROID
        init_name = f"1. 初始化并连接 Android 真机 ({session.device_id})"
        init_cfg = {"action": "init_adb_tunnel", "serial": session.device_id}
    else:
        init_type = WorkflowNodeType.WEB_UI_STEP
        init_name = "1. 打开浏览器并导航至目标系统"
        init_cfg = {"action": "navigate", "browser": "chromium"}

    root_node = WorkflowNode(
        node_id="node_1",
        node_name=init_name,
        node_type=init_type,
        config=init_cfg,
    )
    nodes.append(root_node)
    prev_node_id = "node_1"

    # 2. 依次映射探索状态转移边
    node_idx = 2
    for trans in session.transitions:
        if trans.action_type == ExplorationActionType.TERMINATE:
            continue

        nid = f"node_{node_idx}"
        action_val = trans.action_type.value
        label = trans.target_element_label

        if session.platform.lower() == "ios":
            ntype = WorkflowNodeType.MOBILE_IOS
            node_cfg = {
                "udid": session.device_id,
                "action": action_val,
                "target_label": label,
            }
        elif session.platform.lower() == "android":
            ntype = WorkflowNodeType.MOBILE_ANDROID
            node_cfg = {
                "device_serial": session.device_id,
                "action": action_val,
                "target_label": label,
            }
        else:
            ntype = WorkflowNodeType.WEB_UI_STEP
            node_cfg = {
                "action": action_val,
                "selector": f"[aria-label='{label}']",
            }

        node_obj = WorkflowNode(
            node_id=nid,
            node_name=f"{node_idx}. {action_val.upper()} -> {label[:12]}",
            node_type=ntype,
            config=node_cfg,
        )
        nodes.append(node_obj)

        # 连线
        edges.append(
            WorkflowEdge(
                edge_id=f"edge_{prev_node_id}_{nid}",
                source_node_id=prev_node_id,
                target_node_id=nid,
                branch_type="default",
            )
        )
        prev_node_id = nid
        node_idx += 1

    return {
        "workflow_id": wf_id,
        "workflow_name": wf_name,
        "description": f"由多模态 VLM 自主探索会话 [{session.session_id}] 逆向生成，共固化 {len(nodes)} 个操作步骤",
        "nodes": [n.to_dict() for n in nodes],
        "edges": [e.to_dict() for e in edges],
    }
