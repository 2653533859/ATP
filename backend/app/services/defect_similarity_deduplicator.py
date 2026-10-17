"""缺陷相似度计算与海量失败聚类去重器服务 (T1.2)

基于 64 位异常指纹与文本语义混合相似度，对自动化测试并发执行中的海量失败进行聚类去重:
1. 双层相似度判定算法 (精确指纹比对 + 词袋 Jaccard + 根因代码帧混合相似度);
2. 同源失败聚类合并 (从成百上千个失败中选举 Master 主缺陷，合并伴随失败用例);
3. 历史已知缺陷库比对 (对标已开启未解决工单，自动增加复现计数，阻断重复提单泛滥);
4. 综合去重比率精算与结果结构化输出 (DefectDeduplicationBatchResult & ClusteredDefectGroup)。
"""

from __future__ import annotations

import enum
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from app.services.defect_failure_fingerprint_extractor import (
    FailureFingerprintResult,
    extract_failure_fingerprint,
    sanitize_dynamic_tokens,
)


class DefectClusteringAction(str, enum.Enum):
    CREATED_NEW_MASTER = "CREATED_NEW_MASTER"  # 新发现缺陷，创建新 Master 主缺陷
    MERGED_TO_EXISTING_DEFECT = "MERGED_TO_EXISTING_DEFECT"  # 命中历史已提工单，关联合并并递增频次
    MERGED_TO_BATCH_MASTER = "MERGED_TO_BATCH_MASTER"  # 本批次内部多个同源失败合并为同一 Master


@dataclass
class TestCaseFailureRecord:
    run_id: str
    case_id: str
    case_name: str
    error_message: str
    stack_trace: str
    target_service: str = "unknown-service"
    failure_fingerprint: Optional[str] = None
    failed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ClusteredDefectGroup:
    cluster_id: str
    primary_fingerprint: str
    master_title: str
    exception_type: str
    target_service: str
    root_cause_file: str
    total_failures_count: int
    linked_case_ids: List[str]
    action: DefectClusteringAction
    similarity_score: float
    representative_failure: TestCaseFailureRecord
    existing_defect_id: Optional[str] = None
    associated_case_names: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "primary_fingerprint": self.primary_fingerprint,
            "master_title": self.master_title,
            "exception_type": self.exception_type,
            "target_service": self.target_service,
            "root_cause_file": self.root_cause_file,
            "total_failures_count": self.total_failures_count,
            "linked_case_ids": self.linked_case_ids,
            "associated_case_names": self.associated_case_names,
            "action": self.action.value,
            "existing_defect_id": self.existing_defect_id,
            "similarity_score": round(self.similarity_score, 2),
            "representative_failure": self.representative_failure.to_dict(),
        }


@dataclass
class DefectDeduplicationBatchResult:
    batch_id: str
    total_raw_failures: int
    total_deduplicated_clusters: int
    deduplication_ratio_pct: float  # 去重节省率 (如 50个失败聚为2个，去重率 96.0%)
    new_master_defects_count: int
    merged_to_existing_count: int
    clusters: List[ClusteredDefectGroup]
    processed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "total_raw_failures": self.total_raw_failures,
            "total_deduplicated_clusters": self.total_deduplicated_clusters,
            "deduplication_ratio_pct": round(self.deduplication_ratio_pct, 1),
            "new_master_defects_count": self.new_master_defects_count,
            "merged_to_existing_count": self.merged_to_existing_count,
            "clusters": [c.to_dict() for c in self.clusters],
            "processed_at": self.processed_at,
        }


def _tokenize(text: str) -> Set[str]:
    """对清洗后的文本进行分词提取词袋集合"""
    cleaned = sanitize_dynamic_tokens(text).lower()
    tokens = set(re.findall(r"[a-z_][a-z0-9_]{2,}", cleaned))
    return tokens


def calculate_failure_similarity(
    fp_res_a: FailureFingerprintResult,
    fp_res_b: FailureFingerprintResult,
) -> float:
    """计算两起测试失败之间的混合相似度 (0.0 ~ 1.0)"""
    # 1. 优先比对 64 位 SHA-256 故障指纹 (完全相同直接 1.0)
    if fp_res_a.failure_fingerprint == fp_res_b.failure_fingerprint:
        return 1.0

    score = 0.0

    # 2. 异常类型相同 (+0.35)
    if fp_res_a.exception_type == fp_res_b.exception_type and fp_res_a.exception_type != "UnknownAssertionFailure":
        score += 0.35

    # 3. 根因业务代码帧文件与函数相同 (+0.35)
    frame_a = fp_res_a.root_cause_frame
    frame_b = fp_res_b.root_cause_frame
    if frame_a and frame_b:
        if frame_a.file_path == frame_b.file_path:
            score += 0.20
            if frame_a.function_name == frame_b.function_name:
                score += 0.15

    # 4. 报错文本词袋 Jaccard 相似度 (+0.30)
    tokens_a = _tokenize(fp_res_a.normalized_message)
    tokens_b = _tokenize(fp_res_b.normalized_message)
    if tokens_a and tokens_b:
        intersection = len(tokens_a & tokens_b)
        union = len(tokens_a | tokens_b)
        jaccard = (intersection / union) if union > 0 else 0.0
        score += 0.30 * jaccard

    return min(1.0, score)


