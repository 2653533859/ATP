"""自动化测试用例自愈与断言演进 REST API (T1.3)

为 UI 与接口自动化测试提供失败拦截、定位器动态自愈与补丁生命周期管理:
1. 定位失效多模态自愈诊断 (/self-healing/locator/diagnose);
2. 运行时现场热替换自愈执行 (/self-healing/locator/heal);
3. 自愈补丁采纳与回滚控制 (/self-healing/patch/{patch_id}/commit, /reject);
4. 补丁详情与历史检索 (/self-healing/patch/{patch_id}, /self-healing/patches)。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import require_engineer
from app.models.user import User
from app.services.dynamic_locator_self_healer import (
    BrokenLocatorContext,
    CandidateDOMNode,
    derive_self_healing_candidates,
)
from app.services.runtime_healing_patcher import (
    commit_healing_patch,
    get_healing_patch,
    intercept_and_heal_step,
    list_healing_patches,
    reject_healing_patch,
)
from app.services.response_schema_drift_detector import detect_response_schema_drift
from app.services.assertion_drift_evolution_synthesizer import synthesize_assertion_evolution
from app.services.assertion_evolution_controller import (
    dry_run_evolved_assertion,
    evaluate_assertion_evolution_confidence,
    list_assertion_snapshots,
    record_assertion_version_snapshot,
    rollback_assertion_version,
)

router = APIRouter(prefix="/self-healing", tags=["Test Self-Healing & Assertion Evolution"])


class DiagnoseLocatorRequest(BaseModel):
    step_id: str = Field(..., description="失败步骤 ID")
    failed_locator_type: str = Field("css", description="失效定位器类型 (css | id | xpath)")
    failed_locator_value: str = Field(..., description="失效定位器表达式")
    element_text_hint: Optional[str] = Field(None, description="期望文案提示")
    element_role_hint: Optional[str] = Field("button", description="期望控件角色")
    screen_nodes: List[Dict[str, Any]] = Field(..., description="当前屏幕活体 DOM / UI 节点列表")
    confidence_threshold: float = Field(0.65, ge=0.0, le=1.0, description="自愈置信度门限")


class HealStepRequest(BaseModel):
    step_id: str = Field(..., description="失败步骤 ID")
    failed_locator_type: str = Field("css", description="失效定位器类型")
    failed_locator_value: str = Field(..., description="失效定位器表达式")
    element_text_hint: Optional[str] = Field(None, description="期望文案提示")
    element_role_hint: Optional[str] = Field("button", description="期望角色")
    screen_nodes: List[Dict[str, Any]] = Field(..., description="当前屏幕活体 DOM 节点")
    case_id: Optional[str] = Field(None, description="所属用例 ID")
    platform: str = Field("web", description="执行平台 (web | ios | android)")
    confidence_threshold: float = Field(0.65, ge=0.0, le=1.0, description="自愈门限")


@router.post("/locator/diagnose")
def diagnose_locator_endpoint(
    payload: DiagnoseLocatorRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """对定位器失效场景进行多模态分析并推导演算自愈候选"""
    context = BrokenLocatorContext(
        step_id=payload.step_id,
        failed_locator_type=payload.failed_locator_type,
        failed_locator_value=payload.failed_locator_value,
        element_text_hint=payload.element_text_hint,
        element_role_hint=payload.element_role_hint,
    )

    nodes = [
        CandidateDOMNode(
            node_id=n.get("node_id", f"node_{i}"),
            tag_name=n.get("tag_name", "button"),
            text=n.get("text"),
            attributes=n.get("attributes", {}),
            bounding_box=n.get("bounding_box"),
            xpath=n.get("xpath"),
        )
        for i, n in enumerate(payload.screen_nodes)
    ]

    res = derive_self_healing_candidates(context, nodes, payload.confidence_threshold)
    return {
        "message": f"定位器自愈诊断完成，推导出 {len(res.all_candidates)} 项自愈候选",
        "diagnosis": res.to_dict(),
    }


@router.post("/locator/heal")
def heal_step_endpoint(
    payload: HealStepRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """运行时拦截失败步骤并执行现场热替换自愈重试"""
    context = BrokenLocatorContext(
        step_id=payload.step_id,
        failed_locator_type=payload.failed_locator_type,
        failed_locator_value=payload.failed_locator_value,
        element_text_hint=payload.element_text_hint,
        element_role_hint=payload.element_role_hint,
    )

    nodes = [
        CandidateDOMNode(
            node_id=n.get("node_id", f"node_{i}"),
            tag_name=n.get("tag_name", "button"),
            text=n.get("text"),
            attributes=n.get("attributes", {}),
            bounding_box=n.get("bounding_box"),
            xpath=n.get("xpath"),
        )
        for i, n in enumerate(payload.screen_nodes)
    ]

    exec_res = intercept_and_heal_step(
        context=context,
        screen_nodes=nodes,
        case_id=payload.case_id,
        platform=payload.platform,
        confidence_threshold=payload.confidence_threshold,
    )

    return {
        "message": exec_res.message,
        "result": exec_res.to_dict(),
    }


@router.post("/patch/{patch_id}/commit")
def commit_patch_endpoint(
    patch_id: str,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """确认采纳自愈补丁并永久固化回写至用例库"""
    success = commit_healing_patch(patch_id)
    if not success:
        raise HTTPException(status_code=404, detail="未找到目标自愈补丁")
    patch = get_healing_patch(patch_id)
    return {
        "message": f"自愈补丁 [{patch_id}] 已永久采纳生效！",
        "patch": patch.to_dict() if patch else None,
    }


@router.post("/patch/{patch_id}/reject")
def reject_patch_endpoint(
    patch_id: str,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """人工否决或回滚自愈补丁"""
    success = reject_healing_patch(patch_id)
    if not success:
        raise HTTPException(status_code=404, detail="未找到目标自愈补丁")
    return {"message": f"自愈补丁 [{patch_id}] 已被否决回滚"}


@router.get("/patch/{patch_id}")
def get_patch_endpoint(
    patch_id: str,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """查询单张自愈补丁详细信息"""
    patch = get_healing_patch(patch_id)
    if not patch:
        raise HTTPException(status_code=404, detail="自愈补丁不存在")
    return {"patch": patch.to_dict()}


@router.get("/patches")
def list_patches_endpoint(
    status: Optional[str] = None,
    limit: int = 50,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """查询自愈补丁历史流水列表"""
    patches = list_healing_patches(status=status, limit=limit)
    return {
        "total": len(patches),
        "patches": patches,
    }


class AssertionDriftDetectRequest(BaseModel):
    baseline_response: Dict[str, Any] = Field(..., description="基线接口响应体")
    actual_response: Dict[str, Any] = Field(..., description="实际最新接口响应体")
    confidence_threshold: float = Field(0.70, ge=0.0, le=1.0, description="置信度门限")


class AssertionEvolveRequest(BaseModel):
    case_id: str = Field("case_api_01", description="用例 ID")
    step_id: str = Field("step_assert_01", description="步骤 ID")
    original_code: str = Field(..., description="原始 Python 断言代码")
    baseline_response: Dict[str, Any] = Field(..., description="基线接口响应体")
    actual_response: Dict[str, Any] = Field(..., description="实际接口响应体")


class AssertionDryRunRequest(BaseModel):
    assertion_code: str = Field(..., description="待试跑断言代码")
    response_payload: Dict[str, Any] = Field(..., description="测试响应体数据")


@router.post("/assertion/drift-detect")
def detect_assertion_drift_endpoint(
    payload: AssertionDriftDetectRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """比对基线与最新响应，返回 Schema 漂移报告"""
    report = detect_response_schema_drift(
        payload.baseline_response,
        payload.actual_response,
        payload.confidence_threshold,
    )
    return {
        "message": f"结构漂移检测完成，识别到 {report.drifted_field_count} 处字段变迁",
        "report": report.to_dict(),
    }


@router.post("/assertion/evolve")
def evolve_assertion_endpoint(
    payload: AssertionEvolveRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """基于 Schema 变迁自动演进断言代码并计算置信度健康评分"""
    drift_report = detect_response_schema_drift(payload.baseline_response, payload.actual_response)
    evolution_res = synthesize_assertion_evolution(payload.original_code, drift_report)
    confidence_eval = evaluate_assertion_evolution_confidence(evolution_res, drift_report.drifts)

    snapshot = record_assertion_version_snapshot(
        case_id=payload.case_id,
        step_id=payload.step_id,
        original_assertion=payload.original_code,
        evolved_assertion=evolution_res.evolved_code,
        confidence_score=confidence_eval.score,
        risk_level=confidence_eval.risk_level,
        applied_drift_ids=evolution_res.applied_drift_ids,
    )

    return {
        "message": "语义断言演进合成与置信度评估完成",
        "evolution": evolution_res.to_dict(),
        "confidence_evaluation": confidence_eval.to_dict(),
        "snapshot": snapshot.to_dict(),
    }


@router.post("/assertion/dry-run")
def dry_run_assertion_endpoint(
    payload: AssertionDryRunRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """在隔离沙箱环境中试跑验证演进后的断言"""
    result = dry_run_evolved_assertion(payload.assertion_code, payload.response_payload)
    return {
        "message": "断言沙箱试跑执行完成",
        "result": result.to_dict(),
    }


@router.post("/assertion/rollback/{version_id}")
def rollback_assertion_endpoint(
    version_id: str,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """一键回滚断言演进至旧基线版本"""
    snap = rollback_assertion_version(version_id)
    if not snap:
        raise HTTPException(status_code=404, detail="未找到目标断言版本快照")
    return {
        "message": f"断言版本 [{version_id}] 已成功回滚至原基线！",
        "snapshot": snap.to_dict(),
    }


@router.get("/assertion/snapshots")
def list_snapshots_endpoint(
    case_id: Optional[str] = None,
    step_id: Optional[str] = None,
    limit: int = 50,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """查询断言版本快照历史流水"""
    snapshots = list_assertion_snapshots(case_id=case_id, step_id=step_id, limit=limit)
    return {
        "total": len(snapshots),
        "snapshots": [s.to_dict() for s in snapshots],
    }
