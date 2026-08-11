from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.core.security import verify_password, create_access_token, create_refresh_token, decode_token
from app.models.user import User
from app.schemas.auth import AuthSessionResponse, LoginRequest, RefreshRequest, TokenResponse, UserOut
from app.api.deps import get_current_user
from app.services.audit import write_audit_log
from jwt import InvalidTokenError

router = APIRouter(prefix="/auth", tags=["认证"])


ACCESS_COOKIE = "atp_access_token"
REFRESH_COOKIE = "atp_refresh_token"


def _cookie_samesite() -> str:
    value = settings.APP_AUTH_COOKIE_SAMESITE.lower().strip()
    return value if value in {"lax", "strict", "none"} else "lax"


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    common = {
        "httponly": True,
        "secure": settings.APP_AUTH_COOKIE_SECURE,
        "samesite": _cookie_samesite(),
    }
    response.set_cookie(ACCESS_COOKIE, access_token, max_age=settings.APP_ACCESS_TOKEN_EXPIRE_MINUTES * 60, path="/", **common)
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=settings.APP_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/api/v1/auth",
        **common,
    )


def _uses_browser_session(request: Request) -> bool:
    """Identify the first-party browser client without exposing tokens in its response."""
    return request.headers.get("x-requested-with", "").strip().lower() == "xmlhttprequest"


def _build_auth_response(
    request: Request, response: Response, access_token: str, refresh_token: str
) -> AuthSessionResponse | TokenResponse:
    _set_auth_cookies(response, access_token, refresh_token)
    if _uses_browser_session(request):
        return AuthSessionResponse(authenticated=True)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth")


@router.post("/login", response_model=AuthSessionResponse | TokenResponse)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
async def login(request: Request, response: Response, body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用")
    await write_audit_log(
        db,
        action="login",
        resource_type="user",
        resource_id=user.id,
        username=user.username,
        ip_address=request.client.host if request.client else "",
    )
    await db.commit()
    return _build_auth_response(
        request, response, create_access_token(user.username), create_refresh_token(user.username)
    )


@router.post("/refresh", response_model=AuthSessionResponse | TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    body: RefreshRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    refresh_token = (body.refresh_token if body else None) or request.cookies.get(REFRESH_COOKIE)
    try:
        if not refresh_token:
            raise InvalidTokenError("missing refresh token")
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise InvalidTokenError("wrong token type")
        username = payload["sub"]
    except (InvalidTokenError, KeyError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return _build_auth_response(request, response, create_access_token(username), create_refresh_token(username))


@router.post("/logout", response_model=AuthSessionResponse)
async def logout(response: Response):
    _clear_auth_cookies(response)
    return AuthSessionResponse(authenticated=False)


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    return current_user
