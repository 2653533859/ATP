"""Git Diff 与 AST 变更高危符号提取器服务 (T1.1)

在增量精准回归测试中提供代码补丁与 AST 语法树变更高危符号精准提取能力:
1. Unified Diff 补丁分块解析与文件修改行号范围提取 (parse_unified_diff_hunks);
2. Python AST 语法树类、同步函数与异步方法定义范围扫描 (extract_symbols_from_ast);
3. 变更行与 AST 符号范围碰撞交叉分析与签名变动识别 (extract_diff_changed_symbols);
4. 结构化变更符号报告输出与严重度分类 (DiffSymbolExtractionReport)。
"""

from __future__ import annotations

import ast
import enum
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set


class SymbolType(str, enum.Enum):
    FUNCTION = "FUNCTION"
    ASYNC_FUNCTION = "ASYNC_FUNCTION"
    CLASS = "CLASS"
    METHOD = "METHOD"


class SymbolChangeType(str, enum.Enum):
    MODIFIED = "MODIFIED"  # 函数体内部实现逻辑修改
    ADDED = "ADDED"  # 新增类或函数
    DELETED = "DELETED"  # 废弃删除符号
    SIGNATURE_CHANGED = "SIGNATURE_CHANGED"  # 核心参数签名发生变更 (高危)


class SymbolChangeSeverity(str, enum.Enum):
    CRITICAL = "CRITICAL"  # 签名变更，可能导致依赖调用直接崩溃
    MAJOR = "MAJOR"  # 函数实现或类主体变更
    MINOR = "MINOR"  # 次要微调 (如格式或局部变量重构)


@dataclass
class ChangedSymbolItem:
    symbol_id: str
    file_path: str
    symbol_name: str
    qualified_name: str
    symbol_type: SymbolType
    change_type: SymbolChangeType
    severity: SymbolChangeSeverity
    line_start: int
    line_end: int
    touched_lines: List[int]
    signature: str

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["symbol_type"] = self.symbol_type.value
        d["change_type"] = self.change_type.value
        d["severity"] = self.severity.value
        return d


@dataclass
class DiffSymbolExtractionReport:
    report_id: str
    total_files_analyzed: int
    changed_symbols_count: int
    symbols: List[ChangedSymbolItem]
    analyzed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "total_files_analyzed": self.total_files_analyzed,
            "changed_symbols_count": self.changed_symbols_count,
            "symbols": [s.to_dict() for s in self.symbols],
            "analyzed_at": self.analyzed_at,
        }


def parse_unified_diff_hunks(diff_text: str) -> Dict[str, Set[int]]:
    """解析 Unified Diff 补丁文本，返回每个文件被修改/新增的目标行号集合

    Returns:
        Dict[file_path, Set[line_numbers]]
    """
    file_lines_map: Dict[str, Set[int]] = {}
    current_file: Optional[str] = None
    current_line = 0

    hunk_regex = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")

    for raw_line in diff_text.splitlines():
        # 文件头标记: +++ b/path/to/file.py
        if raw_line.startswith("+++ b/"):
            current_file = raw_line[6:].strip()
            if current_file not in file_lines_map:
                file_lines_map[current_file] = set()
            continue
        elif raw_line.startswith("+++ "):
            # 兼容无 b/ 前缀
            current_file = raw_line[4:].strip()
            if current_file not in file_lines_map:
                file_lines_map[current_file] = set()
            continue

        if current_file is None:
            continue

        # Hunk 头: @@ -15,7 +15,12 @@
        match = hunk_regex.match(raw_line)
        if match:
            current_line = int(match.group(1))
            continue

        # Diff 内容行
        if raw_line.startswith("+") and not raw_line.startswith("+++"):
            file_lines_map[current_file].add(current_line)
            current_line += 1
        elif raw_line.startswith("-") and not raw_line.startswith("---"):
            # 删除行：记录在当前位置
            file_lines_map[current_file].add(max(1, current_line))
        elif raw_line.startswith(" "):
            # 上下文保留行
            current_line += 1

    return file_lines_map


