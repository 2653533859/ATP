"""多源覆盖率报告解析与合并器服务 (T1.1)

支持解析不同技术栈覆盖率数据格式并实现多环境覆盖率并集融合:
1. Coverage.py JSON 格式解析 (Python 单元/集成测试覆盖率);
2. LCOV 格式解析 (JavaScript / TypeScript / C++ / Web 覆盖率);
3. JaCoCo XML 格式解析 (Java / Kotlin 微服务覆盖率);
4. 多源覆盖率合并融合引擎 (Unit + Integration + E2E 覆盖率取并集);
5. 统一数据模型与行级状态映射 (UnifiedCoverageReport, FileCoverageSummary, LineCoverageRecord)。
"""

from __future__ import annotations

import enum
import json
import uuid
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List


class CoverageLineStatus(str, enum.Enum):
    COVERED = "COVERED"  # 绿色：全覆盖执行
    PARTIAL = "PARTIAL"  # 黄色：分支部分覆盖
    UNCOVERED = "UNCOVERED"  # 红色：未执行覆盖
    NOT_EXECUTABLE = "NOT_EXECUTABLE"  # 灰色：非可执行行（注释/空行）


@dataclass
class LineCoverageRecord:
    line_number: int
    hits: int
    status: CoverageLineStatus
    branches_covered: int = 0
    branches_total: int = 0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class FileCoverageSummary:
    file_path: str
    total_lines: int
    covered_lines: int
    uncovered_lines: int
    line_coverage_pct: float
    total_branches: int = 0
    covered_branches: int = 0
    branch_coverage_pct: float = 0.0
    line_records: Dict[int, LineCoverageRecord] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "total_lines": self.total_lines,
            "covered_lines": self.covered_lines,
            "uncovered_lines": self.uncovered_lines,
            "line_coverage_pct": round(self.line_coverage_pct, 1),
            "total_branches": self.total_branches,
            "covered_branches": self.covered_branches,
            "branch_coverage_pct": round(self.branch_coverage_pct, 1),
            "line_records": {str(k): v.to_dict() for k, v in self.line_records.items()},
        }


@dataclass
class UnifiedCoverageReport:
    report_id: str
    project_id: str
    commit_id: str
    total_files: int
    overall_line_coverage_pct: float
    overall_branch_coverage_pct: float
    files: Dict[str, FileCoverageSummary]
    sources_ingested: List[str]
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "project_id": self.project_id,
            "commit_id": self.commit_id,
            "total_files": self.total_files,
            "overall_line_coverage_pct": round(self.overall_line_coverage_pct, 1),
            "overall_branch_coverage_pct": round(self.overall_branch_coverage_pct, 1),
            "files": {k: v.to_dict() for k, v in self.files.items()},
            "sources_ingested": self.sources_ingested,
            "generated_at": self.generated_at,
        }


