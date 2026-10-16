"""大规模测试套件智能动态分片与跨节点负载均衡调度器 (T1.2)。"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class TestCaseShardingInput:
    """待分片测试用例输入。"""

    case_id: str
    case_name: str
    historical_duration_ms: float = 1000.0
    priority: str = "P1"  # P0, P1, P2, P3
    tags: list[str] = field(default_factory=list)


@dataclass
class ShardBucket:
    """单个执行节点分片桶。"""

    shard_index: int
    assigned_node_id: str
    case_ids: list[str] = field(default_factory=list)
    case_names: list[str] = field(default_factory=list)
    estimated_duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "shard_index": self.shard_index,
            "assigned_node_id": self.assigned_node_id,
            "case_ids": self.case_ids,
            "case_count": len(self.case_ids),
            "estimated_duration_ms": round(self.estimated_duration_ms, 2),
        }


@dataclass
class ShardingPlanResult:
    """分片调度方案全景结果。"""

    plan_id: str
    total_cases: int
    total_shards: int
    total_estimated_duration_ms: float
    makespan_ms: float  # 最慢分片的预计耗时
    min_shard_duration_ms: float
    avg_shard_duration_ms: float
    balance_score_pct: float  # 均衡度得分 0~100%
    shards: list[ShardBucket]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "total_cases": self.total_cases,
            "total_shards": self.total_shards,
            "total_estimated_duration_ms": round(self.total_estimated_duration_ms, 2),
            "makespan_ms": round(self.makespan_ms, 2),
            "min_shard_duration_ms": round(self.min_shard_duration_ms, 2),
            "avg_shard_duration_ms": round(self.avg_shard_duration_ms, 2),
            "balance_score_pct": round(self.balance_score_pct, 1),
            "shards": [s.to_dict() for s in self.shards],
            "created_at": self.created_at.isoformat(),
        }


# 全局分片方案仓库
_SHARDING_PLANS: dict[str, ShardingPlanResult] = {}


def clear_sharding_plans() -> None:
    """清空分片方案仓库（单测专用）。"""
    _SHARDING_PLANS.clear()


def calculate_dynamic_sharding(
    cases: list[TestCaseShardingInput],
    total_shards: int = 3,
    node_ids: list[str] | None = None,
) -> ShardingPlanResult:
    """使用 LPT (Longest Processing Time first) 降序贪心装箱算法实现多节点耗时极值最小化。"""
    if total_shards <= 0:
        total_shards = 1
    if not cases:
        shards = [
            ShardBucket(
                shard_index=i,
                assigned_node_id=(node_ids[i] if node_ids and i < len(node_ids) else f"worker-node-{i+1}"),
            )
            for i in range(total_shards)
        ]
        now = datetime.now(timezone.utc)
        plan = ShardingPlanResult(
            plan_id=f"shard_empty_{int(now.timestamp())}",
            total_cases=0,
            total_shards=total_shards,
            total_estimated_duration_ms=0.0,
            makespan_ms=0.0,
            min_shard_duration_ms=0.0,
            avg_shard_duration_ms=0.0,
            balance_score_pct=100.0,
            shards=shards,
            created_at=now,
        )
        return plan

    # 1. 初始化各分片桶
    shards = [
        ShardBucket(
            shard_index=i,
            assigned_node_id=(node_ids[i] if node_ids and i < len(node_ids) else f"worker-node-{i+1}"),
        )
        for i in range(total_shards)
    ]

    # 2. 对用例按照预估耗时降序排序 (LPT 核心逻辑)
    # 结合优先级加权：P0 用例额外增加 20% 权重保证充分散列
    def _weight(c: TestCaseShardingInput) -> float:
        multiplier = 1.2 if c.priority == "P0" else 1.0
        return max(10.0, c.historical_duration_ms * multiplier)

    sorted_cases = sorted(cases, key=_weight, reverse=True)

    # 3. 贪心分配：将当前最耗时的用例放入当前累计耗时最小的桶
    for c in sorted_cases:
        min_bucket = min(shards, key=lambda b: b.estimated_duration_ms)
        min_bucket.case_ids.append(c.case_id)
        min_bucket.case_names.append(c.case_name)
        min_bucket.estimated_duration_ms += c.historical_duration_ms

    durations = [b.estimated_duration_ms for b in shards]
    total_dur = sum(durations)
    makespan = max(durations) if durations else 0.0
    min_dur = min(durations) if durations else 0.0
    avg_dur = total_dur / total_shards if total_shards > 0 else 0.0

    # 4. 计算均衡度得分：100 - (标准差 / 均值 * 100)
    variance = sum((d - avg_dur) ** 2 for d in durations) / total_shards if total_shards > 0 else 0.0
    std_dev = math.sqrt(variance)
    cv = (std_dev / avg_dur) if avg_dur > 0 else 0.0
    balance_score = max(0.0, min(100.0, 100.0 * (1.0 - cv)))

    now = datetime.now(timezone.utc)
    plan_id = f"shard_plan_{int(now.timestamp())}_{len(cases)}"
    result = ShardingPlanResult(
        plan_id=plan_id,
        total_cases=len(cases),
        total_shards=total_shards,
        total_estimated_duration_ms=total_dur,
        makespan_ms=makespan,
        min_shard_duration_ms=min_dur,
        avg_shard_duration_ms=avg_dur,
        balance_score_pct=balance_score,
        shards=shards,
        created_at=now,
    )
    _SHARDING_PLANS[plan_id] = result
    return result


def detect_straggler_shards(
    shard_progress: list[dict[str, Any]],
) -> dict[str, Any]:
    """分析当前运行中各分片的执行进度，探测长尾掉队节点并给出再平衡建议。"""
    if not shard_progress:
        return {"has_straggler": False, "stragglers": [], "recommendation": "无分片进度数据"}

    avg_elapsed = sum(s.get("elapsed_ms", 0.0) for s in shard_progress) / len(shard_progress)
    stragglers = []

    for s in shard_progress:
        elapsed = s.get("elapsed_ms", 0.0)
        remaining = s.get("remaining_cases", 0)
        total = s.get("total_cases", 1)
        # 若耗时超过均值 1.5 倍且剩余未执行用例占比超过 40%，判定为长尾掉队分片
        if elapsed > avg_elapsed * 1.5 and remaining > 0 and (remaining / max(1, total)) >= 0.4:
            stragglers.append(
                {
                    "shard_index": s.get("shard_index"),
                    "node_id": s.get("node_id"),
                    "elapsed_ms": elapsed,
                    "remaining_cases": remaining,
                    "reason": f"耗时 ({elapsed}ms) 超过集群均值 ({round(avg_elapsed, 1)}ms)，积压用例剩余 {remaining} 个",
                }
            )

    has_straggler = len(stragglers) > 0
    if has_straggler:
        rec = f"检测到 {len(stragglers)} 个执行掉队节点，建议将积压用例动态迁移至已完成的空闲 Worker 节点执行重平衡。"
    else:
        rec = "各分片执行进度均衡，无明显长尾卡滞节点。"

    return {
        "has_straggler": has_straggler,
        "stragglers": stragglers,
        "recommendation": rec,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def get_sharding_plan(plan_id: str) -> ShardingPlanResult | None:
    """根据 ID 获取分片调度方案。"""
    return _SHARDING_PLANS.get(plan_id)


def list_sharding_plans(limit: int = 50) -> list[dict[str, Any]]:
    """获取历史分片方案列表。"""
    plans = list(reversed(list(_SHARDING_PLANS.values())))
    return [p.to_dict() for p in plans[:limit]]
