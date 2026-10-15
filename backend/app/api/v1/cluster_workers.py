"""Cluster Worker Node Load Monitoring & Adaptive Dispatching REST API (C1.1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.cluster_load_balancer import (
    get_cluster_capacity_overview,
    get_worker_node,
    list_cluster_nodes,
    register_worker_heartbeat,
    select_optimal_worker,
)
from app.services.adaptive_queue_preemptor import (
    calculate_queue_eta_seconds,
    complete_task,
    enqueue_task,
    list_queued_tasks,
)

router = APIRouter(prefix="/cluster/workers", tags=["跨节点 Worker 集群负载与调度"])


class WorkerHeartbeatIn(BaseModel):
    worker_id: str = Field(min_length=2, max_length=128, description="Worker 节点唯一标识")
    hostname: str = Field(description="主机名")
    ip_address: str = Field(description="节点 IP 地址")
    queues: list[str] = Field(default_factory=lambda: ["default"], description="监听的 Celery 队列列表")
    current_concurrency: int = Field(default=0, ge=0, description="当前正在运行的并发任务数")
    max_concurrency: int = Field(default=10, ge=1, description="最大允许并发任务上限")
    cpu_usage_pct: float = Field(default=0.0, ge=0.0, le=100.0, description="当前 CPU 使用率百分比")
    memory_usage_pct: float = Field(default=0.0, ge=0.0, le=100.0, description="当前内存使用率百分比")
    weight: float = Field(default=1.0, ge=0.1, le=10.0, description="节点算力权重因子")
    status: str = Field(default="online", description="节点状态 (online | busy | draining | offline)")


class SelectOptimalWorkerIn(BaseModel):
    required_queue: str = Field(default="default", description="任务所需派发的 Celery 队列")
    exclude_worker_ids: list[str] = Field(default_factory=list, description="需要排除的 Worker 列表")


class EnqueueTaskIn(BaseModel):
    task_name: str = Field(min_length=1, max_length=128, description="待调度任务名称")
    queue_name: str = Field(default="default", description="目标执行队列")
    priority: str = Field(default="P2", description="优先级等级: P0 | P1 | P2 | P3")
    estimated_duration_sec: float = Field(default=30.0, ge=1.0, description="任务预计执行耗时秒数")
    allow_preemption: bool = Field(default=True, description="是否允许对低优先级运行中任务执行弹性抢占")


@router.get("")
async def list_cluster_workers_endpoint(
    queue: str | None = Query(default=None, description="按所属队列过滤"),
    only_alive: bool = Query(default=True, description="仅返回心跳健康的活跃节点"),
    _user: User = Depends(get_current_user),
):
    """获取跨节点 Worker 集群的节点列表、实时负载与容量评分。"""
    _ = _user
    nodes = list_cluster_nodes(queue=queue, only_alive=only_alive)
    return {"total": len(nodes), "workers": [n.to_dict() for n in nodes]}


@router.post("/heartbeat")
async def report_worker_heartbeat_endpoint(
    body: WorkerHeartbeatIn,
    _user: User = Depends(require_engineer),
):
    """上报 Worker 节点实时心跳与负载指标 (CPU、内存、并发水位)。"""
    _ = _user
    node = register_worker_heartbeat(
        worker_id=body.worker_id,
        hostname=body.hostname,
        ip_address=body.ip_address,
        queues=body.queues,
        current_concurrency=body.current_concurrency,
        max_concurrency=body.max_concurrency,
        cpu_usage_pct=body.cpu_usage_pct,
        memory_usage_pct=body.memory_usage_pct,
        weight=body.weight,
        status=body.status,
    )
    return {"message": "心跳上报成功", "worker": node.to_dict()}


@router.post("/select-optimal")
async def select_optimal_worker_endpoint(
    body: SelectOptimalWorkerIn,
    _user: User = Depends(require_engineer),
):
    """根据加权负载与剩余容量算法，为新任务自动选取最优执行 Worker 节点。"""
    _ = _user
    optimal = select_optimal_worker(
        required_queue=body.required_queue,
        exclude_worker_ids=body.exclude_worker_ids,
    )
    if not optimal:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"当前集群中无可用且具备空闲容量的 Worker 节点 (队列: {body.required_queue})",
        )
    return {"selected": True, "worker": optimal.to_dict()}


@router.get("/overview")
async def get_cluster_overview_endpoint(
    _user: User = Depends(get_current_user),
):
    """获取集群全域并发槽位总数、实时水位利用率与健康分布统计。"""
    _ = _user
    return get_cluster_capacity_overview()


@router.get("/{worker_id}")
async def get_worker_detail_endpoint(
    worker_id: str,
    _user: User = Depends(get_current_user),
):
    """获取单个 Worker 节点的负载指标与容量评分详情。"""
    _ = _user
    node = get_worker_node(worker_id)
    if not node:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Worker 节点不存在: {worker_id}")
    return node.to_dict()


@router.post("/tasks/enqueue")
async def enqueue_task_endpoint(
    body: EnqueueTaskIn,
    _user: User = Depends(require_engineer),
):
    """将新任务提交到自适应调度队列，并根据集群水位尝试即时派发或 P0 弹性抢占。"""
    _ = _user
    task, was_preempted = enqueue_task(
        task_name=body.task_name,
        queue_name=body.queue_name,
        priority=body.priority,
        estimated_duration_sec=body.estimated_duration_sec,
        allow_preemption=body.allow_preemption,
    )
    return {"task": task.to_dict(), "preempted": was_preempted}


@router.get("/tasks")
async def list_tasks_endpoint(
    queue_name: str | None = Query(default=None, description="按队列名称过滤"),
    _user: User = Depends(get_current_user),
):
    """查询当前调度器队列中排队、挂起与运行中的任务列表。"""
    _ = _user
    tasks = list_queued_tasks(queue_name=queue_name)
    return {"total": len(tasks), "tasks": [t.to_dict() for t in tasks]}


@router.post("/tasks/{task_id}/complete")
async def complete_task_endpoint(
    task_id: str,
    status_code_str: str = Query(default="completed", description="终态: completed | aborted"),
    _user: User = Depends(require_engineer),
):
    """完成指定运行任务并释放 Worker 并发槽位，自动唤醒挂起或排队的下一任务。"""
    _ = _user
    try:
        task = complete_task(task_id, status=status_code_str)
        return {"message": "任务已标记完成", "task": task.to_dict()}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/tasks/{task_id}/eta")
async def get_task_eta_endpoint(
    task_id: str,
    _user: User = Depends(get_current_user),
):
    """计算指定排队/挂起任务在集群当前吞吐下的预计等待时长 (ETA) 与排队顺位。"""
    _ = _user
    try:
        return calculate_queue_eta_seconds(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
