"""Git Diff 增量代码行覆盖率染色计算器单测 (T1.2)"""

from __future__ import annotations

from app.services.coverage_report_ingestor import (
    CoverageLineStatus,
    FileCoverageSummary,
    LineCoverageRecord,
    UnifiedCoverageReport,
)
from app.services.diff_coverage_staining_engine import (
    calculate_diff_coverage_staining,
)


def test_calculate_diff_coverage_full_coverage():
    diff_text = """diff --git a/app/services/order.py b/app/services/order.py
index 1234567..89abcdef 100644
--- a/app/services/order.py
+++ b/app/services/order.py
@@ -10,2 +10,2 @@
+    total = price * qty
+    return total
"""
    # 模拟覆盖率：第 10、11 行均被覆盖
    cov_report = UnifiedCoverageReport(
        report_id="cov_1",
        project_id="p1",
        commit_id="c1",
        total_files=1,
        overall_line_coverage_pct=100.0,
        overall_branch_coverage_pct=100.0,
        files={
            "app/services/order.py": FileCoverageSummary(
                file_path="app/services/order.py",
                total_lines=2,
                covered_lines=2,
                uncovered_lines=0,
                line_coverage_pct=100.0,
                line_records={
                    10: LineCoverageRecord(10, hits=3, status=CoverageLineStatus.COVERED),
                    11: LineCoverageRecord(11, hits=3, status=CoverageLineStatus.COVERED),
                },
            )
        },
        sources_ingested=["Unit Tests"],
    )

    report = calculate_diff_coverage_staining(diff_text, cov_report)
    assert report.total_changed_files == 1
    assert "app/services/order.py" in report.files
    f = report.files["app/services/order.py"]
    assert f.changed_executable_lines_count == 2
    assert f.changed_covered_lines_count == 2
    assert f.changed_uncovered_lines_count == 0
    assert f.diff_line_coverage_pct == 100.0
    assert f.green_covered_lines == [10, 11]
    assert f.red_uncovered_lines == []


def test_calculate_diff_coverage_with_red_uncovered_and_yellow_partial():
    diff_text = """diff --git a/app/services/payment.py b/app/services/payment.py
--- a/app/services/payment.py
+++ b/app/services/payment.py
@@ -20,4 +20,4 @@
+    if amount > 1000:
+        discount = 0.9
+    else:
+        raise ValueError("Invalid")
"""
    # 模拟覆盖率：第 20 行 partial (只走了 True)，21 行 covered，23 行 uncovered
    cov_report = UnifiedCoverageReport(
        report_id="cov_2",
        project_id="p1",
        commit_id="c1",
        total_files=1,
        overall_line_coverage_pct=66.7,
        overall_branch_coverage_pct=50.0,
        files={
            "app/services/payment.py": FileCoverageSummary(
                file_path="app/services/payment.py",
                total_lines=3,
                covered_lines=2,
                uncovered_lines=1,
                line_coverage_pct=66.7,
                line_records={
                    20: LineCoverageRecord(
                        20, hits=1, status=CoverageLineStatus.PARTIAL, branches_covered=1, branches_total=2
                    ),
                    21: LineCoverageRecord(21, hits=1, status=CoverageLineStatus.COVERED),
                    23: LineCoverageRecord(23, hits=0, status=CoverageLineStatus.UNCOVERED),
                },
            )
        },
        sources_ingested=["Unit Tests"],
    )

    report = calculate_diff_coverage_staining(diff_text, cov_report)
    f = report.files["app/services/payment.py"]
    assert f.changed_executable_lines_count == 3
    assert f.changed_covered_lines_count == 2  # 行 20 (partial) 和 21 (covered) 均有 hit
    assert f.changed_uncovered_lines_count == 1  # 行 23 红色未覆盖
    assert f.changed_partial_lines_count == 1  # 行 20 黄色部分分支覆盖
    assert round(f.diff_line_coverage_pct, 1) == 66.7
    assert f.red_uncovered_lines == [23]
    assert f.yellow_partial_lines == [20]
    assert f.green_covered_lines == [21]

    d = report.to_dict()
    assert d["total_uncovered_lines"] == 1
    assert "app/services/payment.py" in d["files"]


def test_calculate_diff_coverage_with_source_code_alignment():
    diff_text = """--- a/calc.py
+++ b/calc.py
@@ -2,1 +2,1 @@
+    return a + b
"""
    source_files = {"calc.py": "def add(a, b):\n    return a + b\n"}

    cov_report = UnifiedCoverageReport(
        report_id="cov_3",
        project_id="p1",
        commit_id="c1",
        total_files=1,
        overall_line_coverage_pct=100.0,
        overall_branch_coverage_pct=100.0,
        files={
            "calc.py": FileCoverageSummary(
                file_path="calc.py",
                total_lines=2,
                covered_lines=2,
                uncovered_lines=0,
                line_coverage_pct=100.0,
                line_records={
                    1: LineCoverageRecord(1, hits=1, status=CoverageLineStatus.COVERED),
                    2: LineCoverageRecord(2, hits=1, status=CoverageLineStatus.COVERED),
                },
            )
        },
        sources_ingested=["Unit"],
    )

    report = calculate_diff_coverage_staining(diff_text, cov_report, source_files=source_files)
    f = report.files["calc.py"]
    assert len(f.stained_lines) == 2
    # 第 1 行未在 diff 中修改
    assert f.stained_lines[0].line_number == 1
    assert f.stained_lines[0].is_changed_in_diff is False
    assert f.stained_lines[0].content == "def add(a, b):"
    # 第 2 行为 diff 修改行
    assert f.stained_lines[1].line_number == 2
    assert f.stained_lines[1].is_changed_in_diff is True
    assert f.stained_lines[1].content == "    return a + b"
