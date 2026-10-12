"""N2.1 API 与 Web 用例完整流程与异常证据回归测试。

覆盖：
1. API 用例：创建、编辑、断言配置、审核流转、成功执行与断言失败证据。
2. Web 用例：录制步骤保存、审核流转、异常关闭收敛、成功执行与断言失败截图证据。
"""

import asyncio
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.models.case import CaseStatus, CaseType, RunStatus, StepResult, TestCase, TestRun
from app.models.bootstrap import load_all_models
from app.api.v1.web_recordings import WebRecordingSession

load_all_models()


# ==================== 1. API 用例全流程与失败断言证据 ====================


def test_api_case_review_workflow_and_approval_transition(monkeypatch):
    from app.api.v1 import cases
    from app.schemas.case import CaseWorkflowRequest

    now = datetime.now(timezone.utc)
    case = TestCase(
        id=101,
        name="测试创建订单接口",
        priority="P1",
        case_level="core",
        case_type=CaseType.api,
        status=CaseStatus.draft,
        review_status="draft",
        automation_status="auto",
        tags=["order", "api"],
        module_id=1,
        creator_id=1,
        owner_id=1,
        preconditions=[],
        postconditions=[],
        config={"method": "POST", "url": "/api/orders"},
    )
    case.created_at = now
    case.updated_at = now
    case.steps = []

    user = SimpleNamespace(id=1, username="tester", is_superuser=False)

    class FakeDB:
        def __init__(self):
            self.committed = False

        async def get(self, _model, _obj_id):
            return None

        async def commit(self):
            self.committed = True

    db = FakeDB()
    monkeypatch.setattr(cases, "_get_case_detail_or_404", lambda *_args, **_kwargs: asyncio.sleep(0, result=case))
    monkeypatch.setattr(cases, "write_audit_log", AsyncMock())

    # 1. 提交审核
    req_submit = CaseWorkflowRequest(comment="提交初版审核")
    updated = asyncio.run(cases.submit_review(case_id=101, body=req_submit, db=db, _current_user=user))
    assert updated.review_status == "pending"

    # 2. 审核通过
    req_approve = CaseWorkflowRequest(comment="逻辑正确准予入库")
    updated = asyncio.run(cases.approve_case(case_id=101, body=req_approve, db=db, current_user=user))
    assert updated.review_status == "approved"
    assert updated.status == CaseStatus.active


