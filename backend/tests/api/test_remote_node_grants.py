"""D5 节点授权：按用户/项目授予、只读/读写矩阵、撤销与审计（对应验收矩阵）。"""

from __future__ import annotations

import base64
import time

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.v1 import remote_nodes as rn
from app.models.audit import AuditLog
from app.models.base import Base
from app.models.bootstrap import load_all_models
from app.models.project import Project
from app.models.remote_node_grant import RemoteNodeGrant
from app.models.user import User, UserRole
from app.models.user_project import ProjectRole, UserProject

load_all_models()

ADMIN = User(id=1, username="admin", email="admin@test.local", hashed_password="x", role=UserRole.admin, is_active=True)
ENGINEER = User(
    id=10, username="eng", email="eng@test.local", hashed_password="x", role=UserRole.engineer, is_active=True
)
VIEWER = User(
    id=11, username="view", email="view@test.local", hashed_password="x", role=UserRole.viewer, is_active=True
)
OUTSIDER = User(
    id=12, username="out", email="out@test.local", hashed_password="x", role=UserRole.tester, is_active=True
)


class FakeChannel:
    """替代 NodeChannel：记录被转发的方法/路径/请求体，返回固定响应。"""

    def __init__(self, status: int = 200) -> None:
        self.calls: list[tuple[str, str, bytes]] = []
        self.status = status

    async def send_request(self, method, path, headers, body):
        self.calls.append((method, path, body))
        return {
            "status": self.status,
            "headers": {"content-type": "application/json"},
            "body": base64.b64encode(b'{"ok":true}').decode("ascii"),
        }


def _register_node(client_id: str, *, online: bool = False) -> FakeChannel:
    channel = FakeChannel()
    rn._NODE_REGISTRY[client_id] = {
        "machine_name": f"PC-{client_id}",
        "last_seen_ts": time.time() if online else 0.0,
        "last_seen_at": "2026-11-02T00:00:00Z",
        "capabilities": [],
    }
    if online:
        rn._NODE_CHANNELS[client_id] = channel
    return channel