def parse_coverage_py_json(
    json_content: str, project_id: str = "default_proj", commit_id: str = "head"
) -> UnifiedCoverageReport:
    """解析 Python Coverage.py 生成的 JSON 格式覆盖率报告"""
    data = json.loads(json_content)
    files_data = data.get("files", {})
    parsed_files: Dict[str, FileCoverageSummary] = {}

    tot_exec = 0
    tot_miss = 0
    tot_br_cov = 0
    tot_br_tot = 0

    for file_path, f_info in files_data.items():
        exec_lines = set(f_info.get("executed_lines", []))
        miss_lines = set(f_info.get("missing_lines", []))
        summary = f_info.get("summary", {})

        n_exec = summary.get("covered_lines", len(exec_lines))
        n_miss = summary.get("missing_lines", len(miss_lines))
        n_tot = n_exec + n_miss
        pct = (n_exec / n_tot * 100.0) if n_tot > 0 else 100.0

        n_br_tot = summary.get("num_branches", 0)
        n_br_cov = summary.get("covered_branches", 0)
        br_pct = (n_br_cov / n_br_tot * 100.0) if n_br_tot > 0 else 100.0

        tot_exec += n_exec
        tot_miss += n_miss
        tot_br_cov += n_br_cov
        tot_br_tot += n_br_tot

        line_records: Dict[int, LineCoverageRecord] = {}
        for line in exec_lines:
            line_records[line] = LineCoverageRecord(line_number=line, hits=1, status=CoverageLineStatus.COVERED)
        for line in miss_lines:
            line_records[line] = LineCoverageRecord(line_number=line, hits=0, status=CoverageLineStatus.UNCOVERED)

        parsed_files[file_path] = FileCoverageSummary(
            file_path=file_path,
            total_lines=n_tot,
            covered_lines=n_exec,
            uncovered_lines=n_miss,
            line_coverage_pct=pct,
            total_branches=n_br_tot,
            covered_branches=n_br_cov,
            branch_coverage_pct=br_pct,
            line_records=line_records,
        )

    all_lines = tot_exec + tot_miss
    overall_line_pct = (tot_exec / all_lines * 100.0) if all_lines > 0 else 100.0
    overall_br_pct = (tot_br_cov / tot_br_tot * 100.0) if tot_br_tot > 0 else 100.0

    return UnifiedCoverageReport(
        report_id=f"cov_{uuid.uuid4().hex[:10]}",
        project_id=project_id,
        commit_id=commit_id,
        total_files=len(parsed_files),
        overall_line_coverage_pct=overall_line_pct,
        overall_branch_coverage_pct=overall_br_pct,
        files=parsed_files,
        sources_ingested=["Coverage.py JSON"],
    )


def parse_lcov_content(
    lcov_content: str, project_id: str = "default_proj", commit_id: str = "head"
) -> UnifiedCoverageReport:
    """解析 JavaScript / TypeScript LCOV (info) 覆盖率报告"""
    parsed_files: Dict[str, FileCoverageSummary] = {}
    current_file = ""
    line_records: Dict[int, LineCoverageRecord] = {}
    total_lines = 0
    covered_lines = 0
    total_branches = 0
    covered_branches = 0

    for line in lcov_content.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("SF:"):
            current_file = line[3:].strip()
            line_records = {}
            total_lines = 0
            covered_lines = 0
            total_branches = 0
            covered_branches = 0
        elif line.startswith("DA:"):
            parts = line[3:].split(",")
            if len(parts) >= 2:
                ln = int(parts[0])
                hits = int(parts[1])
                status = CoverageLineStatus.COVERED if hits > 0 else CoverageLineStatus.UNCOVERED
                line_records[ln] = LineCoverageRecord(line_number=ln, hits=hits, status=status)
                total_lines += 1
                if hits > 0:
                    covered_lines += 1
        elif line.startswith("BRDA:"):
            parts = line[5:].split(",")
            if len(parts) >= 4:
                taken = parts[3].strip()
                hits = 0 if taken in ("-", "0") else int(taken)
                total_branches += 1
                if hits > 0:
                    covered_branches += 1
        elif line == "end_of_record" and current_file:
            line_pct = (covered_lines / total_lines * 100.0) if total_lines > 0 else 100.0
            br_pct = (covered_branches / total_branches * 100.0) if total_branches > 0 else 100.0
            parsed_files[current_file] = FileCoverageSummary(
                file_path=current_file,
                total_lines=total_lines,
                covered_lines=covered_lines,
                uncovered_lines=total_lines - covered_lines,
                line_coverage_pct=line_pct,
                total_branches=total_branches,
                covered_branches=covered_branches,
                branch_coverage_pct=br_pct,
                line_records=line_records,
            )

    all_cov = sum(f.covered_lines for f in parsed_files.values())
    all_tot = sum(f.total_lines for f in parsed_files.values())
    all_br_cov = sum(f.covered_branches for f in parsed_files.values())
    all_br_tot = sum(f.total_branches for f in parsed_files.values())

    overall_line_pct = (all_cov / all_tot * 100.0) if all_tot > 0 else 100.0
    overall_br_pct = (all_br_cov / all_br_tot * 100.0) if all_br_tot > 0 else 100.0

    return UnifiedCoverageReport(
        report_id=f"cov_{uuid.uuid4().hex[:10]}",
        project_id=project_id,
        commit_id=commit_id,
        total_files=len(parsed_files),
        overall_line_coverage_pct=overall_line_pct,
        overall_branch_coverage_pct=overall_br_pct,
        files=parsed_files,
        sources_ingested=["LCOV info"],
    )


