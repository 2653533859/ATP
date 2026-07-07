"""P2.1 验证根级 conftest 的 _ensure_stub_attrs helper：

该测试不假设其他 test 文件不污染 sys.modules（事实上 41 个文件直接 hard-set 是已知现状）。
它验证的是 helper 自身契约——给定模块/字段，能否正确补齐而不覆盖已存在值。

这是 P2.1 收口的核心保证：只要 conftest 在 import 时跑一次，且其他测试只是
*替换* 模块对象（而非删除字段），helper 的"补齐不覆盖"语义就守住底线。
"""

import sys
import types


def test_ensure_stub_attrs_creates_module_when_missing():
    from tests.conftest import _ensure_stub_attrs

    target = "tests.fixtures._p21_helper_creates_module"
    sys.modules.pop(target, None)
    _ensure_stub_attrs(target, {"x": 1, "y": "z"})
    mod = sys.modules[target]
    assert mod.x == 1
    assert mod.y == "z"
    sys.modules.pop(target, None)


def test_ensure_stub_attrs_preserves_existing_attributes():
    """已 hard-set 的字段不被覆盖（与 41 个测试文件 hard-set 行为共存的关键）。"""
    from tests.conftest import _ensure_stub_attrs

    target = "tests.fixtures._p21_helper_preserves_existing"
    sys.modules[target] = types.SimpleNamespace(custom="kept-value")
    _ensure_stub_attrs(target, {"custom": "should-not-overwrite", "added": 1})

    mod = sys.modules[target]
    assert mod.custom == "kept-value"
    assert mod.added == 1
    sys.modules.pop(target, None)


def test_ensure_stub_attrs_is_idempotent():
    """重复调用 helper 不产生副作用。"""
    from tests.conftest import _ensure_stub_attrs

    target = "tests.fixtures._p21_helper_idempotent"
    sys.modules.pop(target, None)
    _ensure_stub_attrs(target, {"a": 1})
    _ensure_stub_attrs(target, {"a": 2})  # 第二次调用：a 已存在，不覆盖
    assert sys.modules[target].a == 1
    sys.modules.pop(target, None)


def test_conftest_registers_target_modules_at_collection_time():
    """conftest 加载完成后，4 个目标模块必须在 sys.modules 中（即使后续被替换，也不会被删除）。"""
    for name in (
        "app.core.minio_client",
        "app.core.redis_client",
        "app.api.deps",
        "app.core.database",
    ):
        assert name in sys.modules, f"{name} 应已在 conftest 中被 stub"


def test_ensure_stub_attrs_handles_simplenamespace_and_module_types():
    """helper 应同时支持 SimpleNamespace 和 ModuleType 容器。"""
    from tests.conftest import _ensure_stub_attrs

    # SimpleNamespace
    target1 = "tests.fixtures._p21_simple_ns"
    sys.modules[target1] = types.SimpleNamespace()
    _ensure_stub_attrs(target1, {"k": "v"})
    assert sys.modules[target1].k == "v"
    sys.modules.pop(target1, None)

    # ModuleType
    target2 = "tests.fixtures._p21_module_type"
    sys.modules[target2] = types.ModuleType(target2)
    _ensure_stub_attrs(target2, {"k": "v"})
    assert sys.modules[target2].k == "v"
    sys.modules.pop(target2, None)
