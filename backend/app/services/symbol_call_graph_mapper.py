"""接口-函数-用例三维调用链拓扑映射引擎服务 (T1.2)

建立底层代码符号 (Symbols) ➔ 业务服务接口端点 (Endpoints) ➔ 自动化测试用例 (Test Cases) 的三维调用拓扑图谱:
1. 符号-接口-用例三层网状图谱数据模型 (SymbolCallGraph);
2. 正向拓扑扩散影响面推导演算 (trace_impacted_cases: symbol -> endpoint -> case);
3. 反向追溯可达性查询 (trace_case_symbol_coverage: case -> endpoint -> symbols);
4. 增量精准测试集筛选与回归耗时节省比率估算 (PrecisionImpactAnalysisResult)。
"""

from __future__ import annotations

import collections
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Set, Tuple


@dataclass
class ImpactedCaseItem:
    case_id: str
    case_name: str
    impacted_by_endpoints: List[str]
    impacted_by_symbols: List[str]
    call_lineage: List[str]  # 例如: "OrderService.checkout -> POST /api/v1/orders/checkout -> case_001"
    execution_cost_seconds: float = 12.0
    priority: str = "P0"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PrecisionImpactAnalysisResult:
    analysis_id: str
    changed_symbols: List[str]
    impacted_endpoints_count: int
    impacted_endpoints: List[str]
    impacted_cases_count: int
    impacted_cases: List[ImpactedCaseItem]
    total_cases_in_suite: int
    regression_reduction_ratio: float  # 精准裁剪率 (例如 92.5%)
    estimated_time_saved_seconds: float
    analyzed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "analysis_id": self.analysis_id,
            "changed_symbols": self.changed_symbols,
            "impacted_endpoints_count": self.impacted_endpoints_count,
            "impacted_endpoints": self.impacted_endpoints,
            "impacted_cases_count": self.impacted_cases_count,
            "impacted_cases": [c.to_dict() for c in self.impacted_cases],
            "total_cases_in_suite": self.total_cases_in_suite,
            "regression_reduction_ratio": round(self.regression_reduction_ratio, 4),
            "estimated_time_saved_seconds": round(self.estimated_time_saved_seconds, 1),
            "analyzed_at": self.analyzed_at,
        }


