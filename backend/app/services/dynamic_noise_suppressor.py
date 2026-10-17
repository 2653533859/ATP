"""动态字段动态噪声自适应抑制器服务 (T2.2)

在生产流量回放比对中自动识别与过滤时间戳、分布式追踪 ID、UUID 等动态噪声字段:
1. 启发式时间戳、TraceID、UUID、随机 Nonce 正则与键名特征识别 (Heuristic Noise Detector);
2. 用户自定义 JSONPath Glob 与正则表达式平滑过滤规则 (NoiseSuppressionRule);
3. 对比报告自适应降噪处理，将伪差异标记为 is_noise=True 并从核心破坏性差异中剥离 (suppress_traffic_diff_noise);
4. 完整的有效真实差异与抑制噪声分流统计 (SuppressedDiffReport)。
"""

from __future__ import annotations

import enum
import fnmatch
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from app.services.traffic_response_diff_comparator import (
    DiffSeverity,
    ResponseDiffCategory,
    ResponseDiffItem,
    TrafficResponseDiffReport,
)


class NoiseType(str, enum.Enum):
    TIMESTAMP = "TIMESTAMP"  # 时间戳与日期时间
    TRACE_ID = "TRACE_ID"  # 分布式追踪 ID (trace_id, span_id, request_id)
    UUID_RANDOM = "UUID_RANDOM"  # 随机 UUID / Nonce
    LATENCY_DURATION = "LATENCY_DURATION"  # 耗时统计微差异
    CUSTOM_RULE = "CUSTOM_RULE"  # 自定义规则匹配


# 噪声键名关键词 (小写子串匹配)
_NOISE_KEY_KEYWORDS: Dict[NoiseType, List[str]] = {
    NoiseType.TIMESTAMP: [
        "timestamp",
        "created_at",
        "updated_at",
        "createtime",
        "updatetime",
        "request_time",
        "response_time",
        "expire_at",
    ],
    NoiseType.TRACE_ID: [
        "trace_id",
        "traceid",
        "request_id",
        "requestid",
        "span_id",
        "spanid",
        "x_request_id",
        "b3_traceid",
    ],
    NoiseType.UUID_RANDOM: [
        "uuid",
        "nonce",
        "random_str",
        "session_token",
    ],
    NoiseType.LATENCY_DURATION: [
        "cost_ms",
        "elapsed",
        "process_time",
        "duration_ms",
    ],
}

# 噪声取值正则模式
_REGEX_TIMESTAMP_NUM = re.compile(r"^\d{10}(?:\d{3})?$")  # 10 位秒级或 13 位毫秒级时间戳
_REGEX_ISO_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?$")
_REGEX_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_REGEX_HEX_TRACE = re.compile(r"^[0-9a-fA-F]{16,32}$")


@dataclass
class NoiseSuppressionRule:
    rule_id: str
    name: str
    noise_type: NoiseType
    path_pattern: Optional[str] = None  # 如 $.timestamp 或 *.trace_id
    regex_pattern: Optional[str] = None
    enabled: bool = True
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["noise_type"] = self.noise_type.value
        return d


@dataclass
class SuppressedDiffReport:
    report_id: str
    record_id: str
    original_diff_count: int
    suppressed_noise_count: int
    effective_diff_count: int
    has_effective_breaking: bool
    effective_diffs: List[ResponseDiffItem]
    noise_diffs: List[ResponseDiffItem]
    applied_rule_ids: List[str]
    processed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "record_id": self.record_id,
            "original_diff_count": self.original_diff_count,
            "suppressed_noise_count": self.suppressed_noise_count,
            "effective_diff_count": self.effective_diff_count,
            "has_effective_breaking": self.has_effective_breaking,
            "effective_diffs": [d.to_dict() for d in self.effective_diffs],
            "noise_diffs": [d.to_dict() for d in self.noise_diffs],
            "applied_rule_ids": self.applied_rule_ids,
            "processed_at": self.processed_at,
        }


