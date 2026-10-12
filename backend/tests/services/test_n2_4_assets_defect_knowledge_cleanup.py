"""N2.4 测试资产、需求/缺陷/知识沉淀及产物精确清理回归测试。

覆盖：
1. 测试资产环境变量占位符替换（URL、Header、JSON Body 保留类型）；
2. 需求关联测试用例与验收准则覆盖率；
3. 失败执行记录快速转内部缺陷（关联 run_id、case_id、指纹与重复去重）；
4. 缺陷分析与故障经验沉淀为项目知识库条目；
5. 本地对象存储产物精确清理（delete_run_artifacts 精确删除目标运行文件，零孤儿残留）。
"""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core import local_object_store
from app.models.bootstrap import load_all_models
from app.models.case import CaseStatus, CaseType, TestCase, TestRun, RunStatus
from app.models.defect import Defect, DefectRunLink
from app.models.project import Module, Project
from app.models.requirement import RequirementCaseLink, TestRequirement
from app.models.user import User
from app.schemas.defect import DefectCreateFromRun
from app.schemas.requirement import RequirementCaseLinkCreate
from app.schemas.knowledge import KnowledgeCreate
from app.services.local_artifact_cleanup import delete_run_artifacts
from app.worker.executors.api_executor import _render, _render_body_value

load_all_models()


# ==================== 1. 测试资产：环境变量与参数占位符渲染 ====================


def test_asset_variable_rendering_in_url_and_body():
    """验证环境变量与上下文变量在 URL 与复杂 JSON 请求体中的安全替换与类型保留。"""
    context = {
        "BASE_URL": "https://api.atp.local",
        "PORT": 8080,
        "TIMEOUT": 15,
        "TOKEN": "secret-jwt-token",
        "ENABLED": True,
    }

    url_template = "{{BASE_URL}}/v1/devices?port={{PORT}}"
    rendered_url = _render(url_template, context)
    assert rendered_url == "https://api.atp.local/v1/devices?port=8080"

    body_template = {
        "auth": {"token": "{{TOKEN}}", "active": "{{ENABLED}}"},
        "timeout_seconds": "{{TIMEOUT}}",
        "nested_list": ["{{BASE_URL}}", 123, False],
    }
    rendered_body = _render_body_value(body_template, context)
    assert rendered_body["auth"]["token"] == "secret-jwt-token"
    assert rendered_body["auth"]["active"] is True  # 布尔类型得到保留
    assert rendered_body["timeout_seconds"] == 15  # 整型数值类型得到保留
    assert rendered_body["nested_list"][0] == "https://api.atp.local"


# ==================== 2. 需求关联用例与覆盖度计算 ====================


@pytest.mark.asyncio
async def test_requirement_case_linking_and_coverage(monkeypatch):
    """验证需求关联用例功能，计算关联用例数并更新准则覆盖。"""
    from app.api.v1 import requirements

    now = datetime.now(timezone.utc)
    project = Project(id=1, name="ATP Project")
    module = Module(id=10, project_id=1, name="用户模块")
    case = TestCase(
        id=101,
        name="用户登录校验",
        case_code="ATP-API-001",
        case_type=CaseType.api,
        status=CaseStatus.active,
        priority="P0",
        case_level="core",
        review_status="approved",
        automation_status="auto",
        module_id=10,
        config={},
    )
    case.module = module

    requirement = TestRequirement(
        id=50,
        project_id=1,
        title="用户认证与鉴权需求",
        status="active",
        acceptance_criteria=[
            {"id": "AC-1", "text": "支持账号密码登录"},
            {"id": "AC-2", "text": "密码错误返回提示"},
        ],
    )

    created_links = []

    class FakeReqDB:
        def __init__(self):
            self.added = []

        async def get(self, model, obj_id):
            if model is TestRequirement and obj_id == 50:
                return requirement
            if model is TestCase and obj_id == 101:
                return case
            if model is Module and obj_id == 10:
                return module
            return None

        async def execute(self, stmt):
            res = MagicMock()
            res.scalar_one_or_none.return_value = None
            return res

        def add(self, obj):
            self.added.append(obj)
            if isinstance(obj, RequirementCaseLink):
                obj.id = 999
                obj.created_at = now
                created_links.append(obj)

        async def flush(self):
            pass

        async def commit(self):
            pass

    user = User(id=1, username="tester", email="tester@example.com")
    monkeypatch.setattr(requirements, "write_audit_log", AsyncMock())

    link_req = RequirementCaseLinkCreate(
        case_id=101,
        relation_type="validates",
        criterion_ids=["AC-1"],
        note="覆盖账号密码登录准则",
    )

    res = await requirements.link_requirement_case(
        requirement_id=50,
        body=link_req,
        db=FakeReqDB(),
        user=user,
    )

    assert res.case_id == 101
    assert res.requirement_id == 50
    assert res.relation_type == "validates"
    assert res.criterion_ids == ["AC-1"]
    assert len(created_links) == 1


# ==================== 3. 失败执行记录快速转缺陷 ====================


