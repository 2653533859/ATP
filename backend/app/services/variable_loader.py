"""全局与项目级环境变量加载辅助。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt, decrypt_env_vars
from app.models.environment import EnvVariable
from app.models.global_variable import GlobalVariable, ScopeType


async def load_global_variables_map(db: AsyncSession, project_id: int | None) -> dict[str, str]:
    """加载生效的全局变量：全局作用域 < 当前项目作用域。"""
    if project_id is not None:
        stmt = select(GlobalVariable).where(
            or_(
                GlobalVariable.scope_type == ScopeType.global_scope,
                and_(
                    GlobalVariable.scope_type == ScopeType.project,
                    GlobalVariable.project_id == project_id,
                ),
            )
        )
    else:
        stmt = select(GlobalVariable).where(GlobalVariable.scope_type == ScopeType.global_scope)

    execute_fn = getattr(db, "execute", None)
    if not callable(execute_fn):
        return {}
    result = await execute_fn(stmt)
    scalars_fn = getattr(result, "scalars", None)
    if not callable(scalars_fn):
        return {}
    rows = scalars_fn().all()

    global_vars: dict[str, str] = {}
    project_vars: dict[str, str] = {}
    for row in rows:
        key = getattr(row, "key", None)
        if not isinstance(key, str) or not key:
            continue
        raw_val = getattr(row, "value_encrypted", "")
        try:
            plain = decrypt(raw_val)
        except Exception:
            plain = str(raw_val or "")
        if getattr(row, "scope_type", None) == ScopeType.project:
            project_vars[key] = plain
        else:
            global_vars[key] = plain
    return {**global_vars, **project_vars}


async def load_environment_variables_map(db: AsyncSession, env_id: int) -> dict[str, str]:
    """加载并解密指定环境下的环境变量映射。"""
    execute_fn = getattr(db, "execute", None)
    if not callable(execute_fn):
        return {}
    result = await execute_fn(select(EnvVariable).where(EnvVariable.env_id == env_id))
    scalars_fn = getattr(result, "scalars", None)
    if not callable(scalars_fn):
        return {}
    return decrypt_env_vars(scalars_fn().all())