@dataclass
class _ASTSymbolRange:
    name: str
    qualified_name: str
    symbol_type: SymbolType
    start_line: int
    end_line: int
    signature: str


def _format_function_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = [a.arg for a in node.args.args]
    return f"{node.name}({', '.join(args)})"


def extract_symbols_from_ast(source_code: str) -> List[_ASTSymbolRange]:
    """解析 Python 源码 AST 树，提取所有类、函数与方法的行号范围"""
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return []

    symbols: List[_ASTSymbolRange] = []

    class _Visitor(ast.NodeVisitor):
        def __init__(self):
            self.class_stack: List[str] = []

        def visit_ClassDef(self, node: ast.ClassDef):
            start = node.lineno
            end = getattr(node, "end_lineno", start + len(node.body))
            qname = ".".join(self.class_stack + [node.name])
            symbols.append(
                _ASTSymbolRange(
                    name=node.name,
                    qualified_name=qname,
                    symbol_type=SymbolType.CLASS,
                    start_line=start,
                    end_line=end,
                    signature=f"class {node.name}",
                )
            )
            self.class_stack.append(node.name)
            self.generic_visit(node)
            self.class_stack.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef):
            start = node.lineno
            end = getattr(node, "end_lineno", start + len(node.body))
            stype = SymbolType.METHOD if self.class_stack else SymbolType.FUNCTION
            qname = ".".join(self.class_stack + [node.name])
            symbols.append(
                _ASTSymbolRange(
                    name=node.name,
                    qualified_name=qname,
                    symbol_type=stype,
                    start_line=start,
                    end_line=end,
                    signature=_format_function_signature(node),
                )
            )
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
            start = node.lineno
            end = getattr(node, "end_lineno", start + len(node.body))
            qname = ".".join(self.class_stack + [node.name])
            symbols.append(
                _ASTSymbolRange(
                    name=node.name,
                    qualified_name=qname,
                    symbol_type=SymbolType.ASYNC_FUNCTION,
                    start_line=start,
                    end_line=end,
                    signature=f"async {_format_function_signature(node)}",
                )
            )
            self.generic_visit(node)

    visitor = _Visitor()
    visitor.visit(tree)
    return symbols


def extract_diff_changed_symbols(
    diff_text: str,
    source_files: Dict[str, str],
) -> DiffSymbolExtractionReport:
    """结合代码 Diff 与文件源码，提取发生高危变动的所有 AST 符号"""
    report_id = f"diff_sym_{uuid.uuid4().hex[:10]}"
    file_lines = parse_unified_diff_hunks(diff_text)
    changed_symbols: List[ChangedSymbolItem] = []

    for file_path, modified_lines in file_lines.items():
        if file_path not in source_files:
            continue

        src = source_files[file_path]
        ast_symbols = extract_symbols_from_ast(src)

        for sym in ast_symbols:
            sym_range = set(range(sym.start_line, sym.end_line + 1))
            touched = sorted(list(sym_range & modified_lines))
            if touched:
                # 检查修改行是否命中函数声明签名行 (start_line)
                is_sig_changed = sym.start_line in touched
                change_type = SymbolChangeType.SIGNATURE_CHANGED if is_sig_changed else SymbolChangeType.MODIFIED
                severity = SymbolChangeSeverity.CRITICAL if is_sig_changed else SymbolChangeSeverity.MAJOR

                item = ChangedSymbolItem(
                    symbol_id=f"sym_{uuid.uuid4().hex[:8]}",
                    file_path=file_path,
                    symbol_name=sym.name,
                    qualified_name=sym.qualified_name,
                    symbol_type=sym.symbol_type,
                    change_type=change_type,
                    severity=severity,
                    line_start=sym.start_line,
                    line_end=sym.end_line,
                    touched_lines=touched,
                    signature=sym.signature,
                )
                changed_symbols.append(item)

    return DiffSymbolExtractionReport(
        report_id=report_id,
        total_files_analyzed=len(file_lines),
        changed_symbols_count=len(changed_symbols),
        symbols=changed_symbols,
    )
