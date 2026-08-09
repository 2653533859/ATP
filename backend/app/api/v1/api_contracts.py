from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import assert_project_access, get_current_user
from app.core.database import get_db
from app.models.api_contract_asset import ApiContractAsset
from app.models.user_project import ProjectRole
from app.schemas.api_contract import ApiContractCompareIn, ApiContractCompareOut
from app.schemas.api_contract_asset import ApiContractAssetCompareIn
from app.services.api_contracts import compare_contracts

router = APIRouter(tags=["API 契约"])


@router.post("/projects/{project_id}/api-contracts/compare", response_model=ApiContractCompareOut)
async def compare_api_contracts(
    project_id: int,
    body: ApiContractCompareIn,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """比较项目内两份 OpenAPI/Swagger 或 JSON Schema，返回兼容性结果。"""
    await assert_project_access(db, user, project_id, ProjectRole.editor)
    return compare_contracts(body.baseline, body.current)


@router.post("/projects/{project_id}/api-contracts/compare-assets", response_model=ApiContractCompareOut)
async def compare_api_contract_assets(
    project_id: int,
    body: ApiContractAssetCompareIn,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Compare two saved project contract versions without accepting cross-project assets."""
    await assert_project_access(db, user, project_id, ProjectRole.viewer)
    baseline = await db.get(ApiContractAsset, body.baseline_asset_id)
    current = await db.get(ApiContractAsset, body.current_asset_id)
    if baseline is None or current is None:
        raise HTTPException(status_code=404, detail="契约资产不存在")
    if baseline.project_id != project_id or current.project_id != project_id:
        raise HTTPException(status_code=404, detail="契约资产不属于当前项目")
    return compare_contracts(baseline.definition, current.definition)
