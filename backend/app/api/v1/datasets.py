"""P3.B 测试数据集 API：CRUD + CSV/JSON 上传。

存储约束：rows 直存 JSON 字段，限制 ≤500 行 / 序列化后 ≤256KB（MVP）。
超出建议改用 MinIO 引用（留下迭代）。
"""

from __future__ import annotations

import csv
import io
import json

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    assert_project_access,
    get_current_user,
    require_project_access,
)
from app.core.cache_decorator import cached_json
from app.core.database import get_db
from app.core.redis_client import get_json_cache, set_json_cache
from app.models.dataset import TestDataset, TestDatasetVersion
from app.models.case import TestCase
from app.models.plan import TestPlan
from app.models.suite import TestSuite
from app.models.user import User
from app.models.user_project import ProjectRole
from app.schemas.dataset import (
    DatasetValidateIn,
    DatasetValidateOut,
    DatasetImpactOut,
    DatasetImpactItemOut,
    TestDatasetCreate,
    TestDatasetListItem,
    TestDatasetOut,
    TestDatasetUpdate,
    TestDatasetVersionOut,
)
from app.services.dataset_schema import DatasetSchemaField, validate_dataset_rows

router = APIRouter(tags=["测试数据集"])

_MAX_ROWS = 500
_MAX_ROWS_BYTES = 256 * 1024
_DATASET_LIST_CACHE_TTL = 60


def _dataset_cache_key(name: str, **kwargs) -> str:
    items = ":".join(f"{key}={kwargs[key]}" for key in sorted(kwargs))
    return f"atp:datasets:{name}:{items}"


def _build_dataset_cache_key(name: str, *fields: str):
    def builder(**kwargs) -> str:
        return _dataset_cache_key(name, **{field: kwargs.get(field) for field in fields})

    return builder


async def _safe_get_dataset_cache(key: str):
    try:
        return await get_json_cache(key)
    except Exception:
        return None


async def _safe_set_dataset_cache(key: str, value) -> None:
    try:
        await set_json_cache(key, value, _DATASET_LIST_CACHE_TTL)
    except Exception:
        return None


def _serialize_dataset_list(items: list[TestDatasetListItem]) -> list[dict]:
    return [item.model_dump(mode="json") for item in items]


def _deserialize_dataset_list(payload) -> list[TestDatasetListItem]:
    return [TestDatasetListItem(**item) for item in payload]


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


def _parse_dataset_file(raw: bytes, filename: str, current_format: str) -> tuple[list[dict], str]:
    if not raw:
        raise HTTPException(status_code=400, detail="上传文件为空")

    filename = filename.lower()
    if filename.endswith(".csv") or current_format == "csv":
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
        return rows, "csv"

    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail=f"JSON 解析失败: {exc}")
    if not isinstance(parsed, list) or not all(isinstance(item, dict) for item in parsed):
        raise HTTPException(status_code=400, detail="JSON 顶层必须为对象数组")
    return parsed, "json"


def _schema_fields_from_payload(fields) -> list[DatasetSchemaField]:
    normalized: list[DatasetSchemaField] = []
    for field in fields or []:
        if hasattr(field, "model_dump"):
            raw = field.model_dump()
        else:
            raw = dict(field)
        normalized.append(
            DatasetSchemaField(
                name=raw.get("name", ""),
                type=raw.get("type", "string"),
                required=bool(raw.get("required", False)),
                default=raw.get("default"),
            )
        )
    return normalized


def _schema_fields_to_json(fields) -> list[dict]:
    return [field.model_dump() if hasattr(field, "model_dump") else dict(field) for field in (fields or [])]


def _validation_policy(dataset: TestDataset) -> str:
    return getattr(dataset, "validation_policy", None) or "soft"


def _can_upload_with_policy(valid: bool, policy: str) -> bool:
    return valid or policy == "soft"


