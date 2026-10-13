"""管理员用户管理路由（api-contract §11）。"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_csrf, require_roles
from app.core.db import get_db
from app.models.user import User
from app.schemas.common import Page
from app.schemas.user import UserCreate, UserOut, UserUpdate
from app.services import user_service

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_roles("admin"))],
)


@router.get("/users", response_model=Page[UserOut])
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    rows, total = user_service.list_users(db, page, page_size)
    return {"items": rows, "page": page, "page_size": page_size, "total": total}


@router.post("/users", response_model=UserOut)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
    _: None = Depends(require_csrf),
):
    return user_service.create_user(db, actor, payload)


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
    _: None = Depends(require_csrf),
):
    return user_service.update_user(db, actor, user_id, payload)
