"""基于拓扑排序的并发波次分发与前置状态传递器服务 (T2.2)

将用例 DAG 图谱按 Kahn 拓扑排序算法划分为平行并发波次 (Waves)，并提供跨波次上下文变量管道传递:
1. DAG 拓扑分层与独立并发波次规划 (plan_dag_execution_waves);
2. 同波次最大并发调度与关键路径理论耗时计算 (ExecutionWave);
3. 跨波次执行状态与上下文变量安全管道注入传递 (State Pipeline Injection);
4. 调度执行计划结构化输出与并发加速比评估 (DAGWavePlanResult)。
"""

from __future__ import annotations

import collections
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from app.services.case_dag_dependency_builder import CaseDAGGraphResult


@dataclass
class WaveDispatchNode:
    case_id: str
    case_name: str
    injected_variables: Dict[str, Any] = field(default_factory=dict)
    required_variables: List[str] = field(default_factory=list)
    produced_variables: List[str] = field(default_factory=list)
    estimated_duration_seconds: float = 10.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionWave:
    wave_index: int
    nodes: List[WaveDispatchNode]
    concurrency_level: int
    wave_estimated_duration_seconds: float
    is_terminal: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "wave_index": self.wave_index,
            "nodes": [n.to_dict() for n in self.nodes],
            "concurrency_level": self.concurrency_level,
            "wave_estimated_duration_seconds": round(self.wave_estimated_duration_seconds, 1),
            "is_terminal": self.is_terminal,
        }


@dataclass
class DAGWavePlanResult:
    plan_id: str
    dag_id: str
    total_waves_count: int
    total_cases_count: int
    waves: List[ExecutionWave]
    critical_path_duration_seconds: float
    sequential_duration_seconds: float
    concurrency_acceleration_ratio: float  # 加速比率 (例如 2.5x)
    planned_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "dag_id": self.dag_id,
            "total_waves_count": self.total_waves_count,
            "total_cases_count": self.total_cases_count,
            "waves": [w.to_dict() for w in self.waves],
            "critical_path_duration_seconds": round(self.critical_path_duration_seconds, 1),
            "sequential_duration_seconds": round(self.sequential_duration_seconds, 1),
            "concurrency_acceleration_ratio": round(self.concurrency_acceleration_ratio, 2),
            "planned_at": self.planned_at,
        }


def plan_dag_execution_waves(dag: CaseDAGGraphResult) -> DAGWavePlanResult:
    """基于 Kahn 拓扑排序算法，将 DAG 图谱严格划分为多级独立并发波次 (Waves)"""
    plan_id = f"wplan_{uuid.uuid4().hex[:10]}"

    if not dag.is_valid_dag or dag.nodes_count == 0:
        return DAGWavePlanResult(
            plan_id=plan_id,
            dag_id=dag.dag_id,
            total_waves_count=0,
            total_cases_count=0,
            waves=[],
            critical_path_duration_seconds=0.0,
            sequential_duration_seconds=0.0,
            concurrency_acceleration_ratio=1.0,
        )

    # 计算每个节点的当前入度与出边邻接表
    in_degree: Dict[str, int] = {}
    adj: Dict[str, Set[str]] = collections.defaultdict(set)
    for cid, node in dag.nodes.items():
        in_degree[cid] = len(node.upstream_case_ids)
        for down_id in node.downstream_case_ids:
            adj[cid].add(down_id)

    # 拓扑分层波次
    waves: List[ExecutionWave] = []
    current_wave_idx = 0
    remaining_nodes = dict(in_degree)

    sequential_time = sum(float(n.metadata.get("cost_seconds", 10.0)) for n in dag.nodes.values())
    critical_path_time = 0.0

    while remaining_nodes:
        # 提取当前所有入度为 0 的节点
        zero_in_degree = [cid for cid, deg in remaining_nodes.items() if deg == 0]
        if not zero_in_degree:
            # 存在未被 Tarjan 识别的残余环路防御
            break

        wave_nodes: List[WaveDispatchNode] = []
        max_wave_duration = 0.0

        for cid in sorted(zero_in_degree):
            node_data = dag.nodes[cid]
            duration = float(node_data.metadata.get("cost_seconds", 10.0))
            max_wave_duration = max(max_wave_duration, duration)

            wave_nodes.append(
                WaveDispatchNode(
                    case_id=cid,
                    case_name=node_data.case_name,
                    required_variables=node_data.consumed_variables,
                    produced_variables=node_data.produced_variables,
                    estimated_duration_seconds=duration,
                )
            )

        critical_path_time += max_wave_duration

        # 移除已分配节点，并递减其下游节点的入度
        for cid in zero_in_degree:
            del remaining_nodes[cid]
            for neighbor in adj[cid]:
                if neighbor in remaining_nodes:
                    remaining_nodes[neighbor] -= 1

        is_last = len(remaining_nodes) == 0
        waves.append(
            ExecutionWave(
                wave_index=current_wave_idx,
                nodes=wave_nodes,
                concurrency_level=len(wave_nodes),
                wave_estimated_duration_seconds=max_wave_duration,
                is_terminal=is_last,
            )
        )
        current_wave_idx += 1

    total_cases = sum(len(w.nodes) for w in waves)
    acceleration = (sequential_time / critical_path_time) if (critical_path_time > 0 and sequential_time > 0) else 1.0

    return DAGWavePlanResult(
        plan_id=plan_id,
        dag_id=dag.dag_id,
        total_waves_count=len(waves),
        total_cases_count=total_cases,
        waves=waves,
        critical_path_duration_seconds=critical_path_time,
        sequential_duration_seconds=sequential_time,
        concurrency_acceleration_ratio=acceleration,
    )


def simulate_wave_pipeline_execution(
    wave_plan: DAGWavePlanResult,
    initial_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """模拟执行多波次调度，核验跨波次上下文变量的管道注入流转"""
    pipeline_state: Dict[str, Any] = dict(initial_context or {})
    dispatched_waves_summary: List[Dict[str, Any]] = []

    for wave in wave_plan.waves:
        wave_executed_nodes: List[Dict[str, Any]] = []
        newly_produced_in_wave: Dict[str, Any] = {}

        for node in wave.nodes:
            # 1. 为当前用例节点注入已流转的前置变量
            injected = {var: pipeline_state.get(var) for var in node.required_variables if var in pipeline_state}
            node.injected_variables = injected

            # 2. 模拟用例执行成功并产出输出变量 (若未指定具体值，生成确定性模拟值)
            for pvar in node.produced_variables:
                mock_val = f"val_{pvar}_{node.case_id}"
                newly_produced_in_wave[pvar] = mock_val

            wave_executed_nodes.append(
                {
                    "case_id": node.case_id,
                    "injected_variables": injected,
                    "produced_variables": node.produced_variables,
                    "status": "COMPLETED",
                }
            )

        # 3. 将本波次产出的所有变量合并至全局管道状态，供下一波次消费
        pipeline_state.update(newly_produced_in_wave)

        dispatched_waves_summary.append(
            {
                "wave_index": wave.wave_index,
                "concurrency": wave.concurrency_level,
                "nodes": wave_executed_nodes,
                "pipeline_state_after_wave": dict(pipeline_state),
            }
        )

    return {
        "plan_id": wave_plan.plan_id,
        "total_waves_dispatched": len(wave_plan.waves),
        "final_pipeline_variables_count": len(pipeline_state),
        "final_pipeline_variables": pipeline_state,
        "wave_executions": dispatched_waves_summary,
    }
