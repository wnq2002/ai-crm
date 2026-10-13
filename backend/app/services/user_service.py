"""用户管理业务逻辑（管理员）。"""

import uuid

from sqlalchemy.orm import Session

from app.core.errors import conflict, not_found
from app.core.security import hash_password
from app.models.user import User
from app.repositories import session_repository, user_repository
from app.schemas.user import UserCreate, UserUpdate
from app.services import audit_service


def list_users(db: Session, page: int, page_size: int) -> tuple[list[User], int]:
    return user_repository.list_users(db, page, page_size)


def create_user(db: Session, actor: User, payload: UserCreate) -> User:
    if user_repository.get_user_by_username(db, payload.username) is not None:
        raise conflict("用户名已存在")

    user = User(
        username=payload.username,
        display_name=payload.display_name,
        role=payload.role,
        password_hash=hash_password(payload.password),
        is_active=True,
        must_change_password=True,
    )
    user_repository.create_user(db, user)
    audit_service.record(
        db,
        actor_id=actor.id,
        action="user.create",
        resource_type="user",
        resource_id=str(user.id),
        after={"username": user.username, "role": user.role},
    )
    db.commit()
    return user


def update_user(
    db: Session, actor: User, user_id: uuid.UUID, payload: UserUpdate
) -> User:
    user = user_repository.get_user_by_id(db, user_id)
    if user is None:
        raise not_found("用户不存在")

    # 角色变更（权限变更 → 审计）
    if payload.role is not None and payload.role != user.role:
        before_role = user.role
        user.role = payload.role
        audit_service.record(
            db,
            actor_id=actor.id,
            action="user.role_change",
            resource_type="user",
            resource_id=str(user.id),
            before={"role": before_role},
            after={"role": user.role},
        )

    # 禁用 / 启用（禁用即时撤销会话）
    if payload.is_active is not None and payload.is_active != user.is_active:
        user.is_active = payload.is_active
        if not user.is_active:
            session_repository.delete_sessions_for_user(db, user.id)
        audit_service.record(
            db,
            actor_id=actor.id,
            action="user.disable" if not user.is_active else "user.enable",
            resource_type="user",
            resource_id=str(user.id),
            after={"is_active": user.is_active},
        )

    # 重置密码（强制改密 + 撤销会话）
    if payload.new_password is not None:
        user.password_hash = hash_password(payload.new_password)
        user.must_change_password = True
        session_repository.delete_sessions_for_user(db, user.id)
        audit_service.record(
            db,
            actor_id=actor.id,
            action="user.password_reset",
            resource_type="user",
            resource_id=str(user.id),
        )

    if payload.display_name is not None:
        user.display_name = payload.display_name

    db.commit()
    return user
