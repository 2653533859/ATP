"""接口契约字段级兼容性差分与 Breaking 破坏性评级引擎服务 (T3.2)。

负责比较现网真实流量逆向推导的 Schema 与设计期/基准期 API 契约，
精准识别破坏性变更 (Breaking Change) 与潜在风险，筑牢微服务接口兼容性防线：
1. 请求体与响应体双向非对称破坏性评级规则 (如：请求体新增必填为 Breaking，响应体删除字段为 Breaking)；
2. 字段类型漂移、枚举值缩减与必填约束变更精确判定；
3. 输出三级判定等级 (BREAKING / WARNING / COMPATIBLE) 与契约兼容性得分 (0~100%)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
from typing import Any
import uuid
from app.services.live_contract_schema_extractor import (
    ExtractedContract,
)

logger = logging.getLogger(__name__)


class BreakingLevel(str, Enum):
    BREAKING = "BREAKING"  # 阻断性破坏变更 (导致客户端请求拒绝或下游解析奔溃)
    WARNING = "WARNING"  # 潜在风险告警 (新增字段或类型容差向下拓宽)
    COMPATIBLE = "COMPATIBLE"  # 完全兼容 (未破坏任何既有调用约束)


class DriftChangeType(str, Enum):
    FIELD_REMOVED = "FIELD_REMOVED"  # 字段被删除
    FIELD_ADDED = "FIELD_ADDED"  # 字段新增
    TYPE_CHANGED = "TYPE_CHANGED"  # 字段数据类型发生漂移
    REQUIRED_ADDED = "REQUIRED_ADDED"  # 可选字段变更为必填约束
    REQUIRED_REMOVED = "REQUIRED_REMOVED"  # 必填约束被移除为可选
    ENUM_RESTRICTED = "ENUM_RESTRICTED"  # 枚举值范围缩减
    ENUM_EXPANDED = "ENUM_EXPANDED"  # 枚举值范围扩充


@dataclass
class DriftItem:
    field_path: str  # 如 $.request.order_id 或 $.response.200.data.amount
    target: str  # REQUEST_BODY | RESPONSE_BODY | QUERY_PARAM | HEADER
    change_type: DriftChangeType
    breaking_level: BreakingLevel
    design_value: Any  # 设计期/基准期期望值
    live_value: Any  # 现网流量实测值
    description: str
    impact_summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_path": self.field_path,
            "target": self.target,
            "change_type": self.change_type.value,
            "breaking_level": self.breaking_level.value,
            "design_value": self.design_value,
            "live_value": self.live_value,
            "description": self.description,
            "impact_summary": self.impact_summary,
        }


@dataclass
class ContractDriftEvaluationReport:
    evaluation_id: str
    endpoint: str
    overall_breaking_level: BreakingLevel
    is_breaking: bool
    compatibility_score_pct: float  # 0.0 ~ 100.0%
    breaking_changes_count: int
    warning_changes_count: int
    compatible_changes_count: int
    drift_items: list[DriftItem]
    verdict_summary: str
    design_contract_id: str | None = None
    live_contract_id: str | None = None
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluation_id": self.evaluation_id,
            "endpoint": self.endpoint,
            "overall_breaking_level": self.overall_breaking_level.value,
            "is_breaking": self.is_breaking,
            "compatibility_score_pct": round(self.compatibility_score_pct, 2),
            "breaking_changes_count": self.breaking_changes_count,
            "warning_changes_count": self.warning_changes_count,
            "compatible_changes_count": self.compatible_changes_count,
            "drift_items": [d.to_dict() for d in self.drift_items],
            "verdict_summary": self.verdict_summary,
            "design_contract_id": self.design_contract_id,
            "live_contract_id": self.live_contract_id,
            "evaluated_at": self.evaluated_at.isoformat(),
        }


# 全局内存报告仓库
_EVALUATION_REPORTS: dict[str, ContractDriftEvaluationReport] = {}


def _normalize_type(t: Any) -> str:
    if isinstance(t, list) and t:
        return f"array[{_normalize_type(t[0])}]"
    return str(t or "string").lower()


def compare_schemas_compatibility(
    design_schema: dict[str, Any],
    live_schema: dict[str, Any],
    is_request: bool = True,
    path_prefix: str = "$",
) -> list[DriftItem]:
    """对比两份 JSON Schema 的字段级兼容性，根据伯斯塔尔健壮性法则执行非对称破坏性评级。"""
    drift_items: list[DriftItem] = []
    target_str = "REQUEST_BODY" if is_request else "RESPONSE_BODY"

    design_props = design_schema.get("properties", {})
    live_props = live_schema.get("properties", {})

    design_req = set(design_schema.get("required", []))
    live_req = set(live_schema.get("required", []))

    all_keys = set(design_props.keys()) | set(live_props.keys())

    for k in sorted(all_keys):
        field_path = f"{path_prefix}.{k}"

        # 1. 字段删除: 设计期有，现网缺失
        if k in design_props and k not in live_props:
            if is_request:
                # 请求体中删除了字段：若设计期是必填，则现网不再要求，通常向下兼容；若是可选，客户端继续传通常也容错
                drift_items.append(
                    DriftItem(
                        field_path=field_path,
                        target=target_str,
                        change_type=DriftChangeType.FIELD_REMOVED,
                        breaking_level=BreakingLevel.WARNING,
                        design_value=design_props[k].get("type"),
                        live_value=None,
                        description=f"请求参数未在现网流量中识别出: [{k}]",
                        impact_summary="现网可能已废弃或下线该请求字段，老版本客户端请求可能被忽略",
                    )
                )
            else:
                # 响应体中删除了字段：绝对破坏性变更！下游依赖该字段直接抛空指针或反序列化失败
                drift_items.append(
                    DriftItem(
                        field_path=field_path,
                        target=target_str,
                        change_type=DriftChangeType.FIELD_REMOVED,
                        breaking_level=BreakingLevel.BREAKING,
                        design_value=design_props[k].get("type"),
                        live_value=None,
                        description=f"响应字段严重缺失: 设计期包含的字段 [{k}] 在现网响应中被删除",
                        impact_summary="下游消费方微服务解析此接口响应时将由于缺少必需字段直接抛错奔溃",
                    )
                )
            continue

        # 2. 字段新增: 现网有，设计期无
        if k not in design_props and k in live_props:
            is_new_required = k in live_req
            if is_request and is_new_required:
                # 请求体新增了必填字段：绝对破坏性变更！老客户端未传该新必填字段，请求直接 400
                drift_items.append(
                    DriftItem(
                        field_path=field_path,
                        target=target_str,
                        change_type=DriftChangeType.REQUIRED_ADDED,
                        breaking_level=BreakingLevel.BREAKING,
                        design_value=None,
                        live_value=live_props[k].get("type"),
                        description=f"请求体新增必填参数: 现网将新字段 [{k}] 设置为了必需传参 (required)",
                        impact_summary="未升级的老版本客户端在未传该字段时将直接被服务端校验拒绝 (400 Bad Request)",
                    )
                )
            elif is_request:
                # 请求体新增了非必填可选字段
                drift_items.append(
                    DriftItem(
                        field_path=field_path,
                        target=target_str,
                        change_type=DriftChangeType.FIELD_ADDED,
                        breaking_level=BreakingLevel.COMPATIBLE,
                        design_value=None,
                        live_value=live_props[k].get("type"),
                        description=f"请求体新增可选参数: [{k}]",
                        impact_summary="新增可选传参，不影响老客户端既有调用",
                    )
                )
            else:
                # 响应体新增了字段：通常向下兼容，但严格契约模式下提醒告警
                drift_items.append(
                    DriftItem(
                        field_path=field_path,
                        target=target_str,
                        change_type=DriftChangeType.FIELD_ADDED,
                        breaking_level=BreakingLevel.WARNING,
                        design_value=None,
                        live_value=live_props[k].get("type"),
                        description=f"响应体新增输出字段: 现网返回了设计期未定义字段 [{k}]",
                        impact_summary="大多数宽松解析客户端可兼容，但若下游存在严格反序列化校验可能抛出非预期属性告警",
                    )
                )
            continue

        # 3. 字段同时存在：比对数据类型漂移
        dp = design_props[k]
        lp = live_props[k]
        d_type = _normalize_type(dp.get("type"))
        l_type = _normalize_type(lp.get("type"))

        if d_type != l_type:
            # 允许 integer 自动兼容 number
            is_number_upgrade = d_type == "integer" and l_type == "number"
            if not is_number_upgrade:
                drift_items.append(
                    DriftItem(
                        field_path=field_path,
                        target=target_str,
                        change_type=DriftChangeType.TYPE_CHANGED,
                        breaking_level=BreakingLevel.BREAKING,
                        design_value=d_type,
                        live_value=l_type,
                        description=f"字段类型发生致命漂移: 由 [{d_type}] 变为 [{l_type}]",
                        impact_summary="强类型反序列化将引发 TypeMismatchException 或序列化强转中断",
                    )
                )

        # 4. 必填性约束变更比对 (仅请求体)
        if is_request:
            was_req = k in design_req
            is_req = k in live_req
            if not was_req and is_req:
                drift_items.append(
                    DriftItem(
                        field_path=field_path,
                        target=target_str,
                        change_type=DriftChangeType.REQUIRED_ADDED,
                        breaking_level=BreakingLevel.BREAKING,
                        design_value="optional",
                        live_value="required",
                        description=f"参数由可选变为必填: 现网对现有字段 [{k}] 增加了强制必填校验",
                        impact_summary="此前未传该字段的历史客户端调用将全部被服务端校验拦截失败",
                    )
                )
            elif was_req and not is_req:
                drift_items.append(
                    DriftItem(
                        field_path=field_path,
                        target=target_str,
                        change_type=DriftChangeType.REQUIRED_REMOVED,
                        breaking_level=BreakingLevel.COMPATIBLE,
                        design_value="required",
                        live_value="optional",
                        description=f"参数必填约束放宽: 字段 [{k}] 由必填变更为可选",
                        impact_summary="属于向后兼容的防御性调整，老客户端调用不受任何影响",
                    )
                )

        # 5. 枚举值范围缩减/扩充比对
        d_enum = set(dp.get("enum", []))
        l_enum = set(lp.get("enum", []))
        if d_enum and l_enum:
            dropped_enums = d_enum - l_enum
            added_enums = l_enum - d_enum
            if dropped_enums:
                drift_items.append(
                    DriftItem(
                        field_path=field_path,
                        target=target_str,
                        change_type=DriftChangeType.ENUM_RESTRICTED,
                        breaking_level=BreakingLevel.BREAKING,
                        design_value=list(d_enum),
                        live_value=list(l_enum),
                        description=f"枚举范围缩减: 现网不再支持枚举值 {list(dropped_enums)}",
                        impact_summary="老客户端若继续发送已移除的枚举状态，将被服务端枚举校验直接抛错拒收",
                    )
                )
            if added_enums:
                drift_items.append(
                    DriftItem(
                        field_path=field_path,
                        target=target_str,
                        change_type=DriftChangeType.ENUM_EXPANDED,
                        breaking_level=BreakingLevel.WARNING if not is_request else BreakingLevel.COMPATIBLE,
                        design_value=list(d_enum),
                        live_value=list(l_enum),
                        description=f"枚举范围扩充: 现网新增了枚举值 {list(added_enums)}",
                        impact_summary="如果下游对该枚举使用严格 switch-case 且未设 default，可能会遇到未知枚举异常",
                    )
                )

        # 6. 嵌套结构递归比对
        if d_type == "object" and l_type == "object":
            sub_diffs = compare_schemas_compatibility(dp, lp, is_request=is_request, path_prefix=field_path)
            drift_items.extend(sub_diffs)

    return drift_items


def evaluate_contract_drift(
    design_contract: dict[str, Any] | ExtractedContract,
    live_contract: dict[str, Any] | ExtractedContract,
    endpoint: str | None = None,
) -> ContractDriftEvaluationReport:
    """端到端对比设计期契约与现网流量逆向提取契约，输出破坏性变更评级报告。"""
    eval_id = f"cde_{uuid.uuid4().hex[:12]}"

    d_dict = design_contract.to_dict() if isinstance(design_contract, ExtractedContract) else design_contract
    l_dict = live_contract.to_dict() if isinstance(live_contract, ExtractedContract) else live_contract

    ep = endpoint or l_dict.get("endpoint") or d_dict.get("endpoint") or "UNKNOWN_ENDPOINT"
    d_req_schema = d_dict.get("request_schema", {})
    l_req_schema = l_dict.get("request_schema", {})

    all_drift_items: list[DriftItem] = []

    # 1. 请求体契约差分比对 (is_request = True)
    req_drifts = compare_schemas_compatibility(d_req_schema, l_req_schema, is_request=True, path_prefix="$.request")
    all_drift_items.extend(req_drifts)

    # 2. 响应体契约差分比对 (针对 200/各状态码, is_request = False)
    d_resps = d_dict.get("response_schemas", {})
    l_resps = l_dict.get("response_schemas", {})
    all_status_codes = set(d_resps.keys()) | set(l_resps.keys()) or {"200"}

    for st in sorted(all_status_codes):
        d_res_schema = d_resps.get(st, {})
        l_res_schema = l_resps.get(st, {})
        if d_res_schema or l_res_schema:
            res_drifts = compare_schemas_compatibility(
                d_res_schema, l_res_schema, is_request=False, path_prefix=f"$.response.{st}"
            )
            all_drift_items.extend(res_drifts)

    # 3. 统计破坏性与兼容性得分
    breaking_count = sum(1 for d in all_drift_items if d.breaking_level == BreakingLevel.BREAKING)
    warning_count = sum(1 for d in all_drift_items if d.breaking_level == BreakingLevel.WARNING)
    compatible_count = sum(1 for d in all_drift_items if d.breaking_level == BreakingLevel.COMPATIBLE)

    is_breaking = breaking_count > 0
    if is_breaking:
        overall_level = BreakingLevel.BREAKING
    elif warning_count > 0:
        overall_level = BreakingLevel.WARNING
    else:
        overall_level = BreakingLevel.COMPATIBLE

    # 契约兼容性得分: 满分 100 分，每个 BREAKING 扣 30 分，每个 WARNING 扣 10 分
    penalty = breaking_count * 30.0 + warning_count * 10.0
    compatibility_score = max(0.0, 100.0 - penalty)

    # 生成裁决总结
    if overall_level == BreakingLevel.COMPATIBLE:
        summary = "接口契约完全兼容！现网流量与设计期规范无破坏性漂移，准予正常发布与合流。"
    elif overall_level == BreakingLevel.BREAKING:
        summary = (
            f"【契约破坏性严重阻断】检出 {breaking_count} 处破坏性变更 (如字段删除/类型漂移/新增必填项)，"
            f"兼容性得分仅为 {compatibility_score:.1f}%，严禁直接上线，必须通知下游服务协同整改！"
        )
    else:
        summary = (
            f"【契约存在兼容性警告】检出 {warning_count} 处非破坏性差异 (如新增可选字段/响应体扩展)，"
            f"兼容性得分为 {compatibility_score:.1f}%，建议通知调用方关注新字段。"
        )

    report = ContractDriftEvaluationReport(
        evaluation_id=eval_id,
        endpoint=ep,
        overall_breaking_level=overall_level,
        is_breaking=is_breaking,
        compatibility_score_pct=compatibility_score,
        breaking_changes_count=breaking_count,
        warning_changes_count=warning_count,
        compatible_changes_count=compatible_count,
        drift_items=all_drift_items,
        verdict_summary=summary,
        design_contract_id=d_dict.get("contract_id"),
        live_contract_id=l_dict.get("contract_id"),
    )

    _EVALUATION_REPORTS[eval_id] = report
    logger.info("契约兼容性评估完成 [%s]: 判定为 %s, 破坏性项: %d", eval_id, overall_level.value, breaking_count)
    return report


def get_drift_evaluation_report(evaluation_id: str) -> ContractDriftEvaluationReport | None:
    """根据 ID 获取契约兼容性评估报告详情。"""
    return _EVALUATION_REPORTS.get(evaluation_id)


def list_drift_evaluation_reports() -> list[ContractDriftEvaluationReport]:
    """查询历史契约漂移兼容性评估报告列表。"""
    reports = list(_EVALUATION_REPORTS.values())
    reports.sort(key=lambda r: r.evaluated_at, reverse=True)
    return reports


def clear_drift_evaluation_reports() -> int:
    """清空评定报告缓存。"""
    count = len(_EVALUATION_REPORTS)
    _EVALUATION_REPORTS.clear()
    return count
