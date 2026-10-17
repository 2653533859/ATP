"""接口响应结构变迁与漂移检测器服务 (T2.1)

深度比对基线与最新接口响应，精准识别字段重命名、Envelope层级展开与类型演进:
1. 任意多层嵌套 JSON 扁平化路径映射解析 (JSONPath Flattener);
2. 字段重命名、外层包装变迁与路径深浅位移多模态检测 (Schema Drift Alignment);
3. 结构变迁置信度评分与同义/驼峰智能对齐 (Confidence-Scored Drift Mutation);
4. 漂移报告结构化输出 (ResponseSchemaDriftReport)。
"""

from __future__ import annotations

import difflib
import enum
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple


class DriftMutationType(str, enum.Enum):
    FIELD_RENAMED = "FIELD_RENAMED"  # 字段重命名 (如 user_id -> userId)
    ENVELOPE_UNWRAPPED = "ENVELOPE_UNWRAPPED"  # 外层结构包裹或解包 (如增加/去除 $.data)
    PATH_RELOCATED = "PATH_RELOCATED"  # 嵌套层级深浅跃迁 (如 $.role -> $.account.role)
    TYPE_MUTATED = "TYPE_MUTATED"  # 数据类型兼容演进 (如 "100.5" -> 100.5)


@dataclass
class SchemaDriftItem:
    drift_id: str
    mutation_type: DriftMutationType
    old_path: str  # 例如 $.user_id
    new_path: str  # 例如 $.data.userId
    old_value_sample: Any
    new_value_sample: Any
    confidence: float  # 0.0 ~ 1.0
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["mutation_type"] = self.mutation_type.value
        d["confidence"] = round(self.confidence, 4)
        return d


@dataclass
class ResponseSchemaDriftReport:
    report_id: str
    is_drift_detected: bool
    total_baseline_fields: int
    matched_field_count: int
    drifted_field_count: int
    unmatched_old_paths: List[str]
    newly_added_paths: List[str]
    drifts: List[SchemaDriftItem]
    detected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "is_drift_detected": self.is_drift_detected,
            "total_baseline_fields": self.total_baseline_fields,
            "matched_field_count": self.matched_field_count,
            "drifted_field_count": self.drifted_field_count,
            "unmatched_old_paths": self.unmatched_old_paths,
            "newly_added_paths": self.newly_added_paths,
            "drifts": [d.to_dict() for d in self.drifts],
            "detected_at": self.detected_at,
        }


def flatten_json_paths(data: Any, prefix: str = "$") -> Dict[str, Tuple[Any, str]]:
    """递归将嵌套 JSON 字典或列表扁平化为 JSONPath 映射

    Returns:
        Dict[jsonpath_str, (value, type_name)]
    """
    paths: Dict[str, Tuple[Any, str]] = {}

    if isinstance(data, dict):
        for k, v in data.items():
            current_path = f"{prefix}.{k}"
            if isinstance(v, (dict, list)) and v:
                paths.update(flatten_json_paths(v, current_path))
            else:
                type_name = type(v).__name__
                paths[current_path] = (v, type_name)
    elif isinstance(data, list):
        for idx, item in enumerate(data):
            current_path = f"{prefix}[{idx}]"
            if isinstance(item, (dict, list)) and item:
                paths.update(flatten_json_paths(item, current_path))
            else:
                type_name = type(item).__name__
                paths[current_path] = (item, type_name)
    else:
        paths[prefix] = (data, type(data).__name__)

    return paths


def _normalize_token(name: str) -> str:
    """下划线与驼峰名称统一标准化 (user_id -> userid, userId -> userid)"""
    return re.sub(r"[_\-]", "", name).lower()


def _get_leaf_field_name(path: str) -> str:
    """提取 JSONPath 最后一个叶子节点名称 ($.data.userId -> userId)"""
    return path.split(".")[-1].split("[")[0]


