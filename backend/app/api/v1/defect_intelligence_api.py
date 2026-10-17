"""智能缺陷聚类去重与聚合管理 REST API (T1.3)

挂载至 /api/v1/defect-intelligence/*，提供:
1. POST /api/v1/defect-intelligence/fingerprint (失败堆栈与异常语义指纹提取);
2. POST /api/v1/defect-intelligence/cluster-deduplicate (单批次海量失败智能聚类去重);
3. GET /api/v1/defect-intelligence/clusters (获取已聚类缺陷组列表);
4. GET /api/v1/defect-intelligence/clusters/{cluster_id} (获取指定主缺陷组详情);
5. POST /api/v1/defect-intelligence/clusters/{cluster_id}/merge (手动合并聚类至指定缺陷)。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.defect_failure_fingerprint_extractor import (
    extract_failure_fingerprint,
)
from app.services.defect_similarity_deduplicator import (
    ClusteredDefectGroup,
    DefectClusteringAction,
    DefectDeduplicationBatchResult,
    TestCaseFailureRecord,
    cluster_and_deduplicate_failures,
)

router = APIRouter(prefix="/defect-intelligence", tags=["defect-intelligence"])

_CLUSTERS_STORE: Dict[str, ClusteredDefectGroup] = {}
_BATCH_RESULTS_STORE: Dict[str, DefectDeduplicationBatchResult] = {}


def _load_seed_defect_data():
    """预装载初始示例聚类缺陷"""
    seed_failure_a = TestCaseFailureRecord(
        run_id="run_nightly_01",
        case_id="case_checkout_wechat",
        case_name="收银台微信支付扣款验证",
        error_message="DatabaseConnectionTimeout: PostgreSQL pool exhausted on host db-01 at 0x7fa9",
        stack_trace='  File "/app/services/payment.py", line 45, in execute_charge\n    db.commit()',
        target_service="payment-service",
    )
    seed_cluster = ClusteredDefectGroup(
        cluster_id="cl_seed_master_01",
        primary_fingerprint="fp_hash_7fa8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8",
        master_title="[payment-service] DatabaseConnectionTimeout in payment.py:execute_charge - PostgreSQL pool exhausted",
        exception_type="DatabaseConnectionTimeout",
        target_service="payment-service",
        root_cause_file="/app/services/payment.py",
        total_failures_count=12,
        linked_case_ids=[
            "case_checkout_wechat",
            "case_checkout_alipay",
            "case_checkout_card",
            "case_order_retry_01",
            "case_order_retry_02",
        ],
        associated_case_names=[
            "收银台微信支付扣款验证",
            "收银台支付宝扣款验证",
            "银行卡扣款验证",
            "订单异步重试01",
            "订单异步重试02",
        ],
        action=DefectClusteringAction.CREATED_NEW_MASTER,
        similarity_score=1.0,
        representative_failure=seed_failure_a,
    )
    _CLUSTERS_STORE[seed_cluster.cluster_id] = seed_cluster


_load_seed_defect_data()


def clear_defect_intelligence_store():
    """清空缺陷存储（单测使用）"""
    _CLUSTERS_STORE.clear()
    _BATCH_RESULTS_STORE.clear()
    _load_seed_defect_data()


class FingerprintExtractRequest(BaseModel):
    raw_error_message: str = Field(..., description="原始错误或断言失败信息")
    raw_stack_trace: str = Field(..., description="原始异常调用堆栈")
    exception_type: Optional[str] = Field(default=None, description="显式指定的异常类型名称")
    target_endpoint: Optional[str] = Field(default=None, description="关联的接口路由端点")


class TestCaseFailureInput(BaseModel):
    run_id: str = Field(default="run_current", description="运行任务批次编码")
    case_id: str = Field(..., description="用例编码")
    case_name: str = Field(..., description="用例名称")
    error_message: str = Field(..., description="错误信息")
    stack_trace: str = Field(..., description="堆栈轨迹")
    target_service: str = Field(default="unknown-service", description="受影响的目标微服务")


class BatchClusterDeduplicateRequest(BaseModel):
    failures: List[TestCaseFailureInput] = Field(..., description="测试执行失败记录列表")
    known_open_defects: Optional[List[Dict[str, Any]]] = Field(default=None, description="历史未解决已知缺陷列表")
    similarity_threshold: float = Field(default=0.80, description="聚类相似度阈值 (0.0~1.0)")


class MergeToDefectRequest(BaseModel):
    target_defect_id: str = Field(..., description="目标主缺陷编码，如 DEF-1002")


@router.post("/fingerprint", summary="失败堆栈与异常语义指纹提取")
def extract_fingerprint(req: FingerprintExtractRequest) -> Dict[str, Any]:
    res = extract_failure_fingerprint(
        raw_error_message=req.raw_error_message,
        raw_stack_trace=req.raw_stack_trace,
        exception_type=req.exception_type,
        target_endpoint=req.target_endpoint,
    )
    return res.to_dict()


@router.post("/cluster-deduplicate", summary="单批次海量失败智能聚类去重")
def cluster_and_deduplicate(req: BatchClusterDeduplicateRequest) -> Dict[str, Any]:
    raw_records: List[TestCaseFailureRecord] = [
        TestCaseFailureRecord(
            run_id=f.run_id,
            case_id=f.case_id,
            case_name=f.case_name,
            error_message=f.error_message,
            stack_trace=f.stack_trace,
            target_service=f.target_service,
        )
        for f in req.failures
    ]

    result = cluster_and_deduplicate_failures(
        failures=raw_records,
        known_open_defects=req.known_open_defects,
        similarity_threshold=req.similarity_threshold,
    )

    _BATCH_RESULTS_STORE[result.batch_id] = result
    for c in result.clusters:
        _CLUSTERS_STORE[c.cluster_id] = c

    return result.to_dict()


@router.get("/clusters", summary="获取已聚类缺陷组列表")
def list_clusters(target_service: Optional[str] = None) -> List[Dict[str, Any]]:
    clusters = list(_CLUSTERS_STORE.values())
    if target_service:
        clusters = [c for c in clusters if c.target_service == target_service]
    return [c.to_dict() for c in clusters]


@router.get("/clusters/{cluster_id}", summary="获取指定主缺陷组详情")
def get_cluster(cluster_id: str) -> Dict[str, Any]:
    c = _CLUSTERS_STORE.get(cluster_id)
    if not c:
        raise HTTPException(status_code=404, detail=f"未找到聚类主缺陷组 [{cluster_id}]")
    return c.to_dict()


@router.post("/clusters/{cluster_id}/merge", summary="手动合并聚类至指定主缺陷")
def merge_cluster_to_defect(cluster_id: str, req: MergeToDefectRequest) -> Dict[str, Any]:
    c = _CLUSTERS_STORE.get(cluster_id)
    if not c:
        raise HTTPException(status_code=404, detail=f"未找到聚类主缺陷组 [{cluster_id}]")

    c.action = DefectClusteringAction.MERGED_TO_EXISTING_DEFECT
    c.existing_defect_id = req.target_defect_id
    return {
        "status": "success",
        "message": f"聚类缺陷 [{cluster_id}] 已成功关联合并至主缺陷 [{req.target_defect_id}]",
        "cluster": c.to_dict(),
    }
