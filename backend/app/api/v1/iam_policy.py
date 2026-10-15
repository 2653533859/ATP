"""Fine-Grained RBAC & Resource Action Policy Decision Point API Router (T4.2)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_project_role, require_admin
from app.core.database import get_db
from app.models.user import User
from app.services.fine_grained_iam_policy import (
    PolicyRule,
    evaluate_iam_policy,
    list_effective_policies,
    register_custom_policy,
)

router = APIRouter(prefix="/iam", tags=["企业级细粒度 IAM 策略控制"])


class EvaluatePolicyIn(BaseModel):
    resource_kind: str = Field(description="资源类型: case, suite, plan, device, secret, dataset, mesh_chaos")
    action: str = Field(description="操作动作: read, execute, create, modify, delete, manage_permissions")
    project_id: int | None = Field(default=None, description="上下文当前项目ID")
    resource_project_id: int | None = Field(default=None, description="目标资产所属项目ID")


class RegisterPolicyIn(BaseModel):
    rule_id: str = Field(min_length=3, max_length=64)
    effect: str = Field(pattern="^(allow|deny)$")
    principals: list[str] = Field(min_length=1)
    resources: list[str] = Field(min_length=1)
    actions: list[str] = Field(min_length=1)
    description: str = Field(default="")
    enabled: bool = True


@router.post("/evaluate")
async def evaluate_policy_endpoint(
    body: EvaluatePolicyIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """在线评估当前登录用户对指定资源操作的细粒度 RBAC 策略判定结果。"""
    proj_role = None
    if body.project_id is not None:
        proj_role = await get_project_role(db, current_user, body.project_id)

    decision = evaluate_iam_policy(
        user_role=current_user.role,
        project_role=proj_role,
        resource_kind=body.resource_kind,
        action=body.action,
        project_id=body.project_id,
        resource_project_id=body.resource_project_id,
    )
    return decision.to_dict()


@router.get("/policies")
async def list_policies_endpoint(
    _user: User = Depends(get_current_user),
):
    """获取平台当前生效的细粒度 RBAC 与资源操作安全策略清单。"""
    _ = _user
    policies = list_effective_policies()
    return {
        "total": len(policies),
        "policies": [
            {
                "rule_id": p.rule_id,
                "effect": p.effect,
                "principals": p.principals,
                "resources": p.resources,
                "actions": p.actions,
                "description": p.description,
                "enabled": p.enabled,
            }
            for p in policies
        ],
    }


@router.post("/policies")
async def register_policy_endpoint(
    body: RegisterPolicyIn,
    _admin: User = Depends(require_admin),
):
    """注册自定义企业细粒度安全规则 (需系统管理员权限)。"""
    _ = _admin
    rule = PolicyRule(
        rule_id=body.rule_id,
        effect=body.effect,
        principals=body.principals,
        resources=body.resources,
        actions=body.actions,
        description=body.description,
        enabled=body.enabled,
    )
    register_custom_policy(rule)
    return {"message": "自定义细粒度安全策略注册成功", "rule_id": rule.rule_id}
