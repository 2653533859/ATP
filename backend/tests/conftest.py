"""根级 conftest：统一 stub 高频污染的可选依赖模块，避免跨测试 sys.modules 冲突。

策略：
- 用 _ensure_stub_attrs 模式：模块不存在时 setdefault；已存在则只补缺失字段，绝不覆盖 hard-set 的值。
- 适用于 41+ 个测试文件直接 sys.modules[...] = ... 的历史代码——保持其原有行为，
  仅在它们 stub 出的字段不足时由 conftest 兜底补齐。

P2.1 收口对象：
- app.core.minio_client（list_objects / delete_file / ensure_bucket / read_bytes / upload_bytes）
- app.core.redis_client（get_json_cache / set_json_cache / delete_* / publish_run_event / get_async_redis）
- app.api.deps（get_current_user / require_engineer / require_admin）
- app.core.database（get_db / AsyncSessionLocal / engine.dispose）

注意：celery / celery.utils.log 等 *不* 在根 conftest stub —— 因为 pytest.importorskip("celery") 会因此误判
为"已安装"，导致依赖真实 Celery 的测试无法 skip。需要 celery stub 的测试请在自己文件内做（如 test_db_backup.py）。

P2.3 集成测试模式：ATP_INTEGRATION_TESTS=1 时跳过所有 stub，让 backend/tests/integration/
的用例拿到真 redis/minio/db 客户端。fixtures 在 backend/tests/integration/conftest.py 提供。
"""

import inspect
import os
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"

# `import app...` 与 `from tests.conftest import ...` 都需要 backend/ 在 sys.path 上。
# 此前由各测试文件自己 `sys.path.insert(0, parents[2])`（144 个文件重复了这一行），
# 漏写的文件只在整套按序运行时才能通过——因为别的文件先插好了路径。conftest 在任何
# 测试模块 import 之前执行，放在这里让单文件运行与整套运行拿到同一个 sys.path。
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """仓库根目录。文档/配置契约类测试用它读取仓库文件，替代各文件重复的 ROOT 常量。"""
    return REPO_ROOT


@pytest.fixture(scope="session")
def repo_file(repo_root: Path):
    """读取仓库内相对路径文件的文本内容，替代各测试文件重复的 _read 帮助函数。"""

    def _read(path: str) -> str:
        return (repo_root / path).read_text(encoding="utf-8")

    return _read


def pytest_pycollect_makeitem(collector, name, obj):
    """跳过从应用代码导入的 Test* 命名类（TestCase/TestPlan/TestSuiteCreate 等模型与 schema）。

    这些类带 __init__，pytest 按 Test* 前缀尝试收集会触发 PytestCollectionWarning
    （pyproject 已将其升级为 error）。在此统一拦截后，测试文件可直接以原名导入，
    无需逐文件做 `TestPlan as PlanModel` 之类的别名改写。
    """
    if name.startswith("Test") and inspect.isclass(obj) and obj.__module__.startswith("app."):
        return []
    return None


def _ensure_stub_attrs(module_name: str, defaults: dict) -> None:
    """模块不在 sys.modules 时创建空 SimpleNamespace；已存在则只补缺失字段。

    永远不覆盖已 hard-set 的属性值——这是与早期测试文件 hard-set 行为共存的关键。
    """
    existing = sys.modules.get(module_name)
    if existing is None:
        sys.modules[module_name] = types.SimpleNamespace(**defaults)
        return
    for name, value in defaults.items():
        if not hasattr(existing, name):
            setattr(existing, name, value)


# ── 集成模式早退：不注入任何 stub ─────────────────────────────────
_INTEGRATION_MODE = os.getenv("ATP_INTEGRATION_TESTS") == "1"