class SymbolCallGraph:
    """三维调用拓扑图谱核心类"""

    def __init__(self):
        # symbol -> set of endpoints
        self.symbol_to_endpoints: Dict[str, Set[str]] = collections.defaultdict(set)
        # endpoint -> set of symbols
        self.endpoint_to_symbols: Dict[str, Set[str]] = collections.defaultdict(set)

        # endpoint -> set of case_ids
        self.endpoint_to_cases: Dict[str, Set[str]] = collections.defaultdict(set)
        # case_id -> set of endpoints
        self.case_to_endpoints: Dict[str, Set[str]] = collections.defaultdict(set)

        # case metadata: case_id -> {name, cost, priority}
        self.case_metadata: Dict[str, Dict[str, Any]] = {}

        self._load_seed_lineage()

    def _load_seed_lineage(self) -> None:
        """加载系统内置的典型服务血缘依赖种子数据"""
        # 1. 电商订单域
        self.register_symbol_endpoint("OrderService.checkout", "POST /api/v1/orders/checkout")
        self.register_symbol_endpoint("OrderService.create_order", "POST /api/v1/orders/checkout")
        self.register_symbol_endpoint("discount.calculate_discount", "POST /api/v1/orders/checkout")
        self.register_symbol_endpoint("discount.calculate_discount", "GET /api/v1/discounts/preview")

        self.register_endpoint_case(
            "POST /api/v1/orders/checkout", "case_order_checkout_flow", "收银台正常加购下单主流程", 15.0, "P0"
        )
        self.register_endpoint_case(
            "POST /api/v1/orders/checkout", "case_order_zero_discount", "无优惠券零折扣兜底用例", 8.0, "P1"
        )
        self.register_endpoint_case(
            "GET /api/v1/discounts/preview", "case_discount_preview_vip", "VIP优惠券抵扣预览测试", 6.0, "P1"
        )

        # 2. 用户与认证域
        self.register_symbol_endpoint("UserService.authenticate", "POST /api/v1/users/login")
        self.register_symbol_endpoint("UserService.get_profile", "GET /api/v1/users/profile")
        self.register_symbol_endpoint("token_service.generate_jwt", "POST /api/v1/users/login")

        self.register_endpoint_case(
            "POST /api/v1/users/login", "case_user_login_success", "用户手机验证码密码登录", 5.0, "P0"
        )
        self.register_endpoint_case(
            "POST /api/v1/users/login", "case_user_login_invalid_pwd", "密码连续错误锁定用例", 7.0, "P1"
        )
        self.register_endpoint_case(
            "GET /api/v1/users/profile", "case_user_profile_query", "用户详情与权益查询用例", 4.0, "P2"
        )

    def register_symbol_endpoint(self, symbol_qname: str, endpoint: str) -> None:
        """注册代码符号与服务接口的调用映射"""
        self.symbol_to_endpoints[symbol_qname].add(endpoint)
        self.endpoint_to_symbols[endpoint].add(symbol_qname)

    def register_endpoint_case(
        self,
        endpoint: str,
        case_id: str,
        case_name: str,
        cost_seconds: float = 10.0,
        priority: str = "P1",
    ) -> None:
        """注册接口端点与自动化测试用例的覆盖映射"""
        self.endpoint_to_cases[endpoint].add(case_id)
        self.case_to_endpoints[case_id].add(endpoint)
        self.case_metadata[case_id] = {
            "name": case_name,
            "cost_seconds": cost_seconds,
            "priority": priority,
        }

    def trace_impacted_cases(
        self,
        changed_symbols: List[str],
        total_suite_size: int = 50,
    ) -> PrecisionImpactAnalysisResult:
        """根据变更高危符号列表，正向拓扑扩散推导受影响的用例集"""
        analysis_id = f"prec_{uuid.uuid4().hex[:10]}"

        impacted_endpoints: Set[str] = set()
        symbol_impact_map: Dict[str, Set[str]] = collections.defaultdict(set)

        for sym in changed_symbols:
            # 模糊匹配全限定名 (如 OrderService.checkout 命中 checkout)
            for s_key, eps in self.symbol_to_endpoints.items():
                if sym == s_key or sym in s_key or s_key.endswith(f".{sym}"):
                    for ep in eps:
                        impacted_endpoints.add(ep)
                        symbol_impact_map[ep].add(s_key)

        # 由受影响接口端点扩散到测试用例
        case_to_sources: Dict[str, Tuple[Set[str], Set[str]]] = collections.defaultdict(lambda: (set(), set()))

        for ep in impacted_endpoints:
            cases = self.endpoint_to_cases.get(ep, set())
            symbols = symbol_impact_map.get(ep, set())
            for cid in cases:
                case_to_sources[cid][0].add(ep)
                case_to_sources[cid][1].update(symbols)

        impacted_case_items: List[ImpactedCaseItem] = []
        total_exec_time = 0.0

        for cid, (eps, syms) in case_to_sources.items():
            meta = self.case_metadata.get(cid, {"name": cid, "cost_seconds": 10.0, "priority": "P1"})
            cost = meta["cost_seconds"]
            total_exec_time += cost

            lineage = [f"{s} ➔ {ep} ➔ {cid}" for s in sorted(syms) for ep in sorted(eps)]

            impacted_case_items.append(
                ImpactedCaseItem(
                    case_id=cid,
                    case_name=meta["name"],
                    impacted_by_endpoints=sorted(list(eps)),
                    impacted_by_symbols=sorted(list(syms)),
                    call_lineage=lineage,
                    execution_cost_seconds=cost,
                    priority=meta["priority"],
                )
            )

        # 排序：优先执行 P0，再按耗时排序
        impacted_case_items.sort(key=lambda x: (x.priority, -x.execution_cost_seconds))

        suite_size = max(total_suite_size, len(impacted_case_items))
        reduction_ratio = (suite_size - len(impacted_case_items)) / float(suite_size) if suite_size > 0 else 0.0
        # 估算节省时间 (假设全量用例每条平均 10s)
        time_saved = max(0.0, (suite_size - len(impacted_case_items)) * 10.0)

        return PrecisionImpactAnalysisResult(
            analysis_id=analysis_id,
            changed_symbols=changed_symbols,
            impacted_endpoints_count=len(impacted_endpoints),
            impacted_endpoints=sorted(list(impacted_endpoints)),
            impacted_cases_count=len(impacted_case_items),
            impacted_cases=impacted_case_items,
            total_cases_in_suite=suite_size,
            regression_reduction_ratio=reduction_ratio,
            estimated_time_saved_seconds=time_saved,
        )

    def trace_case_symbol_coverage(self, case_id: str) -> Dict[str, Any]:
        """反向追溯单个测试用例底层覆盖的所有接口与代码符号"""
        endpoints = self.case_to_endpoints.get(case_id, set())
        symbols: Set[str] = set()
        for ep in endpoints:
            symbols.update(self.endpoint_to_symbols.get(ep, set()))

        return {
            "case_id": case_id,
            "case_name": self.case_metadata.get(case_id, {}).get("name", case_id),
            "covered_endpoints": sorted(list(endpoints)),
            "covered_symbols": sorted(list(symbols)),
        }


# 全局单例拓扑映射图谱
_GLOBAL_CALL_GRAPH = SymbolCallGraph()


def get_global_call_graph() -> SymbolCallGraph:
    return _GLOBAL_CALL_GRAPH
