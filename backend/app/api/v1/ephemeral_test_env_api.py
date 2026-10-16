"""临时沙箱测试环境生命周期自动化供给与快速回收 REST API (T1.3)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.ephemeral_test_env_lifecycle_manager import (
    clear_ephemeral_envs,
    extend_env_lease,
    get_ephemeral_environment,
    list_ephemeral_environments,
    provision_ephemeral_environment,
    reclaim_expired_environments,
    teardown_ephemeral_environment,
)

router = APIRouter(prefix="/cluster/ephemeral-env", tags=["临时沙箱测试环境生命周期 (T1.3)"])


class ProvisionEnvIn(BaseModel):
    branch_or_pr: str = Field(..., description="关联代码分支或 PR 标识 (如 pr-1024 或 feat-pay)")
    services: list[str] | None = Field(default=None, description="需要拉起的微服务组件列表")
    cpu_limit_cores: float = Field(default=2.0, ge=0.5, le=32.0, description="CPU 配额核心数")
    memory_limit_gib: float = Field(default=4.0, ge=0.5, le=64.0, description="内存配额 GiB")
    ttl_seconds: int = Field(default=3600, ge=60, le=86400, description="初始生存时间 (秒)")


class ExtendLeaseIn(BaseModel):
    extra_seconds: int = Field(default=1800, ge=60, le=43200, description="延长时间 (秒)")


@router.post("/provision")
async def provision_env_endpoint(
    body: ProvisionEnvIn,
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """自动化供给并拉起全新隔离沙箱测试环境。"""
    env = provision_ephemeral_environment(
        branch_or_pr=body.branch_or_pr,
        creator=user.username or "tester",
        services=body.services,
        cpu_limit_cores=body.cpu_limit_cores,
        memory_limit_gib=body.memory_limit_gib,
        ttl_seconds=body.ttl_seconds,
    )
    return {"message": "临时沙箱测试环境供给成功", "env": env.to_dict()}


@router.post("/{env_id}/extend-lease")
async def extend_lease_endpoint(
    env_id: str,
    body: ExtendLeaseIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """延长临时测试环境租约心跳 (Extend Lease)。"""
    _ = _user
    env = extend_env_lease(env_id=env_id, extra_seconds=body.extra_seconds)
    if not env:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"临时环境 [{env_id}] 不存在或已销毁")
    return {"message": "租约已成功延长", "env": env.to_dict()}


@router.post("/{env_id}/teardown")
async def teardown_env_endpoint(
    env_id: str,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """优雅原子级销毁并回收临时测试环境（需工程师权限）。"""
    _ = _user
    res = teardown_ephemeral_environment(env_id=env_id)
    if not res.get("success"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=res.get("message"))
    return res


@router.post("/reclaim-expired")
async def reclaim_expired_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """批量扫描并回收所有超期的孤儿临时沙箱环境（需工程师权限）。"""
    _ = _user
    res = reclaim_expired_environments()
    return {"message": "已完成超期孤儿测试环境扫描与回收", "result": res}


@router.get("/list")
async def list_envs_endpoint(
    active_only: bool = False,
    limit: int = 50,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询临时测试环境列表。"""
    _ = _user
    envs = list_ephemeral_environments(limit=limit, active_only=active_only)
    return {"total": len(envs), "environments": envs}


@router.get("/{env_id}")
async def get_env_endpoint(
    env_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询单个临时测试环境详情与配额水位。"""
    _ = _user
    env = get_ephemeral_environment(env_id)
    if not env:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"临时环境 [{env_id}] 不存在")
    return {"env": env.to_dict()}


@router.delete("/clear")
async def clear_envs_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空临时测试环境仓库（测试专用）。"""
    _ = _user
    clear_ephemeral_envs()
    return {"message": "已清空所有临时沙箱测试环境"}