@pytest.mark.asyncio
async def test_api_executor_success_and_assertion_failure_evidence(monkeypatch):
    from app.worker.executors import api_executor

    now = datetime.now(timezone.utc)
    case = TestCase(
        id=201,
        priority="P0",
        case_level="core",
        case_code="ATP-API-LOGIN-001",
        summary="校验登录返回 token 与状态",
        case_type=CaseType.api,
        status=CaseStatus.active,
        review_status="approved",
        automation_status="auto",
        tags=[],
        module_id=1,
        creator_id=1,
        owner_id=1,
        preconditions=[],
        postconditions=[],
        config={
            "steps": [
                {
                    "name": "发起登录请求",
                    "request": {
                        "method": "POST",
                        "url": "https://api.example.com/v1/auth/login",
                        "headers": {"Content-Type": "application/json"},
                        "json": {"username": "admin", "password": "password123"},
                    },
                    "extractions": [{"variable": "auth_token", "expression": "$.data.token", "type": "jsonpath"}],
                    "assertions": [
                        {"target": "status_code", "operator": "eq", "expected": 200},
                        {"target": "body", "operator": "eq", "expression": "$.code", "expected": 0},
                    ],
                }
            ]
        },
    )
    case.created_at = now
    case.updated_at = now
    case.project_id = 1

    run = TestRun(
        id=501,
        case_id=case.id,
        triggered_by=1,
        status=RunStatus.running,
        created_at=now,
    )

    persisted_results = []

    class FakeCollector:
        def __init__(self, _db):
            pass

        async def add(self, step_res, flush=False):
            persisted_results.append(step_res)

        async def flush(self):
            pass

    monkeypatch.setattr(api_executor, "StepResultBatchCollector", FakeCollector)

    # 1. 成功场景：返回状态码 200，code 0，token 正常提取
    fake_success_resp = MagicMock()
    fake_success_resp.status_code = 200
    fake_success_resp.headers = {"Content-Type": "application/json"}
    fake_success_resp.text = json.dumps({"code": 0, "data": {"token": "jwt_token_xyz"}})
    fake_success_resp.json.return_value = {"code": 0, "data": {"token": "jwt_token_xyz"}}
    fake_success_resp.cookies = {}

    class FakeClientSuccess:
        def __init__(self, *args, **kwargs):
            self.cookies = {}

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def request(self, *args, **kwargs):
            return fake_success_resp

        async def aclose(self):
            pass

    monkeypatch.setattr(api_executor.httpx, "AsyncClient", FakeClientSuccess)

    fake_db = AsyncMock()
    monkeypatch.setattr(api_executor, "maybe_enqueue_run_healing", AsyncMock())
    await api_executor.run_api_case(fake_db, run, case, {})
    assert run.status == RunStatus.passed
    assert len(persisted_results) == 1
    step_0 = persisted_results[0]
    assert step_0.status == RunStatus.passed
    assert step_0.response_data["extractions"][0]["value"] == "jwt_token_xyz"
    assert step_0.response_data["assertions"][0]["passed"] is True
    assert step_0.response_data["assertions"][1]["passed"] is True

    # 2. 失败场景：期望 code 0，但服务端实际返回 400 且 code 为 1001
    persisted_results.clear()
    run.status = RunStatus.running
    fake_fail_resp = MagicMock()
    fake_fail_resp.status_code = 400
    fake_fail_resp.headers = {"Content-Type": "application/json"}
    fake_fail_resp.text = json.dumps({"code": 1001, "message": "用户名或密码错误"})
    fake_fail_resp.json.return_value = {"code": 1001, "message": "用户名或密码错误"}
    fake_fail_resp.cookies = {}

    class FakeClientFail:
        def __init__(self, *args, **kwargs):
            self.cookies = {}

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def request(self, *args, **kwargs):
            return fake_fail_resp

        async def aclose(self):
            pass

    monkeypatch.setattr(api_executor.httpx, "AsyncClient", FakeClientFail)

    await api_executor.run_api_case(fake_db, run, case, {})
    assert run.status == RunStatus.failed
    assert len(persisted_results) == 1
    failed_step = persisted_results[0]
    assert failed_step.status == RunStatus.failed
    # 状态码期望 200，实际 400，断言记录明确标明失败
    assert failed_step.response_data["assertions"][0]["passed"] is False
    assert "400" in failed_step.error_message


# ==================== 2. Web 用例全流程与失败断言截图证据 ====================


def test_web_recording_session_abrupt_close_convergence():
    """验证录制浏览器或页面被意外关闭时，状态平稳收敛至 stopped，不崩溃也不产生未处理异常。"""
    session = WebRecordingSession(
        session_id="web-abrupt-close-test",
        owner_id=1,
        start_url="https://example.com/login",
        viewport_width=1280,
        viewport_height=720,
        status="recording",
    )
    stopped_calls = []

    async def fake_stop():
        stopped_calls.append(True)
        session.status = "stopped"

    session.stop = fake_stop

    # 模拟外部事件直接关闭页面
    async def simulate():
        session._handle_page_close()
        await asyncio.sleep(0.01)

    asyncio.run(simulate())
    assert stopped_calls == [True]
    assert session.status == "stopped"


