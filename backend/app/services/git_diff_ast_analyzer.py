"""Git Diff AST 语法树代码变更语义提取与符号差异解析引擎 (S1.1).

解析 Git Unified Diff 补丁文本，基于 Python AST 语法树遍历与行号区间交集算法，
精准提取 Git 变更所触及的代码符号（类、函数、异步方法、装饰器路由端点）。
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
import re
from typing import Any
import uuid

logger = logging.getLogger(__name__)


class SymbolType(str, Enum):
    CLASS = "class"
    FUNCTION = "function"
    ASYNC_FUNCTION = "async_function"
    METHOD = "method"
    ROUTE_ENDPOINT = "route_endpoint"


class SymbolChangeKind(str, Enum):
    ADDED = "ADDED"
    MODIFIED = "MODIFIED"
    DELETED = "DELETED"
    SIGNATURE_CHANGED = "SIGNATURE_CHANGED"


@dataclass
class ChangedSymbol:
    symbol_id: str
    symbol_type: SymbolType
    symbol_name: str
    file_path: str
    start_line: int
    end_line: int
    changed_lines: list[int]
    change_kind: SymbolChangeKind
    parent_class: str | None = None
    route_method: str | None = None
    route_path: str | None = None
    decorators: list[str] = field(default_factory=list)
    parameters: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol_id": self.symbol_id,
            "symbol_type": self.symbol_type.value,
            "symbol_name": self.symbol_name,
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "changed_lines": self.changed_lines,
            "change_kind": self.change_kind.value,
            "parent_class": self.parent_class,
            "route_method": self.route_method,
            "route_path": self.route_path,
            "decorators": self.decorators,
            "parameters": self.parameters,
        }


@dataclass
class ChangedFileDiff:
    file_path: str
    is_new_file: bool = False
    is_deleted_file: bool = False
    added_lines_count: int = 0
    deleted_lines_count: int = 0
    changed_line_numbers: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "is_new_file": self.is_new_file,
            "is_deleted_file": self.is_deleted_file,
            "added_lines_count": self.added_lines_count,
            "deleted_lines_count": self.deleted_lines_count,
            "changed_line_numbers": self.changed_line_numbers,
        }


@dataclass
class DiffAstAnalysisReport:
    analysis_id: str
    diff_summary: dict[str, Any]
    changed_files: list[ChangedFileDiff]
    affected_symbols: list[ChangedSymbol]
    affected_routes: list[dict[str, Any]]
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "analysis_id": self.analysis_id,
            "diff_summary": self.diff_summary,
            "changed_files": [f.to_dict() for f in self.changed_files],
            "affected_symbols": [s.to_dict() for s in self.affected_symbols],
            "affected_routes": self.affected_routes,
            "analyzed_at": self.analyzed_at.isoformat(),
        }


# 内存报告仓库
_DIFF_AST_REPORTS: dict[str, DiffAstAnalysisReport] = {}

# 正则匹配统一 Diff 头部行
_DIFF_FILE_HEADER = re.compile(r"^diff --git a/(.*?) b/(.*?)$")
_DIFF_HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def parse_unified_diff(diff_text: str) -> list[ChangedFileDiff]:
    """解析 Git Unified Diff 补丁，提取各文件的增删行数及变更行号列表。"""
    files: list[ChangedFileDiff] = []
    current_file: ChangedFileDiff | None = None
    current_line_no = 0

    for line in diff_text.splitlines():
        file_match = _DIFF_FILE_HEADER.match(line)
        if file_match:
            b_path = file_match.group(2)
            current_file = ChangedFileDiff(file_path=b_path)
            files.append(current_file)
            continue

        if current_file is None:
            continue

        if line.startswith("new file mode"):
            current_file.is_new_file = True
            continue
        elif line.startswith("deleted file mode"):
            current_file.is_deleted_file = True
            continue

        hunk_match = _DIFF_HUNK_HEADER.match(line)
        if hunk_match:
            new_start = int(hunk_match.group(3))
            current_line_no = new_start
            continue

        if line.startswith("+") and not line.startswith("+++"):
            current_file.added_lines_count += 1
            current_file.changed_line_numbers.append(current_line_no)
            current_line_no += 1
        elif line.startswith("-") and not line.startswith("---"):
            current_file.deleted_lines_count += 1
            # 记录删除发生处的对应新行号
            if current_line_no not in current_file.changed_line_numbers:
                current_file.changed_line_numbers.append(current_line_no)
        elif not line.startswith("\\"):
            # 上下文未变行
            current_line_no += 1

    return files


def _extract_decorator_name(dec_node: ast.expr) -> str:
    """提取装饰器表达式的字符串形式。"""
    if isinstance(dec_node, ast.Name):
        return dec_node.id
    elif isinstance(dec_node, ast.Attribute):
        val = _extract_decorator_name(dec_node.value)
        return f"{val}.{dec_node.attr}" if val else dec_node.attr
    elif isinstance(dec_node, ast.Call):
        return _extract_decorator_name(dec_node.func)
    return ""


def _extract_route_info(dec_node: ast.expr) -> tuple[str | None, str | None]:
    """从 FastAPI/Flask/Router 路由装饰器中解析 HTTP Method 与 Path。"""
    # 形如 @router.get("/users") 或 @app.post("/login")
    if isinstance(dec_node, ast.Call):
        func_expr = _extract_decorator_name(dec_node.func).lower()
        method_candidates = ["get", "post", "put", "delete", "patch", "options", "head"]
        matched_method = None
        for m in method_candidates:
            if func_expr.endswith(f".{m}") or func_expr == m:
                matched_method = m.upper()
                break

        if matched_method:
            route_path = None
            if dec_node.args and isinstance(dec_node.args[0], ast.Constant):
                route_path = str(dec_node.args[0].value)
            return matched_method, route_path

    return None, None


def extract_python_ast_symbols(source_code: str, file_path: str) -> list[ChangedSymbol]:
    """遍历 Python 源码 AST 树，提取所有类与函数（含路由）符号范围。"""
    symbols: list[ChangedSymbol] = []
    try:
        tree = ast.parse(source_code, filename=file_path)
    except SyntaxError as exc:
        logger.warning("Failed to parse AST for %s: %s", file_path, exc)
        return symbols

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            class_start = node.lineno
            if node.decorator_list:
                class_start = min(node.lineno, min(getattr(d, "lineno", node.lineno) for d in node.decorator_list))
            class_end = getattr(node, "end_lineno", node.lineno)
            symbols.append(
                ChangedSymbol(
                    symbol_id=f"{file_path}:{node.name}",
                    symbol_type=SymbolType.CLASS,
                    symbol_name=node.name,
                    file_path=file_path,
                    start_line=class_start,
                    end_line=class_end,
                    changed_lines=[],
                    change_kind=SymbolChangeKind.MODIFIED,
                    parent_class=None,
                )
            )

            # 遍历类内部方法
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    fn_start = item.lineno
                    if item.decorator_list:
                        fn_start = min(item.lineno, min(getattr(d, "lineno", item.lineno) for d in item.decorator_list))
                    fn_end = getattr(item, "end_lineno", item.lineno)
                    decs = [_extract_decorator_name(d) for d in item.decorator_list]
                    params = [arg.arg for arg in item.args.args]
                    symbols.append(
                        ChangedSymbol(
                            symbol_id=f"{file_path}:{node.name}.{item.name}",
                            symbol_type=SymbolType.METHOD,
                            symbol_name=item.name,
                            file_path=file_path,
                            start_line=fn_start,
                            end_line=fn_end,
                            changed_lines=[],
                            change_kind=SymbolChangeKind.MODIFIED,
                            parent_class=node.name,
                            decorators=decs,
                            parameters=params,
                        )
                    )

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fn_start = node.lineno
            if node.decorator_list:
                fn_start = min(node.lineno, min(getattr(d, "lineno", node.lineno) for d in node.decorator_list))
            fn_end = getattr(node, "end_lineno", node.lineno)
            decs = [_extract_decorator_name(d) for d in node.decorator_list]
            params = [arg.arg for arg in node.args.args]

            # 检查是否有路由装饰器
            route_method, route_path = None, None
            for dec in node.decorator_list:
                m, p = _extract_route_info(dec)
                if m and p:
                    route_method, route_path = m, p
                    break

            sym_type = (
                SymbolType.ROUTE_ENDPOINT
                if route_method
                else (SymbolType.ASYNC_FUNCTION if isinstance(node, ast.AsyncFunctionDef) else SymbolType.FUNCTION)
            )

            symbols.append(
                ChangedSymbol(
                    symbol_id=f"{file_path}:{node.name}",
                    symbol_type=sym_type,
                    symbol_name=node.name,
                    file_path=file_path,
                    start_line=fn_start,
                    end_line=fn_end,
                    changed_lines=[],
                    change_kind=SymbolChangeKind.MODIFIED,
                    route_method=route_method,
                    route_path=route_path,
                    decorators=decs,
                    parameters=params,
                )
            )

    return symbols


def analyze_git_diff_ast(
    diff_text: str,
    file_sources: dict[str, str] | None = None,
) -> DiffAstAnalysisReport:
    """对 Git Diff 执行 AST 语法树符号交集语义分析。"""
    analysis_id = f"diff_ast_{uuid.uuid4().hex[:12]}"
    file_diffs = parse_unified_diff(diff_text)
    sources = file_sources or {}

    total_added = sum(f.added_lines_count for f in file_diffs)
    total_deleted = sum(f.deleted_lines_count for f in file_diffs)

    affected_symbols: list[ChangedSymbol] = []
    affected_routes: list[dict[str, Any]] = []

    for fdiff in file_diffs:
        # 仅针对 Python 代码文件进行 AST 树深度解析
        if not fdiff.file_path.endswith(".py"):
            continue

        src = sources.get(fdiff.file_path, "")
        if not src:
            continue

        file_symbols = extract_python_ast_symbols(src, fdiff.file_path)
        changed_set = set(fdiff.changed_line_numbers)

        for sym in file_symbols:
            # 判断变更行与符号跨越行号是否产生交集
            intersect = [ln for ln in changed_set if sym.start_line <= ln <= sym.end_line]
            if intersect:
                sym.changed_lines = sorted(intersect)
                if fdiff.is_new_file:
                    sym.change_kind = SymbolChangeKind.ADDED
                else:
                    sym.change_kind = SymbolChangeKind.MODIFIED

                affected_symbols.append(sym)

                if sym.route_method and sym.route_path:
                    affected_routes.append(
                        {
                            "route_method": sym.route_method,
                            "route_path": sym.route_path,
                            "handler_function": sym.symbol_name,
                            "file_path": sym.file_path,
                            "symbol_id": sym.symbol_id,
                            "changed_lines_count": len(intersect),
                        }
                    )

    report = DiffAstAnalysisReport(
        analysis_id=analysis_id,
        diff_summary={
            "total_files_changed": len(file_diffs),
            "total_added_lines": total_added,
            "total_deleted_lines": total_deleted,
            "net_lines_delta": total_added - total_deleted,
            "affected_symbols_count": len(affected_symbols),
            "affected_routes_count": len(affected_routes),
        },
        changed_files=file_diffs,
        affected_symbols=affected_symbols,
        affected_routes=affected_routes,
    )

    _DIFF_AST_REPORTS[analysis_id] = report
    logger.info(
        "Analyzed git diff AST: analysis_id=%s files=%d symbols=%d routes=%d",
        analysis_id,
        len(file_diffs),
        len(affected_symbols),
        len(affected_routes),
    )
    return report


def get_diff_ast_report(analysis_id: str) -> DiffAstAnalysisReport | None:
    """获取指定分析报告。"""
    return _DIFF_AST_REPORTS.get(analysis_id)


def list_diff_ast_reports() -> list[DiffAstAnalysisReport]:
    """查询历史分析报告列表。"""
    return list(_DIFF_AST_REPORTS.values())


def reset_diff_ast_registry() -> None:
    """单元测试清理状态使用。"""
    _DIFF_AST_REPORTS.clear()
