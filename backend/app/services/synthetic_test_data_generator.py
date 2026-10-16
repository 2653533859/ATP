"""针对复杂业务边界条件的生产级测试合成数据生成器 (T3.2)。"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class GenerationMode(str, Enum):
    """数据合成模式。"""

    POSITIVE_VALID = "POSITIVE_VALID"  # 正向有效数据
    BOUNDARY_EDGE = "BOUNDARY_EDGE"  # 极限边界值探测数据
    NEGATIVE_ANOMALY = "NEGATIVE_ANOMALY"  # 负向异常违规数据


@dataclass
class FieldConstraintRule:
    """字段业务约束定义。"""

    field_name: str
    data_type: str  # string, integer, float, boolean, email, phone, id_card, enum
    min_value: float | None = None
    max_value: float | None = None
    min_length: int | None = None
    max_length: int | None = None
    enum_values: list[str] = field(default_factory=list)
    nullable: bool = False


@dataclass
class SyntheticDataRow:
    """合成的单行测试数据。"""

    row_index: int
    mode: GenerationMode
    data: dict[str, Any]
    is_expected_valid: bool
    anomaly_field: str | None = None
    anomaly_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "row_index": self.row_index,
            "mode": self.mode.value,
            "data": self.data,
            "is_expected_valid": self.is_expected_valid,
            "anomaly_field": self.anomaly_field,
            "anomaly_reason": self.anomaly_reason,
        }


@dataclass
class SyntheticDatasetBatch:
    """合成测试数据集批次结果。"""

    batch_id: str
    dataset_name: str
    total_rows: int
    positive_count: int
    boundary_count: int
    negative_count: int
    fields_count: int
    rows: list[SyntheticDataRow]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "dataset_name": self.dataset_name,
            "total_rows": self.total_rows,
            "positive_count": self.positive_count,
            "boundary_count": self.boundary_count,
            "negative_count": self.negative_count,
            "fields_count": self.fields_count,
            "rows": [r.to_dict() for r in self.rows],
            "created_at": self.created_at.isoformat(),
        }


# 全局生成数据集批次存储
_SYNTHETIC_DATA_BATCHES: dict[str, SyntheticDatasetBatch] = {}


def clear_synthetic_data_store() -> None:
    """清空合成数据仓库（单测专用）。"""
    _SYNTHETIC_DATA_BATCHES.clear()


def _generate_field_value(rule: FieldConstraintRule, mode: GenerationMode) -> tuple[Any, bool, str | None]:
    """针对单个字段规则与合成模式生成模拟数据。返回 (value, is_valid, anomaly_reason)。"""
    dt = rule.data_type.lower()

    if mode == GenerationMode.POSITIVE_VALID:
        if dt == "integer":
            low = int(rule.min_value if rule.min_value is not None else 1)
            high = int(rule.max_value if rule.max_value is not None else 1000)
            return (random.randint(low, max(low, high)), True, None)
        elif dt == "float":
            low_f = rule.min_value if rule.min_value is not None else 0.01
            high_f = rule.max_value if rule.max_value is not None else 999.99
            return (round(random.uniform(low_f, max(low_f, high_f)), 2), True, None)
        elif dt == "boolean":
            return (True, True, None)
        elif dt == "email":
            return (f"user_{uuid.uuid4().hex[:6]}@example.com", True, None)
        elif dt == "phone":
            return (f"138{random.randint(10000000, 99999999)}", True, None)
        elif dt == "id_card":
            # 模拟标准 18 位身份证
            return ("110101199003072345", True, None)
        elif dt == "enum" and rule.enum_values:
            return (random.choice(rule.enum_values), True, None)
        else:
            # 默认 string
            min_l = rule.min_length if rule.min_length is not None else 4
            max_l = rule.max_length if rule.max_length is not None else 16
            length = random.randint(min_l, max(min_l, max_l))
            return ("val_" + uuid.uuid4().hex[: max(0, length - 4)], True, None)

    elif mode == GenerationMode.BOUNDARY_EDGE:
        if dt == "integer":
            # 返回正好在边界上的极值
            val = int(rule.min_value if rule.min_value is not None else 0)
            return (val, True, None)
        elif dt == "float":
            val_f = rule.min_value if rule.min_value is not None else 0.0
            return (val_f, True, None)
        elif dt == "string":
            min_l = rule.min_length if rule.min_length is not None else 1
            return ("x" * min_l, True, None)
        elif dt == "enum" and rule.enum_values:
            return (rule.enum_values[0], True, None)
        else:
            return (_generate_field_value(rule, GenerationMode.POSITIVE_VALID)[0], True, None)

    else:
        # NEGATIVE_ANOMALY (异常越界数据)
        if dt == "integer":
            # 产生超出 max_value 的违规数值
            high = int(rule.max_value if rule.max_value is not None else 1000)
            return (high + 99999, False, f"数值越界溢出 (预期最大值: {high})")
        elif dt == "email":
            return ("invalid_email_format_no_at", False, "邮箱格式缺失 @ 域名标记")
        elif dt == "phone":
            return ("120000", False, "手机号长度不足 11 位且号段非法")
        elif dt == "enum" and rule.enum_values:
            return ("ILLEGAL_ENUM_VALUE_XYZ", False, "枚举取值超出允许范围")
        elif dt == "string" and rule.max_length is not None:
            return ("A" * (rule.max_length + 50), False, f"字符串长度溢出 (允许最大长度: {rule.max_length})")
        else:
            return (None if not rule.nullable else "OVERFLOW_ERR", False, "非空字段被注入 NULL 或非法异常值")


def generate_synthetic_dataset(
    dataset_name: str,
    rules: list[dict[str, Any]],
    row_count: int = 10,
) -> SyntheticDatasetBatch:
    """根据业务约束规则合成多模态测试数据集。"""
    parsed_rules: list[FieldConstraintRule] = []
    for rule_item in rules:
        parsed_rules.append(
            FieldConstraintRule(
                field_name=rule_item["field_name"],
                data_type=rule_item.get("data_type", "string"),
                min_value=rule_item.get("min_value"),
                max_value=rule_item.get("max_value"),
                min_length=rule_item.get("min_length"),
                max_length=rule_item.get("max_length"),
                enum_values=rule_item.get("enum_values", []),
                nullable=rule_item.get("nullable", False),
            )
        )

    rows: list[SyntheticDataRow] = []
    pos_c = 0
    bound_c = 0
    neg_c = 0

    for idx in range(1, max(1, row_count) + 1):
        # 轮转模式：70% 正向数据，15% 边界极限，15% 负向异常
        if idx % 7 == 0:
            mode = GenerationMode.NEGATIVE_ANOMALY
            neg_c += 1
        elif idx % 4 == 0:
            mode = GenerationMode.BOUNDARY_EDGE
            bound_c += 1
        else:
            mode = GenerationMode.POSITIVE_VALID
            pos_c += 1

        row_data: dict[str, Any] = {}
        row_valid = True
        anomaly_field = None
        anomaly_reason = None

        # 针对每个字段生成取值
        for p_rule in parsed_rules:
            # 如果是异常模式，随机挑选其中一个字段制造异常，其他字段保持合法
            field_mode = mode
            if mode == GenerationMode.NEGATIVE_ANOMALY and anomaly_field is not None:
                field_mode = GenerationMode.POSITIVE_VALID

            val, is_v, reason = _generate_field_value(p_rule, field_mode)
            row_data[p_rule.field_name] = val
            if not is_v and row_valid:
                row_valid = False
                anomaly_field = p_rule.field_name
                anomaly_reason = reason

        rows.append(
            SyntheticDataRow(
                row_index=idx,
                mode=mode,
                data=row_data,
                is_expected_valid=row_valid,
                anomaly_field=anomaly_field,
                anomaly_reason=anomaly_reason,
            )
        )

    now = datetime.now(timezone.utc)
    batch_id = f"synth_{dataset_name[:12]}_{int(now.timestamp())}_{len(rows)}"
    batch = SyntheticDatasetBatch(
        batch_id=batch_id,
        dataset_name=dataset_name,
        total_rows=len(rows),
        positive_count=pos_c,
        boundary_count=bound_c,
        negative_count=neg_c,
        fields_count=len(parsed_rules),
        rows=rows,
        created_at=now,
    )
    _SYNTHETIC_DATA_BATCHES[batch_id] = batch
    return batch


def get_synthetic_dataset_batch(batch_id: str) -> SyntheticDatasetBatch | None:
    """按 ID 查询合成测试数据批次。"""
    return _SYNTHETIC_DATA_BATCHES.get(batch_id)


def list_synthetic_dataset_batches(limit: int = 50) -> list[dict[str, Any]]:
    """获取历史合成数据集批次列表。"""
    batches = list(reversed(list(_SYNTHETIC_DATA_BATCHES.values())))
    return [b.to_dict() for b in batches[:limit]]
