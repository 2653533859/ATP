"""P3.A Celery 任务包装层测试：成功路径 + 异常吞掉不抛。"""

import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


# stub celery_app 避免真 celery 依赖
class _FakeCelery:
    def task(self, *a, **kw):
        def deco(fn):
            return fn

        return deco


sys.modules.setdefault(
    "app.worker.celery_app",
    types.SimpleNamespace(celery_app=_FakeCelery()),
)


def test_diagnose_step_failure_invokes_run_diagnosis(monkeypatch):
    from app.worker import tasks_healing
    from app.services import ai_healing
    import app.core.database as db_mod

    called: list[int] = []

    async def fake_run_diagnosis(_db, sid):
        called.append(sid)

    monkeypatch.setattr(ai_healing, "run_diagnosis", fake_run_diagnosis)

    # 替换 AsyncSessionLocal
    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

    monkeypatch.setattr(db_mod, "AsyncSessionLocal", lambda: FakeSession())

    # bind=True：自身 self 是任意值
    tasks_healing.diagnose_step_failure(None, 42)

    assert called == [42]


def test_diagnose_step_failure_swallows_exceptions(monkeypatch):
    from app.worker import tasks_healing
    from app.services import ai_healing
    import app.core.database as db_mod

    async def boom(_db, _sid):
        raise RuntimeError("LLM down")

    monkeypatch.setattr(ai_healing, "run_diagnosis", boom)

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

    monkeypatch.setattr(db_mod, "AsyncSessionLocal", lambda: FakeSession())

    # 不抛
    tasks_healing.diagnose_step_failure(None, 99)