def _refresh_common_test_stubs() -> None:
    """补回被历史测试模块替换掉的公共 stub 属性。

    许多旧测试在模块级 import 前直接替换了 `sys.modules` 中的对象。只在
    session 启动时补一次仍会让后续测试收集顺序影响结果，因此在每个测试
    模块收集前再次执行 fill-missing-only 修复，既保持测试自己的替身，也
    不允许缺失的公共符号污染下一个模块。
    """
    if _INTEGRATION_MODE:
        return
    _ensure_stub_attrs(
        "app.core.minio_client",
        {
            "list_objects": lambda *_a, **_kw: [],
            "delete_file": lambda *_a, **_kw: None,
            "ensure_bucket": lambda *_a, **_kw: None,
            "read_bytes": lambda *_a, **_kw: b"",
            "upload_bytes": lambda *_a, **_kw: None,
            "download_file": lambda *_a, **_kw: None,
            "upload_file": lambda *_a, **_kw: None,
            "presigned_url": lambda *_a, **_kw: "",
            "get_client": lambda *_a, **_kw: None,
        },
    )
    _ensure_stub_attrs(
        "app.core.redis_client",
        {
            "get_json_cache": lambda *_a, **_kw: None,
            "set_json_cache": lambda *_a, **_kw: None,
            "delete_json_cache": lambda *_a, **_kw: None,
            "delete_json_cache_pattern": lambda *_a, **_kw: None,
            "publish_run_event": lambda *_a, **_kw: None,
            "get_async_redis": lambda *_a, **_kw: None,
            "close_async_redis": _noop_async,
        },
    )
    _ensure_stub_attrs(
        "app.core.database",
        {
            "get_db": lambda: None,
            "AsyncSessionLocal": lambda *_a, **_kw: None,
            "engine": types.SimpleNamespace(dispose=lambda: None, sync_engine=None),
        },
    )
    _ensure_stub_attrs(
        "app.api.deps",
        {
            "get_current_user": lambda: None,
            "require_engineer": lambda: None,
            "require_admin": lambda: None,
            "assert_project_access": _noop_async,
            "assert_project_role": _noop_async,
            "get_project_role": _noop_async,
            "require_project_access": lambda *_a, **_kw: _noop_async,
            "require_project_writable_access": lambda *_a, **_kw: _noop_async,
        },
    )


@pytest.hookimpl(tryfirst=True)
def pytest_pycollect_makemodule(module_path, parent):
    _refresh_common_test_stubs()
    return None


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    """Restore required stub symbols after module-level test replacements.

    Some historical tests replace a shared module in ``sys.modules`` while
    being collected.  A later test may import its application module lazily,
    so collection-time repair alone is not sufficient to keep that import
    isolated from the replacement.
    """
    _refresh_common_test_stubs()


if not _INTEGRATION_MODE:
    # ── 单元模式：立即应用所有 stub（必须在测试文件 import 之前）──
    async def _noop_async(*_a, **_kw):
        return None

    _ensure_stub_attrs(
        "app.core.minio_client",
        {
            "list_objects": lambda *_a, **_kw: [],
            "delete_file": lambda *_a, **_kw: None,
            "ensure_bucket": lambda: None,
            "read_bytes": lambda *_a, **_kw: b"",
            "upload_bytes": lambda *_a, **_kw: None,
            "download_file": lambda *_a, **_kw: None,
            "upload_file": lambda *_a, **_kw: None,
            "presigned_url": lambda *_a, **_kw: "",
            "get_client": lambda: None,
        },
    )

    _ensure_stub_attrs(
        "app.core.redis_client",
        {
            "get_json_cache": lambda *_a, **_kw: None,
            "set_json_cache": lambda *_a, **_kw: None,
            "delete_json_cache": lambda *_a, **_kw: None,
            "delete_json_cache_pattern": lambda *_a, **_kw: None,
            "publish_run_event": lambda *_a, **_kw: None,
            "get_async_redis": lambda *_a, **_kw: None,
            "close_async_redis": _noop_async,
        },
    )

    _ensure_stub_attrs(
        "app.api.deps",
        {
            "get_current_user": lambda: None,
            "require_engineer": lambda: None,
            "require_admin": lambda: None,
            # 路由模块在 import 期就 `from app.api.deps import assert_project_access`，
            # 缺这两项时任何 import 这类路由的测试文件只有在别的文件先 hard-set 过
            # 更全的 stub 时才能通过。默认值沿用各文件既有约定（异步 no-op + 返回
            # 可调用对象的工厂）；hard-set 过自己版本的文件不受影响。
            "assert_project_access": _noop_async,
            "assert_project_role": _noop_async,
            "get_project_role": _noop_async,
            "require_project_access": lambda *_a, **_kw: _noop_async,
            "require_project_writable_access": lambda *_a, **_kw: _noop_async,
        },
    )

    _ensure_stub_attrs(
        "app.core.database",
        {
            "get_db": lambda: None,
            "AsyncSessionLocal": lambda *_a, **_kw: None,
            "engine": types.SimpleNamespace(dispose=lambda: None, sync_engine=None),
        },
    )
