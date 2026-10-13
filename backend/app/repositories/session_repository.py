"""会话数据访问。"""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.user_session import UserSession


def get_session_by_token_hash(db: Session, token_hash: str) -> UserSession | None:
    return db.scalar(select(UserSession).where(UserSession.token_hash == token_hash))


def create_session(db: Session, session: UserSession) -> UserSession:
    db.add(session)
    db.flush()
    return session


def delete_session(db: Session, session: UserSession) -> None:
    db.delete(session)


def delete_sessions_for_user(db: Session, user_id: uuid.UUID) -> int:
    result = db.execute(delete(UserSession).where(UserSession.user_id == user_id))
    return result.rowcount or 0


def delete_sessions_for_user_except(
    db: Session, user_id: uuid.UUID, keep_session_id: uuid.UUID
) -> int:
    result = db.execute(
        delete(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.id != keep_session_id,
        )
    )
    return result.rowcount or 0