def parse_jacoco_xml(
    xml_content: str, project_id: str = "default_proj", commit_id: str = "head"
) -> UnifiedCoverageReport:
    """解析 Java JaCoCo XML 覆盖率报告"""
    root = ET.fromstring(xml_content)
    parsed_files: Dict[str, FileCoverageSummary] = {}

    for package_el in root.findall(".//package"):
        pkg_name = package_el.get("name", "").replace("/", ".")
        for sf_el in package_el.findall("./sourcefile"):
            sf_name = sf_el.get("name", "")
            file_path = f"{pkg_name}/{sf_name}" if pkg_name else sf_name

            line_records: Dict[int, LineCoverageRecord] = {}
            total_lines = 0
            covered_lines = 0
            total_branches = 0
            covered_branches = 0

            for line_el in sf_el.findall("./line"):
                ln = int(line_el.get("nr", "0"))
                _mi = int(line_el.get("mi", "0"))  # missed instructions
                ci = int(line_el.get("ci", "0"))  # covered instructions
                mb = int(line_el.get("mb", "0"))  # missed branches
                cb = int(line_el.get("cb", "0"))  # covered branches

                branches_t = mb + cb
                if ci > 0 and mb > 0:
                    status = CoverageLineStatus.PARTIAL
                elif ci > 0:
                    status = CoverageLineStatus.COVERED
                else:
                    status = CoverageLineStatus.UNCOVERED

                hits = 1 if ci > 0 else 0
                line_records[ln] = LineCoverageRecord(
                    line_number=ln,
                    hits=hits,
                    status=status,
                    branches_covered=cb,
                    branches_total=branches_t,
                )
                total_lines += 1
                if hits > 0:
                    covered_lines += 1
                total_branches += branches_t
                covered_branches += cb

            line_pct = (covered_lines / total_lines * 100.0) if total_lines > 0 else 100.0
            br_pct = (covered_branches / total_branches * 100.0) if total_branches > 0 else 100.0

            parsed_files[file_path] = FileCoverageSummary(
                file_path=file_path,
                total_lines=total_lines,
                covered_lines=covered_lines,
                uncovered_lines=total_lines - covered_lines,
                line_coverage_pct=line_pct,
                total_branches=total_branches,
                covered_branches=covered_branches,
                branch_coverage_pct=br_pct,
                line_records=line_records,
            )

    all_cov = sum(f.covered_lines for f in parsed_files.values())
    all_tot = sum(f.total_lines for f in parsed_files.values())
    all_br_cov = sum(f.covered_branches for f in parsed_files.values())
    all_br_tot = sum(f.total_branches for f in parsed_files.values())

    overall_line_pct = (all_cov / all_tot * 100.0) if all_tot > 0 else 100.0
    overall_br_pct = (all_br_cov / all_br_tot * 100.0) if all_br_tot > 0 else 100.0

    return UnifiedCoverageReport(
        report_id=f"cov_{uuid.uuid4().hex[:10]}",
        project_id=project_id,
        commit_id=commit_id,
        total_files=len(parsed_files),
        overall_line_coverage_pct=overall_line_pct,
        overall_branch_coverage_pct=overall_br_pct,
        files=parsed_files,
        sources_ingested=["JaCoCo XML"],
    )


