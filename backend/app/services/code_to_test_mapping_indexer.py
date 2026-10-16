"""代码函数/端点与自动化测试用例双向依赖映射索引引擎 (S1.2).

建立源码符号（文件、类、函数、FastAPI 路由端点）与平台测试用例（API/Web/移动端）之间的
双向血缘倒排索引，支持在代码发生变更时快速反查全部受波及的测试用例。
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TestCaseRef:
    case_id: int
    case_name: str
    case_type: str = "api"  # api | web | android | ios
    project_id: int | None = None
    priority: str = "P1"  # P0 | P1 | P2 | P3
    target_endpoints: list[str] = field(default_factory=list)  # ["POST /api/v1/orders"]
    target_symbols: list[str] = field(default_factory=list)  # ["app/api/orders.py:calculate_discount"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "case_name": self.case_name,
            "case_type": self.case_type,
            "project_id": self.project_id,
            "priority": self.priority,
            "target_endpoints": self.target_endpoints,
            "target_symbols": self.target_symbols,
        }


class CodeToTestMappingIndexer:
    """双向倒排索引引擎：Code Symbol <-> Test Case."""

    def __init__(self) -> None:
        # symbol_id (如 "app/api/orders.py:OrderService.checkout") -> list[TestCaseRef]
        self._symbol_to_cases: dict[str, dict[int, TestCaseRef]] = {}
        # route_key (如 "POST /api/v1/orders/create") -> list[TestCaseRef]
        self._route_to_cases: dict[str, dict[int, TestCaseRef]] = {}
        # file_path (如 "app/api/orders.py") -> list[TestCaseRef]
        self._file_to_cases: dict[str, dict[int, TestCaseRef]] = {}
        # case_id -> TestCaseRef
        self._cases: dict[int, TestCaseRef] = {}

    def _normalize_route_key(self, method: str, path: str) -> str:
        """归一化路由标识: METHOD /path (消除末尾斜线与大小写差异)."""
        clean_method = method.strip().upper()
        clean_path = "/" + path.strip().strip("/")
        return f"{clean_method} {clean_path}"

    def register_binding(
        self,
        case: TestCaseRef,
        bound_symbols: list[str] | None = None,
        bound_routes: list[tuple[str, str]] | None = None,
    ) -> TestCaseRef:
        """注册测试用例与代码符号、API 路由的双向依赖绑定。"""
        self._cases[case.case_id] = case

        # 1. 绑定代码符号
        symbols = bound_symbols or []
        for sym_id in symbols:
            if sym_id not in self._symbol_to_cases:
                self._symbol_to_cases[sym_id] = {}
            self._symbol_to_cases[sym_id][case.case_id] = case

            # 提取文件路径建立文件级倒排索引
            if ":" in sym_id:
                file_path = sym_id.split(":", 1)[0]
                if file_path not in self._file_to_cases:
                    self._file_to_cases[file_path] = {}
                self._file_to_cases[file_path][case.case_id] = case

            if sym_id not in case.target_symbols:
                case.target_symbols.append(sym_id)

        # 2. 绑定 API 路由
        routes = bound_routes or []
        for method, path in routes:
            route_key = self._normalize_route_key(method, path)
            if route_key not in self._route_to_cases:
                self._route_to_cases[route_key] = {}
            self._route_to_cases[route_key][case.case_id] = case

            if route_key not in case.target_endpoints:
                case.target_endpoints.append(route_key)

        logger.debug(
            "Registered code-to-test binding for case_id=%d symbols=%d routes=%d",
            case.case_id,
            len(symbols),
            len(routes),
        )
        return case

    def auto_index_from_steps(
        self,
        case_id: int,
        case_name: str,
        case_type: str = "api",
        steps: list[dict[str, Any]] | None = None,
        project_id: int | None = None,
        priority: str = "P1",
    ) -> TestCaseRef:
        """从测试用例步骤中自动解析请求的 HTTP 方法与 URL，自动建立路由级映射。"""
        case = TestCaseRef(
            case_id=case_id,
            case_name=case_name,
            case_type=case_type,
            project_id=project_id,
            priority=priority,
        )

        routes: list[tuple[str, str]] = []
        for step in steps or []:
            method = step.get("method") or step.get("http_method")
            url = step.get("url") or step.get("path") or step.get("endpoint")
            if method and url:
                # 提取纯路径部分（去除 http://host:port 与 query 传参）
                clean_path = re.sub(r"^https?://[^/]+", "", str(url))
                clean_path = clean_path.split("?")[0]
                routes.append((str(method), clean_path))

        return self.register_binding(case, bound_routes=routes)

    def query_affected_cases(
        self,
        symbols: list[str] | None = None,
        routes: list[tuple[str, str] | str] | None = None,
        file_paths: list[str] | None = None,
        project_id: int | None = None,
    ) -> list[TestCaseRef]:
        """根据变更的符号、路由或文件，逆向反查全部波及的测试用例（去重并按优先级排序）。"""
        matched_cases: dict[int, TestCaseRef] = {}

        # 1. 匹配符号
        for sym_id in symbols or []:
            if sym_id in self._symbol_to_cases:
                for cid, case in self._symbol_to_cases[sym_id].items():
                    matched_cases[cid] = case

        # 2. 匹配路由
        for r in routes or []:
            if isinstance(r, tuple):
                route_key = self._normalize_route_key(r[0], r[1])
            else:
                parts = r.strip().split(" ", 1)
                route_key = self._normalize_route_key(parts[0], parts[1]) if len(parts) == 2 else r.strip()

            if route_key in self._route_to_cases:
                for cid, case in self._route_to_cases[route_key].items():
                    matched_cases[cid] = case

        # 3. 匹配文件级泛化兜底
        for fpath in file_paths or []:
            if fpath in self._file_to_cases:
                for cid, case in self._file_to_cases[fpath].items():
                    matched_cases[cid] = case

        # 项目边界过滤
        results = list(matched_cases.values())
        if project_id is not None:
            results = [c for c in results if c.project_id is None or c.project_id == project_id]

        # 按优先级升序排序 (P0 > P1 > P2 > P3)
        priority_weights = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
        results.sort(key=lambda c: (priority_weights.get(c.priority, 9), c.case_id))
        return results

    def get_stats(self) -> dict[str, Any]:
        """获取映射图谱总体统计与覆盖指标。"""
        return {
            "total_indexed_cases": len(self._cases),
            "total_indexed_symbols": len(self._symbol_to_cases),
            "total_indexed_routes": len(self._route_to_cases),
            "total_indexed_files": len(self._file_to_cases),
        }

    def clear(self) -> None:
        """单元测试状态重置。"""
        self._symbol_to_cases.clear()
        self._route_to_cases.clear()
        self._file_to_cases.clear()
        self._cases.clear()


# 全局单例
_GLOBAL_INDEXER = CodeToTestMappingIndexer()


def get_mapping_indexer() -> CodeToTestMappingIndexer:
    """获取代码-测试映射索引器实例。"""
    return _GLOBAL_INDEXER
