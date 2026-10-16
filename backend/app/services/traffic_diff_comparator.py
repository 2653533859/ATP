"""响应体动态字段智能过滤与字段级精确差分比对器服务 (T2.2)。

为生产流量镜像与影子回放提供高保真响应比对能力：
1. 自动识别并滤除动态时间戳、UUID、trace_id、随机 Token 等噪声字段；
2. 执行深度嵌套 JSON 字段级差分 (ADDED, DELETED, MODIFIED, TYPE_CHANGED)；
3. 量化响应相似度得分 (Similarity Score 0~100%) 与差异严重度评级；
4. 杜绝因动态时间与流水号造成的虚假误报，精准揭示业务重构逻辑漂移。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
import logging
import re
from typing import Any
import uuid

logger = logging.getLogger(__name__)


class DiffType(str, Enum):
    ADDED = "ADDED"  # 回放响应中新增了字段
    DELETED = "DELETED"  # 回放响应中缺失了基线字段 (通常为严重故障)
    MODIFIED = "MODIFIED"  # 核心字段值发生了变更
    TYPE_CHANGED = "TYPE_CHANGED"  # 字段类型发生漂移 (如 int -> str)


class DiffSeverity(str, Enum):
    CRITICAL = "CRITICAL"  # 阻断级差异: 字段删除/核心业务值篡改/类型漂移
    WARNING = "WARNING"  # 警告级差异: 次要值不一致或新增字段
    INFO = "INFO"  # 提示级轻微差异


# 常见动态噪声字段 Key 正则
DYNAMIC_KEY_PATTERNS = [
    re.compile(
        r"(?i)^(timestamp|time|server[_-]?time|sys[_-]?time|now|date|created[_-]?at|updated[_-]?at|expire[_-]?at)$"
    ),
    re.compile(
        r"(?i)^(trace[_-]?id|span[_-]?id|request[_-]?id|req[_-]?id|x[_-]?b3[_-]?(?:traceid|spanid)|client[_-]?uuid|nonce)$"
    ),
    re.compile(r"(?i)^(duration|duration[_-]?ms|elapsed|cost[_-]?time|latency)$"),
    re.compile(r"(?i)^(token|access[_-]?token|refresh[_-]?token|sign|signature|hash)$"),
]

# 动态噪声值特征正则 (ISO8601 时间, UUIDv4)
ISO8601_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?$")
UUID_REGEX = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

# 业务核心敏感 Key (发生变更直接判定为 CRITICAL)
CORE_BUSINESS_KEYS = {"code", "status", "success", "amount", "total", "price", "order_id", "user_id", "result"}


@dataclass
class NoiseFilterConfig:
    ignore_keys: list[str] = field(
        default_factory=lambda: [
            "timestamp",
            "time",
            "trace_id",
            "request_id",
            "span_id",
            "nonce",
            "sign",
            "duration_ms",
        ]
    )
    ignore_paths: list[str] = field(default_factory=list)  # 如 ["$.metadata.time", "$.traceId"]
    auto_detect_uuid: bool = True
    auto_detect_timestamp: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "ignore_keys": self.ignore_keys,
            "ignore_paths": self.ignore_paths,
            "auto_detect_uuid": self.auto_detect_uuid,
            "auto_detect_timestamp": self.auto_detect_timestamp,
        }


@dataclass
class DiffItem:
    path: str
    diff_type: DiffType
    severity: DiffSeverity
    baseline_value: Any
    replayed_value: Any
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "diff_type": self.diff_type.value,
            "severity": self.severity.value,
            "baseline_value": self.baseline_value,
            "replayed_value": self.replayed_value,
            "description": self.description,
        }


@dataclass
class TrafficDiffReport:
    report_id: str
    similarity_score_pct: float  # 0.0 ~ 100.0%
    is_identical: bool
    total_differences_count: int
    critical_diffs_count: int
    warning_diffs_count: int
    ignored_noise_fields_count: int
    differences: list[DiffItem]
    diff_summary: str
    baseline_status_code: int
    replayed_status_code: int
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "similarity_score_pct": round(self.similarity_score_pct, 2),
            "is_identical": self.is_identical,
            "total_differences_count": self.total_differences_count,
            "critical_diffs_count": self.critical_diffs_count,
            "warning_diffs_count": self.warning_diffs_count,
            "ignored_noise_fields_count": self.ignored_noise_fields_count,
            "differences": [d.to_dict() for d in self.differences],
            "diff_summary": self.diff_summary,
            "baseline_status_code": self.baseline_status_code,
            "replayed_status_code": self.replayed_status_code,
            "created_at": self.created_at.isoformat(),
        }


# 全局内存报告仓库
_DIFF_REPORTS: dict[str, TrafficDiffReport] = {}


def is_dynamic_noise_field(key: str, val: Any, config: NoiseFilterConfig) -> bool:
    """判定某字段是否为动态噪声，若是则在精确比对时予以忽略。"""
    key_lower = key.lower()

    # 1. 精确配置白名单匹配
    if any(k.lower() == key_lower for k in config.ignore_keys):
        return True

    # 2. 正则键名特征匹配
    if any(p.match(key) for p in DYNAMIC_KEY_PATTERNS):
        return True

    # 3. 动态值特征判定 (UUID、时间字符串、毫秒时间戳)
    if isinstance(val, str):
        if config.auto_detect_uuid and UUID_REGEX.match(val):
            return True
        if config.auto_detect_timestamp and ISO8601_REGEX.match(val):
            return True
    elif isinstance(val, (int, float)) and config.auto_detect_timestamp:
        # 13位毫秒时间戳 (如 1760000000000) 或 10位秒时间戳
        val_int = int(val)
        if 1600000000 <= val_int <= 2500000000 or 1600000000000 <= val_int <= 2500000000000:
            return True

    return False


def _parse_payload(payload: Any) -> Any:
    """尝试将字符串反序列化为 JSON 结构体，无法解析则保留原样。"""
    if isinstance(payload, str):
        trimmed = payload.strip()
        if (trimmed.startswith("{") and trimmed.endswith("}")) or (trimmed.startswith("[") and trimmed.endswith("]")):
            try:
                return json.loads(trimmed)
            except Exception:
                pass
    return payload


def compare_payloads_deep(
    baseline: Any,
    replayed: Any,
    current_path: str = "$",
    config: NoiseFilterConfig | None = None,
) -> tuple[list[DiffItem], int]:
    """深度递归比对两个 Payload，输出结构化字段级差异列表与被忽略的噪声字段计数。"""
    cfg = config or NoiseFilterConfig()
    diffs: list[DiffItem] = []
    ignored_count = 0

    base_norm = _parse_payload(baseline)
    repl_norm = _parse_payload(replayed)

    # 1. 基础类型漂移比对
    if type(base_norm) is not type(repl_norm):
        # 宽容处理 int 与 float 的微小浮点差异
        if isinstance(base_norm, (int, float)) and isinstance(repl_norm, (int, float)):
            if abs(float(base_norm) - float(repl_norm)) > 1e-6:
                diffs.append(
                    DiffItem(
                        path=current_path,
                        diff_type=DiffType.MODIFIED,
                        severity=DiffSeverity.CRITICAL,
                        baseline_value=base_norm,
                        replayed_value=repl_norm,
                        description=f"数值不一致: 基线 {base_norm} vs 回放 {repl_norm}",
                    )
                )
            return diffs, ignored_count

        diffs.append(
            DiffItem(
                path=current_path,
                diff_type=DiffType.TYPE_CHANGED,
                severity=DiffSeverity.CRITICAL,
                baseline_value=type(base_norm).__name__,
                replayed_value=type(repl_norm).__name__,
                description=f"字段类型漂移: 由 [{type(base_norm).__name__}] 变为 [{type(repl_norm).__name__}]",
            )
        )
        return diffs, ignored_count

    # 2. 字典深度递归比对
    if isinstance(base_norm, dict) and isinstance(repl_norm, dict):
        base_keys = set(base_norm.keys())
        repl_keys = set(repl_norm.keys())

        all_keys = base_keys | repl_keys
        for k in sorted(all_keys):
            field_path = f"{current_path}.{k}"

            # 忽略动态噪声
            val_sample = base_norm.get(k, repl_norm.get(k))
            if is_dynamic_noise_field(k, val_sample, cfg):
                ignored_count += 1
                continue

            if k not in repl_keys:
                # 基线有，回放缺失 -> DELETED (严重)
                diffs.append(
                    DiffItem(
                        path=field_path,
                        diff_type=DiffType.DELETED,
                        severity=DiffSeverity.CRITICAL,
                        baseline_value=base_norm[k],
                        replayed_value=None,
                        description=f"关键字段缺失: 回放响应中未找到字段 [{k}]",
                    )
                )
            elif k not in base_keys:
                # 回放新增 -> ADDED
                diffs.append(
                    DiffItem(
                        path=field_path,
                        diff_type=DiffType.ADDED,
                        severity=DiffSeverity.WARNING,
                        baseline_value=None,
                        replayed_value=repl_norm[k],
                        description=f"新增返回字段: 回放响应中出现新字段 [{k}]",
                    )
                )
            else:
                # 两边都有，递归深入
                sub_diffs, sub_ignored = compare_payloads_deep(base_norm[k], repl_norm[k], field_path, cfg)
                diffs.extend(sub_diffs)
                ignored_count += sub_ignored

        return diffs, ignored_count

    # 3. 列表深度比对
    if isinstance(base_norm, list) and isinstance(repl_norm, list):
        len_base = len(base_norm)
        len_repl = len(repl_norm)
        if len_base != len_repl:
            diffs.append(
                DiffItem(
                    path=f"{current_path}.length",
                    diff_type=DiffType.MODIFIED,
                    severity=DiffSeverity.CRITICAL if len_repl == 0 and len_base > 0 else DiffSeverity.WARNING,
                    baseline_value=len_base,
                    replayed_value=len_repl,
                    description=f"数组长度不匹配: 基线长度 {len_base} vs 回放长度 {len_repl}",
                )
            )

        min_len = min(len_base, len_repl)
        for i in range(min_len):
            sub_diffs, sub_ignored = compare_payloads_deep(base_norm[i], repl_norm[i], f"{current_path}[{i}]", cfg)
            diffs.extend(sub_diffs)
            ignored_count += sub_ignored

        return diffs, ignored_count

    # 4. 基础标量值比对 (str / int / float / bool)
    if base_norm != repl_norm:
        key_name = current_path.split(".")[-1].strip("[]0123456789")
        is_core = key_name.lower() in CORE_BUSINESS_KEYS
        diffs.append(
            DiffItem(
                path=current_path,
                diff_type=DiffType.MODIFIED,
                severity=DiffSeverity.CRITICAL if is_core else DiffSeverity.WARNING,
                baseline_value=base_norm,
                replayed_value=repl_norm,
                description=f"字段值变更: 基线值 [{base_norm}] vs 回放值 [{repl_norm}]",
            )
        )

    return diffs, ignored_count


def compare_traffic_responses(
    baseline_response_body: str | dict[str, Any],
    replayed_response_body: str | dict[str, Any],
    baseline_status_code: int = 200,
    replayed_status_code: int = 200,
    config: NoiseFilterConfig | None = None,
) -> TrafficDiffReport:
    """端到端智能对比基线与回放响应，输出字段级 Diff 报告与相似度评分。"""
    report_id = f"diff_{uuid.uuid4().hex[:12]}"
    cfg = config or NoiseFilterConfig()

    differences: list[DiffItem] = []
    ignored_count = 0

    # 1. 状态码预先校验
    if baseline_status_code != replayed_status_code:
        differences.append(
            DiffItem(
                path="$.status_code",
                diff_type=DiffType.MODIFIED,
                severity=DiffSeverity.CRITICAL,
                baseline_value=baseline_status_code,
                replayed_value=replayed_status_code,
                description=f"HTTP 响应状态码严重不符: 基线为 {baseline_status_code}，回放为 {replayed_status_code}",
            )
        )

    # 2. 深度 JSON 字段级递归比对
    body_diffs, body_ignored = compare_payloads_deep(baseline_response_body, replayed_response_body, "$", cfg)
    differences.extend(body_diffs)
    ignored_count += body_ignored

    critical_count = sum(1 for d in differences if d.severity == DiffSeverity.CRITICAL)
    warning_count = sum(1 for d in differences if d.severity == DiffSeverity.WARNING)

    # 3. 计算相似度得分 (满分 100，每个 CRITICAL 扣 25 分，每个 WARNING 扣 10 分)
    penalty = critical_count * 25.0 + warning_count * 10.0
    similarity = max(0.0, 100.0 - penalty)
    is_identical = len(differences) == 0

    # 4. 生成裁决总结
    if is_identical:
        summary = (
            f"完美一致！响应体经动态噪声过滤后与基线完全相同 (已智能忽略 {ignored_count} 处时间戳/UUID/Token 噪声)。"
        )
    elif critical_count > 0:
        summary = (
            f"检出 {critical_count} 处阻断级核心差异与 {warning_count} 处警告差异，"
            f"相似度得分仅为 {round(similarity, 1)}%，需重点排查缺失字段与业务值篡改！"
        )
    else:
        summary = (
            f"检出 {warning_count} 处次要告警差异，相似度得分为 {round(similarity, 1)}%，"
            f"核心业务逻辑稳固，建议人工确认新增字段。"
        )

    report = TrafficDiffReport(
        report_id=report_id,
        similarity_score_pct=similarity,
        is_identical=is_identical,
        total_differences_count=len(differences),
        critical_diffs_count=critical_count,
        warning_diffs_count=warning_count,
        ignored_noise_fields_count=ignored_count,
        differences=differences,
        diff_summary=summary,
        baseline_status_code=baseline_status_code,
        replayed_status_code=replayed_status_code,
    )

    _DIFF_REPORTS[report_id] = report
    logger.info(
        "响应体比对完成 [%s]: 相似度 %.2f%%, 差异数 %d, 忽略噪声 %d",
        report_id,
        similarity,
        len(differences),
        ignored_count,
    )
    return report


def get_diff_report(report_id: str) -> TrafficDiffReport | None:
    """根据 ID 获取指定 Diff 比对报告详情。"""
    return _DIFF_REPORTS.get(report_id)


def list_diff_reports() -> list[TrafficDiffReport]:
    """获取历史 Diff 比对报告列表。"""
    reports = list(_DIFF_REPORTS.values())
    reports.sort(key=lambda r: r.created_at, reverse=True)
    return reports


def clear_diff_reports() -> int:
    """清空 Diff 报告缓存。"""
    count = len(_DIFF_REPORTS)
    _DIFF_REPORTS.clear()
    return count
