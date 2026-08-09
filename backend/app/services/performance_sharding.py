"""Load split and summary aggregation for distributed performance runs."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


class PerformanceShardingError(ValueError):
    pass


def split_performance_options(options: dict[str, Any], shard_count: int) -> list[dict[str, Any]]:
    if shard_count < 2:
        raise PerformanceShardingError("多节点分片至少需要 2 个节点")
    load_key = next((key for key in ("vus", "users", "concurrency") if _positive_int(options.get(key))), None)
    if load_key is None:
        raise PerformanceShardingError("多节点分片需要配置 vus、users 或 concurrency")
    total = int(options[load_key])
    base, remainder = divmod(total, shard_count)
    if base < 1:
        raise PerformanceShardingError("总负载必须不少于节点数")
    result = []
    for index in range(shard_count):
        shard = deepcopy(options)
        shard[load_key] = base + (1 if index < remainder else 0)
        shard["__shard_index"] = index
        shard["__shard_count"] = shard_count
        result.append(shard)
    return result


def aggregate_performance_summaries(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    if not summaries:
        return {"sharded": True, "shard_count": 0, "executor": "distributed"}
    result: dict[str, Any] = {
        "executor": "distributed",
        "sharded": True,
        "shard_count": len(summaries),
        "shards": summaries,
    }
    for metric in ("rps", "iterations", "data_received", "data_sent"):
        values: list[float] = []
        for item in summaries:
            value = item.get(metric)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                values.append(float(value))
        if values:
            result[metric] = sum(values)
    for metric in ("p95_ms", "p99_ms"):
        values = []
        for item in summaries:
            value = item.get(metric)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                values.append(float(value))
        if values:
            result[metric] = max(values)
    weighted_errors = []
    for item in summaries:
        rate = item.get("error_rate")
        count = item.get("iterations")
        if isinstance(rate, (int, float)) and isinstance(count, (int, float)):
            weighted_errors.append((rate, count))
    if weighted_errors:
        total = sum(count for _, count in weighted_errors)
        result["error_rate"] = sum(rate * count for rate, count in weighted_errors) / total if total else None
    return result


def _positive_int(value: object) -> bool:
    try:
        return int(str(value)) > 0 if value is not None else False
    except (TypeError, ValueError):
        return False