def merge_coverage_reports(reports: List[UnifiedCoverageReport]) -> UnifiedCoverageReport:
    """多环境覆盖率合并器：取并集融合 (只要任一环境执行过即视为覆盖)"""
    if not reports:
        return UnifiedCoverageReport(
            report_id=f"cov_empty_{uuid.uuid4().hex[:8]}",
            project_id="merged",
            commit_id="merged",
            total_files=0,
            overall_line_coverage_pct=100.0,
            overall_branch_coverage_pct=100.0,
            files={},
            sources_ingested=[],
        )

    merged_files: Dict[str, FileCoverageSummary] = {}
    sources: List[str] = []

    for r in reports:
        for s in r.sources_ingested:
            if s not in sources:
                sources.append(s)

        for path, f_summary in r.files.items():
            if path not in merged_files:
                # 克隆一份基础结构
                merged_files[path] = FileCoverageSummary(
                    file_path=path,
                    total_lines=f_summary.total_lines,
                    covered_lines=f_summary.covered_lines,
                    uncovered_lines=f_summary.uncovered_lines,
                    line_coverage_pct=f_summary.line_coverage_pct,
                    total_branches=f_summary.total_branches,
                    covered_branches=f_summary.covered_branches,
                    branch_coverage_pct=f_summary.branch_coverage_pct,
                    line_records={
                        ln: LineCoverageRecord(
                            line_number=rec.line_number,
                            hits=rec.hits,
                            status=rec.status,
                            branches_covered=rec.branches_covered,
                            branches_total=rec.branches_total,
                        )
                        for ln, rec in f_summary.line_records.items()
                    },
                )
            else:
                existing = merged_files[path]
                for ln, rec in f_summary.line_records.items():
                    if ln not in existing.line_records:
                        existing.line_records[ln] = LineCoverageRecord(
                            line_number=rec.line_number,
                            hits=rec.hits,
                            status=rec.status,
                            branches_covered=rec.branches_covered,
                            branches_total=rec.branches_total,
                        )
                    else:
                        ex_rec = existing.line_records[ln]
                        ex_rec.hits += rec.hits
                        ex_rec.branches_covered = max(ex_rec.branches_covered, rec.branches_covered)
                        ex_rec.branches_total = max(ex_rec.branches_total, rec.branches_total)

                        # 更新行状态并集逻辑
                        if ex_rec.hits > 0:
                            if ex_rec.branches_total > 0 and ex_rec.branches_covered < ex_rec.branches_total:
                                ex_rec.status = CoverageLineStatus.PARTIAL
                            else:
                                ex_rec.status = CoverageLineStatus.COVERED

                # 重新计算单个文件的覆盖率指标
                cov_lines = sum(1 for rec in existing.line_records.values() if rec.hits > 0)
                tot_lines = len(existing.line_records)
                existing.total_lines = tot_lines
                existing.covered_lines = cov_lines
                existing.uncovered_lines = tot_lines - cov_lines
                existing.line_coverage_pct = (cov_lines / tot_lines * 100.0) if tot_lines > 0 else 100.0

    all_cov = sum(f.covered_lines for f in merged_files.values())
    all_tot = sum(f.total_lines for f in merged_files.values())
    all_br_cov = sum(f.covered_branches for f in merged_files.values())
    all_br_tot = sum(f.total_branches for f in merged_files.values())

    overall_line_pct = (all_cov / all_tot * 100.0) if all_tot > 0 else 100.0
    overall_br_pct = (all_br_cov / all_br_tot * 100.0) if all_br_tot > 0 else 100.0

    return UnifiedCoverageReport(
        report_id=f"cov_merged_{uuid.uuid4().hex[:10]}",
        project_id=reports[0].project_id,
        commit_id=reports[0].commit_id,
        total_files=len(merged_files),
        overall_line_coverage_pct=overall_line_pct,
        overall_branch_coverage_pct=overall_br_pct,
        files=merged_files,
        sources_ingested=sources,
    )