async def _next_dataset_version(db: AsyncSession, dataset_id: int) -> int:
    result = await db.execute(
        select(func.coalesce(func.max(TestDatasetVersion.version), 0)).where(
            TestDatasetVersion.dataset_id == dataset_id
        )
    )
    return int(result.scalar_one() or 0) + 1


async def _snapshot_dataset(
    db: AsyncSession,
    dataset: TestDataset,
    *,
    created_by: int | None,
    change_type: str,
) -> TestDatasetVersion:
    version = TestDatasetVersion(
        dataset_id=dataset.id,
        version=await _next_dataset_version(db, dataset.id),
        format=dataset.format,
        rows=dataset.rows or [],
        schema_fields=dataset.schema_fields or [],
        validation_policy=_validation_policy(dataset),
        change_type=change_type,
        created_by=created_by,
    )
    db.add(version)
    return version


def _version_out(version: TestDatasetVersion) -> TestDatasetVersionOut:
    return TestDatasetVersionOut(
        id=version.id,
        dataset_id=version.dataset_id,
        version=version.version,
        format=version.format,
        row_count=len(version.rows or []),
        schema_field_count=len(version.schema_fields or []),
        validation_policy=version.validation_policy or "soft",
        change_type=version.change_type,
        created_by=version.created_by,
        created_at=version.created_at,
    )


def _json_references_dataset(value, dataset_id: int) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "dataset_id":
                try:
                    if int(item) == dataset_id:
                        return True
                except (TypeError, ValueError):
                    pass
            if _json_references_dataset(item, dataset_id):
                return True
    if isinstance(value, list):
        return any(_json_references_dataset(item, dataset_id) for item in value)
    return False


def _case_ids_from_suite(suite: TestSuite) -> set[int]:
    ids: set[int] = set()
    for item in suite.case_ids or []:
        if not isinstance(item, dict):
            continue
        try:
            ids.add(int(item.get("case_id")))
        except (TypeError, ValueError):
            continue
    return ids


def _suite_ids_from_plan(plan: TestPlan) -> set[int]:
    ids: set[int] = set()
    for item in plan.suite_ids or []:
        if not isinstance(item, dict):
            continue
        try:
            ids.add(int(item.get("suite_id")))
        except (TypeError, ValueError):
            continue
    return ids


@router.post("/datasets/validate", response_model=DatasetValidateOut)
async def validate_dataset(
    body: DatasetValidateIn,
    _: User = Depends(get_current_user),
):
    _validate_rows(body.rows)
    result = validate_dataset_rows(
        rows=body.rows,
        schema=_schema_fields_from_payload(body.schema_fields),
        preview_limit=body.preview_limit,
    )
    return DatasetValidateOut(
        valid=result.valid,
        row_count=result.row_count,
        normalized_rows=result.normalized_rows,
        issues=[
            {"row_index": issue.row_index, "field": issue.field, "message": issue.message} for issue in result.issues
        ],
        validation_policy=None,
        can_upload=None,
    )


