"""
WebSocket 端点：订阅 Redis Pub/Sub，将执行事件实时推送给前端

路径：/ws/runs/{run_id}
协议：ws://
"""

import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jwt import InvalidTokenError
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import decode_token
from app.core.redis_client import get_async_redis
from app.models.case import TestCase, TestRun
from app.models.mobile_special import MobileSpecialRun, MobileSpecialTask
from app.models.project import Module, Project
from app.models.user import User, UserRole
from app.models.user_project import UserProject

logger = logging.getLogger(__name__)

ws_router = APIRouter(prefix="/ws")


async def _get_ws_user(websocket: WebSocket) -> User | None:
    # Browser clients use the HttpOnly cookie. Keep query-token support temporarily for
    # non-browser integrations, but the UI must never put a JWT in a URL.
    token = getattr(websocket, "cookies", {}).get("atp_access_token") or websocket.query_params.get("token")
    if not token:
        return None

    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        username = payload["sub"]
    except (InvalidTokenError, KeyError):
        return None

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        if user is None or not user.is_active:
            return None
        return user


async def _can_subscribe_run(run_id: int, user: User, run_type: str = "case") -> bool:
    if run_type not in {"case", "mobile"}:
        return False
    async with AsyncSessionLocal() as db:
        if run_type == "case":
            run = await db.get(TestRun, run_id)
            if run is None:
                return False
            if user.role == UserRole.admin:
                return True
            if run.triggered_by == user.id:
                return True

            case = await db.get(TestCase, run.case_id)
            if case is not None:
                if case.creator_id == user.id:
                    return True

                module = await db.get(Module, case.module_id)
                if module is not None:
                    # P3.C 项目成员（UserProject）也可订阅
                    membership = await db.execute(
                        select(UserProject.id).where(
                            UserProject.user_id == user.id,
                            UserProject.project_id == module.project_id,
                        )
                    )
                    if membership.scalar_one_or_none() is not None:
                        return True
                    project = await db.get(Project, module.project_id)
                    if project is not None and project.owner_id == user.id:
                        return True
            return False

        mobile_run = await db.get(MobileSpecialRun, run_id)
        if mobile_run is None:
            return False
        if user.role == UserRole.admin or mobile_run.triggered_by == user.id:
            return True

        mobile_task = await db.get(MobileSpecialTask, mobile_run.task_id)
        if mobile_task is None:
            return False
        membership = await db.execute(
            select(UserProject.id).where(
                UserProject.user_id == user.id,
                UserProject.project_id == mobile_task.project_id,
            )
        )
        if membership.scalar_one_or_none() is not None:
            return True
        project = await db.get(Project, mobile_task.project_id)
        return project is not None and project.owner_id == user.id


@ws_router.websocket("/runs/{run_id}")
async def ws_run_events(websocket: WebSocket, run_id: int):
    """
    订阅执行 {run_id} 的实时事件流。

    消息类型：
      run_status  - run 状态变更
      step_result - 单步骤执行完成
      completed   - 执行结束（前端收到后可关闭）
    """
    run_type = websocket.query_params.get("run_type", "case")
    user = await _get_ws_user(websocket)
    if user is None:
        await websocket.close(code=1008, reason="Unauthorized")
        return
    if not await _can_subscribe_run(run_id, user, run_type):
        await websocket.close(code=1008, reason="Forbidden")
        return

    await websocket.accept()
    redis = None
    pubsub = None
    channel = f"atp:run:{run_type}:{run_id}"

    try:
        redis = get_async_redis()
        pubsub = redis.pubsub()
        await pubsub.subscribe(channel)
        logger.info(f"WS client connected for run {run_id}")

        # 轮询 Redis 消息，同时检测 WebSocket 断开
        while True:
            # 非阻塞获取，避免长时间挂起导致 WebSocket 心跳失败
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
            if message and message["type"] == "message":
                data: str = message["data"]
                await websocket.send_text(data)

                # 收到 completed 消息后服务端主动关闭
                import json as _json

                try:
                    payload = _json.loads(data)
                    if payload.get("type") == "completed":
                        break
                except Exception:
                    pass

            await asyncio.sleep(0.05)  # 让出事件循环

    except WebSocketDisconnect:
        logger.info(f"WS client disconnected for run {run_id}")
    except Exception as e:
        logger.error(f"WS error for run {run_id}: {e}")
    finally:
        if pubsub is not None:
            await pubsub.unsubscribe(channel)
        if redis is not None:
            await redis.aclose()
        try:
            await websocket.close()
        except Exception:
            pass
