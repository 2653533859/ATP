"""默认管理员初始化的幂等性回归。"""

import pytest

from app import main


class _Result:
    def __init__(self, value):
        self.value = value

    def scalars(self):
        return self

    def first(self):
        return self.value


class _Session:
    def __init__(self, *results):
        self.results = list(results)
        self.statements = []
        self.added = []
        self.commit_count = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def execute(self, statement):
        self.statements.append(statement)
        return _Result(self.results.pop(0))

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.commit_count += 1

    async def rollback(self):
        return None


@pytest.mark.asyncio
async def test_init_admin_skips_existing_identity_by_bootstrap_email(monkeypatch):
    session = _Session(object())
    monkeypatch.setattr(main, "AsyncSessionLocal", lambda: session)

    await main._init_admin()

    assert session.added == []
    assert session.commit_count == 0
    assert "users.email" in str(session.statements[0])


@pytest.mark.asyncio
async def test_init_admin_creates_missing_identity(monkeypatch):
    session = _Session(None)
    monkeypatch.setattr(main, "AsyncSessionLocal", lambda: session)

    await main._init_admin()

    assert len(session.added) == 1
    assert session.added[0].username == main.settings.FIRST_ADMIN_USERNAME
    assert session.added[0].email == main.settings.FIRST_ADMIN_EMAIL
    assert session.added[0].role == main.UserRole.admin
    assert session.commit_count == 1
