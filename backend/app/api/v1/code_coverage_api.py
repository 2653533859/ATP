"""全链路代码覆盖率动态染色与增量发布准入 REST API (T1.3)

挂载至 /api/v1/code-coverage/*，提供:
1. POST /api/v1/code-coverage/ingest (多格式覆盖率报告上报与解析);
2. POST /api/v1/code-coverage/diff-staining (Git Diff 增量代码行覆盖率染色计算);
3. GET /api/v1/code-coverage/reports (获取已归档覆盖率报告列表);
4. GET /api/v1/code-coverage/reports/{report_id} (获取指定覆盖率详情);
5. GET /api/v1/code-coverage/files/staining (获取指定文件逐行红黄绿高亮染色明细)。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.coverage_report_ingestor import (
    CoverageLineStatus,
    FileCoverageSummary,
    LineCoverageRecord,
    UnifiedCoverageReport,
    parse_coverage_py_json,
    parse_jacoco_xml,
    parse_lcov_content,
)
from app.services.diff_coverage_staining_engine import (
    DiffCoverageReport,
    FileDiffCoverageStaining,
    calculate_diff_coverage_staining,
)

router = APIRouter(prefix="/code-coverage", tags=["code-coverage"])

_COVERAGE_STORE: Dict[str, UnifiedCoverageReport] = {}
_DIFF_COVERAGE_STORE: Dict[str, DiffCoverageReport] = {}


def _load_seed_coverage_data():
    """预装载初始示例覆盖率与染色报告"""
    seed_report = UnifiedCoverageReport(
        report_id="cov_seed_master_01",
        project_id="atp_core",
        commit_id="git_hash_8be5d4d1",
        total_files=2,
        overall_line_coverage_pct=88.5,
        overall_branch_coverage_pct=82.0,
        files={
            "backend/app/services/payment.py": FileCoverageSummary(
                file_path="backend/app/services/payment.py",
                total_lines=10,
                covered_lines=9,
                uncovered_lines=1,
                line_coverage_pct=90.0,
                total_branches=4,
                covered_branches=3,
                branch_coverage_pct=75.0,
                line_records={
                    1: LineCoverageRecord(1, hits=5, status=CoverageLineStatus.COVERED),
                    2: LineCoverageRecord(2, hits=5, status=CoverageLineStatus.COVERED),
                    3: LineCoverageRecord(3, hits=5, status=CoverageLineStatus.COVERED),
                    4: LineCoverageRecord(4, hits=5, status=CoverageLineStatus.COVERED),
                    5: LineCoverageRecord(5, hits=5, status=CoverageLineStatus.COVERED),
                    6: LineCoverageRecord(
                        6, hits=2, status=CoverageLineStatus.PARTIAL, branches_covered=1, branches_total=2
                    ),
                    7: LineCoverageRecord(7, hits=2, status=CoverageLineStatus.COVERED),
                    8: LineCoverageRecord(8, hits=0, status=CoverageLineStatus.UNCOVERED),
                    9: LineCoverageRecord(9, hits=3, status=CoverageLineStatus.COVERED),
                    10: LineCoverageRecord(10, hits=3, status=CoverageLineStatus.COVERED),
                },
            ),
            "backend/app/services/order.py": FileCoverageSummary(
                file_path="backend/app/services/order.py",
                total_lines=5,
                covered_lines=4,
                uncovered_lines=1,
                line_coverage_pct=80.0,
                total_branches=2,
                covered_branches=2,
                branch_coverage_pct=100.0,
                line_records={
                    1: LineCoverageRecord(1, hits=4, status=CoverageLineStatus.COVERED),
                    2: LineCoverageRecord(2, hits=4, status=CoverageLineStatus.COVERED),
                    3: LineCoverageRecord(3, hits=4, status=CoverageLineStatus.COVERED),
                    4: LineCoverageRecord(4, hits=0, status=CoverageLineStatus.UNCOVERED),
                    5: LineCoverageRecord(5, hits=4, status=CoverageLineStatus.COVERED),
                },
            ),
        },
        sources_ingested=["Coverage.py JSON", "JaCoCo XML"],
    )
    _COVERAGE_STORE[seed_report.report_id] = seed_report


_load_seed_coverage_data()


def clear_coverage_store():
    """清空覆盖率存储（单测使用）"""
    _COVERAGE_STORE.clear()
    _DIFF_COVERAGE_STORE.clear()
    _load_seed_coverage_data()


class CoverageIngestRequest(BaseModel):
    report_format: str = Field(..., description="覆盖率格式: coverage_py | lcov | jacoco")
    content: str = Field(..., description="报告文本内容 (JSON / LCOV / XML)")
    project_id: str = Field(default="atp_default", description="项目编码")
    commit_id: str = Field(default="head", description="提交哈希")


class DiffStainingRequest(BaseModel):
    diff_text: str = Field(..., description="Git Unified Diff 补丁文本")
    report_id: Optional[str] = Field(default=None, description="已上报的覆盖率报告编码")
    coverage_json: Optional[str] = Field(default=None, description="直接传入的 Coverage.py JSON (可选)")
    source_files: Optional[Dict[str, str]] = Field(default=None, description="变更源码全量内容 (可选)")
    base_commit: str = Field(default="main", description="基线提交")
    target_commit: str = Field(default="head", description="目标提交")


@router.post("/ingest", summary="多格式覆盖率报告解析上报")
def ingest_coverage_report(req: CoverageIngestRequest) -> Dict[str, Any]:
    fmt = req.report_format.strip().lower()
    try:
        if fmt in ("coverage_py", "coveragepy", "json", "python"):
            report = parse_coverage_py_json(req.content, project_id=req.project_id, commit_id=req.commit_id)
        elif fmt in ("lcov", "info"):
            report = parse_lcov_content(req.content, project_id=req.project_id, commit_id=req.commit_id)
        elif fmt in ("jacoco", "xml", "java"):
            report = parse_jacoco_xml(req.content, project_id=req.project_id, commit_id=req.commit_id)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的覆盖率报告格式 [{req.report_format}], 可选: coverage_py, lcov, jacoco",
            )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=400, detail=f"覆盖率报告解析失败: {str(e)}")

    _COVERAGE_STORE[report.report_id] = report
    return report.to_dict()


@router.post("/diff-staining", summary="Git Diff 增量代码行覆盖率染色计算")
def calculate_diff_staining(req: DiffStainingRequest) -> Dict[str, Any]:
    cov_report: Optional[UnifiedCoverageReport] = None

    if req.report_id and req.report_id in _COVERAGE_STORE:
        cov_report = _COVERAGE_STORE[req.report_id]
    elif req.coverage_json:
        try:
            cov_report = parse_coverage_py_json(req.coverage_json)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"解析内联覆盖率 JSON 失败: {str(e)}")
    else:
        # 回退使用当前最新存储的基线覆盖率
        if _COVERAGE_STORE:
            cov_report = next(iter(_COVERAGE_STORE.values()))

    if not cov_report:
        raise HTTPException(status_code=404, detail="未检索到可对齐的覆盖率报告基准，请先上报覆盖率数据。")

    diff_report = calculate_diff_coverage_staining(
        diff_text=req.diff_text,
        coverage_report=cov_report,
        source_files=req.source_files,
        base_commit=req.base_commit,
        target_commit=req.target_commit,
    )
    _DIFF_COVERAGE_STORE[diff_report.diff_report_id] = diff_report
    return diff_report.to_dict()


@router.get("/reports", summary="获取已归档覆盖率报告列表")
def list_coverage_reports(project_id: Optional[str] = None) -> List[Dict[str, Any]]:
    reports = list(_COVERAGE_STORE.values())
    if project_id:
        reports = [r for r in reports if r.project_id == project_id]
    return [r.to_dict() for r in reports]


@router.get("/reports/{report_id}", summary="获取指定覆盖率详情")
def get_coverage_report(report_id: str) -> Dict[str, Any]:
    report = _COVERAGE_STORE.get(report_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"未找到覆盖率报告 [{report_id}]")
    return report.to_dict()


@router.get("/files/staining", summary="获取指定文件逐行红黄绿高亮染色明细")
def get_file_staining_detail(
    diff_report_id: str,
    file_path: str,
) -> Dict[str, Any]:
    diff_report = _DIFF_COVERAGE_STORE.get(diff_report_id)
    if not diff_report:
        raise HTTPException(status_code=404, detail=f"未找到增量染色报告 [{diff_report_id}]")

    norm_path = file_path.replace("\\", "/").strip("/")
    target_staining: Optional[FileDiffCoverageStaining] = None
    for p, fs in diff_report.files.items():
        if p.replace("\\", "/").strip("/") == norm_path or norm_path.endswith(p):
            target_staining = fs
            break

    if not target_staining:
        raise HTTPException(
            status_code=404,
            detail=f"在增量报告 [{diff_report_id}] 中未找到文件 [{file_path}] 的染色数据",
        )
    return target_staining.to_dict()