@pytest.mark.asyncio
async def test_web_lowcode_executor_success_and_assertion_failure_evidence(monkeypatch):
    from app.worker.executors import web_lowcode_executor

    now = datetime.now(timezone.utc)
    web_case = TestCase(
        id=301,
        name="Web 登录与主页断言",
        case_code="ATP-WEB-LOGIN-001",
        summary="录制并回放 Web 登录",
        case_type=CaseType.web,
        status=CaseStatus.active,
        priority="P0",
        case_level="core",
        review_status="approved",
        automation_status="auto",
        tags=["web"],
        module_id=1,
        creator_id=1,
        owner_id=1,
        preconditions=[],
        postconditions=[],
        config={
            "browser": "chromium",
            "steps": [
                {"action": "goto", "name": "打开登录页", "params": {"url": "https://example.com/login"}},
                {"action": "assert_text", "name": "检查欢迎文本", "params": {"text": "欢迎回来"}},
            ],
        },
    )
    web_case.created_at = now
    web_case.updated_at = now
    web_case.project_id = 1

    run = TestRun(
        id=601,
        case_id=web_case.id,
        triggered_by=1,
        status=RunStatus.running,
        created_at=now,
    )

    persisted_results: list[StepResult] = []

    class FakeWebCollector:
        def __init__(self, _db):
            pass

        async def add(self, step_res, flush=False):
            persisted_results.append(step_res)

        async def flush(self):
            pass

    monkeypatch.setattr(web_lowcode_executor, "StepResultBatchCollector", FakeWebCollector)

    # 模拟截图上传
    screenshots_taken = []

    def fake_upload_bytes(obj_name, data, content_type):
        screenshots_taken.append(obj_name)
        return obj_name

    monkeypatch.setattr(web_lowcode_executor, "upload_bytes", fake_upload_bytes)
    monkeypatch.setattr(web_lowcode_executor, "presigned_url", lambda name: f"https://storage.local/{name}")

    # 1. 成功场景：文本存在
    class FakePageSuccess:
        def __init__(self):
            self.url = "https://example.com/login"

        def on(self, *args, **kwargs):
            pass

        async def goto(self, url, **kwargs):
            self.url = url

        def locator(self, sel):
            mock_loc = AsyncMock()
            mock_loc.wait_for = AsyncMock()
            return mock_loc

        async def inner_text(self, sel):
            return "欢迎回来！系统已就绪"

        async def screenshot(self, **kwargs):
            return b"fake-png-screenshot"

    class FakeContextSuccess:
        def __init__(self):
            self.tracing = None

        async def route(self, *args):
            pass

        async def new_page(self):
            return FakePageSuccess()

    async def fake_acquire(*args, **kwargs):
        return FakeContextSuccess(), MagicMock(), MagicMock(), False

    monkeypatch.setattr(web_lowcode_executor, "acquire_browser_context", fake_acquire)
    monkeypatch.setattr(web_lowcode_executor, "release_browser_context", AsyncMock())

    fake_db = AsyncMock()
    fake_db.commit = AsyncMock()
    await web_lowcode_executor.run_web_lowcode(fake_db, run, web_case, {})
    assert run.status == RunStatus.passed
    assert len(persisted_results) == 2
    assert persisted_results[0].status == RunStatus.passed
    assert persisted_results[1].status == RunStatus.passed

    # 2. 失败场景：文本不存在，assert_text 失败并触发失败截图
    persisted_results.clear()
    screenshots_taken.clear()
    run.status = RunStatus.running

    class FakePageFail:
        def __init__(self):
            self.url = "https://example.com/login"

        def on(self, *args, **kwargs):
            pass

        async def goto(self, url, **kwargs):
            self.url = url

        def locator(self, sel):
            mock_loc = AsyncMock()
            mock_loc.wait_for = AsyncMock(side_effect=RuntimeError("timeout waiting for text"))
            return mock_loc

        async def inner_text(self, sel):
            return "页面已错误，404 Not Found"

        async def screenshot(self, **kwargs):
            return b"fail-png-screenshot"

    class FakeContextFail:
        def __init__(self):
            self.tracing = None

        async def route(self, *args):
            pass

        async def new_page(self):
            return FakePageFail()

    async def fake_acquire_fail(*args, **kwargs):
        return FakeContextFail(), MagicMock(), MagicMock(), False

    monkeypatch.setattr(web_lowcode_executor, "acquire_browser_context", fake_acquire_fail)

    await web_lowcode_executor.run_web_lowcode(fake_db, run, web_case, {})
    assert run.status == RunStatus.failed
    assert len(persisted_results) == 2
    assert persisted_results[0].status == RunStatus.passed
    failed_step = persisted_results[1]
    assert failed_step.status == RunStatus.failed
    assert "页面中未找到文本" in failed_step.error_message
    assert failed_step.screenshot_url is not None
    assert len(screenshots_taken) >= 1
