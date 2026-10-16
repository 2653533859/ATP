"""Unit tests for Smart Test Selection Engine Service (S1.3)."""

from __future__ import annotations

import pytest

from app.services.code_to_test_mapping_indexer import TestCaseRef, get_mapping_indexer
from app.services.git_diff_ast_analyzer import reset_diff_ast_registry
from app.services.smart_test_selection_engine import (
    SelectionStrategy,
    get_selection_report,
    list_selection_reports,
    reset_test_selection_registry,
    select_tests_from_diff,
)


@pytest.fixture(autouse=True)
def clean_services():
    reset_diff_ast_registry()
    reset_test_selection_registry()
    indexer = get_mapping_indexer()
    indexer.clear()
    yield
    reset_diff_ast_registry()
    reset_test_selection_registry()
    indexer.clear()


SAMPLE_DIFF = """diff --git a/app/api/orders.py b/app/api/orders.py
--- a/app/api/orders.py
+++ b/app/api/orders.py
@@ -8,4 +8,6 @@ def calculate_discount(price: float) -> float:
+    if price > 1000:
+        return price * 0.8
     return price * 0.95
"""

SAMPLE_CODE = """# Orders module
from fastapi import APIRouter
router = APIRouter()

def helper_init():
    pass

def calculate_discount(price: float) -> float:
    if price > 1000:
        return price * 0.8
    return price * 0.95

def unused_func():
    return 1

class OrderService:
    def checkout(self, user_id: int) -> bool:
        return True
"""


def test_smart_test_selection_directly_matches_symbol():
    indexer = get_mapping_indexer()

    # 注册 3 个用例：一个直接关联 calculate_discount，一个关联同文件 OrderService，另一个关联外部文件
    case_target = TestCaseRef(case_id=101, case_name="优惠折扣核算用例", priority="P0")
    case_context = TestCaseRef(case_id=102, case_name="下单结算流程用例", priority="P1")
    case_irrelevant = TestCaseRef(case_id=999, case_name="用户个人中心", priority="P2")

    indexer.register_binding(case_target, bound_symbols=["app/api/orders.py:calculate_discount"])
    indexer.register_binding(case_context, bound_symbols=["app/api/orders.py:OrderService.checkout"])
    indexer.register_binding(case_irrelevant, bound_symbols=["app/api/users.py:get_profile"])

    # 1. 最小影响面模式 (MINIMAL_IMPACT)
    minimal_report = select_tests_from_diff(
        diff_text=SAMPLE_DIFF,
        file_sources={"app/api/orders.py": SAMPLE_CODE},
        strategy=SelectionStrategy.MINIMAL_IMPACT,
        total_repo_cases_override=10,
    )

    # 只应该选中直接修改的 calculate_discount 用例
    assert minimal_report.selected_cases_count == 1
    assert minimal_report.selected_cases[0].case_id == 101
    assert minimal_report.selected_cases[0].confidence_score >= 0.95
    assert minimal_report.total_repository_cases_count == 10
    assert minimal_report.pruned_cases_count == 9
    assert minimal_report.pruning_ratio_pct == 90.0
    assert minimal_report.estimated_time_saved_sec > 0

    # 2. 平衡模式 (BALANCED) 包含同文件用例
    balanced_report = select_tests_from_diff(
        diff_text=SAMPLE_DIFF,
        file_sources={"app/api/orders.py": SAMPLE_CODE},
        strategy=SelectionStrategy.BALANCED,
        total_repo_cases_override=10,
    )

    # 应该包含 case 101 和 case 102，但绝不包含 case 999
    assert balanced_report.selected_cases_count == 2
    selected_ids = {c.case_id for c in balanced_report.selected_cases}
    assert 101 in selected_ids
    assert 102 in selected_ids
    assert 999 not in selected_ids


def test_smart_test_selection_reports_lifecycle():
    indexer = get_mapping_indexer()
    case = TestCaseRef(case_id=1, case_name="折扣校验", priority="P0")
    indexer.register_binding(case, bound_symbols=["app/api/orders.py:calculate_discount"])

    report = select_tests_from_diff(
        diff_text=SAMPLE_DIFF,
        file_sources={"app/api/orders.py": SAMPLE_CODE},
    )

    fetched = get_selection_report(report.selection_id)
    assert fetched is not None
    assert fetched.selection_id == report.selection_id

    reports = list_selection_reports()
    assert len(reports) == 1
    assert reports[0].selection_id == report.selection_id
