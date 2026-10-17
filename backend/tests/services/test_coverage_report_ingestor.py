"""多源覆盖率报告解析与合并器单测 (T1.1)"""

from __future__ import annotations

import json

from app.services.coverage_report_ingestor import (
    CoverageLineStatus,
    merge_coverage_reports,
    parse_coverage_py_json,
    parse_jacoco_xml,
    parse_lcov_content,
)


def test_parse_coverage_py_json():
    sample_json = {
        "files": {
            "app/services/payment.py": {
                "executed_lines": [10, 11, 12, 15],
                "missing_lines": [20],
                "summary": {
                    "covered_lines": 4,
                    "num_statements": 5,
                    "percent_covered": 80.0,
                    "missing_lines": 1,
                    "covered_branches": 2,
                    "num_branches": 2,
                },
            }
        }
    }

    report = parse_coverage_py_json(json.dumps(sample_json), project_id="p1", commit_id="c1")
    assert report.total_files == 1
    assert "app/services/payment.py" in report.files
    f = report.files["app/services/payment.py"]
    assert f.covered_lines == 4
    assert f.uncovered_lines == 1
    assert f.line_coverage_pct == 80.0
    assert f.line_records[10].status == CoverageLineStatus.COVERED
    assert f.line_records[20].status == CoverageLineStatus.UNCOVERED
    assert report.sources_ingested == ["Coverage.py JSON"]


def test_parse_lcov_content():
    sample_lcov = """
TN:
SF:frontend/src/utils/math.ts
DA:1,1
DA:2,1
DA:5,0
BRDA:2,0,0,1
BRDA:2,0,1,0
end_of_record
"""
    report = parse_lcov_content(sample_lcov, project_id="frontend_proj")
    assert report.total_files == 1
    assert "frontend/src/utils/math.ts" in report.files
    f = report.files["frontend/src/utils/math.ts"]
    assert f.total_lines == 3
    assert f.covered_lines == 2
    assert f.uncovered_lines == 1
    assert round(f.line_coverage_pct, 1) == 66.7
    assert f.total_branches == 2
    assert f.covered_branches == 1
    assert f.branch_coverage_pct == 50.0


def test_parse_jacoco_xml():
    sample_xml = """<?xml version="1.0" encoding="UTF-8"?>
<report name="atp-service">
    <package name="com/atp/orders">
        <sourcefile name="OrderService.java">
            <line nr="1" mi="0" ci="5" mb="0" cb="0"/>
            <line nr="2" mi="0" ci="3" mb="1" cb="1"/>
            <line nr="3" mi="4" ci="0" mb="0" cb="0"/>
        </sourcefile>
    </package>
</report>
"""
    report = parse_jacoco_xml(sample_xml)
    assert report.total_files == 1
    assert "com.atp.orders/OrderService.java" in report.files
    f = report.files["com.atp.orders/OrderService.java"]
    assert f.total_lines == 3
    assert f.covered_lines == 2
    assert f.uncovered_lines == 1
    assert f.line_records[1].status == CoverageLineStatus.COVERED
    assert f.line_records[2].status == CoverageLineStatus.PARTIAL
    assert f.line_records[3].status == CoverageLineStatus.UNCOVERED


def test_merge_coverage_reports_union():
    # 环境 1 (单元测试): 跑了 10, 11 行，漏了 12 行
    json_unit = {
        "files": {
            "service.py": {
                "executed_lines": [10, 11],
                "missing_lines": [12],
                "summary": {"covered_lines": 2, "missing_lines": 1},
            }
        }
    }
    # 环境 2 (集成测试): 跑了 12 行，漏了 10, 11 行
    json_integration = {
        "files": {
            "service.py": {
                "executed_lines": [12],
                "missing_lines": [10, 11],
                "summary": {"covered_lines": 1, "missing_lines": 2},
            }
        }
    }

    rep1 = parse_coverage_py_json(json.dumps(json_unit))
    rep1.sources_ingested = ["Unit Tests"]
    rep2 = parse_coverage_py_json(json.dumps(json_integration))
    rep2.sources_ingested = ["Integration Tests"]

    merged = merge_coverage_reports([rep1, rep2])
    assert merged.total_files == 1
    f = merged.files["service.py"]
    # 取并集后 10, 11, 12 全被执行覆盖！
    assert f.covered_lines == 3
    assert f.uncovered_lines == 0
    assert f.line_coverage_pct == 100.0
    assert f.line_records[12].status == CoverageLineStatus.COVERED
    assert "Unit Tests" in merged.sources_ingested
    assert "Integration Tests" in merged.sources_ingested

    d = merged.to_dict()
    assert d["overall_line_coverage_pct"] == 100.0
    assert "service.py" in d["files"]


def test_merge_empty_reports():
    merged = merge_coverage_reports([])
    assert merged.total_files == 0
    assert merged.overall_line_coverage_pct == 100.0
