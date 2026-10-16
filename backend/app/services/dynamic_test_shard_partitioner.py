"""多容器弹性 Worker 负载均衡动态测试切片分发器 (S2.1).

基于 Longest Processing Time First (LPT) 贪心装箱算法，
依据测试用例的历史执行耗时，将测试集智能均衡切片为 N 个并发任务分片，
将各分片总耗时方差降至最低，消除长尾木桶效应，实现接近理论极限的 CI 并发加速比。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import heapq
import logging
from typing import Any
import uuid

logger = logging.getLogger(__name__)


@dataclass
class TestShard:
    shard_index: int
    case_ids: list[int]
    cases_count: int
    estimated_duration_sec: float
    worker_assigned_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "shard_index": self.shard_index,
            "case_ids": self.case_ids,
            "cases_count": self.cases_count,
            "estimated_duration_sec": round(self.estimated_duration_sec, 2),
            "worker_assigned_id": self.worker_assigned_id,
        }


@dataclass
class DynamicShardingReport:
    sharding_id: str
    target_shards_count: int
    actual_shards_count: int
    total_cases_count: int
    total_estimated_duration_sec: float
    max_shard_duration_sec: float
    min_shard_duration_sec: float
    duration_variance: float
    theoretical_speedup_ratio: float
    shards: list[TestShard]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "sharding_id": self.sharding_id,
            "target_shards_count": self.target_shards_count,
            "actual_shards_count": self.actual_shards_count,
            "total_cases_count": self.total_cases_count,
            "total_estimated_duration_sec": round(self.total_estimated_duration_sec, 2),
            "max_shard_duration_sec": round(self.max_shard_duration_sec, 2),
            "min_shard_duration_sec": round(self.min_shard_duration_sec, 2),
            "duration_variance": round(self.duration_variance, 4),
            "theoretical_speedup_ratio": round(self.theoretical_speedup_ratio, 2),
            "shards": [s.to_dict() for s in self.shards],
            "created_at": self.created_at.isoformat(),
        }


# 内存分片报告仓库
_SHARDING_REPORTS: dict[str, DynamicShardingReport] = {}


def partition_tests_dynamically(
    case_ids: list[int],
    target_shards_count: int = 4,
    case_duration_history: dict[int, float] | None = None,
    default_case_duration_sec: float = 3.5,
) -> DynamicShardingReport:
    """运行贪心 LPT 算法，将测试用例集动态均衡切片为 N 个并发分片。"""
    sharding_id = f"shard_{uuid.uuid4().hex[:12]}"
    history = case_duration_history or {}

    # 参数合法性防御
    shards_count = max(1, target_shards_count)
    unique_case_ids = list(dict.fromkeys(case_ids))  # 保序去重

    if not unique_case_ids:
        report = DynamicShardingReport(
            sharding_id=sharding_id,
            target_shards_count=shards_count,
            actual_shards_count=0,
            total_cases_count=0,
            total_estimated_duration_sec=0.0,
            max_shard_duration_sec=0.0,
            min_shard_duration_sec=0.0,
            duration_variance=0.0,
            theoretical_speedup_ratio=1.0,
            shards=[],
        )
        _SHARDING_REPORTS[sharding_id] = report
        return report

    # 若用例数少于目标分片数，自动压缩分片数
    actual_k = min(len(unique_case_ids), shards_count)

    # 1. 用例按耗时降序排列 (Longest Processing Time first)
    case_durations = [(cid, float(history.get(cid, default_case_duration_sec))) for cid in unique_case_ids]
    case_durations.sort(key=lambda x: -x[1])

    # 2. 最小堆贪心分配: 堆元素 (current_total_duration, shard_index)
    # 分片存储: shard_index -> (accumulated_duration, list_of_case_ids)
    shard_allocations: list[list[int]] = [[] for _ in range(actual_k)]
    shard_totals: list[float] = [0.0 for _ in range(actual_k)]

    min_heap: list[tuple[float, int]] = [(0.0, i) for i in range(actual_k)]
    heapq.heapify(min_heap)

    for cid, duration in case_durations:
        cur_duration, shard_idx = heapq.heappop(min_heap)
        shard_allocations[shard_idx].append(cid)
        new_duration = cur_duration + duration
        shard_totals[shard_idx] = new_duration
        heapq.heappush(min_heap, (new_duration, shard_idx))

    # 3. 统计指标计算
    total_duration = sum(shard_totals)
    max_duration = max(shard_totals)
    min_duration = min(shard_totals)

    # 计算方差
    mean_duration = total_duration / float(actual_k)
    variance = sum((d - mean_duration) ** 2 for d in shard_totals) / float(actual_k)

    # 理论加速比 = 单机总时长 / 最慢分片木桶时长
    speedup = (total_duration / max_duration) if max_duration > 0 else 1.0

    shards_list = [
        TestShard(
            shard_index=i,
            case_ids=shard_allocations[i],
            cases_count=len(shard_allocations[i]),
            estimated_duration_sec=shard_totals[i],
            worker_assigned_id=f"worker-pod-shard-{i}",
        )
        for i in range(actual_k)
    ]

    report = DynamicShardingReport(
        sharding_id=sharding_id,
        target_shards_count=shards_count,
        actual_shards_count=actual_k,
        total_cases_count=len(unique_case_ids),
        total_estimated_duration_sec=total_duration,
        max_shard_duration_sec=max_duration,
        min_shard_duration_sec=min_duration,
        duration_variance=variance,
        theoretical_speedup_ratio=speedup,
        shards=shards_list,
    )

    _SHARDING_REPORTS[sharding_id] = report
    logger.info(
        "Partitioned %d cases into %d shards: max=%.1fs min=%.1fs speedup=%.2fx",
        len(unique_case_ids),
        actual_k,
        max_duration,
        min_duration,
        speedup,
    )
    return report


def get_sharding_report(sharding_id: str) -> DynamicShardingReport | None:
    """获取指定分片报告。"""
    return _SHARDING_REPORTS.get(sharding_id)


def list_sharding_reports() -> list[DynamicShardingReport]:
    """查询历史分片报告列表。"""
    return list(_SHARDING_REPORTS.values())


def reset_sharding_registry() -> None:
    """单元测试清理状态使用。"""
    _SHARDING_REPORTS.clear()
