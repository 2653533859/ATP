import asyncio
import sys
import types
from pathlib import Path

from starlette.responses import Response


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.middleware.csrf import CSRFMiddleware


def _request(path: str, method: str = "POST", headers: dict | None = None):
    return types.SimpleNamespace(
        method=method,
        url=types.SimpleNamespace(path=path),
        headers=headers or {},
    )


def _middleware():
    return CSRFMiddleware(app=lambda *_args, **_kwargs: None)


def test_csrf_allows_auth_login_without_custom_headers():
    async def call_next(_request):
        return Response(status_code=204)

    response = asyncio.run(
        _middleware().dispatch(
            _request("/api/v1/auth/login"),
            call_next,
        )
    )

    assert response.status_code == 204


def test_csrf_allows_auth_refresh_without_custom_headers():
    async def call_next(_request):
        return Response(status_code=204)

    response = asyncio.run(
        _middleware().dispatch(
            _request("/api/v1/auth/refresh"),
            call_next,
        )
    )

    assert response.status_code == 204


def test_csrf_still_blocks_anonymous_state_change_requests():
    async def call_next(_request):
        return Response(status_code=204)

    response = asyncio.run(
        _middleware().dispatch(
            _request("/api/v1/projects"),
            call_next,
        )
    )

    assert response.status_code == 403
