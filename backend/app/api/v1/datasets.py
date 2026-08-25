"""P3.B 测试数据集 API：CRUD + CSV/JSON 上传。

默认小数据集直存数据库；显式选择 MinIO 或上传内容超过数据库阈值时，rows
存入对象存储，数据库只保留引用和元数据。
"""

from __future__ import annotations

import csv
import io
import json
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    assert_project_access,
    get_current_user,
    require_admin,
    require_project_access,
)
from app.core.cache_decorator import cached_json
from app.core.database import get_db
from app.core.redis_client import delete_json_cache_pattern, get_json_cache, set_json_cache
from app.models.dataset import TestDataset, TestDatasetVersion
from app.models.ai_llm_config import AILLMConfig
from app.models.project import Project
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
    DatasetAIGenerateIn,
    DatasetAIGenerateOut,
    DatasetStorageReconcileIn,
    DatasetStorageReconcileOut,
    TestDatasetCreate,
    TestDatasetListItem,
    TestDatasetOut,
    TestDatasetUpdate,
    TestDatasetVersionOut,
)
from app.services.dataset_schema import DatasetSchemaField, validate_dataset_rows
from app.services.dataset_storage import (
    DATASET_STORAGE_DATABASE,
    DATASET_STORAGE_MINIO,
    DatasetStorageError,
    DatasetStorageLimitError,
    cleanup_dataset_object_names,
    dataset_current_object_name,
    delete_dataset_objects,
    reconcile_dataset_objects,
    rows_from_source,
    upload_dataset_rows,
    validate_dataset_rows_size,
)
from app.services.ai_dataset_generator import generate_dataset_rows
from app.services.audit import write_audit_log

router = APIRouter(tags=["测试数据集"])

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


async def _invalidate_dataset_list_cache(project_id: int) -> None:
    try:
        await delete_json_cache_pattern(f"atp:datasets:list:project_id={project_id}")
    except Exception:
        return None


def _serialize_dataset_list(items: list[TestDatasetListItem]) -> list[dict]:
    return [item.model_dump(mode="json") for item in items]


def _deserialize_dataset_list(payload) -> list[TestDatasetListItem]:
    return [TestDatasetListItem(**item) for item in payload]


def _validate_rows(rows: list[dict], storage_mode: str = DATASET_STORAGE_DATABASE) -> None:
    try:
        validate_dataset_rows_size(rows, storage_mode)
    except DatasetStorageLimitError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _dataset_row_count(source: TestDataset | TestDatasetVersion) -> int:
    stored_count = getattr(source, "row_count", None)
    return int(stored_count) if stored_count is not None else len(getattr(source, "rows", None) or [])


def _storage_mode(source: TestDataset | TestDatasetVersion) -> str:
    return getattr(source, "storage_mode", None) or DATASET_STORAGE_DATABASE


def _store_current_rows(
    dataset: TestDataset,
    rows: list[dict],
    storage_mode: str,
    *,
    uploaded_object_names: list[str] | None = None,
) -> str | None:
    _validate_rows(rows, storage_mode)
    if storage_mode == DATASET_STORAGE_MINIO:
        if getattr(dataset, "object_name", None):
            object_name = upload_dataset_rows(
                project_id=dataset.project_id,
                dataset_id=dataset.id,
                rows=rows,
                object_name=dataset_current_object_name(dataset.project_id, dataset.id),
            )
        else:
            object_name = upload_dataset_rows(project_id=dataset.project_id, dataset_id=dataset.id, rows=rows)
        if uploaded_object_names is not None:
            uploaded_object_names.append(object_name)
        dataset.rows = []
        dataset.object_name = object_name
    else:
        dataset.rows = rows
        dataset.object_name = None
    dataset.storage_mode = storage_mode
    dataset.row_count = len(rows)
    return dataset.object_name