async def _make_env(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'grants.sqlite3'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db():
        async with sessions() as session:
            yield session

    actors: dict[str, User] = {"current": ADMIN, "admin": ADMIN}
    app = FastAPI()
    app.include_router(rn.router, prefix="/api/v1")
    app.dependency_overrides[rn.get_db] = override_get_db
    app.dependency_overrides[rn.get_current_user] = lambda: actors["current"]
    app.dependency_overrides[rn.require_admin] = lambda: actors["admin"]
    monkeypatch.setattr(rn, "AsyncSessionLocal", sessions)
    return app, sessions, actors


async def _seed_base(sessions) -> None:
    async with sessions() as db:
        db.add_all(
            [
                User(id=1, username="admin", email="admin@test.local", hashed_password="x", role=UserRole.admin),
                User(id=10, username="eng", email="eng@test.local", hashed_password="x", role=UserRole.engineer),
                User(id=11, username="view", email="view@test.local", hashed_password="x", role=UserRole.viewer),
                User(id=12, username="out", email="out@test.local", hashed_password="x", role=UserRole.tester),
                Project(id=5, name="P5", owner_id=1),
            ]
        )
        await db.commit()


async def _audit_actions(sessions) -> list[str]:
    async with sessions() as db:
        return list((await db.scalars(select(AuditLog.action))).all())


@pytest.fixture(autouse=True)
def _clean_node_state():
    yield
    rn._NODE_REGISTRY.clear()
    rn._NODE_CHANNELS.clear()


@pytest.mark.asyncio
async def test_grant_crud_validates_subjects_and_audits(tmp_path, monkeypatch):
    app, sessions, _actors = await _make_env(tmp_path, monkeypatch)
    await _seed_base(sessions)
    _register_node("win-a")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        base = "/api/v1/remote-nodes"
        assert (
            await client.post(
                f"{base}/ghost/grants",
                json={"subject_type": "user", "subject_id": 10, "access_level": "read_only"},
            )
        ).status_code == 404
        assert (
            await client.post(
                f"{base}/win-a/grants",
                json={"subject_type": "user", "subject_id": 999, "access_level": "read_only"},
            )
        ).status_code == 404
        assert (
            await client.post(
                f"{base}/win-a/grants",
                json={"subject_type": "project", "subject_id": 999, "access_level": "read_only"},
            )
        ).status_code == 404
        assert (
            await client.post(
                f"{base}/win-a/grants",
                json={"subject_type": "user", "subject_id": 11, "access_level": "read_write"},
            )
        ).status_code == 400
        created = await client.post(
            f"{base}/win-a/grants",
            json={"subject_type": "user", "subject_id": 10, "access_level": "read_write"},
        )
        assert created.status_code == 201
        body = created.json()
        assert body["subject_type"] == "user"
        assert body["subject_name"] == "eng"
        assert body["created_by"] == "admin"
        assert body["revoked_at"] is None
        duplicate = await client.post(
            f"{base}/win-a/grants",
            json={"subject_type": "user", "subject_id": 10, "access_level": "read_only"},
        )
        assert duplicate.status_code == 409
        project_grant = await client.post(
            f"{base}/win-a/grants",
            json={"subject_type": "project", "subject_id": 5, "access_level": "read_only"},
        )
        assert project_grant.status_code == 201
        assert project_grant.json()["subject_name"] == "P5"
        listed = (await client.get(f"{base}/win-a/grants")).json()
        assert {item["subject_name"] for item in listed} == {"eng", "P5"}
    assert (await _audit_actions(sessions)).count("remote_node_grant_created") == 2


@pytest.mark.asyncio
async def test_unauthorized_user_is_denied_audited_and_admin_still_passes(tmp_path, monkeypatch):
    app, sessions, actors = await _make_env(tmp_path, monkeypatch)
    await _seed_base(sessions)
    channel = _register_node("win-a", online=True)
    url = "/api/v1/remote-nodes/win-a/proxy/api/v1/projects"
    actors["current"] = OUTSIDER
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get(url)).status_code == 403
        assert (await client.post(url, json={"name": "x"})).status_code == 403
    assert channel.calls == []
    assert (await _audit_actions(sessions)).count("remote_node_access_denied") == 2
    # 管理员无需授权即可访问（保留原有行为）
    actors["current"] = ADMIN
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get(url)).status_code == 200
    assert [call[0] for call in channel.calls] == ["GET"]


@pytest.mark.asyncio
async def test_read_write_grant_allows_reads_and_audits_writes(tmp_path, monkeypatch):
    app, sessions, actors = await _make_env(tmp_path, monkeypatch)
    await _seed_base(sessions)
    channel = _register_node("win-a", online=True)
    async with sessions() as db:
        db.add(RemoteNodeGrant(node_client_id="win-a", user_id=10, access_level="read_write", created_by_id=1))
        await db.commit()
    actors["current"] = ENGINEER
    url = "/api/v1/remote-nodes/win-a/proxy/api/v1/projects"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get(url)).status_code == 200
        assert (await client.post(url, json={"name": "x"})).status_code == 200
    assert [call[0] for call in channel.calls] == ["GET", "POST"]
    actions = await _audit_actions(sessions)
    assert actions.count("remote_node_proxy_write") == 1
    assert "remote_node_access_denied" not in actions


@pytest.mark.asyncio
async def test_grant_is_scoped_to_one_node(tmp_path, monkeypatch):
    app, sessions, actors = await _make_env(tmp_path, monkeypatch)
    await _seed_base(sessions)
    _register_node("win-a", online=True)
    channel_b = _register_node("win-b", online=True)
    async with sessions() as db:
        db.add(RemoteNodeGrant(node_client_id="win-a", user_id=10, access_level="read_write", created_by_id=1))
        await db.commit()
    actors["current"] = ENGINEER
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/api/v1/remote-nodes/win-a/proxy/api/v1/projects")).status_code == 200
        assert (await client.get("/api/v1/remote-nodes/win-b/proxy/api/v1/projects")).status_code == 403
    assert channel_b.calls == []


