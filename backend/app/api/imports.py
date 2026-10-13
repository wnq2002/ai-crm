"""线索导入路由（api-contract §8）。"""

import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_csrf
from app.core.db import get_db
from app.models.user import User
from app.services import import_service

router = APIRouter(prefix="/imports", tags=["imports"])


class CommitRequest(BaseModel):
    preview_token: str
    idempotency_key: str = Field(min_length=1, max_length=128)


@router.get("/template")
def template(_: User = Depends(get_current_user)):
    content = import_service.build_template_xlsx()
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="leads_import_template.xlsx"'
        },
    )


@router.post("/preview")
async def preview(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    __: None = Depends(require_csrf),
):
    content = await file.read()
    return import_service.preview(db, file.filename or "upload.xlsx", content)


@router.post("/commit")
def commit(
    payload: CommitRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
    _: None = Depends(require_csrf),
):
    return import_service.commit(
        db, actor, payload.preview_token, payload.idempotency_key
    )


@router.get("/{job_id}")
def result(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return import_service.get_result(db, job_id)