def cluster_and_deduplicate_failures(
    failures: List[TestCaseFailureRecord],
    known_open_defects: Optional[List[Dict[str, Any]]] = None,
    similarity_threshold: float = 0.80,
) -> DefectDeduplicationBatchResult:
    """对单批次测试执行海量失败进行指纹提取、历史比对与聚类去重"""
    batch_id = f"dedup_{uuid.uuid4().hex[:10]}"
    if not failures:
        return DefectDeduplicationBatchResult(
            batch_id=batch_id,
            total_raw_failures=0,
            total_deduplicated_clusters=0,
            deduplication_ratio_pct=100.0,
            new_master_defects_count=0,
            merged_to_existing_count=0,
            clusters=[],
        )

    # 1. 为每个失败记录计算标准化故障指纹
    failure_entries: List[tuple[TestCaseFailureRecord, FailureFingerprintResult]] = []
    for f in failures:
        fp_res = extract_failure_fingerprint(
            raw_error_message=f.error_message,
            raw_stack_trace=f.stack_trace,
        )
        f.failure_fingerprint = fp_res.failure_fingerprint
        failure_entries.append((f, fp_res))

    known_list = known_open_defects or []
    clusters: List[ClusteredDefectGroup] = []
    new_master_count = 0
    merged_existing_count = 0

    # 2. 聚类分组
    for fail_item, fp_res in failure_entries:
        matched_cluster: Optional[ClusteredDefectGroup] = None

        # 尝试匹配已形成的组
        for c in clusters:
            # 找到对应代表失败的指纹结果
            c_rep = next((item[1] for item in failure_entries if item[0] == c.representative_failure), None)
            if c_rep:
                sim = calculate_failure_similarity(fp_res, c_rep)
                if sim >= similarity_threshold:
                    matched_cluster = c
                    break

        if matched_cluster:
            matched_cluster.total_failures_count += 1
            if fail_item.case_id not in matched_cluster.linked_case_ids:
                matched_cluster.linked_case_ids.append(fail_item.case_id)
            if fail_item.case_name not in matched_cluster.associated_case_names:
                matched_cluster.associated_case_names.append(fail_item.case_name)
        else:
            # 3. 检查是否匹配历史已知缺陷
            matched_known_id: Optional[str] = None
            for kd in known_list:
                kd_fp = kd.get("failure_fingerprint", "")
                if kd_fp and kd_fp == fp_res.failure_fingerprint:
                    matched_known_id = str(kd.get("id") or kd.get("defect_id"))
                    break
                # 或者标题/异常匹配
                kd_title = str(kd.get("title", "")).lower()
                if fp_res.exception_type.lower() in kd_title and kd.get("target_service") == fail_item.target_service:
                    matched_known_id = str(kd.get("id") or kd.get("defect_id"))
                    break

            action = (
                DefectClusteringAction.MERGED_TO_EXISTING_DEFECT
                if matched_known_id
                else DefectClusteringAction.CREATED_NEW_MASTER
            )

            if matched_known_id:
                merged_existing_count += 1
            else:
                new_master_count += 1

            root_file = fp_res.root_cause_frame.file_path if fp_res.root_cause_frame else "unknown"
            root_func = fp_res.root_cause_frame.function_name if fp_res.root_cause_frame else ""
            title_prefix = f"[{fail_item.target_service}]" if fail_item.target_service != "unknown-service" else ""
            master_title = (
                f"{title_prefix} {fp_res.exception_type} in {root_file.split('/')[-1]}:{root_func} - {fp_res.normalized_message[:60]}"
            ).strip()

            new_cluster = ClusteredDefectGroup(
                cluster_id=f"cl_{uuid.uuid4().hex[:8]}",
                primary_fingerprint=fp_res.failure_fingerprint,
                master_title=master_title,
                exception_type=fp_res.exception_type,
                target_service=fail_item.target_service,
                root_cause_file=root_file,
                total_failures_count=1,
                linked_case_ids=[fail_item.case_id],
                associated_case_names=[fail_item.case_name],
                action=action,
                existing_defect_id=matched_known_id,
                similarity_score=1.0,
                representative_failure=fail_item,
            )
            clusters.append(new_cluster)

    total_raw = len(failures)
    total_cl = len(clusters)
    dedup_ratio = ((total_raw - total_cl) / total_raw * 100.0) if total_raw > 0 else 0.0

    return DefectDeduplicationBatchResult(
        batch_id=batch_id,
        total_raw_failures=total_raw,
        total_deduplicated_clusters=total_cl,
        deduplication_ratio_pct=dedup_ratio,
        new_master_defects_count=new_master_count,
        merged_to_existing_count=merged_existing_count,
        clusters=clusters,
    )
