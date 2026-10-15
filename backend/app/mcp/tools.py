"""MCP (Model Context Protocol) tool definitions and handlers for ATP.

Exposes standardized testing tools conforming to the MCP v1 specification:
- atp_list_cases: Search and filter test cases in a project
- atp_get_case_detail: Retrieve complete test case configuration and steps
- atp_run_case: Dispatch an asynchronous execution for a test case
- atp_get_run_status: Inspect real-time status and step outcomes of an execution
- atp_diagnose_failure: Run AI failure diagnosis for an execution
- atp_create_defect: Log an internal project defect with optional execution link
- atp_get_project_summary: Summarize project modules, test case statistics, and health
"""

from __future__ import annotations

import json
from typing import Any, Callable, Coroutine
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import assert_project_access
from app.models.case import CaseType, RunStatus, TestCase, TestRun
from app.models.defect import Defect
from app.models.project import Module, Project
from app.models.user import User
from app.models.user_project import ProjectRole
from app.services.execution_routing import enqueue_case_run
from app.services.failure_diagnosis import generate_failure_diagnosis


TOOLS_MANIFEST = [
    {
        "name": "atp_list_cases",
        "description": "列出或搜索指定项目下的测试用例列表，支持按关键词、类型、状态过滤",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer", "description": "项目编号 ID"},
                "keyword": {"type": "string", "description": "用例名称模糊搜索关键词"},
                "case_type": {
                    "type": "string",
                    "enum": ["api", "web", "android", "graphql", "websocket", "grpc"],
                    "description": "用例协议或类型",
                },
                "limit": {"type": "integer", "default": 20, "description": "最多返回数量"},
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "atp_get_case_detail",
        "description": "获取单个测试用例的完整详细信息，包含请求配置、步骤列表、断言与提取规则",
        "inputSchema": {
            "type": "object",
            "properties": {
                "case_id": {"type": "integer", "description": "测试用例编号 ID"},
            },
            "required": ["case_id"],
        },
    },
    {
        "name": "atp_run_case",
        "description": "异步触发单条测试用例执行，返回新生成的执行记录 run_id",
        "inputSchema": {
            "type": "object",
            "properties": {
                "case_id": {"type": "integer", "description": "目标测试用例编号 ID"},
                "env_id": {"type": "integer", "description": "关联执行环境 ID（可选）"},
                "extra_vars": {"type": "object", "description": "执行时动态注入的外部参数变量字典"},
            },
            "required": ["case_id"],
        },
    },
    {
        "name": "atp_get_run_status",
        "description": "查询执行记录的最新运行状态、耗时、报错信息与分步结果",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "integer", "description": "执行记录编号 ID"},
            },
            "required": ["run_id"],
        },
    },
    {
        "name": "atp_diagnose_failure",
        "description": "对执行失败的记录调用 AI 诊断，分析根因并生成自愈与排查建议",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "integer", "description": "执行失败的记录编号 ID"},
            },
            "required": ["run_id"],
        },
    },
    {
        "name": "atp_create_defect",
        "description": "在项目中记录一条内部缺陷工单，可选择关联至具体的执行记录",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer", "description": "项目编号 ID"},
                "title": {"type": "string", "description": "缺陷简明标题"},
                "description": {"type": "string", "description": "缺陷详细描述与重现步骤"},
                "run_id": {"type": "integer", "description": "关联的失败执行记录 ID（可选）"},
                "severity": {
                    "type": "string",
                    "enum": ["fatal", "critical", "major", "minor"],
                    "default": "major",
                    "description": "缺陷严重级别",
                },
            },
            "required": ["project_id", "title"],
        },
    },
    {
        "name": "atp_get_project_summary",
        "description": "查询项目的模块架构、用例总数及各类型分布概览",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer", "description": "项目编号 ID"},
            },
            "required": ["project_id"],
        },
    },
]


async def handle_list_cases(db: AsyncSession, user: User, args: dict[str, Any]) -> dict[str, Any]:
    project_id = int(args["project_id"])
    await assert_project_access(db, user, project_id, ProjectRole.viewer)

    query = select(TestCase).join(Module, TestCase.module_id == Module.id).where(Module.project_id == project_id)

    keyword = args.get("keyword")
    if keyword:
        query = query.where(TestCase.name.ilike(f"%{keyword}%"))

    case_type = args.get("case_type")
    if case_type:
        query = query.where(TestCase.case_type == CaseType(case_type))

    limit = min(int(args.get("limit", 20)), 100)
    query = query.order_by(TestCase.id.desc()).limit(limit)

    result = await db.execute(query)
    cases = result.scalars().all()

    return {
        "project_id": project_id,
        "count": len(cases),
        "cases": [
            {
                "id": c.id,
                "name": c.name,
                "case_type": c.case_type.value,
                "priority": c.priority,
                "status": c.status.value,
                "module_id": c.module_id,
            }
            for c in cases
        ],
    }


async def handle_get_case_detail(db: AsyncSession, user: User, args: dict[str, Any]) -> dict[str, Any]:
    case_id = int(args["case_id"])
    case = await db.get(TestCase, case_id)
    if not case:
        raise ValueError(f"测试用例不存在: ID {case_id}")

    module = await db.get(Module, case.module_id)
    if module:
        await assert_project_access(db, user, module.project_id, ProjectRole.viewer)

    return {
        "id": case.id,
        "name": case.name,
        "case_type": case.case_type.value,
        "priority": case.priority,
        "status": case.status.value,
        "module_id": case.module_id,
        "config": case.config,
    }


