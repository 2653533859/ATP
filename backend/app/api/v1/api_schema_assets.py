"""Project-scoped JSON Schema asset CRUD."""

from __future__ import annotations

import asyncio

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import assert_project_access, get_current_user, require_engineer
from app.core.database import get_db
from app.core.url_security import validate_public_http_url
from app.models.api_schema import ApiSchemaAsset
from app.models.project import Project
from app.models.user import User
from app.models.user_project import ProjectRole
from app.schemas.api_schema import ApiSchemaAssetCreate, ApiSchemaAssetOut, ApiSchemaAssetUpdate

router = APIRouter(tags=["API Schema 资产"])

_GRAPHQL_INTROSPECTION_QUERY = """
query ATPIntrospection {
  __schema {
    queryType { name }
    mutationType { name }
    subscriptionType { name }
    types {
      kind
      name
      fields(includeDeprecated: true) {
        name
        args { name type { kind name ofType { kind name } } }
        type { kind name ofType { kind name } }
      }
    }
  }
}
""".strip()


class GraphqlIntrospectionIn(BaseModel):
    endpoint: str = Field(min_length=1, max_length=2048)
    headers: dict[str, str] = Field(default_factory=dict)
    timeout: int = Field(default=15, ge=1, le=60)


class GraphqlFieldOut(BaseModel):
    operation_type: str
    parent_type: str
    name: str
    arguments: list[str]


class GraphqlIntrospectionOut(BaseModel):
    query_type: str | None = None
    mutation_type: str | None = None
    subscription_type: str | None = None
    fields: list[GraphqlFieldOut]


async def _ensure_project(db: AsyncSession, user: User, project_id: int, role: ProjectRole) -> None:
    await assert_project_access(db, user, project_id, role)
    if await db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="项目不存在")


@router.post("/projects/{project_id}/graphql/introspect", response_model=GraphqlIntrospectionOut)
async def introspect_graphql_schema(
    project_id: int,
    body: GraphqlIntrospectionIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_engineer),
):
    """读取公开 GraphQL 端点 Schema，返回用例编辑器所需的有限补全信息。"""
    await _ensure_project(db, user, project_id, ProjectRole.editor)
    try:
        endpoint = await asyncio.to_thread(validate_public_http_url, body.endpoint)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if len(body.headers) > 50 or any(len(key) > 128 or len(value) > 4096 for key, value in body.headers.items()):
        raise HTTPException(status_code=422, detail="GraphQL 请求头超出限制")
    try:
        async with httpx.AsyncClient(timeout=body.timeout, follow_redirects=False) as client:
            response = await client.post(
                endpoint,
                headers={"Content-Type": "application/json", **body.headers},
                json={"query": _GRAPHQL_INTROSPECTION_QUERY, "operationName": "ATPIntrospection"},
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"GraphQL Schema 读取失败: {type(exc).__name__}") from exc

    schema = (payload.get("data") or {}).get("__schema") if isinstance(payload, dict) else None
    if not isinstance(schema, dict):
        raise HTTPException(status_code=422, detail="GraphQL 端点未返回可用 introspection Schema")
    root_types = {
        "query": (schema.get("queryType") or {}).get("name"),
        "mutation": (schema.get("mutationType") or {}).get("name"),
        "subscription": (schema.get("subscriptionType") or {}).get("name"),
    }
    operation_by_parent = {name: operation for operation, name in root_types.items() if name}
    fields = []
    for item in schema.get("types") or []:
        parent_type = item.get("name") if isinstance(item, dict) else None
        operation_type = operation_by_parent.get(parent_type)
        if not operation_type:
            continue
        for field in item.get("fields") or []:
            if isinstance(field, dict) and field.get("name"):
                fields.append(
                    GraphqlFieldOut(
                        operation_type=operation_type,
                        parent_type=parent_type,
                        name=field["name"],
                        arguments=[arg.get("name") for arg in field.get("args") or [] if arg.get("name")],
                    )
                )
    return GraphqlIntrospectionOut(
        query_type=root_types["query"],
        mutation_type=root_types["mutation"],
        subscription_type=root_types["subscription"],
        fields=fields,
    )


@router.get("/projects/{project_id}/api-schema-assets", response_model=list[ApiSchemaAssetOut])
async def list_api_schema_assets(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _ensure_project(db, user, project_id, ProjectRole.viewer)
    result = await db.execute(
        select(ApiSchemaAsset)
        .where(ApiSchemaAsset.project_id == project_id)
        .order_by(ApiSchemaAsset.name.asc(), ApiSchemaAsset.id.asc())
    )
    return result.scalars().all()


@router.post(
    "/projects/{project_id}/api-schema-assets",
    response_model=ApiSchemaAssetOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_api_schema_asset(
    project_id: int,
    body: ApiSchemaAssetCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_engineer),
):
    await _ensure_project(db, user, project_id, ProjectRole.editor)
    item = ApiSchemaAsset(project_id=project_id, owner_id=user.id, **body.model_dump())
    db.add(item)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Schema 资产名称已存在") from exc
    await db.refresh(item)
    return item


@router.patch("/api-schema-assets/{asset_id}", response_model=ApiSchemaAssetOut)
async def update_api_schema_asset(
    asset_id: int,
    body: ApiSchemaAssetUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_engineer),
):
    item = await db.get(ApiSchemaAsset, asset_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Schema 资产不存在")
    await _ensure_project(db, user, item.project_id, ProjectRole.editor)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    if body.model_dump(exclude_unset=True):
        item.version += 1
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Schema 资产名称已存在") from exc
    await db.refresh(item)
    return item


@router.delete("/api-schema-assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_schema_asset(
    asset_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_engineer),
):
    item = await db.get(ApiSchemaAsset, asset_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Schema 资产不存在")
    await _ensure_project(db, user, item.project_id, ProjectRole.editor)
    await db.delete(item)
    await db.commit()
