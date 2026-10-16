"""云原生弹性 Worker 容器 Pod 调度与配额管控 API (D1.1)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.k8s_worker_provisioner import (
    ContainerRuntime,
    PodStatus,
    ResourceQuota,
    get_worker_pod,
    list_worker_pods,
    provision_worker_pod,
    reap_stale_worker_pods,
    terminate_worker_pod,
)

router = APIRouter(prefix="/cloud-native/workers", tags=["云原生弹性 Worker 调度与配额"])


class ProvisionPodIn(BaseModel):
    worker_name: str = Field(min_length=1, max_length=128, description="Worker 容器名称")
    image: str = Field(default="atp/worker-python:3.12-v1", description="容器镜像地址与标签")
    assigned_queue: str = Field(default="default", description="承接任务的 Celery 队列")
    runtime: str = Field(default="kubernetes", description="容器运行时 (kubernetes | docker | containerd)")
    cpu_limit_cores: float = Field(default=2.0, ge=0.1, le=16.0, description="CPU 核心配额限制")
    memory_limit_mb: int = Field(default=2048, ge=128, le=32768, description="内存配额限制 (MB)")
    cpu_request_cores: float = Field(default=0.5, ge=0.1, le=16.0, description="CPU Request 请求")
    memory_request_mb: int = Field(default=512, ge=64, le=32768, description="Memory Request 请求")
    metadata: dict[str, Any] = Field(default_factory=dict, description="业务元数据")


class TerminatePodIn(BaseModel):
    exit_code: int = Field(default=0, description="容器退出码")


@router.post("/provision")
async def provision_worker_pod_endpoint(
    body: ProvisionPodIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """动态拉起并调度瞬时 Worker 容器 Pod 实例 (需工程师权限)。"""
    _ = _user
    try:
        runtime_enum = ContainerRuntime(body.runtime.lower())
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"不支持的容器运行时: {body.runtime}")

    try:
        quota = ResourceQuota(
            cpu_limit_cores=body.cpu_limit_cores,
            memory_limit_mb=body.memory_limit_mb,
            cpu_request_cores=body.cpu_request_cores,
            memory_request_mb=body.memory_request_mb,
        )
        pod = provision_worker_pod(
            worker_name=body.worker_name,
            image=body.image,
            assigned_queue=body.assigned_queue,
            resource_quota=quota,
            runtime=runtime_enum,
            metadata=body.metadata,
        )
        return {"message": "Worker 容器 Pod 拉起成功", "pod": pod.to_dict()}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("")
async def list_worker_pods_endpoint(
    assigned_queue: str | None = Query(default=None, description="按队列过滤"),
    status_str: str | None = Query(default=None, alias="status", description="按状态过滤"),
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询集群当前所有 Worker 容器 Pod 清单与状态。"""
    _ = _user
    status_enum = None
    if status_str:
        try:
            status_enum = PodStatus(status_str.lower())
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"无效的 Pod 状态: {status_str}")

    pods = list_worker_pods(assigned_queue=assigned_queue, status=status_enum)
    return {"total": len(pods), "pods": [p.to_dict() for p in pods]}


@router.get("/{pod_id}")
async def get_worker_pod_endpoint(
    pod_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取单个 Worker 容器 Pod 详情与运行日志。"""
    _ = _user
    pod = get_worker_pod(pod_id)
    if not pod:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Worker Pod 不存在: {pod_id}")

    res = pod.to_dict()
    res["logs"] = pod.logs
    return res


@router.post("/{pod_id}/terminate")
async def terminate_worker_pod_endpoint(
    pod_id: str,
    body: TerminatePodIn | None = None,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """优雅终止并回收指定 Worker 容器 Pod。"""
    _ = _user
    exit_code = body.exit_code if body else 0
    try:
        pod = terminate_worker_pod(pod_id, exit_code=exit_code)
        return {"message": "Worker 容器 Pod 终止成功", "pod": pod.to_dict()}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/reap")
async def reap_stale_worker_pods_endpoint(
    max_lifetime_sec: float = Query(default=3600.0, ge=10.0, description="最大允许存活秒数"),
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """批量巡检并收割运行超时的僵尸 Worker 容器。"""
    _ = _user
    reaped_ids = reap_stale_worker_pods(max_lifetime_sec=max_lifetime_sec)
    return {"message": "超限僵尸 Pod 收割完成", "reaped_count": len(reaped_ids), "reaped_pod_ids": reaped_ids}
