"""用户数据访问。"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.user import User


def get_user_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    return db.get(User, user_id)


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == username))


def list_users(db: Session, page: int, page_size: int) -> tuple[list[User], int]:
    total = db.scalar(select(func.count()).select_from(User)) or 0
    stmt = (
        select(User)
        .order_by(User.created_at.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = list(db.scalars(stmt).all())
    return rows, total


def create_user(db: Session, user: User) -> User:
    db.add(user)
    db.flush()
    return user