async def handle_run_case(db: AsyncSession, user: User, args: dict[str, Any]) -> dict[str, Any]:
    from app.worker.tasks import run_test_case

    case_id = int(args["case_id"])
    case = await db.get(TestCase, case_id)
    if not case:
        raise ValueError(f"测试用例不存在: ID {case_id}")

    module = await db.get(Module, case.module_id)
    if module:
        await assert_project_access(db, user, module.project_id, ProjectRole.editor)

    extra_vars = args.get("extra_vars") or {}
    run = TestRun(
        case_id=case_id,
        triggered_by=user.id,
        status=RunStatus.pending,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    enqueue_case_run(run_test_case, run.id, extra_vars, run.trace_id, case.case_type)

    return {
        "run_id": run.id,
        "case_id": case.id,
        "case_name": case.name,
        "status": "pending",
        "message": "测试用例已成功下发至队列",
    }


async def handle_get_run_status(db: AsyncSession, user: User, args: dict[str, Any]) -> dict[str, Any]:
    run_id = int(args["run_id"])
    result = await db.execute(select(TestRun).where(TestRun.id == run_id).options(selectinload(TestRun.steps)))
    run = result.scalar_one_or_none()
    if not run:
        raise ValueError(f"执行记录不存在: ID {run_id}")

    case = await db.get(TestCase, run.case_id)
    if case:
        module = await db.get(Module, case.module_id)
        if module:
            await assert_project_access(db, user, module.project_id, ProjectRole.viewer)

    return {
        "run_id": run.id,
        "case_id": run.case_id,
        "status": run.status.value,
        "duration_ms": run.duration_ms,
        "error_message": run.error_message,
        "steps_count": len(run.steps),
        "steps": [
            {
                "step_index": s.step_index,
                "name": s.name,
                "status": s.status.value,
                "duration_ms": s.duration_ms,
                "error_message": s.error_message,
            }
            for s in run.steps
        ],
    }


async def handle_diagnose_failure(db: AsyncSession, user: User, args: dict[str, Any]) -> dict[str, Any]:
    run_id = int(args["run_id"])
    result = await db.execute(select(TestRun).where(TestRun.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise ValueError(f"执行记录不存在: ID {run_id}")

    case = await db.get(TestCase, run.case_id)
    if case:
        module = await db.get(Module, case.module_id)
        if module:
            await assert_project_access(db, user, module.project_id, ProjectRole.viewer)

    diagnosis = await generate_failure_diagnosis(db, run_id)
    if not diagnosis:
        return {
            "run_id": run_id,
            "status": "no_failures",
            "message": "当前执行未包含失败步骤或无法生成诊断",
        }
    return {
        "run_id": run_id,
        "source": diagnosis.get("source"),
        "summary": diagnosis.get("summary"),
        "failed_step_count": diagnosis.get("failed_step_count", 0),
        "repair_suggestions": diagnosis.get("repair_suggestions", []),
    }


async def handle_create_defect(db: AsyncSession, user: User, args: dict[str, Any]) -> dict[str, Any]:
    project_id = int(args["project_id"])
    await assert_project_access(db, user, project_id, ProjectRole.editor)

    title = str(args.get("title", "")).strip()
    if not title:
        raise ValueError("缺陷标题不能为空")

    description = args.get("description", "")
    run_id = args.get("run_id")
    case_id = None
    if run_id:
        run = await db.get(TestRun, int(run_id))
        if run:
            case_id = run.case_id

    defect = Defect(
        project_id=project_id,
        title=title,
        description=description,
        case_id=case_id,
        severity=str(args.get("severity", "major")),
        creator_id=user.id,
        status="open",
        occurrence_count=1,
        last_seen_at=datetime.now(timezone.utc),
    )
    db.add(defect)
    await db.commit()
    await db.refresh(defect)

    return {
        "defect_id": defect.id,
        "project_id": defect.project_id,
        "title": defect.title,
        "status": defect.status,
        "severity": defect.severity,
    }


async def handle_get_project_summary(db: AsyncSession, user: User, args: dict[str, Any]) -> dict[str, Any]:
    project_id = int(args["project_id"])
    await assert_project_access(db, user, project_id, ProjectRole.viewer)

    project = await db.get(Project, project_id)
    if not project:
        raise ValueError(f"项目不存在: ID {project_id}")

    modules_res = await db.execute(select(Module).where(Module.project_id == project_id))
    modules = modules_res.scalars().all()
    module_ids = [m.id for m in modules]

    case_count = 0
    if module_ids:
        case_res = await db.execute(select(func.count(TestCase.id)).where(TestCase.module_id.in_(module_ids)))
        case_count = case_res.scalar() or 0

    return {
        "project_id": project.id,
        "project_name": project.name,
        "modules_count": len(modules),
        "cases_count": case_count,
        "modules": [{"id": m.id, "name": m.name} for m in modules],
    }


TOOL_HANDLERS: dict[str, Callable[[AsyncSession, User, dict[str, Any]], Coroutine[Any, Any, dict[str, Any]]]] = {
    "atp_list_cases": handle_list_cases,
    "atp_get_case_detail": handle_get_case_detail,
    "atp_run_case": handle_run_case,
    "atp_get_run_status": handle_get_run_status,
    "atp_diagnose_failure": handle_diagnose_failure,
    "atp_create_defect": handle_create_defect,
    "atp_get_project_summary": handle_get_project_summary,
}


async def execute_tool(db: AsyncSession, user: User, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    handler = TOOL_HANDLERS.get(tool_name)
    if not handler:
        return {
            "content": [{"type": "text", "text": f"未知工具: {tool_name}"}],
            "isError": True,
        }

    try:
        data = await handler(db, user, arguments)
        return {
            "content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False, indent=2)}],
            "isError": False,
        }
    except Exception as exc:
        return {
            "content": [{"type": "text", "text": f"工具执行失败 [{tool_name}]: {str(exc)}"}],
            "isError": True,
        }
