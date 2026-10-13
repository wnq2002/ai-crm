"""FastAPI 鉴权依赖。

- `get_session_record`：解析 Cookie → 校验会话（绝对/空闲超时、账号有效）。
- `get_current_user`：返回当前用户。
- `require_roles`：RBAC，服务端逐条校验角色。
- `require_csrf`：同步令牌 CSRF 校验（登录端点豁免）。
"""

from datetime import datetime, timezone
from typing import Callable

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.errors import forbidden, unauthorized
from app.core.security import constant_time_equals, hash_token
from app.models.user import User
from app.models.user_session import UserSession
from app.repositories import session_repository


def get_session_record(request: Request, db: Session = Depends(get_db)) -> UserSession:
    token = request.cookies.get(settings.cookie_name)
    if not token:
        raise unauthorized()

    session = session_repository.get_session_by_token_hash(db, hash_token(token))
    if session is None:
        raise unauthorized()

    now = datetime.now(timezone.utc)
    if session.expires_at <= now:
        session_repository.delete_session(db, session)
        db.commit()
        raise unauthorized("会话已过期，请重新登录")

    if (now - session.last_activity_at).total_seconds() > settings.session_idle_timeout:
        session_repository.delete_session(db, session)
        db.commit()
        raise unauthorized("会话因长时间未活动已失效，请重新登录")

    if not session.user.is_active:
        session_repository.delete_session(db, session)
        db.commit()
        raise unauthorized("账号已禁用")

    # 刷新最近活动时间（每次请求写一次，MVP 可接受）
    session.last_activity_at = now
    db.commit()
    return session


def get_current_user(
    session: UserSession = Depends(get_session_record),
) -> User:
    return session.user


def require_roles(*roles: str) -> Callable:
    def _dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise forbidden()
        return user

    return _dependency


def require_csrf(
    request: Request,
    session: UserSession = Depends(get_session_record),
) -> None:
    """双提交 Cookie 校验（ADR-016）：`X-CSRF-Token` 头 == `csrf_token` Cookie。

    依赖 get_session_record 以保证先鉴权（未登录返回 401 而非 403）。
    """
    header_token = request.headers.get("X-CSRF-Token", "")
    cookie_token = request.cookies.get(settings.csrf_cookie_name, "")
    if (
        not header_token
        or not cookie_token
        or not constant_time_equals(header_token, cookie_token)
    ):
        raise forbidden("CSRF 校验失败")
