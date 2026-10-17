"""双端响应体深度结构 Diff 对比器服务 (T2.1)

在生产流量回放验证中提供深层、结构化的基线与实际响应差异比对能力:
1. HTTP 状态码偏离检测 (STATUS_CODE_MISMATCH);
2. 键丢失 (MISSING_KEY)、新增意外字段 (UNEXPECTED_KEY) 结构比对;
3. 数据类型不兼容 (TYPE_MISMATCH) 与字段值偏离 (VALUE_MISMATCH) 递归检测;
4. 结构化呈现差异报告与严重程度分类 (TrafficResponseDiffReport)。
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class ResponseDiffCategory(str, enum.Enum):
    STATUS_CODE_MISMATCH = "STATUS_CODE_MISMATCH"  # 状态码不匹配 (如 200 vs 500)
    MISSING_KEY = "MISSING_KEY"  # 基线存在但回放丢失的键 (高危)
    UNEXPECTED_KEY = "UNEXPECTED_KEY"  # 回放意外多出的键
    TYPE_MISMATCH = "TYPE_MISMATCH"  # 数据类型不兼容 (如 str vs int, list vs dict)
    VALUE_MISMATCH = "VALUE_MISMATCH"  # 字段取值偏离


class DiffSeverity(str, enum.Enum):
    BLOCKER = "BLOCKER"  # 阻塞性差异 (状态码偏离/核心主键缺失)
    MAJOR = "MAJOR"  # 重大差异 (关键业务键丢失/类型不兼容)
    MINOR = "MINOR"  # 次要差异 (非核心数值差异)
    INFO = "INFO"  # 提示性差异 (新增可选字段)


@dataclass
class ResponseDiffItem:
    diff_id: str
    category: ResponseDiffCategory
    severity: DiffSeverity
    json_path: str
    baseline_value: Any
    replayed_value: Any
    message: str
    is_noise: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["category"] = self.category.value
        d["severity"] = self.severity.value
        return d


@dataclass
class TrafficResponseDiffReport:
    report_id: str
    record_id: str
    baseline_status_code: int
    replayed_status_code: int
    is_identical: bool
    has_critical_breaking: bool
    diff_count: int
    diffs: List[ResponseDiffItem]
    diff_summary: Dict[str, int]
    compared_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "record_id": self.record_id,
            "baseline_status_code": self.baseline_status_code,
            "replayed_status_code": self.replayed_status_code,
            "is_identical": self.is_identical,
            "has_critical_breaking": self.has_critical_breaking,
            "diff_count": self.diff_count,
            "diff_summary": self.diff_summary,
            "diffs": [d.to_dict() for d in self.diffs],
            "compared_at": self.compared_at,
        }


def _compare_recursive(
    base: Any,
    actual: Any,
    current_path: str,
    diffs: List[ResponseDiffItem],
) -> None:
    """递归比对任意嵌套的数据结构"""
    # 1. 检查数据类型是否匹配
    base_type = type(base)
    actual_type = type(actual)

    if base_type != actual_type:
        # NoneType 兼容检查
        if base is None or actual is None:
            did = f"diff_{uuid.uuid4().hex[:8]}"
            diffs.append(
                ResponseDiffItem(
                    diff_id=did,
                    category=ResponseDiffCategory.TYPE_MISMATCH,
                    severity=DiffSeverity.MAJOR,
                    json_path=current_path,
                    baseline_value=base,
                    replayed_value=actual,
                    message=f"字段空值与非空类型不匹配: 基线为 {base_type.__name__}，回放为 {actual_type.__name__}",
                )
            )
            return

        # 浮点与整数兼容性容忍 (如 100 vs 100.0)
        if isinstance(base, (int, float)) and isinstance(actual, (int, float)):
            if float(base) != float(actual):
                did = f"diff_{uuid.uuid4().hex[:8]}"
                diffs.append(
                    ResponseDiffItem(
                        diff_id=did,
                        category=ResponseDiffCategory.VALUE_MISMATCH,
                        severity=DiffSeverity.MINOR,
                        json_path=current_path,
                        baseline_value=base,
                        replayed_value=actual,
                        message=f"数值偏离: 基线={base}, 回放={actual}",
                    )
                )
            return

        did = f"diff_{uuid.uuid4().hex[:8]}"
        diffs.append(
            ResponseDiffItem(
                diff_id=did,
                category=ResponseDiffCategory.TYPE_MISMATCH,
                severity=DiffSeverity.MAJOR,
                json_path=current_path,
                baseline_value=base,
                replayed_value=actual,
                message=f"数据类型不匹配: 基线为 '{base_type.__name__}'，回放为 '{actual_type.__name__}'",
            )
        )
        return

    # 2. 对字典比对
    if isinstance(base, dict):
        base_keys = set(base.keys())
        actual_keys = set(actual.keys())

        # 缺失键 (基线有，回放无)
        for missing_k in base_keys - actual_keys:
            did = f"diff_{uuid.uuid4().hex[:8]}"
            p = f"{current_path}.{missing_k}"
            diffs.append(
                ResponseDiffItem(
                    diff_id=did,
                    category=ResponseDiffCategory.MISSING_KEY,
                    severity=DiffSeverity.MAJOR,
                    json_path=p,
                    baseline_value=base[missing_k],
                    replayed_value=None,
                    message=f"字段缺失: 回放响应中缺少必要键 '{missing_k}'",
                )
            )

        # 意外多出键 (基线无，回放有)
        for extra_k in actual_keys - base_keys:
            did = f"diff_{uuid.uuid4().hex[:8]}"
            p = f"{current_path}.{extra_k}"
            diffs.append(
                ResponseDiffItem(
                    diff_id=did,
                    category=ResponseDiffCategory.UNEXPECTED_KEY,
                    severity=DiffSeverity.INFO,
                    json_path=p,
                    baseline_value=None,
                    replayed_value=actual[extra_k],
                    message=f"新增冗余字段: 回放响应中出现基线不存在的键 '{extra_k}'",
                )
            )

        # 共有键深度递归比对
        for common_k in base_keys & actual_keys:
            p = f"{current_path}.{common_k}"
            _compare_recursive(base[common_k], actual[common_k], p, diffs)

    # 3. 对列表比对
    elif isinstance(base, list):
        len_base = len(base)
        len_act = len(actual)

        if len_base != len_act:
            did = f"diff_{uuid.uuid4().hex[:8]}"
            diffs.append(
                ResponseDiffItem(
                    diff_id=did,
                    category=ResponseDiffCategory.VALUE_MISMATCH,
                    severity=DiffSeverity.MINOR,
                    json_path=f"{current_path}.length",
                    baseline_value=len_base,
                    replayed_value=len_act,
                    message=f"列表元素数量不一致: 基线长度={len_base}, 回放长度={len_act}",
                )
            )

        min_len = min(len_base, len_act)
        for idx in range(min_len):
            p = f"{current_path}[{idx}]"
            _compare_recursive(base[idx], actual[idx], p, diffs)

    # 4. 对标量比对 (str, int, float, bool)
    else:
        if base != actual:
            did = f"diff_{uuid.uuid4().hex[:8]}"
            diffs.append(
                ResponseDiffItem(
                    diff_id=did,
                    category=ResponseDiffCategory.VALUE_MISMATCH,
                    severity=DiffSeverity.MINOR,
                    json_path=current_path,
                    baseline_value=base,
                    replayed_value=actual,
                    message=f"字段取值偏离: 基线={repr(base)}, 回放={repr(actual)}",
                )
            )


def compare_traffic_responses(
    record_id: str,
    baseline_status_code: int,
    baseline_body: Any,
    replayed_status_code: int,
    replayed_body: Any,
    baseline_headers: Optional[Dict[str, str]] = None,
    replayed_headers: Optional[Dict[str, str]] = None,
) -> TrafficResponseDiffReport:
    """深度比对流量基线与回放响应，输出差异透视报告"""
    report_id = f"diff_rep_{uuid.uuid4().hex[:10]}"
    diffs: List[ResponseDiffItem] = []

    # 1. 比对 HTTP 状态码
    if baseline_status_code != replayed_status_code:
        severity = (
            DiffSeverity.BLOCKER if (baseline_status_code // 100 != replayed_status_code // 100) else DiffSeverity.MAJOR
        )
        diffs.append(
            ResponseDiffItem(
                diff_id=f"diff_{uuid.uuid4().hex[:8]}",
                category=ResponseDiffCategory.STATUS_CODE_MISMATCH,
                severity=severity,
                json_path="$.status_code",
                baseline_value=baseline_status_code,
                replayed_value=replayed_status_code,
                message=f"HTTP 状态码发生偏离: 基线为 {baseline_status_code}，回放为 {replayed_status_code}",
            )
        )
    # 2. 比对响应头 (可选)
    if baseline_headers is not None and replayed_headers is not None:
        _compare_recursive(baseline_headers, replayed_headers, "$.headers", diffs)

    # 3. 递归比对响应体
    _compare_recursive(baseline_body, replayed_body, "$", diffs)

    # 3. 统计汇总
    summary: Dict[str, int] = {cat.value: 0 for cat in ResponseDiffCategory}
    has_critical = False
    for d in diffs:
        summary[d.category.value] += 1
        if d.severity in (DiffSeverity.BLOCKER, DiffSeverity.MAJOR):
            has_critical = True

    return TrafficResponseDiffReport(
        report_id=report_id,
        record_id=record_id,
        baseline_status_code=baseline_status_code,
        replayed_status_code=replayed_status_code,
        is_identical=len(diffs) == 0,
        has_critical_breaking=has_critical,
        diff_count=len(diffs),
        diffs=diffs,
        diff_summary=summary,
    )
