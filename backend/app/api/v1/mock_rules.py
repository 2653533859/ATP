import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    assert_project_access,
    get_current_user,
    require_engineer,
    require_project_access,
)
from app.core.database import get_db
from app.models.mock import MockMethod, MockRule
from app.models.ai_llm_config import AILLMConfig
from app.models.mock_snapshot import MockRuleSnapshot
from app.models.project import Project
from app.models.user import User
from app.models.user_project import ProjectRole
from app.schemas.mock import (
    MockRuleCreate,
    MockAIGenerateIn,
    MockAIGenerateOut,
    MockRuleOut,
    MockRulePromoteSampleRequest,
    MockRuleSnapshotOut,
    MockRuleUpdate,
    MockRulesExportOut,
    MockRulesImportRequest,
    PaginatedMockSnapshotsOut,
)
from app.api.v1.mock_server import get_mock_logs, invalidate_mock_cache
from app.services.project_scope import scope_to_visible_projects
from app.services.ai_mock_generator import generate_mock_rule_drafts

router = APIRouter(tags=["mock-rules"])


def _bump_rule_version(rule: MockRule):
    rule.version = (rule.version or 1) + 1


def _serialize_rule(rule: MockRule) -> dict:
    """构造完整的规则快照 payload，用于版本历史与回滚。"""
    method_value = rule.method.value if hasattr(rule.method, "value") else rule.method
    return {
        "name": rule.name,
        "method": method_value,
        "path": rule.path,
        "status_code": rule.status_code,
        "response_headers": dict(rule.response_headers or {}),
        "response_body": rule.response_body,
        "match_conditions": dict(rule.match_conditions or {}),
        "delay_ms": rule.delay_ms,
        "is_enabled": rule.is_enabled,
        "render_template": rule.render_template,
        "record_requests": rule.record_requests,
        "version": rule.version,
    }


async def _persist_snapshot(
    db: AsyncSession,
    rule: MockRule,
    changed_by: int,
    note: str | None = None,
) -> MockRuleSnapshot:
    snapshot = MockRuleSnapshot(
        rule_id=rule.id,
        version=rule.version or 1,
        snapshot_data=_serialize_rule(rule),
        note=note,
        changed_by=changed_by,
    )
    db.add(snapshot)
    await db.flush()
    return snapshot


@router.post("/mock-rules/ai-generate", response_model=MockAIGenerateOut)
async def generate_mock_rules_with_ai(
    body: MockAIGenerateIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_engineer),
):
    """Generate editable Mock rule drafts without persisting AI output."""
    await assert_project_access(db, current_user, body.project_id, ProjectRole.editor)
    project = await db.get(Project, body.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not project.ai_llm_config_id:
        raise HTTPException(status_code=400, detail="项目未配置 AI 模型")

    source_rules = []
    seen_rule_ids: set[int] = set()
    for rule_id in body.rule_ids:
        if rule_id in seen_rule_ids:
            continue
        seen_rule_ids.add(rule_id)
        rule = await db.get(MockRule, rule_id)
        if rule is None:
            raise HTTPException(status_code=404, detail="参考 Mock 规则不存在")
        if rule.project_id != body.project_id:
            raise HTTPException(status_code=400, detail="参考 Mock 规则不属于当前项目")
        source_rules.append(rule)

    config = await db.get(AILLMConfig, project.ai_llm_config_id)
    if config is None:
        raise HTTPException(status_code=400, detail="项目关联的 AI 配置不存在")
    try:
        rules, warnings = await generate_mock_rule_drafts(
            config=config,
            source_rules=source_rules,
            requirement=body.requirement,
            rule_count=body.rule_count,
        )
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"LLM 调用失败: {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"LLM 网络错误: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return MockAIGenerateOut(project_id=body.project_id, rules=rules, warnings=warnings)


@router.post("/mock-rules", response_model=MockRuleOut, status_code=201)
async def create_mock_rule(
    body: MockRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_engineer),
):
    await assert_project_access(db, current_user, body.project_id, ProjectRole.editor)
    project = await db.get(Project, body.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    rule = MockRule(**body.model_dump(), creator_id=current_user.id)
    db.add(rule)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=404, detail="项目不存在") from exc
    await db.refresh(rule)
    await invalidate_mock_cache(rule.project_id)
    return rule


@router.post("/mock-rules/import", response_model=list[MockRuleOut])
async def import_mock_rules(
    body: MockRulesImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_engineer),
):
    await assert_project_access(db, current_user, body.project_id, ProjectRole.editor)
    project = await db.get(Project, body.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    created_rules = []
    for item in body.rules:
        payload = item.model_dump(exclude={"project_id"})
        rule = MockRule(**payload, project_id=body.project_id, creator_id=current_user.id)
        db.add(rule)
        created_rules.append(rule)
    await db.commit()
    for rule in created_rules:
        await db.refresh(rule)
    await invalidate_mock_cache(body.project_id)
    return created_rules


@router.get("/mock-rules/export/{project_id}", response_model=MockRulesExportOut)
async def export_mock_rules(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_project_access(ProjectRole.viewer)),
):
    stmt = select(MockRule).where(MockRule.project_id == project_id).order_by(MockRule.id.desc())
    result = await db.execute(stmt)
    rules = result.scalars().all()
    return MockRulesExportOut(project_id=project_id, rules=rules)


