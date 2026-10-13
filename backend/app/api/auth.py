"""认证路由（api-contract §2 / ADR-016）。"""

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.auth.dependencies import get_session_record, require_csrf
from app.core.config import settings
from app.core.db import get_db
from app.models.user_session import UserSession
from app.schemas.auth import ChangePasswordRequest, LoginRequest
from app.schemas.user import UserOut
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_cookies(response: Response, session_token: str, csrf_token: str) -> None:
    response.set_cookie(
        key=settings.cookie_name,
        value=session_token,
        httponly=True,
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
        max_age=settings.session_absolute_timeout,
        path="/",
    )
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf_token,
        httponly=False,
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
        max_age=settings.session_absolute_timeout,
        path="/",
    )


@router.post("/login", response_model=UserOut)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    client_ip = request.client.host if request.client else "unknown"
    token, csrf_token, user = auth_service.login(
        db, payload.username, payload.password, client_ip
    )
    _set_cookies(response, token, csrf_token)
    return user


@router.post("/logout")
def logout(
    response: Response,
    session: UserSession = Depends(get_session_record),
    _: None = Depends(require_csrf),
    db: Session = Depends(get_db),
):
    auth_service.logout(db, session)
    response.delete_cookie(settings.cookie_name, path="/")
    response.delete_cookie(settings.csrf_cookie_name, path="/")
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(
    request: Request,
    response: Response,
    session: UserSession = Depends(get_session_record),
):
    # 已认证但缺失 csrf_token Cookie 时补发（ADR-016）
    if settings.csrf_cookie_name not in request.cookies:
        response.set_cookie(
            key=settings.csrf_cookie_name,
            value=session.csrf_token,
            httponly=False,
            samesite=settings.cookie_samesite,
            secure=settings.cookie_secure,
            max_age=settings.session_absolute_timeout,
            path="/",
        )
    return session.user


@router.post("/change-password", response_model=UserOut)
def change_password(
    payload: ChangePasswordRequest,
    session: UserSession = Depends(get_session_record),
    _: None = Depends(require_csrf),
    db: Session = Depends(get_db),
):
    return auth_service.change_password(
        db, session, payload.old_password, payload.new_password
    )
