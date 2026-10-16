"""Unit tests for Dynamic Test Shard Partitioner Service (S2.1)."""

from __future__ import annotations

import pytest

from app.services.dynamic_test_shard_partitioner import (
    get_sharding_report,
    list_sharding_reports,
    partition_tests_dynamically,
    reset_sharding_registry,
)


@pytest.fixture(autouse=True)
def clean_sharding():
    reset_sharding_registry()
    yield
    reset_sharding_registry()


def test_partition_empty_cases():
    report = partition_tests_dynamically(case_ids=[], target_shards_count=4)
    assert report.total_cases_count == 0
    assert report.actual_shards_count == 0
    assert report.total_estimated_duration_sec == 0.0
    assert len(report.shards) == 0


def test_partition_fewer_cases_than_shards():
    # 2 个用例请求 5 个分片 -> 自动收敛为 2 个分片
    report = partition_tests_dynamically(case_ids=[101, 102], target_shards_count=5)
    assert report.total_cases_count == 2
    assert report.actual_shards_count == 2
    assert len(report.shards) == 2


def test_partition_lpt_greedy_load_balancing():
    case_ids = [1, 2, 3, 4, 5]
    durations = {
        1: 10.0,
        2: 8.0,
        3: 6.0,
        4: 4.0,
        5: 2.0,
    }
    # 目标 2 个分片，总耗时 30.0s
    # LPT 算法分配：
    # 1 (10s) -> S0 (10s)
    # 2 (8s)  -> S1 (8s)
    # 3 (6s)  -> S1 (8+6=14s)
    # 4 (4s)  -> S0 (10+4=14s)
    # 5 (2s)  -> S0 或 S1 (14+2=16s)
    # 两个分片最终为 14s 和 16s，极差仅 2s，方差极小！
    report = partition_tests_dynamically(
        case_ids=case_ids,
        target_shards_count=2,
        case_duration_history=durations,
    )

    assert report.total_cases_count == 5
    assert report.actual_shards_count == 2
    assert report.total_estimated_duration_sec == 30.0
    assert report.max_shard_duration_sec == 16.0
    assert report.min_shard_duration_sec == 14.0

    # 理论加速比 = 30 / 16 = 1.875
    assert round(report.theoretical_speedup_ratio, 2) == 1.88

    # 两个分片用例总数等于 5
    all_assigned = []
    for s in report.shards:
        all_assigned.extend(s.case_ids)
    assert set(all_assigned) == {1, 2, 3, 4, 5}


def test_get_and_list_sharding_reports():
    report = partition_tests_dynamically(case_ids=[1, 2, 3], target_shards_count=2)
    fetched = get_sharding_report(report.sharding_id)
    assert fetched is not None
    assert fetched.sharding_id == report.sharding_id

    reports = list_sharding_reports()
    assert len(reports) == 1
    assert reports[0].sharding_id == report.sharding_id