def _dataset_output(dataset: TestDataset, rows: list[dict] | None = None) -> TestDatasetOut:
    return TestDatasetOut.model_construct(
        id=dataset.id,
        name=dataset.name,
        description=dataset.description,
        project_id=dataset.project_id,
        format=dataset.format,
        storage_mode=_storage_mode(dataset),
        row_count=_dataset_row_count(dataset),
        rows=rows if rows is not None else list(dataset.rows or []),
        schema_fields=dataset.schema_fields or [],
        validation_policy=_validation_policy(dataset),
        creator_id=dataset.creator_id,
        created_at=dataset.created_at,
        updated_at=dataset.updated_at,
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


def _cleanup_uploaded_objects(dataset: TestDataset, object_names: list[str]) -> None:
    if object_names:
        cleanup_dataset_object_names(dataset.project_id, dataset.id, object_names)


@router.post("/datasets/ai-generate", response_model=DatasetAIGenerateOut)
async def generate_dataset_with_ai(
    body: DatasetAIGenerateIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Generate rows for the dataset editor without persisting AI output."""
    await assert_project_access(db, user, body.project_id, ProjectRole.editor)
    project = await db.get(Project, body.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not project.ai_llm_config_id:
        raise HTTPException(status_code=400, detail="项目未配置 AI 模型")

    dataset = None
    if body.dataset_id is not None:
        dataset = await db.get(TestDataset, body.dataset_id)
        if dataset is None:
            raise HTTPException(status_code=404, detail="测试数据集不存在")
        if dataset.project_id != body.project_id:
            raise HTTPException(status_code=400, detail="测试数据集不属于当前项目")

    config = await db.get(AILLMConfig, project.ai_llm_config_id)
    if config is None:
        raise HTTPException(status_code=400, detail="项目关联的 AI 配置不存在")
    schema_fields = (
        _schema_fields_to_json(dataset.schema_fields or [])
        if dataset is not None
        else _schema_fields_to_json(body.schema_fields)
    )
    try:
        rows, inferred_schema, warnings = await generate_dataset_rows(
            config=config,
            schema_fields=schema_fields,
            requirement=body.requirement,
            row_count=body.row_count,
        )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="LLM 请求超时") from None
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"LLM 调用失败: {exc.response.status_code}") from exc
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="LLM 网络请求失败") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return DatasetAIGenerateOut(
        project_id=body.project_id,
        dataset_id=body.dataset_id,
        rows=rows,
        schema_fields=inferred_schema,
        warnings=warnings,
    )


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
    rows: list[dict] | None = None,
    uploaded_object_names: list[str] | None = None,
) -> TestDatasetVersion:
    version_number = await _next_dataset_version(db, dataset.id)
    storage_mode = _storage_mode(dataset)
    snapshot_rows = list(dataset.rows or [])
    snapshot_object_name = None
    if storage_mode == DATASET_STORAGE_MINIO:
        snapshot_rows = rows if rows is not None else rows_from_source(dataset)
        snapshot_object_name = upload_dataset_rows(
            project_id=dataset.project_id,
            dataset_id=dataset.id,
            rows=snapshot_rows,
            version=version_number,
        )
        if uploaded_object_names is not None:
            uploaded_object_names.append(snapshot_object_name)
    version = TestDatasetVersion(
        dataset_id=dataset.id,
        version=version_number,
        format=dataset.format,
        rows=snapshot_rows if storage_mode == DATASET_STORAGE_DATABASE else [],
        storage_mode=storage_mode,
        object_name=snapshot_object_name,
        row_count=_dataset_row_count(dataset),
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
        storage_mode=_storage_mode(version),
        row_count=_dataset_row_count(version),
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
    _validate_rows(rows, _storage_mode(dataset))
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
            row_count=_dataset_row_count(d),
            storage_mode=_storage_mode(d),
            schema_field_count=len(d.schema_fields or []),
            validation_policy=_validation_policy(d),
            creator_id=d.creator_id,
            created_at=d.created_at,
            updated_at=d.updated_at,
        )
        for d in items
    ]


@router.post(
    "/projects/{project_id}/datasets/storage/reconcile",
    response_model=DatasetStorageReconcileOut,
)
async def reconcile_project_dataset_storage(
    project_id: int,
    body: DatasetStorageReconcileIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Audit project-scoped MinIO dataset objects; purge only when explicit."""
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")

    current_result = await db.execute(
        select(TestDataset.object_name).where(
            TestDataset.project_id == project_id,
            TestDataset.object_name.is_not(None),
        )
    )
    version_result = await db.execute(
        select(TestDatasetVersion.object_name)
        .join(TestDataset, TestDatasetVersion.dataset_id == TestDataset.id)
        .where(
            TestDataset.project_id == project_id,
            TestDatasetVersion.object_name.is_not(None),
        )
    )
    referenced_object_names = {
        object_name
        for result in (current_result, version_result)
        for object_name in result.scalars().all()
        if object_name
    }
    try:
        result = reconcile_dataset_objects(
            project_id,
            referenced_object_names,
            purge=body.purge,
        )
    except DatasetStorageError as exc:
        raise HTTPException(status_code=503, detail=f"MinIO 数据集对象核对失败: {exc}") from exc

    await write_audit_log(
        db,
        action="dataset_storage_reconcile",
        resource_type="dataset_storage",
        resource_id=project_id,
        user_id=user.id,
        username=getattr(user, "username", ""),
        project_id=project_id,
        detail=(
            f"purge={body.purge}, scanned={result['scanned_count']}, "
            f"referenced={result['referenced_count']}, orphan={result['orphan_count']}, "
            f"deleted={result['deleted_count']}, errors={len(result['errors'])}"
        ),
    )
    await db.commit()
    return DatasetStorageReconcileOut(**result)


@router.post("/datasets", response_model=TestDatasetOut, status_code=status.HTTP_201_CREATED)
async def create_dataset(
    body: TestDatasetCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await assert_project_access(db, user, body.project_id, ProjectRole.editor)
    _validate_rows(body.rows, body.storage_mode)
    dataset = TestDataset(
        name=body.name,
        description=body.description,
        project_id=body.project_id,
        format=body.format,
        rows=[],
        storage_mode=body.storage_mode,
        schema_fields=_schema_fields_to_json(body.schema_fields),
        validation_policy=body.validation_policy,
        creator_id=user.id,
    )
    db.add(dataset)
    uploaded_object_names: list[str] = []
    try:
        if hasattr(db, "flush"):
            await db.flush()
        _store_current_rows(
            dataset,
            body.rows,
            body.storage_mode,
            uploaded_object_names=uploaded_object_names,
        )
        await _snapshot_dataset(
            db,
            dataset,
            created_by=user.id,
            change_type="create",
            rows=body.rows,
            uploaded_object_names=uploaded_object_names,
        )
        await db.commit()
        await _invalidate_dataset_list_cache(dataset.project_id)
    except DatasetStorageError as exc:
        await db.rollback()
        _cleanup_uploaded_objects(dataset, uploaded_object_names)
        raise HTTPException(status_code=503, detail=f"MinIO 数据集存储失败: {exc}") from exc
    except Exception:
        await db.rollback()
        _cleanup_uploaded_objects(dataset, uploaded_object_names)
        raise HTTPException(status_code=409, detail="数据集名称已被项目内占用")
    await db.refresh(dataset)
    return _dataset_output(dataset, body.rows if body.storage_mode == DATASET_STORAGE_MINIO else None)


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
    try:
        rows = rows_from_source(dataset)
    except DatasetStorageError as exc:
        raise HTTPException(status_code=503, detail=f"MinIO 数据集读取失败: {exc}") from exc
    return _dataset_output(dataset, rows)


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
    previous_object_name = getattr(dataset, "object_name", None)
    if body.name is not None:
        dataset.name = body.name
    if body.description is not None:
        dataset.description = body.description
    target_storage_mode = body.storage_mode or _storage_mode(dataset)
    rows_to_store = body.rows
    if rows_to_store is None and body.storage_mode is not None and body.storage_mode != _storage_mode(dataset):
        try:
            rows_to_store = rows_from_source(dataset)
        except DatasetStorageError as exc:
            raise HTTPException(status_code=503, detail=f"MinIO 数据集读取失败: {exc}") from exc
    if rows_to_store is not None:
        _validate_rows(rows_to_store, target_storage_mode)
    uploaded_object_names: list[str] = []
    try:
        if rows_to_store is not None:
            _store_current_rows(
                dataset,
                rows_to_store,
                target_storage_mode,
                uploaded_object_names=uploaded_object_names,
            )
        if body.schema_fields is not None:
            dataset.schema_fields = _schema_fields_to_json(body.schema_fields)
        if body.validation_policy is not None:
            dataset.validation_policy = body.validation_policy
        await _snapshot_dataset(
            db,
            dataset,
            created_by=user.id,
            change_type="update",
            rows=rows_to_store,
            uploaded_object_names=uploaded_object_names,
        )
        await db.commit()
    except DatasetStorageError as exc:
        await db.rollback()
        _cleanup_uploaded_objects(dataset, uploaded_object_names)
        raise HTTPException(status_code=503, detail=f"MinIO 数据集存储失败: {exc}") from exc
    except Exception as exc:
        await db.rollback()
        _cleanup_uploaded_objects(dataset, uploaded_object_names)
        raise HTTPException(status_code=409, detail="数据集更新失败，请检查名称或版本写入状态") from exc
    await _invalidate_dataset_list_cache(dataset.project_id)
    if previous_object_name and previous_object_name != getattr(dataset, "object_name", None):
        try:
            from app.core.minio_client import delete_file

            delete_file(previous_object_name)
        except Exception:
            pass
    await db.refresh(dataset)
    response_rows = None
    if target_storage_mode == DATASET_STORAGE_MINIO:
        if rows_to_store is not None:
            response_rows = rows_to_store
        else:
            try:
                response_rows = rows_from_source(dataset)
            except DatasetStorageError as exc:
                raise HTTPException(status_code=503, detail=f"MinIO 鏁版嵁闆嗚鍙栧け璐? {exc}") from exc
    return _dataset_output(dataset, response_rows)


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
    project_id = dataset.project_id
    await db.delete(dataset)
    await db.commit()
    await _invalidate_dataset_list_cache(project_id)
    try:
        delete_dataset_objects(project_id, dataset_id)
    except Exception:
        pass
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

    previous_object_name = getattr(dataset, "object_name", None)
    snapshot_storage_mode = _storage_mode(snapshot)
    uploaded_object_names: list[str] = []
    try:
        dataset.format = snapshot.format
        snapshot_rows = rows_from_source(snapshot)
        if snapshot_storage_mode == DATASET_STORAGE_MINIO:
            _store_current_rows(
                dataset,
                snapshot_rows,
                DATASET_STORAGE_MINIO,
                uploaded_object_names=uploaded_object_names,
            )
        else:
            dataset.rows = snapshot_rows
            dataset.object_name = None
            dataset.storage_mode = DATASET_STORAGE_DATABASE
            dataset.row_count = len(snapshot_rows)
        dataset.schema_fields = snapshot.schema_fields or []
        dataset.validation_policy = snapshot.validation_policy or "soft"
        await _snapshot_dataset(
            db,
            dataset,
            created_by=user.id,
            change_type=f"rollback:{version}",
            rows=snapshot_rows,
            uploaded_object_names=uploaded_object_names,
        )
        await db.commit()
    except DatasetStorageError as exc:
        await db.rollback()
        _cleanup_uploaded_objects(dataset, uploaded_object_names)
        raise HTTPException(status_code=503, detail=f"MinIO 数据集回滚失败: {exc}") from exc
    except Exception as exc:
        await db.rollback()
        _cleanup_uploaded_objects(dataset, uploaded_object_names)
        raise HTTPException(status_code=409, detail="数据集回滚失败，请检查版本写入状态") from exc
    await _invalidate_dataset_list_cache(dataset.project_id)
    if previous_object_name and previous_object_name != getattr(dataset, "object_name", None):
        try:
            from app.core.minio_client import delete_file

            delete_file(previous_object_name)
        except Exception:
            pass
    await db.refresh(dataset)
    return _dataset_output(dataset, snapshot_rows if snapshot_storage_mode == DATASET_STORAGE_MINIO else None)


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

    _validate_rows(rows, _storage_mode(dataset))
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
    previous_object_name = getattr(dataset, "object_name", None)
    uploaded_object_names: list[str] = []
    try:
        _store_current_rows(
            dataset,
            rows,
            _storage_mode(dataset),
            uploaded_object_names=uploaded_object_names,
        )
        dataset.format = new_format
        await _snapshot_dataset(
            db,
            dataset,
            created_by=user.id,
            change_type="upload",
            rows=rows,
            uploaded_object_names=uploaded_object_names,
        )
        await db.commit()
    except DatasetStorageError as exc:
        await db.rollback()
        _cleanup_uploaded_objects(dataset, uploaded_object_names)
        raise HTTPException(status_code=503, detail=f"MinIO 数据集存储失败: {exc}") from exc
    except Exception as exc:
        await db.rollback()
        _cleanup_uploaded_objects(dataset, uploaded_object_names)
        raise HTTPException(status_code=409, detail="数据集上传失败，请检查版本写入状态") from exc
    await _invalidate_dataset_list_cache(dataset.project_id)
    if previous_object_name and previous_object_name != getattr(dataset, "object_name", None):
        try:
            from app.core.minio_client import delete_file

            delete_file(previous_object_name)
        except Exception:
            pass
    await db.refresh(dataset)
    return _dataset_output(dataset, rows if _storage_mode(dataset) == DATASET_STORAGE_MINIO else None)
