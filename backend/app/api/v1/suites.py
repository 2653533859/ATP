"""
测试套件管理 API

POST   /suites              创建套件
GET    /suites              套件列表
GET    /suites/{id}         套件详情
PATCH  /suites/{id}         更新套件
DELETE /suites/{id}         删除套件
POST   /suites/{id}/run     触发套件执行
GET    /suite-runs           套件执行记录列表
GET    /suite-runs/{id}     套件执行记录详情
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from app.models.hermes_action import HermesAction
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.config import settings
from app.core.encryption import decrypt_env_vars
from app.core.tracing import get_trace_id
from app.models.case import TestCase
from app.models.environment import Environment, EnvVariable
from app.models.project import Project
from app.models.suite import SuiteRun, SuiteRunStatus, TestSuite
from app.models.user import User
from app.schemas.suite import (
    TestSuiteCreate,
    TestSuiteUpdate,
    TestSuiteOut,
    SuiteRunTrigger,
    SuiteRunOut,
    SuiteBatchCopyIn,
    SuiteBatchDeleteIn,
    SuiteBatchOpOut,
)
from app.api.deps import assert_project_access, get_current_user
from app.models.user_project import ProjectRole
from app.services.execution_routing import resolve_suite_execution_queue
from app.services.api_scenario import ApiScenarioError, build_api_scenario_policy
from app.services.project_scope import scope_to_visible_projects
from app.services.hermes_commands import (
    CommandAction,
    CommandConflict,
    command_request_hash,
    command_resource,
    record_command,
    replay_command,
)
from app.schemas.execution_dispatch import ExecutionDispatchOut
from app.services.execution_dispatch import get_suite_dispatch, record_suite_dispatch, wake_dispatcher

router = APIRouter(tags=["测试套件"])


async def _replay_suite_command(
    db: AsyncSession,
    *,
    user_id: int,
    project_id: int,
    command_id: str | None,
    action: CommandAction,
    request_hash: str,
) -> TestSuite | SuiteRun | None:
    try:
        return await replay_command(
            db,
            user_id=user_id,
            project_id=project_id,
            command_id=command_id,
            action=action,
            request_hash=request_hash,
        )
    except CommandConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None


def _validate_suite_fixtures(config: object) -> None:
    if not isinstance(config, dict):
        return
    shared_variables = config.get("shared_variables", {})
    if not isinstance(shared_variables, dict) or len(shared_variables) > 100:
        raise HTTPException(status_code=422, detail="套件共享变量必须是最多 100 项的对象")
    fixtures = config.get("fixtures", {})
    if not isinstance(fixtures, dict):
        raise HTTPException(status_code=422, detail="Suite Fixtures 必须是对象")
    allowed_actions = {"set_variable", "delete_variable", "assert"}
    for phase in ("setup", "teardown"):
        actions = fixtures.get(phase, [])
        if not isinstance(actions, list) or len(actions) > 50:
            raise HTTPException(status_code=422, detail=f"Suite Fixture {phase} 必须是最多 50 项的数组")
        if any(not isinstance(action, dict) or action.get("action") not in allowed_actions for action in actions):
            raise HTTPException(status_code=422, detail=f"Suite Fixture {phase} 包含不受支持的动作")


def _normalize_case_items(case_items: list[object]) -> list[dict]:
    return [item if isinstance(item, dict) else item.model_dump() for item in case_items]


async def _validate_suite_case_ids(db: AsyncSession, project_id: int, case_items: list[object]) -> list[dict]:
    normalized = _normalize_case_items(case_items)
    case_ids = [item["case_id"] for item in normalized]

    if len(case_ids) != len(set(case_ids)):
        raise HTTPException(status_code=400, detail="套件中包含重复用例")

    if not case_ids:
        return normalized

    result = await db.execute(select(TestCase).options(selectinload(TestCase.module)).where(TestCase.id.in_(case_ids)))
    cases = result.scalars().all()
    if settings.ATP_LOCAL_MODE and any(
        str(getattr(case.case_type, "value", case.case_type)) == "ios" for case in cases
    ):
        raise HTTPException(status_code=409, detail="本地套件不支持 iOS 用例")
    case_map = {case.id: case for case in cases}

    missing_case_id = next((case_id for case_id in case_ids if case_id not in case_map), None)
    if missing_case_id is not None:
        raise HTTPException(status_code=400, detail=f"用例不存在: {missing_case_id}")

    wrong_project_case_id = next(
        (
            case_id
            for case_id in case_ids
            if getattr(getattr(case_map[case_id], "module", None), "project_id", None) != project_id
        ),
        None,
    )
    if wrong_project_case_id is not None:
        raise HTTPException(status_code=400, detail=f"用例 {wrong_project_case_id} 不属于当前项目")

    return normalized


async def _validate_parallel_api_session_reuse(
    db: AsyncSession,
    case_items: list[object],
    config: object,
) -> None:
    """Reject nondeterministic project-cookie reuse inside parallel suites."""
    if not isinstance(config, dict) or config.get("execution_mode") != "parallel":
        return
    normalized = _normalize_case_items(case_items)
    case_ids = [item["case_id"] for item in normalized]
    if not case_ids:
        return

    rows = (await db.execute(select(TestCase).where(TestCase.id.in_(case_ids)))).scalars().all()
    for case in rows:
        case_type = getattr(getattr(case, "case_type", None), "value", getattr(case, "case_type", None))
        if case_type != "api":
            continue
        try:
            policy = build_api_scenario_policy(getattr(case, "config", None) or {})
        except ApiScenarioError:
            # The executor will return the existing detailed scenario error.
            continue
        if policy.session_lifecycle == "reuse":
            raise HTTPException(
                status_code=400,
                detail="并行套件不能包含开启项目 API 登录态复用的用例，请改为串行执行或关闭该用例的登录态复用",
            )


@router.post("/suites", response_model=TestSuiteOut, status_code=status.HTTP_201_CREATED)
async def create_suite(
    body: TestSuiteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await assert_project_access(db, current_user, body.project_id, ProjectRole.editor)
    user_id = current_user.id
    project = await db.get(Project, body.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    request_hash = command_request_hash(body.model_dump(exclude={"command_id"}))
    command_args = {
        "user_id": user_id,
        "project_id": body.project_id,
        "command_id": body.command_id,
        "action": "create_suite",
        "request_hash": request_hash,
    }
    existing = await _replay_suite_command(db, **command_args)
    if existing is not None:
        return existing
    case_ids = await _validate_suite_case_ids(db, body.project_id, body.case_ids)
    _validate_suite_fixtures(body.config)
    await _validate_parallel_api_session_reuse(db, case_ids, body.config)

    suite = TestSuite(
        name=body.name,
        description=body.description,
        project_id=body.project_id,
        case_ids=case_ids,
        parameterization=body.parameterization,
        config=body.config,
        creator_id=current_user.id,
    )
    db.add(suite)
    if body.command_id:
        await db.flush()
        record_command(db, **command_args, resource=suite)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        if not body.command_id:
            raise
        existing = await _replay_suite_command(db, **command_args)
        if existing is None:
            raise HTTPException(status_code=409, detail="操作提交冲突，请检查处理记录") from None
        return existing
    await db.refresh(suite)
    return suite


@router.get("/hermes/action-records")
async def list_hermes_action_records(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await assert_project_access(db, user, project_id, ProjectRole.viewer)
    records = (
        await db.scalars(
            select(HermesAction)
            .where(HermesAction.project_id == project_id, HermesAction.user_id == user.id)
            .order_by(HermesAction.id.desc())
            .limit(20)
        )
    ).all()
    output = []
    for item in records:
        resource, resource_state = await command_resource(db, item)
        run = resource if isinstance(resource, SuiteRun) else None
        dispatch = await get_suite_dispatch(db, run) if run is not None else None
        output.append(
            {
                "command_id": item.command_id,
                "action": item.action,
                "resource_id": item.resource_id,
                "created_at": item.created_at,
                "status": "completed",
                "run_status": run.status if run else None,
                "resource_state": resource_state,
                "resource_unverified": resource_state == "unverified",
                "resource_missing": resource_state in {"missing", "replaced"},
                "dispatch_status": dispatch.status if dispatch is not None else None,
                "dispatch_error_code": dispatch.error_code if dispatch is not None else None,
            }
        )
    return output


@router.get("/suites", response_model=list[TestSuiteOut])
async def list_suites(
    project_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    if project_id is not None:
        await assert_project_access(db, user, project_id, ProjectRole.viewer)
    q = scope_to_visible_projects(select(TestSuite), TestSuite.project_id, user, project_id).order_by(
        TestSuite.created_at.desc()
    )
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/suites/{suite_id}", response_model=TestSuiteOut)
async def get_suite(
    suite_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    suite = await db.get(TestSuite, suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="套件不存在")
    await assert_project_access(db, user, suite.project_id, ProjectRole.viewer)
    return suite


@router.patch("/suites/{suite_id}", response_model=TestSuiteOut)
async def update_suite(
    suite_id: int,
    body: TestSuiteUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    suite = await db.get(TestSuite, suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="套件不存在")
    await assert_project_access(db, user, suite.project_id, ProjectRole.editor)

    update_data = body.model_dump(exclude_none=True)
    if "case_ids" in update_data:
        update_data["case_ids"] = await _validate_suite_case_ids(db, suite.project_id, update_data["case_ids"])
    _validate_suite_fixtures(update_data.get("config", suite.config))
    await _validate_parallel_api_session_reuse(
        db,
        update_data.get("case_ids", suite.case_ids or []),
        update_data.get("config", suite.config),
    )
    for k, v in update_data.items():
        setattr(suite, k, v)
    await db.commit()
    await db.refresh(suite)
    return suite


@router.delete("/suites/{suite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_suite(
    suite_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    suite = await db.get(TestSuite, suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="套件不存在")
    await assert_project_access(db, user, suite.project_id, ProjectRole.editor)
    await db.delete(suite)
    await db.commit()


@router.post("/suites/batch/delete", response_model=SuiteBatchOpOut)
async def batch_delete_suites(
    body: SuiteBatchDeleteIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    requested_ids = list(dict.fromkeys(body.suite_ids))
    rows = (await db.execute(select(TestSuite).where(TestSuite.id.in_(requested_ids)))).scalars().all()
    for suite in rows:
        await assert_project_access(db, current_user, suite.project_id, ProjectRole.editor)
    found_ids = {row.id for row in rows}
    skipped_ids = [sid for sid in requested_ids if sid not in found_ids]

    for suite in rows:
        await db.delete(suite)
    await db.commit()
    return SuiteBatchOpOut(
        requested=len(requested_ids),
        processed=len(rows),
        skipped_ids=skipped_ids,
    )


@router.post("/suites/batch/copy", response_model=SuiteBatchOpOut)
async def batch_copy_suites(
    body: SuiteBatchCopyIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    requested_ids = list(dict.fromkeys(body.suite_ids))
    rows = (await db.execute(select(TestSuite).where(TestSuite.id.in_(requested_ids)))).scalars().all()
    for suite in rows:
        await assert_project_access(db, current_user, suite.project_id, ProjectRole.editor)
    found_ids = {row.id for row in rows}
    skipped_ids = [sid for sid in requested_ids if sid not in found_ids]

    created_ids: list[int] = []
    for src in rows:
        clone = TestSuite(
            name=f"{src.name}{body.suffix}",
            description=src.description,
            project_id=src.project_id,
            case_ids=list(src.case_ids or []),
            parameterization=dict(src.parameterization or {}) if src.parameterization else {},
            config=dict(src.config or {}),
            creator_id=current_user.id,
        )
        db.add(clone)
        await db.flush()
        created_ids.append(clone.id)
    await db.commit()
    return SuiteBatchOpOut(
        requested=len(requested_ids),
        processed=len(created_ids),
        skipped_ids=skipped_ids,
        created_ids=created_ids,
    )


@router.post("/suites/{suite_id}/run", response_model=SuiteRunOut, status_code=status.HTTP_202_ACCEPTED)
async def trigger_suite_run(
    suite_id: int,
    body: SuiteRunTrigger,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    suite = await db.get(TestSuite, suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="套件不存在")
    await assert_project_access(db, current_user, suite.project_id, ProjectRole.editor)
    user_id = current_user.id
    project_id = suite.project_id
    request_hash = command_request_hash(
        {
            "suite_id": suite_id,
            "suite_identity": suite.identity_token,
            **body.model_dump(exclude={"command_id"}),
        }
    )
    command_args = {
        "user_id": user_id,
        "project_id": project_id,
        "command_id": body.command_id,
        "action": "run_suite",
        "request_hash": request_hash,
    }
    original = await _replay_suite_command(db, **command_args)
    if original is not None:
        return original
    if not suite.case_ids:
        raise HTTPException(status_code=400, detail="套件中没有用例")

    # 解析环境变量
    env_name: str | None = None
    merged_vars = dict(body.extra_vars)
    if body.env_id is not None:
        env = await db.get(Environment, body.env_id)
        if not env:
            raise HTTPException(status_code=404, detail="环境不存在")
        if env.project_id != suite.project_id:
            raise HTTPException(status_code=400, detail="环境不属于套件所在项目")
        env_name = env.name
        result = await db.execute(select(EnvVariable).where(EnvVariable.env_id == env.id))
        env_vars = decrypt_env_vars(result.scalars().all())
        merged_vars = {**env_vars, **body.extra_vars}

    suite_run = SuiteRun(
        suite_id=suite_id,
        triggered_by=current_user.id,
        trace_id=get_trace_id() or None,
        status=SuiteRunStatus.pending,
        environment=env_name,
    )
    db.add(suite_run)
    # 先解析路由，避免路由失败留下无法投递的新运行。
    queue = await resolve_suite_execution_queue(db, suite)
    await db.flush()
    record_command(db, **command_args, resource=suite_run)
    record_suite_dispatch(db, run=suite_run, project_id=project_id, extra_vars=merged_vars, queue=queue)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        if not body.command_id:
            raise
        original = await _replay_suite_command(db, **command_args)
        if original is None:
            raise HTTPException(status_code=409, detail="运行提交冲突，请查看处理记录") from None
        return original
    await db.refresh(suite_run)

    # 唤醒只是延迟优化；即使此处退出，后台/重启扫描仍能发现已提交意图。
    wake_dispatcher()

    return suite_run


@router.get("/suite-runs/{run_id}/dispatch", response_model=ExecutionDispatchOut | None)
async def get_suite_run_dispatch(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    run = await db.get(SuiteRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="套件执行记录不存在")
    suite = await db.get(TestSuite, run.suite_id)
    if suite is None:
        raise HTTPException(status_code=404, detail="套件不存在")
    await assert_project_access(db, user, suite.project_id, ProjectRole.viewer)
    return await get_suite_dispatch(db, run)


@router.get("/suite-runs", response_model=list[SuiteRunOut])
async def list_suite_runs(
    suite_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = scope_to_visible_projects(
        select(SuiteRun).join(TestSuite, SuiteRun.suite_id == TestSuite.id),
        TestSuite.project_id,
        _,
    ).order_by(SuiteRun.created_at.desc())
    if suite_id is not None:
        q = q.where(SuiteRun.suite_id == suite_id)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/suite-runs/{run_id}", response_model=SuiteRunOut)
async def get_suite_run(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    suite_run = await db.get(SuiteRun, run_id)
    if not suite_run:
        raise HTTPException(status_code=404, detail="套件执行记录不存在")
    suite = await db.get(TestSuite, suite_run.suite_id)
    if not suite:
        raise HTTPException(status_code=404, detail="套件不存在")
    await assert_project_access(db, _, suite.project_id, ProjectRole.viewer)
    return suite_run