@pytest.mark.asyncio
async def test_read_only_grant_blocks_every_write_method(tmp_path, monkeypatch):
    app, sessions, actors = await _make_env(tmp_path, monkeypatch)
    await _seed_base(sessions)
    channel = _register_node("win-a", online=True)
    async with sessions() as db:
        db.add(RemoteNodeGrant(node_client_id="win-a", user_id=10, access_level="read_only", created_by_id=1))
        await db.commit()
    actors["current"] = ENGINEER
    url = "/api/v1/remote-nodes/win-a/proxy/api/v1/projects"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get(url)).status_code == 200
        for method in ("post", "put", "patch", "delete"):
            response = await getattr(client, method)(url)
            assert response.status_code == 403, method
    assert [call[0] for call in channel.calls] == ["GET"]
    assert (await _audit_actions(sessions)).count("remote_node_access_denied") == 4


@pytest.mark.asyncio
async def test_project_grant_follows_membership_and_clamps_viewer_member(tmp_path, monkeypatch):
    app, sessions, actors = await _make_env(tmp_path, monkeypatch)
    await _seed_base(sessions)
    _register_node("win-a", online=True)
    async with sessions() as db:
        db.add(RemoteNodeGrant(node_client_id="win-a", project_id=5, access_level="read_write", created_by_id=1))
        db.add_all(
            [
                UserProject(user_id=10, project_id=5, role=ProjectRole.editor),
                UserProject(user_id=11, project_id=5, role=ProjectRole.viewer),
            ]
        )
        await db.commit()
    url = "/api/v1/remote-nodes/win-a/proxy/api/v1/projects"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        actors["current"] = ENGINEER
        assert (await client.get(url)).status_code == 200
        assert (await client.post(url, json={"name": "x"})).status_code == 200
        actors["current"] = VIEWER
        assert (await client.get(url)).status_code == 200
        assert (await client.post(url, json={"name": "x"})).status_code == 403
    # 成员被移出项目后授权立即失效（每次请求实时解析成员关系）
    async with sessions() as db:
        await db.execute(delete(UserProject).where(UserProject.user_id == 10))
        await db.commit()
    actors["current"] = ENGINEER
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get(url)).status_code == 403


@pytest.mark.asyncio
async def test_global_viewer_role_stays_read_only_even_with_read_write_row(tmp_path, monkeypatch):
    app, sessions, actors = await _make_env(tmp_path, monkeypatch)
    await _seed_base(sessions)
    _register_node("win-a", online=True)
    async with sessions() as db:
        # 即便存在 read_write 记录（历史数据），全局 viewer 角色也只读
        db.add(RemoteNodeGrant(node_client_id="win-a", user_id=11, access_level="read_write", created_by_id=1))
        await db.commit()
    actors["current"] = VIEWER
    url = "/api/v1/remote-nodes/win-a/proxy/api/v1/projects"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get(url)).status_code == 200
        assert (await client.post(url, json={"name": "x"})).status_code == 403


@pytest.mark.asyncio
async def test_revoke_blocks_future_access_and_keeps_auditable_record(tmp_path, monkeypatch):
    app, sessions, actors = await _make_env(tmp_path, monkeypatch)
    await _seed_base(sessions)
    _register_node("win-a", online=True)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        base = "/api/v1/remote-nodes/win-a"
        created = await client.post(
            f"{base}/grants",
            json={"subject_type": "user", "subject_id": 10, "access_level": "read_write"},
        )
        assert created.status_code == 201
        grant_id = created.json()["id"]
        actors["current"] = ENGINEER
        assert (await client.get(f"{base}/proxy/api/v1/projects")).status_code == 200
        revoked = await client.delete(f"{base}/grants/{grant_id}")
        assert revoked.status_code == 200
        assert revoked.json()["revoked_at"] is not None
        assert revoked.json()["revoked_by"] == "admin"
        # 撤销立即生效，且记录保留可查
        assert (await client.get(f"{base}/proxy/api/v1/projects")).status_code == 403
        assert (await client.delete(f"{base}/grants/{grant_id}")).status_code == 409
        assert (await client.get(f"{base}/grants")).json() == []
        with_revoked = (await client.get(f"{base}/grants", params={"include_revoked": "true"})).json()
        assert len(with_revoked) == 1
        assert with_revoked[0]["revoked_at"] is not None
    actions = await _audit_actions(sessions)
    assert actions.count("remote_node_grant_created") == 1
    assert actions.count("remote_node_grant_revoked") == 1
    assert actions.count("remote_node_access_denied") == 1
