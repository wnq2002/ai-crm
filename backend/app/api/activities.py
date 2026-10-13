"""跟进活动撤销路由（api-contract §6）。"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_csrf
from app.core.db import get_db
from app.models.user import User
from app.schemas.activity import ActivityOut, ActivityReviseRequest, RevokeRequest
from app.services import activity_service

router = APIRouter(prefix="/activities", tags=["activities"])


@router.patch("/{activity_id}", response_model=ActivityOut)
def revise_activity(
    activity_id: uuid.UUID,
    payload: ActivityReviseRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
    _: None = Depends(require_csrf),
):
    return activity_service.revise_activity(db, actor, activity_id, payload)


@router.post("/{activity_id}/revoke", response_model=ActivityOut)
def revoke_activity(
    activity_id: uuid.UUID,
    payload: RevokeRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
    _: None = Depends(require_csrf),
):
    return activity_service.revoke_activity(db, actor, activity_id, payload.reason)
