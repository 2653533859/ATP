"""
CSRF 防护中间件

对 state-changing 请求（POST/PUT/PATCH/DELETE）检查必须携带
Authorization 或 X-Requested-With header，防止跨站表单伪造。

白名单路径（不做检查）：
- /health
- /mock/  （Mock 服务可被外部直接调用）
- /docs, /openapi.json （Swagger UI）
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_WHITELIST_PREFIXES = ("/health", "/mock/", "/docs", "/openapi.json", "/redoc")
_WHITELIST_PATHS = {"/api/v1/auth/login", "/api/v1/auth/refresh"}


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in _UNSAFE_METHODS:
            path = request.url.path
            if path not in _WHITELIST_PATHS and not any(path.startswith(p) for p in _WHITELIST_PREFIXES):
                has_auth = "authorization" in request.headers
                has_xhr = "x-requested-with" in request.headers
                has_api_key = "x-api-key" in request.headers
                if not (has_auth or has_xhr or has_api_key):
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "CSRF check failed: missing required header"},
                    )
        return await call_next(request)
