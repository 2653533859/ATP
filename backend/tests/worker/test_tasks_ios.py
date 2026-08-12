import importlib
import sys
import types


class _FakeCeleryApp:
    def task(self, *_args, **_kwargs):
        def decorate(func):
            return func

        return decorate


class _Session:
    def __init__(self):
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def commit(self):
        self.commits += 1


def test_reclaim_ios_lease_task_commits_and_returns_count(monkeypatch):
    monkeypatch.setitem(sys.modules, "app.worker.celery_app", types.SimpleNamespace(celery_app=_FakeCeleryApp()))
    monkeypatch.delitem(sys.modules, "app.worker.tasks_ios", raising=False)
    tasks_ios = importlib.import_module("app.worker.tasks_ios")
    session = _Session()
    monkeypatch.setattr(tasks_ios, "AsyncSessionLocal", lambda: session)

    lease_service = importlib.import_module("app.services.ios_device_leases")

    async def reclaim(_db):
        return 3

    monkeypatch.setattr(lease_service, "reclaim_expired_ios_device_leases", reclaim)

    assert tasks_ios.reclaim_expired_ios_device_leases() == 3
    assert session.commits == 1