@router.post("/datasets/{dataset_id}/upload-preview", response_model=DatasetValidateOut)
async def preview_upload_dataset(
    dataset_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    dataset = await db.get(TestDataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="数据集不存在")
    await assert_project_access(db, user, dataset.project_id, ProjectRole.editor)

    rows, _new_format = _parse_dataset_file(await file.read(), file.filename or "", dataset.format)
    _validate_rows(rows)
    result = validate_dataset_rows(
        rows=rows,
        schema=_schema_fields_from_payload(dataset.schema_fields or []),
        preview_limit=5,
    )
    policy = _validation_policy(dataset)
    return DatasetValidateOut(
        valid=result.valid,
        row_count=result.row_count,
        normalized_rows=result.normalized_rows,
        issues=[
            {"row_index": issue.row_index, "field": issue.field, "message": issue.message} for issue in result.issues
        ],
        validation_policy=policy,
        can_upload=_can_upload_with_policy(result.valid, policy),
    )


@router.get("/projects/{project_id}/datasets", response_model=list[TestDatasetListItem])
@cached_json(
    key_builder=_build_dataset_cache_key("list", "project_id"),
    serializer=_serialize_dataset_list,
    deserializer=_deserialize_dataset_list,
    read_cache=_safe_get_dataset_cache,
    write_cache=_safe_set_dataset_cache,
)
async def list_datasets(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_project_access(ProjectRole.viewer)),
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
            schema_field_count=len(d.schema_fields or []),
            validation_policy=_validation_policy(d),
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
    await assert_project_access(db, user, body.project_id, ProjectRole.editor)
    _validate_rows(body.rows)
    dataset = TestDataset(
        name=body.name,
        description=body.description,
        project_id=body.project_id,
        format=body.format,
        rows=body.rows,
        schema_fields=_schema_fields_to_json(body.schema_fields),
        validation_policy=body.validation_policy,
        creator_id=user.id,
    )
    db.add(dataset)
    try:
        if hasattr(db, "flush"):
            await db.flush()
        await _snapshot_dataset(db, dataset, created_by=user.id, change_type="create")
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
    user: User = Depends(get_current_user),
):
    dataset = await db.get(TestDataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="数据集不存在")
    await assert_project_access(db, user, dataset.project_id, ProjectRole.viewer)
    return dataset