def is_heuristic_noise(json_path: str, base_val: Any, actual_val: Any) -> Optional[NoiseType]:
    """通过键名与取值正则启发式推导是否属于动态噪声"""
    leaf_key = json_path.split(".")[-1].split("[")[0].lower()

    # 1. 检查键名关键词
    for ntype, keywords in _NOISE_KEY_KEYWORDS.items():
        if any(kw == leaf_key or kw in leaf_key for kw in keywords):
            return ntype

    # 2. 检查取值正则 (若基线与回放值均为同构动态格式)
    if isinstance(base_val, str) and isinstance(actual_val, str):
        if _REGEX_ISO_DATETIME.match(base_val) and _REGEX_ISO_DATETIME.match(actual_val):
            return NoiseType.TIMESTAMP
        if _REGEX_UUID.match(base_val) and _REGEX_UUID.match(actual_val):
            return NoiseType.UUID_RANDOM
        if _REGEX_HEX_TRACE.match(base_val) and _REGEX_HEX_TRACE.match(actual_val):
            return NoiseType.TRACE_ID

    elif isinstance(base_val, (int, float)) and isinstance(actual_val, (int, float)):
        # 纯数字时间戳
        if _REGEX_TIMESTAMP_NUM.match(str(int(base_val))) and _REGEX_TIMESTAMP_NUM.match(str(int(actual_val))):
            return NoiseType.TIMESTAMP

    return None


def match_custom_rule(
    diff: ResponseDiffItem,
    rule: NoiseSuppressionRule,
) -> bool:
    """检查差异项是否命中用户自定义规则"""
    if not rule.enabled:
        return False

    # 1. 检查 JSONPath 匹配
    if rule.path_pattern:
        if fnmatch.fnmatch(diff.json_path, rule.path_pattern) or fnmatch.fnmatch(
            diff.json_path.lstrip("$."), rule.path_pattern
        ):
            return True

    # 2. 检查正则表达式匹配取值
    if rule.regex_pattern:
        pattern = re.compile(rule.regex_pattern)
        base_match = pattern.search(str(diff.baseline_value))
        act_match = pattern.search(str(diff.replayed_value))
        if base_match or act_match:
            return True

    return False


def suppress_traffic_diff_noise(
    diff_report: TrafficResponseDiffReport,
    custom_rules: Optional[List[NoiseSuppressionRule]] = None,
    enable_heuristics: bool = True,
) -> SuppressedDiffReport:
    """对比对报告进行自适应降噪，剥离并沉淀动态伪差异"""
    report_id = f"sup_{uuid.uuid4().hex[:10]}"
    rules = custom_rules or []

    effective_diffs: List[ResponseDiffItem] = []
    noise_diffs: List[ResponseDiffItem] = []
    applied_rule_ids: Set[str] = set()

    for diff in diff_report.diffs:
        # 状态码不匹配绝对不能作为噪声抑制
        if diff.category == ResponseDiffCategory.STATUS_CODE_MISMATCH:
            effective_diffs.append(diff)
            continue

        is_suppressed = False

        # 1. 优先匹配自定义规则
        for r in rules:
            if match_custom_rule(diff, r):
                is_suppressed = True
                applied_rule_ids.add(r.rule_id)
                diff.is_noise = True
                diff.message = f"[自定义规则抑制: {r.name}] {diff.message}"
                noise_diffs.append(diff)
                break

        if is_suppressed:
            continue

        # 2. 启发式智能降噪
        if enable_heuristics:
            ntype = is_heuristic_noise(diff.json_path, diff.baseline_value, diff.replayed_value)
            if ntype:
                diff.is_noise = True
                diff.message = f"[启发式降噪: {ntype.value}] {diff.message}"
                noise_diffs.append(diff)
                continue

        # 未命中任何降噪策略，判定为真实业务偏离
        effective_diffs.append(diff)

    has_breaking = any(d.severity in (DiffSeverity.BLOCKER, DiffSeverity.MAJOR) for d in effective_diffs)

    return SuppressedDiffReport(
        report_id=report_id,
        record_id=diff_report.record_id,
        original_diff_count=len(diff_report.diffs),
        suppressed_noise_count=len(noise_diffs),
        effective_diff_count=len(effective_diffs),
        has_effective_breaking=has_breaking,
        effective_diffs=effective_diffs,
        noise_diffs=noise_diffs,
        applied_rule_ids=list(applied_rule_ids),
    )
