import pytest

from app.services.performance_sharding import (
    PerformanceShardingError,
    aggregate_performance_summaries,
    split_performance_options,
)


def test_split_vus_preserves_total_and_marks_shards():
    shards = split_performance_options({"vus": 10, "duration": "1m"}, 3)

    assert [item["vus"] for item in shards] == [4, 3, 3]
    assert sum(item["vus"] for item in shards) == 10
    assert [item["__shard_index"] for item in shards] == [0, 1, 2]


def test_split_requires_explicit_load_model():
    with pytest.raises(PerformanceShardingError):
        split_performance_options({"duration": "1m"}, 2)


def test_aggregate_summaries_sums_throughput_and_weights_errors():
    result = aggregate_performance_summaries(
        [
            {"rps": 10, "iterations": 100, "error_rate": 0.1, "p95_ms": 20},
            {"rps": 5, "iterations": 50, "error_rate": 0.2, "p95_ms": 40},
        ]
    )

    assert result["rps"] == 15
    assert result["iterations"] == 150
    assert result["error_rate"] == pytest.approx(1 / 7.5)
    assert result["p95_ms"] == 40
