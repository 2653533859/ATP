"""Unit tests for Code-to-Test Mapping Indexer Service (S1.2)."""

from __future__ import annotations

import pytest

from app.services.code_to_test_mapping_indexer import (
    TestCaseRef,
    get_mapping_indexer,
)


@pytest.fixture(autouse=True)
def clean_indexer():
    indexer = get_mapping_indexer()
    indexer.clear()
    yield
    indexer.clear()


def test_register_binding_and_query_by_symbol():
    indexer = get_mapping_indexer()
    case1 = TestCaseRef(
        case_id=101,
        case_name="结算优惠抵扣用例",
        case_type="api",
        priority="P1",
        project_id=1,
    )
    indexer.register_binding(
        case=case1,
        bound_symbols=["app/api/orders.py:calculate_discount"],
        bound_routes=[("POST", "/api/v1/orders/create")],
    )

    stats = indexer.get_stats()
    assert stats["total_indexed_cases"] == 1
    assert stats["total_indexed_symbols"] == 1
    assert stats["total_indexed_routes"] == 1
    assert stats["total_indexed_files"] == 1

    # 按代码符号反查
    affected = indexer.query_affected_cases(symbols=["app/api/orders.py:calculate_discount"])
    assert len(affected) == 1
    assert affected[0].case_id == 101


def test_query_by_route_and_normalization():
    indexer = get_mapping_indexer()
    case = TestCaseRef(
        case_id=202,
        case_name="下单创建主链路",
        case_type="api",
        priority="P0",
    )
    indexer.register_binding(
        case=case,
        bound_routes=[("post", "api/v1/orders/create/")],
    )

    # 用不同大小写与斜线查询，验证归一化
    res1 = indexer.query_affected_cases(routes=["POST /api/v1/orders/create"])
    assert len(res1) == 1
    assert res1[0].case_id == 202

    res2 = indexer.query_affected_cases(routes=[("POST", "/api/v1/orders/create/")])
    assert len(res2) == 1


def test_auto_index_from_steps():
    indexer = get_mapping_indexer()
    steps = [
        {"method": "GET", "url": "https://gateway.internal/api/v1/users/profile?active=true"},
        {"method": "POST", "url": "/api/v1/cart/items"},
    ]

    case = indexer.auto_index_from_steps(
        case_id=303,
        case_name="查看资料并加购测试",
        case_type="api",
        steps=steps,
        priority="P1",
        project_id=2,
    )

    assert len(case.target_endpoints) == 2
    assert "GET /api/v1/users/profile" in case.target_endpoints
    assert "POST /api/v1/cart/items" in case.target_endpoints

    # 查寻受影响用例
    matched = indexer.query_affected_cases(routes=["GET /api/v1/users/profile"])
    assert len(matched) == 1
    assert matched[0].case_id == 303


def test_deduplication_and_priority_sorting():
    indexer = get_mapping_indexer()

    case_p1 = TestCaseRef(case_id=1, case_name="次要验证", priority="P1", project_id=1)
    case_p0 = TestCaseRef(case_id=2, case_name="核心支付", priority="P0", project_id=1)

    # 两个用例都引用了同一文件和函数
    indexer.register_binding(case_p1, bound_symbols=["app/services/pay.py:pay"])
    indexer.register_binding(case_p0, bound_symbols=["app/services/pay.py:pay"])

    # 同时通过函数和文件查询，验证去重和排序 (P0 应排在 P1 前)
    res = indexer.query_affected_cases(
        symbols=["app/services/pay.py:pay"],
        file_paths=["app/services/pay.py"],
        project_id=1,
    )

    assert len(res) == 2
    assert res[0].case_id == 2
    assert res[0].priority == "P0"
    assert res[1].case_id == 1
    assert res[1].priority == "P1"

    # 项目过滤隔离验证
    res_other_project = indexer.query_affected_cases(
        symbols=["app/services/pay.py:pay"],
        project_id=999,
    )
    assert len(res_other_project) == 0
