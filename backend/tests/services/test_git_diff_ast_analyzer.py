"""Unit tests for Git Diff AST Analyzer Service (S1.1)."""

from __future__ import annotations

import pytest

from app.services.git_diff_ast_analyzer import (
    SymbolChangeKind,
    SymbolType,
    analyze_git_diff_ast,
    get_diff_ast_report,
    list_diff_ast_reports,
    parse_unified_diff,
    reset_diff_ast_registry,
)


@pytest.fixture(autouse=True)
def clean_registry():
    reset_diff_ast_registry()
    yield
    reset_diff_ast_registry()


SAMPLE_DIFF = """diff --git a/app/api/orders.py b/app/api/orders.py
index 1122334..5566778 100644
--- a/app/api/orders.py
+++ b/app/api/orders.py
@@ -8,4 +8,6 @@ def calculate_discount(price: float) -> float:
+    if price > 1000:
+        return price * 0.8
     return price * 0.95
@@ -19,4 +21,6 @@ class OrderService:
     def checkout(self, user_id: int) -> bool:
+        # Added fraud detection check
+        logger.info("Checking fraud for user %s", user_id)
         return True
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
    def __init__(self):
        pass

    def checkout(self, user_id: int) -> bool:
        # Added fraud detection check
        logger.info("Checking fraud for user %s", user_id)
        return True

@router.post("/api/v1/orders/create")
async def create_order_endpoint(payload: dict):
    return {"status": "created"}
"""


def test_parse_unified_diff():
    file_diffs = parse_unified_diff(SAMPLE_DIFF)
    assert len(file_diffs) == 1
    diff = file_diffs[0]
    assert diff.file_path == "app/api/orders.py"
    assert diff.added_lines_count == 4
    assert 8 in diff.changed_line_numbers
    assert 22 in diff.changed_line_numbers


def test_analyze_git_diff_ast_symbols():
    sources = {"app/api/orders.py": SAMPLE_CODE}
    report = analyze_git_diff_ast(SAMPLE_DIFF, file_sources=sources)

    assert report.diff_summary["total_files_changed"] == 1
    assert report.diff_summary["total_added_lines"] == 4

    affected = report.affected_symbols
    assert len(affected) >= 2

    # calculate_discount 应该被识别为受影响的函数
    fn_sym = next((s for s in affected if s.symbol_name == "calculate_discount"), None)
    assert fn_sym is not None
    assert fn_sym.symbol_type == SymbolType.FUNCTION
    assert fn_sym.change_kind == SymbolChangeKind.MODIFIED
    assert len(fn_sym.changed_lines) > 0

    # OrderService.checkout 应该被识别为受影响的类方法
    method_sym = next((s for s in affected if s.symbol_name == "checkout"), None)
    assert method_sym is not None
    assert method_sym.symbol_type == SymbolType.METHOD
    assert method_sym.parent_class == "OrderService"


def test_analyze_diff_ast_with_route_endpoint():
    diff_with_route = """diff --git a/app/api/orders.py b/app/api/orders.py
--- a/app/api/orders.py
+++ b/app/api/orders.py
@@ -25,3 +25,4 @@
 @router.post("/api/v1/orders/create")
 async def create_order_endpoint(payload: dict):
+    logger.info("Audit log order creation")
     return {"status": "created"}
"""
    sources = {"app/api/orders.py": SAMPLE_CODE}
    report = analyze_git_diff_ast(diff_with_route, file_sources=sources)

    assert len(report.affected_routes) == 1
    route = report.affected_routes[0]
    assert route["route_method"] == "POST"
    assert route["route_path"] == "/api/v1/orders/create"
    assert route["handler_function"] == "create_order_endpoint"


def test_get_and_list_diff_ast_reports():
    sources = {"app/api/orders.py": SAMPLE_CODE}
    report = analyze_git_diff_ast(SAMPLE_DIFF, file_sources=sources)

    fetched = get_diff_ast_report(report.analysis_id)
    assert fetched is not None
    assert fetched.analysis_id == report.analysis_id

    reports = list_diff_ast_reports()
    assert len(reports) == 1
    assert reports[0].analysis_id == report.analysis_id