def detect_response_schema_drift(
    baseline_response: Any,
    actual_response: Any,
    confidence_threshold: float = 0.70,
) -> ResponseSchemaDriftReport:
    """深度比对基准响应与实际响应，精准推导结构与字段漂移"""
    report_id = f"drf_{uuid.uuid4().hex[:10]}"

    base_paths = flatten_json_paths(baseline_response)
    actual_paths = flatten_json_paths(actual_response)

    matched_exact: Set[str] = set()
    drifts: List[SchemaDriftItem] = []
    used_actual_paths: Set[str] = set()

    # 1. 查找路径完全一致的字段
    for path, (val, t_name) in base_paths.items():
        if path in actual_paths:
            act_val, act_t = actual_paths[path]
            matched_exact.add(path)
            used_actual_paths.add(path)

            # 检查同路径下的数据类型变迁 (如 "100" -> 100)
            if t_name != act_t:
                did = f"ditem_{uuid.uuid4().hex[:8]}"
                drifts.append(
                    SchemaDriftItem(
                        drift_id=did,
                        mutation_type=DriftMutationType.TYPE_MUTATED,
                        old_path=path,
                        new_path=path,
                        old_value_sample=val,
                        new_value_sample=act_val,
                        confidence=0.95,
                        explanation=f"字段类型变迁: 原类型为 '{t_name}'，现演进为 '{act_t}'",
                    )
                )

    unmatched_base = [p for p in base_paths.keys() if p not in matched_exact]
    unmatched_actual = [p for p in actual_paths.keys() if p not in used_actual_paths]

    # 2. 对未完全匹配的基准字段，模糊推导重命名或包装层级跃迁
    for old_p in unmatched_base:
        old_val, _ = base_paths[old_p]
        old_leaf = _get_leaf_field_name(old_p)
        old_norm = _normalize_token(old_leaf)

        best_cand: Optional[str] = None
        best_conf = 0.0
        best_mut_type = DriftMutationType.FIELD_RENAMED
        best_expl = ""

        for new_p in unmatched_actual:
            if new_p in used_actual_paths:
                continue
            new_val, _ = actual_paths[new_p]
            new_leaf = _get_leaf_field_name(new_p)
            new_norm = _normalize_token(new_leaf)

            # 模式 A: 规范化名称完全一致 (如 user_id vs userId)
            if old_norm == new_norm:
                # 检查是单纯重命名，还是伴随外层 Envelope 包装 (如 $.user_id vs $.data.userId)
                if ".data." in new_p and ".data." not in old_p:
                    mtype = DriftMutationType.ENVELOPE_UNWRAPPED
                    conf = 0.98
                    expl = f"外层包装展开: 字段由 '{old_p}' 规范归入至 '{new_p}'"
                elif old_p.count(".") != new_p.count("."):
                    mtype = DriftMutationType.PATH_RELOCATED
                    conf = 0.92
                    expl = f"层级路径位移: 字段层级发生深浅调整，由 '{old_p}' 位移至 '{new_p}'"
                else:
                    mtype = DriftMutationType.FIELD_RENAMED
                    conf = 0.95
                    expl = f"命名规范对齐: 字段由 '{old_leaf}' 演进为 '{new_leaf}'"

                if conf > best_conf:
                    best_conf = conf
                    best_cand = new_p
                    best_mut_type = mtype
                    best_expl = expl

            # 模式 B: 字符相似度高或取值相等
            else:
                sim = difflib.SequenceMatcher(None, old_leaf.lower(), new_leaf.lower()).ratio()
                # 若值完全一致且字符串相似度 >= 0.6
                if str(old_val) == str(new_val) and sim >= 0.60:
                    conf = 0.85
                    mtype = DriftMutationType.FIELD_RENAMED
                    expl = f"样本值完全匹配且键名高度相似 ({round(sim * 100, 1)}%): '{old_leaf}' ➔ '{new_leaf}'"
                    if conf > best_conf:
                        best_conf = conf
                        best_cand = new_p
                        best_mut_type = mtype
                        best_expl = expl

        if best_cand and best_conf >= confidence_threshold:
            did = f"ditem_{uuid.uuid4().hex[:8]}"
            used_actual_paths.add(best_cand)
            drifts.append(
                SchemaDriftItem(
                    drift_id=did,
                    mutation_type=best_mut_type,
                    old_path=old_p,
                    new_path=best_cand,
                    old_value_sample=old_val,
                    new_value_sample=actual_paths[best_cand][0],
                    confidence=best_conf,
                    explanation=best_expl,
                )
            )

    newly_added = [p for p in actual_paths.keys() if p not in used_actual_paths]
    remaining_unmatched_old = [p for p in unmatched_base if not any(d.old_path == p for d in drifts)]

    return ResponseSchemaDriftReport(
        report_id=report_id,
        is_drift_detected=len(drifts) > 0,
        total_baseline_fields=len(base_paths),
        matched_field_count=len(matched_exact),
        drifted_field_count=len(drifts),
        unmatched_old_paths=remaining_unmatched_old,
        newly_added_paths=newly_added,
        drifts=drifts,
    )