@router.get("/mock-rules", response_model=list[MockRuleOut])
async def list_mock_rules(
    project_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if project_id is not None:
        await assert_project_access(db, user, project_id, ProjectRole.viewer)
    stmt = scope_to_visible_projects(select(MockRule), MockRule.project_id, user, project_id).order_by(
        MockRule.id.desc()
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/mock-rules/logs/{project_id}")
async def list_mock_logs(
    project_id: int,
    _: User = Depends(require_project_access(ProjectRole.viewer)),
):
    return get_mock_logs(project_id)


@router.get("/mock-rules/{rule_id}", response_model=MockRuleOut)
async def get_mock_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rule = await db.get(MockRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Mock 规则不存在")
    await assert_project_access(db, user, rule.project_id, ProjectRole.viewer)
    return rule


@router.patch("/mock-rules/{rule_id}", response_model=MockRuleOut)
async def update_mock_rule(
    rule_id: int,
    body: MockRuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_engineer),
):
    rule = await db.get(MockRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Mock 规则不存在")
    await assert_project_access(db, current_user, rule.project_id, ProjectRole.editor)

    payload = body.model_dump(exclude_none=True)
    if payload:
        await _persist_snapshot(db, rule, changed_by=current_user.id, note="auto on update")
        for key, value in payload.items():
            setattr(rule, key, value)
        _bump_rule_version(rule)
    await db.commit()
    await db.refresh(rule)
    await invalidate_mock_cache(rule.project_id)
    return rule


@router.delete("/mock-rules/{rule_id}", status_code=204)
async def delete_mock_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_engineer),
):
    rule = await db.get(MockRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Mock 规则不存在")
    await assert_project_access(db, user, rule.project_id, ProjectRole.editor)
    project_id = rule.project_id
    await db.delete(rule)
    await db.commit()
    await invalidate_mock_cache(project_id)


# ============================================================================
# D.2 版本快照 / 回滚 / 录制转正式
# ============================================================================


@router.get("/mock-rules/{rule_id}/snapshots", response_model=PaginatedMockSnapshotsOut)
async def list_mock_rule_snapshots(
    rule_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rule = await db.get(MockRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Mock 规则不存在")
    await assert_project_access(db, user, rule.project_id, ProjectRole.viewer)
    total = await db.scalar(
        select(func.count()).select_from(
            select(MockRuleSnapshot.id).where(MockRuleSnapshot.rule_id == rule_id).subquery()
        )
    )
    result = await db.execute(
        select(MockRuleSnapshot)
        .where(MockRuleSnapshot.rule_id == rule_id)
        .order_by(MockRuleSnapshot.version.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = result.scalars().all()
    return PaginatedMockSnapshotsOut(items=items, total=total or 0, page=page, page_size=page_size)


@router.post(
    "/mock-rules/{rule_id}/rollback/{snapshot_id}",
    response_model=MockRuleOut,
)
async def rollback_mock_rule(
    rule_id: int,
    snapshot_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_engineer),
):
    rule = await db.get(MockRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Mock 规则不存在")
    await assert_project_access(db, current_user, rule.project_id, ProjectRole.editor)
    snapshot = await db.get(MockRuleSnapshot, snapshot_id)
    if not snapshot or snapshot.rule_id != rule_id:
        raise HTTPException(status_code=404, detail="快照不存在")

    # 回滚前先保存当前版本快照（构成"前向"历史，便于撤销回滚）
    await _persist_snapshot(db, rule, changed_by=current_user.id, note=f"before rollback to v{snapshot.version}")

    data = snapshot.snapshot_data or {}
    if data.get("method"):
        rule.method = MockMethod(data["method"])
    if data.get("path") is not None:
        rule.path = data["path"]
    if data.get("name") is not None:
        rule.name = data["name"]
    if data.get("status_code") is not None:
        rule.status_code = data["status_code"]
    rule.response_headers = dict(data.get("response_headers") or {})
    rule.response_body = data.get("response_body")
    rule.match_conditions = dict(data.get("match_conditions") or {})
    rule.delay_ms = data.get("delay_ms", 0)
    rule.is_enabled = bool(data.get("is_enabled", True))
    rule.render_template = bool(data.get("render_template", False))
    rule.record_requests = bool(data.get("record_requests", False))
    _bump_rule_version(rule)

    await db.commit()
    await db.refresh(rule)
    await invalidate_mock_cache(rule.project_id)
    return rule


@router.post(
    "/mock-rules/{rule_id}/promote-sample",
    response_model=MockRuleOut,
    status_code=201,
)
async def promote_recorded_sample(
    rule_id: int,
    body: MockRulePromoteSampleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_engineer),
):
    """将 recorded_samples 中的样本一键转换为新的 Mock 规则（同项目）。"""
    src = await db.get(MockRule, rule_id)
    if not src:
        raise HTTPException(status_code=404, detail="Mock 规则不存在")
    await assert_project_access(db, current_user, src.project_id, ProjectRole.editor)

    samples = list(src.recorded_samples or [])
    if body.sample_index >= len(samples):
        raise HTTPException(status_code=400, detail="sample_index 超出录制样本范围")

    sample = samples[body.sample_index] or {}
    request_payload = sample.get("request") or {}
    response_payload = sample.get("response") or {}

    new_rule = MockRule(
        project_id=src.project_id,
        name=body.name or f"{src.name} (recorded #{body.sample_index})",
        method=src.method,
        path=src.path,
        status_code=int(response_payload.get("status_code", 200)),
        response_headers=dict(response_payload.get("headers") or {}),
        response_body=response_payload.get("body"),
        match_conditions={
            "query": dict(request_payload.get("query") or {}),
            "headers": {},
            "body": dict(request_payload.get("body") or {}) if isinstance(request_payload.get("body"), dict) else {},
        },
        delay_ms=0,
        is_enabled=bool(body.enable),
        render_template=False,
        record_requests=False,
        version=1,
        recorded_samples=[],
        creator_id=current_user.id,
    )
    db.add(new_rule)
    await db.commit()
    await db.refresh(new_rule)
    await invalidate_mock_cache(new_rule.project_id)
    return new_rule
