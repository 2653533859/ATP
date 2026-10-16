"""接口响应 Schema 动态漂移自适应修正与智能柔性断言引擎 (D2.2).

支持针对接口测试中常见的非破坏性字段增加、数组乱序、类型兼容等动态响应漂移，
提供多级容差模式（STRICT / COMPATIBLE / LENIENT），自动推导 Schema 自愈修正方案并杜绝假阳性。
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
from typing import Any
import uuid

logger = logging.getLogger(__name__)


class AssertionToleranceMode(str, Enum):
    STRICT = "strict"  # 严格模式：禁止任何冗余字段、类型严格匹配
    COMPATIBLE = "compatible"  # 兼容模式：允许新增额外字段、允许数组排序差异
    LENIENT = "lenient"  # 宽容模式：允许数字类型自动强制转换与兼容


class SchemaDriftType(str, Enum):
    EXTRA_FIELD = "extra_field"
    MISSING_FIELD = "missing_field"
    TYPE_DRIFT = "type_drift"
    NULLABLE_DRIFT = "nullable_drift"


@dataclass
class SchemaDriftDetail:
    field_path: str
    drift_type: SchemaDriftType
    expected: Any
    actual: Any
    is_breaking: bool
    description: str
    suggested_autofix: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_path": self.field_path,
            "drift_type": self.drift_type.value,
            "expected": self.expected,
            "actual": self.actual,
            "is_breaking": self.is_breaking,
            "description": self.description,
            "suggested_autofix": self.suggested_autofix,
        }


@dataclass
class FlexibleAssertionConfig:
    mode: AssertionToleranceMode = AssertionToleranceMode.COMPATIBLE
    ignore_extra_fields: bool = True
    ignore_array_order: bool = True
    allow_numeric_string_coercion: bool = True
    autofix_schema: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "ignore_extra_fields": self.ignore_extra_fields,
            "ignore_array_order": self.ignore_array_order,
            "allow_numeric_string_coercion": self.allow_numeric_string_coercion,
            "autofix_schema": self.autofix_schema,
        }


@dataclass
class FlexibleAssertionResult:
    passed: bool
    tolerance_mode: AssertionToleranceMode
    total_drifts_count: int
    drifts: list[SchemaDriftDetail]
    autofixed_schema: dict[str, Any] | None
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    audit_id: str = field(default_factory=lambda: f"drift_audit_{uuid.uuid4().hex[:12]}")
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_id": self.audit_id,
            "passed": self.passed,
            "tolerance_mode": self.tolerance_mode.value,
            "total_drifts_count": self.total_drifts_count,
            "drifts": [d.to_dict() for d in self.drifts],
            "autofixed_schema": self.autofixed_schema,
            "evaluated_at": self.evaluated_at.isoformat(),
            "summary": self.summary,
        }


# 内存审计台账
_ASSERTION_AUDIT_HISTORY: list[FlexibleAssertionResult] = []


def _infer_json_type(val: Any) -> str:
    """推断 Python 值的 JSON Schema 类型。"""
    if val is None:
        return "null"
    if isinstance(val, bool):
        return "boolean"
    if isinstance(val, int):
        return "integer"
    if isinstance(val, float):
        return "number"
    if isinstance(val, str):
        return "string"
    if isinstance(val, list):
        return "array"
    if isinstance(val, dict):
        return "object"
    return "string"


def _is_coercible_numeric(expected_type: str, val: Any) -> bool:
    """检查是否为可安全强转的数字。"""
    if expected_type in {"integer", "number"} and isinstance(val, str):
        try:
            float(val)
            return True
        except ValueError:
            return False
    if expected_type == "number" and isinstance(val, int):
        return True
    return False


def _check_schema_recursive(
    schema: dict[str, Any],
    payload: Any,
    current_path: str,
    config: FlexibleAssertionConfig,
    drifts: list[SchemaDriftDetail],
    autofix_target: dict[str, Any] | None,
) -> bool:
    """递归对比 JSON Schema 与实际 Payload。"""
    is_valid = True
    expected_type = schema.get("type", "object")

    # 1. 类型校验
    actual_type = _infer_json_type(payload)
    if expected_type != actual_type:
        # 宽容类型转换检查
        if config.allow_numeric_string_coercion and _is_coercible_numeric(expected_type, payload):
            drifts.append(
                SchemaDriftDetail(
                    field_path=current_path,
                    drift_type=SchemaDriftType.TYPE_DRIFT,
                    expected=expected_type,
                    actual=actual_type,
                    is_breaking=False,
                    description=f"字段 [{current_path}] 存在类型漂移 ({expected_type} -> {actual_type})，宽容模式已自动兼容强转",
                )
            )
        else:
            drifts.append(
                SchemaDriftDetail(
                    field_path=current_path,
                    drift_type=SchemaDriftType.TYPE_DRIFT,
                    expected=expected_type,
                    actual=actual_type,
                    is_breaking=True,
                    description=f"字段 [{current_path}] 发生破坏性类型不匹配: 预期 {expected_type}，实际为 {actual_type}",
                )
            )
            return False

    # 2. 如果是 Object 结构
    if expected_type == "object" and isinstance(payload, dict):
        properties: dict[str, Any] = schema.get("properties", {})
        required_fields: list[str] = schema.get("required", [])

        # 检查缺失字段 (Missing fields)
        for req_field in required_fields:
            if req_field not in payload:
                field_p = f"{current_path}.{req_field}" if current_path else req_field
                drifts.append(
                    SchemaDriftDetail(
                        field_path=field_p,
                        drift_type=SchemaDriftType.MISSING_FIELD,
                        expected=properties.get(req_field, {}).get("type", "any"),
                        actual=None,
                        is_breaking=True,
                        description=f"必填字段 [{field_p}] 在接口响应中缺失！",
                    )
                )
                is_valid = False

        # 检查多余冗余字段 (Extra fields)
        for act_key, act_val in payload.items():
            field_p = f"{current_path}.{act_key}" if current_path else act_key
            if act_key not in properties:
                inferred_sub_type = _infer_json_type(act_val)
                sub_fix: dict[str, Any] = {"type": inferred_sub_type}
                if inferred_sub_type == "object" and isinstance(act_val, dict):
                    sub_fix["properties"] = {k: {"type": _infer_json_type(v)} for k, v in act_val.items()}

                if config.ignore_extra_fields:
                    drifts.append(
                        SchemaDriftDetail(
                            field_path=field_p,
                            drift_type=SchemaDriftType.EXTRA_FIELD,
                            expected=None,
                            actual=inferred_sub_type,
                            is_breaking=False,
                            description=f"检测到未在契约中声明的冗余字段 [{field_p}] (类型: {inferred_sub_type})，兼容模式已放行",
                            suggested_autofix=sub_fix,
                        )
                    )
                    # 动态扩充 autofix
                    if autofix_target is not None and "properties" in autofix_target:
                        autofix_target["properties"][act_key] = sub_fix
                else:
                    drifts.append(
                        SchemaDriftDetail(
                            field_path=field_p,
                            drift_type=SchemaDriftType.EXTRA_FIELD,
                            expected=None,
                            actual=inferred_sub_type,
                            is_breaking=True,
                            description=f"严格模式下禁止多余未声明字段 [{field_p}]",
                        )
                    )
                    is_valid = False
            else:
                # 递归校验已知属性
                sub_schema = properties[act_key]
                sub_target = (
                    autofix_target["properties"].get(act_key)
                    if autofix_target and "properties" in autofix_target
                    else None
                )
                valid_child = _check_schema_recursive(sub_schema, act_val, field_p, config, drifts, sub_target)
                if not valid_child:
                    is_valid = False

    # 3. 如果是 Array 结构
    elif expected_type == "array" and isinstance(payload, list):
        items_schema = schema.get("items")
        if items_schema and payload:
            for idx, item in enumerate(payload[:5]):  # 采样前 5 个元素验证
                elem_p = f"{current_path}[{idx}]"
                valid_child = _check_schema_recursive(items_schema, item, elem_p, config, drifts, None)
                if not valid_child:
                    is_valid = False

    return is_valid


def assert_flexible_schema(
    expected_schema: dict[str, Any],
    actual_payload: Any,
    config: FlexibleAssertionConfig | None = None,
) -> FlexibleAssertionResult:
    """核心入口：执行自适应柔性契约断言，捕获漂移并生成修复版 Schema。"""
    cfg = config or FlexibleAssertionConfig()
    drifts: list[SchemaDriftDetail] = []
    autofixed_target: dict[str, Any] | None = copy.deepcopy(expected_schema) if cfg.autofix_schema else None

    # 如果配置模式覆盖
    if cfg.mode == AssertionToleranceMode.STRICT:
        cfg.ignore_extra_fields = False
        cfg.allow_numeric_string_coercion = False
    elif cfg.mode == AssertionToleranceMode.LENIENT:
        cfg.ignore_extra_fields = True
        cfg.allow_numeric_string_coercion = True

    is_valid = _check_schema_recursive(
        schema=expected_schema,
        payload=actual_payload,
        current_path="",
        config=cfg,
        drifts=drifts,
        autofix_target=autofixed_target,
    )

    breaking_count = sum(1 for d in drifts if d.is_breaking)
    passed = is_valid and (breaking_count == 0)

    summary = (
        f"柔性断言 {'PASS' if passed else 'FAIL'} (模式: {cfg.mode.value})，"
        f"共检测到 {len(drifts)} 处 Schema 响应漂移 (其中破坏性 {breaking_count} 处)。"
    )

    result = FlexibleAssertionResult(
        passed=passed,
        tolerance_mode=cfg.mode,
        total_drifts_count=len(drifts),
        drifts=drifts,
        autofixed_schema=autofixed_target if (passed and len(drifts) > 0) else None,
        summary=summary,
    )

    _ASSERTION_AUDIT_HISTORY.append(result)
    logger.info(
        "Executed flexible schema assertion passed=%s mode=%s drifts=%s breaking=%s",
        passed,
        cfg.mode.value,
        len(drifts),
        breaking_count,
    )
    return result


def list_assertion_audits() -> list[FlexibleAssertionResult]:
    """查询历史柔性断言评估记录。"""
    return list(_ASSERTION_AUDIT_HISTORY)


def reset_assertion_registry() -> None:
    """仅供单元测试清理状态使用。"""
    _ASSERTION_AUDIT_HISTORY.clear()