@router.patch("/datasets/{dataset_id}", response_model=TestDatasetOut)
async def update_dataset(
    dataset_id: int,
    body: TestDatasetUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    dataset = await db.get(TestDataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="数据集不存在")
    await assert_project_access(db, user, dataset.project_id, ProjectRole.editor)
    if body.name is not None:
        dataset.name = body.name
    if body.description is not None:
        dataset.description = body.description
    if body.rows is not None:
        _validate_rows(body.rows)
        dataset.rows = body.rows
    if body.schema_fields is not None:
        dataset.schema_fields = _schema_fields_to_json(body.schema_fields)
    if body.validation_policy is not None:
        dataset.validation_policy = body.validation_policy
    await _snapshot_dataset(db, dataset, created_by=user.id, change_type="update")
    await db.commit()
    await db.refresh(dataset)
    return dataset


@router.delete("/datasets/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset(
    dataset_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    dataset = await db.get(TestDataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="数据集不存在")
    await assert_project_access(db, user, dataset.project_id, ProjectRole.editor)
    # 引用检查：被用例绑定时拒绝（依赖 MVP-B 引入的 case.dataset_id 字段；
    # 如果该字段还未存在则跳过本检查——MVP-A 阶段无引用风险）
    from sqlalchemy import select as _select

    from app.models.case import TestCase

    if hasattr(TestCase, "dataset_id"):
        ref = await db.execute(_select(TestCase.id).where(TestCase.dataset_id == dataset_id).limit(1))
        if ref.scalar_one_or_none() is not None:
            raise HTTPException(status_code=409, detail="数据集被用例引用，请先解绑")
    await db.delete(dataset)
    await db.commit()
    return None


@router.get("/datasets/{dataset_id}/impact", response_model=DatasetImpactOut)
async def get_dataset_impact(
    dataset_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    dataset = await db.get(TestDataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="数据集不存在")
    await assert_project_access(db, user, dataset.project_id, ProjectRole.viewer)

    case_result = await db.execute(select(TestCase).where(TestCase.dataset_id == dataset_id))
    cases = list(case_result.scalars().all())
    case_ids = {case.id for case in cases}

    suite_result = await db.execute(select(TestSuite).where(TestSuite.project_id == dataset.project_id))
    impacted_suites: list[DatasetImpactItemOut] = []
    impacted_suite_ids: set[int] = set()
    for suite in suite_result.scalars().all():
        reasons: list[str] = []
        if _case_ids_from_suite(suite) & case_ids:
            reasons.append("contains_dataset_cases")
        if _json_references_dataset(suite.parameterization or {}, dataset_id):
            reasons.append("suite_parameterization")
        if reasons:
            impacted_suite_ids.add(suite.id)
            impacted_suites.append(DatasetImpactItemOut(id=suite.id, name=suite.name, reason=",".join(reasons)))

    plan_result = await db.execute(select(TestPlan).where(TestPlan.project_id == dataset.project_id))
    impacted_plans = [
        DatasetImpactItemOut(id=plan.id, name=plan.name, reason="contains_dataset_suites")
        for plan in plan_result.scalars().all()
        if _suite_ids_from_plan(plan) & impacted_suite_ids
    ]

    impacted_cases = [DatasetImpactItemOut(id=case.id, name=case.name, reason="case_dataset_binding") for case in cases]
    return DatasetImpactOut(
        dataset_id=dataset_id,
        cases=impacted_cases,
        suites=impacted_suites,
        plans=impacted_plans,
        total_count=len(impacted_cases) + len(impacted_suites) + len(impacted_plans),
    )


@router.get("/datasets/{dataset_id}/versions", response_model=list[TestDatasetVersionOut])
async def list_dataset_versions(
    dataset_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    dataset = await db.get(TestDataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="数据集不存在")
    await assert_project_access(db, user, dataset.project_id, ProjectRole.viewer)
    result = await db.execute(
        select(TestDatasetVersion)
        .where(TestDatasetVersion.dataset_id == dataset_id)
        .order_by(TestDatasetVersion.version.desc())
    )
    return [_version_out(version) for version in result.scalars().all()]


@router.post("/datasets/{dataset_id}/rollback/{version}", response_model=TestDatasetOut)
async def rollback_dataset(
    dataset_id: int,
    version: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    dataset = await db.get(TestDataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="数据集不存在")
    await assert_project_access(db, user, dataset.project_id, ProjectRole.editor)
    result = await db.execute(
        select(TestDatasetVersion).where(
            TestDatasetVersion.dataset_id == dataset_id,
            TestDatasetVersion.version == version,
        )
    )
    snapshot = result.scalar_one_or_none()
    if snapshot is None:
        raise HTTPException(status_code=404, detail="数据集版本不存在")

    dataset.format = snapshot.format
    dataset.rows = snapshot.rows or []
    dataset.schema_fields = snapshot.schema_fields or []
    dataset.validation_policy = snapshot.validation_policy or "soft"
    await _snapshot_dataset(db, dataset, created_by=user.id, change_type=f"rollback:{version}")
    await db.commit()
    await db.refresh(dataset)
    return dataset


@router.post("/datasets/{dataset_id}/upload", response_model=TestDatasetOut)
async def upload_dataset(
    dataset_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """上传 CSV 或 JSON 文件覆盖数据集 rows。

    - CSV：首行 header → 后续行映射为 dict；全空白行跳过
    - JSON：要求顶层数组 `[{...}, {...}]`
    """
    dataset = await db.get(TestDataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="数据集不存在")
    await assert_project_access(db, user, dataset.project_id, ProjectRole.editor)

    rows, new_format = _parse_dataset_file(await file.read(), file.filename or "", dataset.format)

    _validate_rows(rows)
    validation = validate_dataset_rows(
        rows=rows,
        schema=_schema_fields_from_payload(dataset.schema_fields or []),
        preview_limit=0,
    )
    policy = _validation_policy(dataset)
    if not _can_upload_with_policy(validation.valid, policy):
        raise HTTPException(
            status_code=400,
            detail=f"数据集 schema 校验失败，hard-block 策略已拒绝覆盖；共 {len(validation.issues)} 个问题",
        )
    dataset.rows = rows
    dataset.format = new_format
    await _snapshot_dataset(db, dataset, created_by=user.id, change_type="upload")
    await db.commit()
    await db.refresh(dataset)
    return dataset