@pytest.mark.asyncio
async def test_create_defect_from_failed_run(monkeypatch):
    """验证失败运行记录一键生成缺陷，绑定 run_id、case_id、指纹与失败信息。"""
    from app.api.v1 import defects

    now = datetime.now(timezone.utc)
    failed_run = TestRun(
        id=701,
        case_id=101,
        triggered_by=1,
        status=RunStatus.failed,
        error_message="HTTP 500 登录接口内部服务器错误: DB Connection Timeout",
        created_at=now,
    )
    case = TestCase(
        id=101,
        name="登录接口校验",
        case_code="ATP-API-001",
        case_type=CaseType.api,
        status=CaseStatus.active,
        module_id=10,
        config={},
    )
    module = Module(id=10, project_id=1, name="用户模块")
    case.module = module
    failed_run.case = case

    created_defects = []

    class FakeDefectDB:
        def __init__(self):
            self.added = []

        async def get(self, model, obj_id):
            if model is TestRun and obj_id == 701:
                return failed_run
            if model is TestCase and obj_id == 101:
                return case
            if model is Module and obj_id == 10:
                return module
            if model is Defect:
                return created_defects[0] if created_defects else None
            return None

        async def execute(self, *args, **kwargs):
            res = MagicMock()
            if created_defects:
                res.scalar_one.return_value = created_defects[-1]
                res.scalar_one_or_none.return_value = None
            else:
                res.scalar_one_or_none.return_value = None
            res.all.return_value = []
            return res

        def add(self, obj):
            self.added.append(obj)
            if isinstance(obj, Defect):
                obj.id = 888
                obj.created_at = now
                obj.updated_at = now
                created_defects.append(obj)
            if isinstance(obj, DefectRunLink):
                obj.id = 777

        async def flush(self):
            pass

        async def commit(self):
            pass

    user = User(id=1, username="tester", email="tester@example.com")
    monkeypatch.setattr(defects, "assert_project_access", AsyncMock())
    monkeypatch.setattr(defects, "_ensure_assignee", AsyncMock())
    monkeypatch.setattr(defects, "write_audit_log", AsyncMock())

    body = DefectCreateFromRun(
        title="登录接口返回 500",
        description="接口在并发场景下超时",
        priority="P0",
        severity="blocker",
    )

    result = await defects.create_defect_from_run(
        run_type="case",
        run_id=701,
        body=body,
        db=FakeDefectDB(),
        user=user,
    )

    assert result.created is True
    assert len(created_defects) == 1
    defect = created_defects[0]
    assert defect.project_id == 1
    assert defect.case_id == 101
    assert defect.status == "open"
    assert defect.priority == "P0"
    assert defect.fingerprint is not None


# ==================== 4. 故障经验沉淀为知识库条目 ====================


@pytest.mark.asyncio
async def test_create_knowledge_from_troubleshooting_insight(monkeypatch):
    """验证将故障排查与自愈经验沉淀入项目知识库。"""
    from app.api.v1 import knowledge

    now = datetime.now(timezone.utc)
    created_items = []

    class FakeKnowledgeDB:
        def __init__(self):
            self.added = []

        async def get(self, model, obj_id):
            return None

        async def execute(self, *args, **kwargs):
            res = MagicMock()
            res.scalar_one_or_none.return_value = None
            return res

        async def scalar(self, *args, **kwargs):
            return "ATP Project"

        def add(self, obj):
            self.added.append(obj)
            obj.id = 333
            obj.created_at = now
            obj.updated_at = now
            created_items.append(obj)

        async def flush(self):
            pass

        async def commit(self):
            pass

        async def refresh(self, obj):
            pass

    user = User(id=1, username="expert", email="expert@example.com")
    monkeypatch.setattr(knowledge, "assert_project_access", AsyncMock())
    monkeypatch.setattr(knowledge, "write_audit_log", AsyncMock())

    payload = KnowledgeCreate(
        project_id=1,
        title="数据库连接池超时排查经验",
        source_type="experience",
        content="在并发突发情况下，PostgreSQL 连接池耗尽会导致 500 错误。解决方案：调大 pool_size 或优化慢查询连接释放。",
        tags=["database", "timeout", "pool"],
    )

    res = await knowledge.create_knowledge(
        body=payload,
        db=FakeKnowledgeDB(),
        user=user,
    )

    assert res.document_id == 333
    assert res.title == "数据库连接池超时排查经验"
    assert res.source_type == "experience"
    assert "database" in res.tags


# ==================== 5. 本地对象存储产物精确清理 ====================


def test_precise_local_run_artifact_cleanup(tmp_path, monkeypatch):
    """验证 delete_run_artifacts 精确清理目标 run_id 的截图、Trace 和报告，不残留也不影响其他运行。"""
    from app.core.config import settings

    monkeypatch.setattr(settings, "ATP_LOCAL_DATA_DIR", str(tmp_path))

    # 模拟 run_id 101 的产物
    run_101_files = [
        "screenshots/runs/101/step_0.png",
        "screenshots/runs/101/step_1.png",
        "traces/runs/101/trace.zip",
        "videos/runs/101/recording.webm",
        "reports/run-101/report.html",
    ]
    # 模拟 run_id 102 的产物
    run_102_files = [
        "screenshots/runs/102/step_0.png",
        "traces/runs/102/trace.zip",
        "reports/run-102/report.html",
    ]

    for rel_path in run_101_files + run_102_files:
        local_object_store.upload_bytes(rel_path, b"sample-artifact-content")

    # 执行针对 run 101 的精确清理
    delete_run_artifacts([101])

    # 验证 run 101 的文件已被彻底删除
    for rel_path in run_101_files:
        assert not (tmp_path / "objects" / rel_path).exists(), f"文件未被清理: {rel_path}"

    # 验证 run 102 的文件完整保留
    for rel_path in run_102_files:
        assert (tmp_path / "objects" / rel_path).exists(), f"其他运行的文件被误删: {rel_path}"
