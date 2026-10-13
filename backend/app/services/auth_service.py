"""认证业务逻辑。"""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.auth.rate_limit import login_rate_limiter
from app.core.config import settings
from app.core.errors import APIError, rate_limited
from app.core.security import (
    generate_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.user import User
from app.models.user_session import UserSession
from app.repositories import session_repository, user_repository
from app.services import audit_service


def login(db: Session, username: str, password: str, ip: str) -> tuple[str, str, User]:
    """登录：校验凭据 + 限流，成功后创建服务端会话。

    返回 (session_token, csrf_token, user)。
    """
    key = f"login:{username}:{ip}"
    if not login_rate_limiter.is_allowed(key):
        raise rate_limited()

    user = user_repository.get_user_by_username(db, username)
    if user is None or not verify_password(password, user.password_hash):
        raise APIError(401, "UNAUTHORIZED", "用户名或密码错误")

    if not user.is_active:
        raise APIError(401, "UNAUTHORIZED", "账号已禁用")

    login_rate_limiter.reset(key)

    token = generate_token()
    csrf_token = generate_token()
    now = datetime.now(timezone.utc)
    session = UserSession(
        user_id=user.id,
        token_hash=hash_token(token),
        csrf_token=csrf_token,
        last_activity_at=now,
        expires_at=now + timedelta(seconds=settings.session_absolute_timeout),
    )
    session_repository.create_session(db, session)
    db.commit()
    return token, csrf_token, user


def logout(db: Session, session: UserSession) -> None:
    session_repository.delete_session(db, session)
    db.commit()


def change_password(
    db: Session, session: UserSession, old_password: str, new_password: str
) -> User:
    """修改密码：校验旧密码，更新哈希，清除 must_change_password 并撤销其他会话。"""
    user = session.user
    if not verify_password(old_password, user.password_hash):
        raise APIError(401, "UNAUTHORIZED", "旧密码不正确")

    user.password_hash = hash_password(new_password)
    user.must_change_password = False

    # 撤销该用户其他会话，仅保留当前会话（避免旧密码会话残留）
    session_repository.delete_sessions_for_user_except(db, user.id, session.id)
    audit_service.record(
        db,
        actor_id=user.id,
        action="user.password_change",
        resource_type="user",
        resource_id=str(user.id),
    )
    db.commit()
    return user
