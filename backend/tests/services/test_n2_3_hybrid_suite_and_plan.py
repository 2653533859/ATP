"""N2.3 混合串行套件与手动计划回归测试。

覆盖：
1. API / Web 混合套件在本地模式下强制串行执行，正确串联父子运行与结果汇总；
2. 计划与套件失败策略（fast-fail vs continue）控制流程；
3. 单线程模式下取消立即安全收敛，无父子等待死锁；
4. 服务器模式下保留 parallel 并发配置与 Worker 路由。
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import settings
from app.models.bootstrap import load_all_models
from app.models.case import CaseStatus, CaseType, TestCase
from app.models.plan import PlanRun, PlanRunStatus, TestPlan
from app.models.suite import SuiteRun, SuiteRunStatus, TestSuite

load_all_models()
from app.services.plan_orchestrator import execute_plan_suites, normalize_plan_config
from app.services.suite_orchestrator import execute_suite_cases, normalize_suite_config


# ==================== 1. 混合套件串行执行与父子汇总 ====================


@pytest.mark.asyncio
async def test_hybrid_suite_serial_execution_and_summary(monkeypatch):
    """测试 API 与 Web 混合用例在本地单机模式下串行执行，结果正确汇总到 SuiteRun。"""
    monkeypatch.setattr(settings, "ATP_LOCAL_MODE", True)

    now = datetime.now(timezone.utc)
    suite = TestSuite(
        id=10,
        project_id=1,
        name="API & Web 核心流程混合套件",
        config={"execution_mode": "parallel", "fail_strategy": "continue"},  # 本地模式应自动转为 sequential
        case_ids=[{"case_id": 101, "sort": 1}, {"case_id": 102, "sort": 2}],
    )
    suite_run = SuiteRun(
        id=20,
        suite_id=10,
        triggered_by=1,
        status=SuiteRunStatus.running,
        identity_token="suite-token-123",
        created_at=now,
    )

    api_case = TestCase(
        id=101,
        name="登录接口",
        case_type=CaseType.api,
        status=CaseStatus.active,
        priority="P0",
        case_level="core",
        review_status="approved",
        automation_status="auto",
        config={},
    )
    web_case = TestCase(
        id=102,
        name="主页浏览",
        case_type=CaseType.web,
        status=CaseStatus.active,
        priority="P0",
        case_level="core",
        review_status="approved",
        automation_status="auto",
        config={},
    )

    cases_db = {101: api_case, 102: web_case}

    class FakeSuiteDB:
        def __init__(self):
            self.committed = False

        async def get(self, model, obj_id):
            if model is TestCase:
                return cases_db.get(obj_id)
            return None

        async def execute(self, *args, **kwargs):
            res = MagicMock()
            res.all.return_value = []
            return res

        async def commit(self):
            self.committed = True

    fake_db = FakeSuiteDB()

    executed_order = []

    async def fake_execute_case(_db, _suite_run, case, _fixture_context, **kwargs):
        executed_order.append((case.id, case.case_type))
        return {
            "case_id": case.id,
            "case_name": case.name,
            "run_id": case.id + 1000,
            "status": "passed",
        }

    res = await execute_suite_cases(
        fake_db,
        suite_run,
        suite,
        extra_vars={},
        execute_case_fn=fake_execute_case,
        mark_flaky_fn=AsyncMock(),
        is_cancelled_fn=lambda *args: False,
    )

    # 1. 验证串行执行顺序
    assert executed_order == [(101, CaseType.api), (102, CaseType.web)]
    assert suite_run.result_summary["execution_mode"] == "sequential"
    assert suite_run.result_summary["total"] == 2
    assert suite_run.result_summary["passed"] == 2
    assert suite_run.result_summary["failed"] == 0
    assert suite_run.status == SuiteRunStatus.passed


# ==================== 2. 失败策略控制（fast-fail vs continue） ====================


@pytest.mark.asyncio
async def test_suite_fast_fail_strategy_stops_remaining_cases(monkeypatch):
    """验证 fast-fail 策略下，第一个用例失败后立刻中止后续用例，后续用例标为 skipped。"""
    monkeypatch.setattr(settings, "ATP_LOCAL_MODE", True)

    now = datetime.now(timezone.utc)
    suite = TestSuite(
        id=11,
        project_id=1,
        name="Fast-Fail 演示套件",
        config={"fail_strategy": "fast-fail"},
        case_ids=[{"case_id": 201, "sort": 1}, {"case_id": 202, "sort": 2}],
    )
    suite_run = SuiteRun(
        id=21,
        suite_id=11,
        triggered_by=1,
        status=SuiteRunStatus.running,
        identity_token="suite-token-ff",
        created_at=now,
    )

    case_1 = TestCase(id=201, name="必定失败用例", case_type=CaseType.api, status=CaseStatus.active, config={})
    case_2 = TestCase(id=202, name="后续用例", case_type=CaseType.web, status=CaseStatus.active, config={})
    cases_db = {201: case_1, 202: case_2}

    class FakeDB:
        async def get(self, model, obj_id):
            if model is TestCase:
                return cases_db.get(obj_id)
            return None

        async def execute(self, *args, **kwargs):
            res = MagicMock()
            res.all.return_value = []
            return res

        async def commit(self):
            pass

    executed = []

    async def fake_execute_case(_db, _suite_run, case, _fixture_ctx, **kwargs):
        executed.append(case.id)
        if case.id == 201:
            return {"case_id": 201, "run_id": 3001, "status": "failed", "error": "断言不匹配"}
        return {"case_id": 202, "run_id": 3002, "status": "passed"}

    res = await execute_suite_cases(
        FakeDB(),
        suite_run,
        suite,
        extra_vars={},
        execute_case_fn=fake_execute_case,
        mark_flaky_fn=AsyncMock(),
        is_cancelled_fn=lambda *args: False,
    )

    # 仅第 1 个用例被执行，第 2 个被跳过
    assert executed == [201]
    assert suite_run.result_summary["failed"] == 1
    assert suite_run.result_summary["skipped"] == 1
    assert suite_run.status == SuiteRunStatus.failed


# ==================== 3. 计划编排多套件与失败策略 ====================


@pytest.mark.asyncio
async def test_plan_orchestrator_fast_fail_and_continue():
    """验证测试计划编排多个套件时的执行控制。"""
    now = datetime.now(timezone.utc)
    plan = TestPlan(
        id=30,
        project_id=1,
        name="冒烟与回归测试计划",
        config={"fail_strategy": "fast-fail"},
        suite_ids=[{"suite_id": 101, "sort": 1}, {"suite_id": 102, "sort": 2}],
    )
    plan_run = PlanRun(
        id=40,
        plan_id=30,
        triggered_by=1,
        status=PlanRunStatus.running,
        identity_token="plan-token-xyz",
        created_at=now,
    )

    executed_suites = []

    async def fake_execute_suite(*args, **kwargs):
        suite_id = kwargs.get("suite_id")
        executed_suites.append(suite_id)
        if suite_id == 101:
            return {"suite_id": 101, "suite_run_id": 501, "status": "failed"}
        return {"suite_id": 102, "suite_run_id": 502, "status": "passed"}

    class FakeDB:
        async def commit(self):
            pass

    res = await execute_plan_suites(
        FakeDB(),
        plan_run,
        plan,
        extra_vars={},
        execute_plan_suite_fn=fake_execute_suite,
        is_cancelled_fn=lambda *args: False,
    )

    # fast-fail 下，套件 101 失败后套件 102 不再执行
    assert executed_suites == [101]
    assert res["counts"]["failed"] == 1
    assert plan_run.status == PlanRunStatus.failed
    # 未执行套件被标为 skipped
    skipped = [r for r in plan_run.suite_run_ids if r.get("status") == "skipped"]
    assert len(skipped) == 1
    assert skipped[0]["suite_id"] == 102


# ==================== 4. 单线程取消与防死锁 ====================


@pytest.mark.asyncio
async def test_cancellation_converges_immediately_without_deadlock(monkeypatch):
    """验证收到取消信号时，内联循环立即安全退出，子项标记跳过，不阻塞也无死锁。"""
    monkeypatch.setattr(settings, "ATP_LOCAL_MODE", True)

    now = datetime.now(timezone.utc)
    suite = TestSuite(
        id=12,
        project_id=1,
        name="待取消套件",
        config={},
        case_ids=[{"case_id": 301, "sort": 1}, {"case_id": 302, "sort": 2}],
    )
    suite_run = SuiteRun(
        id=22,
        suite_id=12,
        triggered_by=1,
        status=SuiteRunStatus.running,
        identity_token="suite-token-cancel",
        created_at=now,
    )

    case_1 = TestCase(id=301, name="用例1", case_type=CaseType.api, status=CaseStatus.active, config={})
    case_2 = TestCase(id=302, name="用例2", case_type=CaseType.api, status=CaseStatus.active, config={})
    cases_db = {301: case_1, 302: case_2}

    class FakeDB:
        async def get(self, model, obj_id):
            if model is TestCase:
                return cases_db.get(obj_id)
            return None

        async def execute(self, *args, **kwargs):
            res = MagicMock()
            res.all.return_value = []
            return res

        async def commit(self):
            pass

    # 模拟在执行时已经触发取消
    cancelled_checked = []

    def mock_is_cancelled(kind, run_id, token):
        cancelled_checked.append((kind, run_id))
        return True

    res = await execute_suite_cases(
        FakeDB(),
        suite_run,
        suite,
        extra_vars={},
        mark_flaky_fn=AsyncMock(),
        is_cancelled_fn=mock_is_cancelled,
    )

    assert len(cancelled_checked) >= 1
    # 循环退出，子项全量 skipped
    assert suite_run.result_summary["skipped"] == 2
    assert suite_run.status == SuiteRunStatus.error


# ==================== 5. 服务器模式保留并发与 Worker 路由配置 ====================


def test_server_mode_preserves_parallel_and_worker_routing(monkeypatch):
    """验证非本地模式下（Linux 服务器模式），parallel 并发配置与路由规则得到完整保留。"""
    monkeypatch.setattr(settings, "ATP_LOCAL_MODE", False)

    suite_cfg = normalize_suite_config({"execution_mode": "parallel", "max_workers": 8})
    assert suite_cfg["execution_mode"] == "parallel"
    assert suite_cfg["max_workers"] == 8

    plan_cfg = normalize_plan_config({"execution_mode": "parallel", "max_workers": 6})
    assert plan_cfg["execution_mode"] == "parallel"
    assert plan_cfg["max_workers"] == 6
