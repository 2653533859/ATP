"""
请求级别 trace_id 注入中间件

每个 HTTP 请求生成唯一 trace_id，存入共享 tracing helper，
供日志 Formatter 自动附加。响应头返回 X-Trace-ID。
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.tracing import generate_trace_id, reset_trace_id, set_trace_id


class TraceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        tid = generate_trace_id()
        token = set_trace_id(tid)
        try:
            response = await call_next(request)
            response.headers["X-Trace-ID"] = tid
            return response
        finally:
            reset_trace_id(token)
