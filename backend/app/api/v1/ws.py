"""
WebSocket 端点：订阅 Redis Pub/Sub，将执行事件实时推送给前端

路径：/ws/runs/{run_id}
协议：ws://
"""
import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import decode_token
from app.core.redis_client import get_async_redis
from app.models.case import TestCase, TestRun
from app.models.project import Module, Project
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)

ws_router = APIRouter(prefix="/ws")


async def _get_ws_user(websocket: WebSocket) -> User | None:
    token = websocket.query_params.get("token")
    if not token:
        return None

    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        username = payload["sub"]
    except (JWTError, KeyError):
        return None

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        if user is None or not user.is_active:
            return None
        return user


async def _can_subscribe_run(run_id: int, user: User) -> bool:
    async with AsyncSessionLocal() as db:
        run = await db.get(TestRun, run_id)
        if run is None:
            return False

        if user.role == UserRole.admin:
            return True
        if run.triggered_by == user.id:
            return True

        case = await db.get(TestCase, run.case_id)
        if case is None:
            return False
        if case.creator_id == user.id:
            return True

        module = await db.get(Module, case.module_id)
        if module is None:
            return False
        project = await db.get(Project, module.project_id)
        if project is None:
            return False
        return project.owner_id == user.id


@ws_router.websocket("/runs/{run_id}")
async def ws_run_events(websocket: WebSocket, run_id: int):
    """
    订阅执行 {run_id} 的实时事件流。

    消息类型：
      run_status  - run 状态变更
      step_result - 单步骤执行完成
      completed   - 执行结束（前端收到后可关闭）
    """
    user = await _get_ws_user(websocket)
    if user is None:
        await websocket.close(code=1008, reason="Unauthorized")
        return
    if not await _can_subscribe_run(run_id, user):
        await websocket.close(code=1008, reason="Forbidden")
        return

    await websocket.accept()
    redis = None
    pubsub = None
    channel = f"atp:run:{run_id}"

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
