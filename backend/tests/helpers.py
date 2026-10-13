"""测试辅助函数。"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User


def make_user(
    db: Session,
    username: str,
    password: str,
    role: str,
    *,
    is_active: bool = True,
    must_change_password: bool = False,
) -> User:
    user = User(
        username=username,
        display_name=username,
        role=role,
        password_hash=hash_password(password),
        is_active=is_active,
        must_change_password=must_change_password,
    )
    db.add(user)
    db.commit()
    return user


def login(client: TestClient, username: str, password: str):
    return client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )


def get_csrf(client: TestClient) -> str:
    return client.cookies["csrf_token"]
