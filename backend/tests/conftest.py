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
"""
import sys
import types


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


# ── 立即应用所有 stub（必须在测试文件 import 之前）──────────────

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
    },
)

_ensure_stub_attrs(
    "app.api.deps",
    {
        "get_current_user": lambda: None,
        "require_engineer": lambda: None,
        "require_admin": lambda: None,
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
