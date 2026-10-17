"""Git Diff 增量代码行覆盖率染色计算器服务 (T1.2)

对比 Git Unified Diff 补丁与多源覆盖率报告，计算增量代码覆盖率指标并生成逐行染色元数据:
1. 提取本次 PR/Commit 目标变更行号 (基于 parse_unified_diff_hunks);
2. 增量代码行覆盖率计算 (Diff Line Coverage % = 已覆盖变更行 / 变更可执行行);
3. 增量代码分支覆盖率计算 (Diff Branch Coverage % = 已覆盖变更分支 / 变更可执行分支);
4. 行级红/黄/绿高亮染色状态打标 (StainedLine: COVERED 绿, PARTIAL 黄, UNCOVERED 红);
5. 综合增量染色报告生成 (DiffCoverageReport & FileDiffCoverageStaining)。
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.code_diff_symbol_extractor import parse_unified_diff_hunks
from app.services.coverage_report_ingestor import (
    CoverageLineStatus,
    FileCoverageSummary,
    LineCoverageRecord,
    UnifiedCoverageReport,
)


@dataclass
class StainedLine:
    line_number: int
    content: str
    is_changed_in_diff: bool
    status: CoverageLineStatus
    hits: int = 0
    branches_covered: int = 0
    branches_total: int = 0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class FileDiffCoverageStaining:
    file_path: str
    changed_executable_lines_count: int
    changed_covered_lines_count: int
    changed_uncovered_lines_count: int
    changed_partial_lines_count: int
    diff_line_coverage_pct: float
    changed_branches_total: int
    changed_branches_covered: int
    diff_branch_coverage_pct: float
    stained_lines: List[StainedLine] = field(default_factory=list)
    red_uncovered_lines: List[int] = field(default_factory=list)
    yellow_partial_lines: List[int] = field(default_factory=list)
    green_covered_lines: List[int] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "changed_executable_lines_count": self.changed_executable_lines_count,
            "changed_covered_lines_count": self.changed_covered_lines_count,
            "changed_uncovered_lines_count": self.changed_uncovered_lines_count,
            "changed_partial_lines_count": self.changed_partial_lines_count,
            "diff_line_coverage_pct": round(self.diff_line_coverage_pct, 1),
            "changed_branches_total": self.changed_branches_total,
            "changed_branches_covered": self.changed_branches_covered,
            "diff_branch_coverage_pct": round(self.diff_branch_coverage_pct, 1),
            "red_uncovered_lines": self.red_uncovered_lines,
            "yellow_partial_lines": self.yellow_partial_lines,
            "green_covered_lines": self.green_covered_lines,
            "stained_lines": [sl.to_dict() for sl in self.stained_lines],
        }


@dataclass
class DiffCoverageReport:
    diff_report_id: str
    base_commit: str
    target_commit: str
    total_changed_files: int
    overall_diff_line_coverage_pct: float
    overall_diff_branch_coverage_pct: float
    files: Dict[str, FileDiffCoverageStaining]
    total_changed_lines: int
    total_uncovered_lines: int
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "diff_report_id": self.diff_report_id,
            "base_commit": self.base_commit,
            "target_commit": self.target_commit,
            "total_changed_files": self.total_changed_files,
            "overall_diff_line_coverage_pct": round(self.overall_diff_line_coverage_pct, 1),
            "overall_diff_branch_coverage_pct": round(self.overall_diff_branch_coverage_pct, 1),
            "total_changed_lines": self.total_changed_lines,
            "total_uncovered_lines": self.total_uncovered_lines,
            "files": {k: v.to_dict() for k, v in self.files.items()},
            "generated_at": self.generated_at,
        }


def _match_coverage_file_summary(
    diff_path: str,
    coverage_files: Dict[str, FileCoverageSummary],
) -> Optional[FileCoverageSummary]:
    """宽松匹配覆盖率报告中的文件路径 (支持绝对路径、相对路径或包名映射)"""
    norm_diff = diff_path.replace("\\", "/").strip("/")
    if norm_diff in coverage_files:
        return coverage_files[norm_diff]

    for c_path, summary in coverage_files.items():
        norm_c = c_path.replace("\\", "/").strip("/")
        if norm_c.endswith(norm_diff) or norm_diff.endswith(norm_c):
            return summary
    return None


def calculate_diff_coverage_staining(
    diff_text: str,
    coverage_report: UnifiedCoverageReport,
    source_files: Optional[Dict[str, str]] = None,
    base_commit: str = "main",
    target_commit: str = "head",
) -> DiffCoverageReport:
    """计算 Git Diff 增量代码行与分支覆盖率，并生成逐行染色元数据"""
    changed_files_lines = parse_unified_diff_hunks(diff_text)
    sources = source_files or {}

    total_changed_exec_lines = 0
    total_changed_covered_lines = 0
    total_changed_branches = 0
    total_changed_covered_branches = 0

    staining_results: Dict[str, FileDiffCoverageStaining] = {}

    for file_path, changed_lines in changed_files_lines.items():
        if not changed_lines:
            continue

        file_cov = _match_coverage_file_summary(file_path, coverage_report.files)
        file_lines_records: Dict[int, LineCoverageRecord] = file_cov.line_records if file_cov else {}

        # 读取源码全量行（若提供）
        file_content = sources.get(file_path, "")
        raw_source_lines = file_content.splitlines() if file_content else []

        red_lines: List[int] = []
        yellow_lines: List[int] = []
        green_lines: List[int] = []
        stained_lines: List[StainedLine] = []

        file_changed_exec = 0
        file_changed_cov = 0
        file_changed_partial = 0
        file_changed_uncovered = 0

        file_br_tot = 0
        file_br_cov = 0

        # 如果提供了源码，输出整文件所有行；若未提供，只输出变更行
        max_line = max(max(changed_lines, default=0), len(raw_source_lines))
        for ln in range(1, max_line + 1):
            is_changed = ln in changed_lines
            content = raw_source_lines[ln - 1] if ln <= len(raw_source_lines) else ""
            rec = file_lines_records.get(ln)

            if rec is not None:
                status = rec.status
                hits = rec.hits
                br_cov = rec.branches_covered
                br_tot = rec.branches_total
            else:
                status = CoverageLineStatus.NOT_EXECUTABLE
                hits = 0
                br_cov = 0
                br_tot = 0

            # 仅对本次 Diff 修改的可执行行进行增量覆盖率统计
            if is_changed and status != CoverageLineStatus.NOT_EXECUTABLE:
                file_changed_exec += 1
                file_br_tot += br_tot
                file_br_cov += br_cov

                if status == CoverageLineStatus.COVERED:
                    file_changed_cov += 1
                    green_lines.append(ln)
                elif status == CoverageLineStatus.PARTIAL:
                    file_changed_cov += 1
                    file_changed_partial += 1
                    yellow_lines.append(ln)
                elif status == CoverageLineStatus.UNCOVERED:
                    file_changed_uncovered += 1
                    red_lines.append(ln)

            # 只保留源码行或变更行进行染色
            if is_changed or file_content:
                stained_lines.append(
                    StainedLine(
                        line_number=ln,
                        content=content,
                        is_changed_in_diff=is_changed,
                        status=status,
                        hits=hits,
                        branches_covered=br_cov,
                        branches_total=br_tot,
                    )
                )

        diff_line_pct = (file_changed_cov / file_changed_exec * 100.0) if file_changed_exec > 0 else 100.0
        diff_br_pct = (file_br_cov / file_br_tot * 100.0) if file_br_tot > 0 else 100.0

        total_changed_exec_lines += file_changed_exec
        total_changed_covered_lines += file_changed_cov
        total_changed_branches += file_br_tot
        total_changed_covered_branches += file_br_cov

        staining_results[file_path] = FileDiffCoverageStaining(
            file_path=file_path,
            changed_executable_lines_count=file_changed_exec,
            changed_covered_lines_count=file_changed_cov,
            changed_uncovered_lines_count=file_changed_uncovered,
            changed_partial_lines_count=file_changed_partial,
            diff_line_coverage_pct=diff_line_pct,
            changed_branches_total=file_br_tot,
            changed_branches_covered=file_br_cov,
            diff_branch_coverage_pct=diff_br_pct,
            stained_lines=stained_lines,
            red_uncovered_lines=red_lines,
            yellow_partial_lines=yellow_lines,
            green_covered_lines=green_lines,
        )

    overall_diff_line_pct = (
        (total_changed_covered_lines / total_changed_exec_lines * 100.0) if total_changed_exec_lines > 0 else 100.0
    )
    overall_diff_br_pct = (
        (total_changed_covered_branches / total_changed_branches * 100.0) if total_changed_branches > 0 else 100.0
    )

    tot_uncovered = sum(f.changed_uncovered_lines_count for f in staining_results.values())

    return DiffCoverageReport(
        diff_report_id=f"dcov_{uuid.uuid4().hex[:10]}",
        base_commit=base_commit,
        target_commit=target_commit,
        total_changed_files=len(staining_results),
        overall_diff_line_coverage_pct=overall_diff_line_pct,
        overall_diff_branch_coverage_pct=overall_diff_br_pct,
        files=staining_results,
        total_changed_lines=total_changed_exec_lines,
        total_uncovered_lines=tot_uncovered,
    )
