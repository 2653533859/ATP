"""
请求级别 trace_id 注入中间件

每个 HTTP 请求生成唯一 trace_id，存入 ContextVar，
供日志 Formatter 自动附加。响应头返回 X-Trace-ID。
"""
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")


class TraceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        tid = uuid.uuid4().hex[:16]
        trace_id_var.set(tid)
        response = await call_next(request)
        response.headers["X-Trace-ID"] = tid
        return response
