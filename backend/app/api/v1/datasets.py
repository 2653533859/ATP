"""P3.B 测试数据集 API：CRUD + CSV/JSON 上传。

存储约束：rows 直存 JSON 字段，限制 ≤500 行 / 序列化后 ≤256KB（MVP）。
超出建议改用 MinIO 引用（留下迭代）。
"""
from __future__ import annotations

import csv
import io
import json

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.dataset import TestDataset
from app.models.user import User
from app.schemas.dataset import (
    TestDatasetCreate,
    TestDatasetListItem,
    TestDatasetOut,
    TestDatasetUpdate,
)

router = APIRouter(tags=["测试数据集"])

_MAX_ROWS = 500
_MAX_ROWS_BYTES = 256 * 1024


def _validate_rows(rows: list[dict]) -> None:
    if len(rows) > _MAX_ROWS:
        raise HTTPException(
            status_code=400,
            detail=f"行数超过 {_MAX_ROWS} 上限；请拆分或改用 MinIO 引用模式",
        )
    serialized = json.dumps(rows, ensure_ascii=False)
    if len(serialized.encode("utf-8")) > _MAX_ROWS_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"序列化后超过 {_MAX_ROWS_BYTES // 1024}KB；请精简或拆分",
        )


@router.get("/projects/{project_id}/datasets", response_model=list[TestDatasetListItem])
async def list_datasets(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(TestDataset).where(TestDataset.project_id == project_id).order_by(TestDataset.id.desc())
    )
    items = result.scalars().all()
    return [
        TestDatasetListItem(
            id=d.id,
            name=d.name,
            description=d.description,
            project_id=d.project_id,
            format=d.format,
            row_count=len(d.rows or []),
            creator_id=d.creator_id,
            created_at=d.created_at,
            updated_at=d.updated_at,
        )
        for d in items
    ]


@router.post("/datasets", response_model=TestDatasetOut, status_code=status.HTTP_201_CREATED)
async def create_dataset(
    body: TestDatasetCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _validate_rows(body.rows)
    dataset = TestDataset(
        name=body.name,
        description=body.description,
        project_id=body.project_id,
        format=body.format,
        rows=body.rows,
        creator_id=user.id,
    )
    db.add(dataset)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=409, detail="数据集名称已被项目内占用")
    await db.refresh(dataset)
    return dataset


@router.get("/datasets/{dataset_id}", response_model=TestDatasetOut)
async def get_dataset(
    dataset_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    dataset = await db.get(TestDataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="数据集不存在")
    return dataset


@router.patch("/datasets/{dataset_id}", response_model=TestDatasetOut)
async def update_dataset(
    dataset_id: int,
    body: TestDatasetUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    dataset = await db.get(TestDataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="数据集不存在")
    if body.name is not None:
        dataset.name = body.name
    if body.description is not None:
        dataset.description = body.description
    if body.rows is not None:
        _validate_rows(body.rows)
        dataset.rows = body.rows
    await db.commit()
    await db.refresh(dataset)
    return dataset


@router.delete("/datasets/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset(
    dataset_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    dataset = await db.get(TestDataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="数据集不存在")
    # 引用检查：被用例绑定时拒绝（依赖 MVP-B 引入的 case.dataset_id 字段；
    # 如果该字段还未存在则跳过本检查——MVP-A 阶段无引用风险）
    from sqlalchemy import select as _select

    from app.models.case import TestCase

    if hasattr(TestCase, "dataset_id"):
        ref = await db.execute(
            _select(TestCase.id).where(TestCase.dataset_id == dataset_id).limit(1)
        )
        if ref.scalar_one_or_none() is not None:
            raise HTTPException(status_code=409, detail="数据集被用例引用，请先解绑")
    await db.delete(dataset)
    await db.commit()
    return None


@router.post("/datasets/{dataset_id}/upload", response_model=TestDatasetOut)
async def upload_dataset(
    dataset_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """上传 CSV 或 JSON 文件覆盖数据集 rows。

    - CSV：首行 header → 后续行映射为 dict；全空白行跳过
    - JSON：要求顶层数组 `[{...}, {...}]`
    """
    dataset = await db.get(TestDataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="数据集不存在")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="上传文件为空")

    filename = (file.filename or "").lower()
    rows: list[dict]
    if filename.endswith(".csv") or dataset.format == "csv":
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="CSV 文件需为 UTF-8 编码")
        reader = csv.DictReader(io.StringIO(text))
        rows = [
            {k: (v or "") for k, v in row.items() if k is not None}
            for row in reader
            if any((v or "").strip() for v in row.values())
        ]
        new_format = "csv"
    else:
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=400, detail=f"JSON 解析失败: {exc}")
        if not isinstance(parsed, list) or not all(isinstance(item, dict) for item in parsed):
            raise HTTPException(status_code=400, detail="JSON 顶层必须为对象数组")
        rows = parsed
        new_format = "json"

    _validate_rows(rows)
    dataset.rows = rows
    dataset.format = new_format
    await db.commit()
    await db.refresh(dataset)
    return dataset
