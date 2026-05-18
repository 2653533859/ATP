"""cases 包入口。

import 顺序设计：先把所有可被 monkeypatch 的外部符号挂到 cases 模块命名空间，
再 import 子模块；子模块通过 ``import app.api.v1.cases as _cases`` 引用这些符号，
这样测试中 ``monkeypatch.setattr(cases, "X", fake)`` 自然生效。

向后兼容：导出原 cases.py 暴露的所有顶层符号，老测试通过 ``cases.X`` 直接调用
endpoint 函数、辅助函数与外部依赖仍可工作。
"""
from fastapi import APIRouter

# === 1. 外部依赖（先于子模块 import） ===
from app.api.v1.statistics import invalidate_stats_cache
from app.core.tracing import get_trace_id
from app.models.case import (
    CaseSnapshot,
    CaseStatus,
    CaseStep,
    CaseType,
    RunStatus,
    TestCase,
    TestRun,
)
from app.schemas.case import (
    CaseBatchDeleteIn,
    CaseBatchImportOut,
    CaseBatchMoveIn,
    CaseBatchOpOut,
    CaseSnapshotOut,
    CaseWorkflowRequest,
    PaginatedRunsOut,
    PaginatedSnapshotsOut,
    RunTriggerRequest,
    TestCaseCreate,
    TestCaseDetailOut,
    TestCaseOut,
    TestCaseUpdate,
    TestRunOut,
)
from app.services.audit import write_audit_log
from app.worker.tasks import run_test_case

# === 2. common 辅助函数（先挂上来供子模块通过 _cases.X 访问） ===
from .common import (
    _assert_can_trigger_run,
    _build_snapshot,
    _derive_steps_from_config,
    _generate_case_code,
    _get_case_detail_or_404,
    _get_module_for_case_code,
    _next_snapshot_version,
    _normalize_case_legacy_fields,
    _normalize_code_fragment,
    _normalize_steps,
    _normalize_string_list,
    _replace_case_steps,
    _reset_review_after_edit,
    _serialize_case_snapshot,
    _serialize_steps,
    _type_code,
)

# === 3. 子模块（此时它们 import app.api.v1.cases 时已能看到所有外部依赖与 common 函数） ===
from . import batch, crud, runs, workflow

# === 4. router 装配 ===
router = APIRouter(tags=["用例管理"])
router.include_router(crud.router)
router.include_router(batch.router)
router.include_router(workflow.router)
router.include_router(runs.router)

# === 5. 兼容层：re-export endpoint 函数与子模块私有符号 ===
from .crud import (
    copy_case,
    create_case,
    delete_case,
    get_case,
    list_cases,
    update_case,
)
from .batch import (
    _serialize_case_for_zip,
    batch_delete_cases,
    batch_export_cases,
    batch_export_cases_zip,
    batch_import_cases_zip,
    batch_move_cases,
)
from .workflow import (
    approve_case,
    deprecate_case,
    get_snapshot,
    list_snapshots,
    reactivate_case,
    reject_case,
    rollback_case,
    submit_review,
)
from .runs import get_run, list_runs, trigger_run

__all__ = [
    "router",
    # endpoint
    "list_cases", "create_case", "get_case", "update_case", "copy_case", "delete_case",
    "batch_delete_cases", "batch_move_cases", "batch_export_cases",
    "batch_export_cases_zip", "batch_import_cases_zip",
    "submit_review", "approve_case", "reject_case", "deprecate_case", "reactivate_case",
    "list_snapshots", "get_snapshot", "rollback_case",
    "trigger_run", "list_runs", "get_run",
    # 子模块（供测试访问 cases.batch / cases.workflow 等）
    "batch", "crud", "workflow", "runs",
    # schemas（测试中常 isinstance / model_validate 使用）
    "TestCase", "TestRun", "CaseSnapshot", "CaseStep", "CaseStatus", "CaseType", "RunStatus",
    "TestCaseCreate", "TestCaseDetailOut", "TestCaseOut", "TestCaseUpdate", "TestRunOut",
    "CaseSnapshotOut", "CaseWorkflowRequest", "RunTriggerRequest",
    "PaginatedRunsOut", "PaginatedSnapshotsOut",
    "CaseBatchDeleteIn", "CaseBatchMoveIn", "CaseBatchOpOut",
    "CaseBatchImportOut",
    # 外部依赖（可被测试 monkeypatch）
    "write_audit_log", "invalidate_stats_cache", "get_trace_id", "run_test_case",
]
