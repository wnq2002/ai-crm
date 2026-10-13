"""企业客户与联系人路由（api-contract §5）。"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_csrf, require_roles
from app.core.db import get_db
from app.models.user import User
from app.schemas.common import Page
from app.schemas.company import (
    CompanyCreate,
    CompanyListItem,
    CompanyMergeRequest,
    CompanyOut,
    CompanyUpdate,
    ContactCreate,
    ContactOut,
    ContactUpdate,
)
from app.schemas.lead import LeadOut
from app.services import company_service

router = APIRouter(prefix="/companies", tags=["companies"])

contacts_router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.get("", response_model=Page[CompanyListItem])
def list_companies(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    items, total = company_service.list_companies(db, page, page_size)
    return {"items": items, "page": page, "page_size": page_size, "total": total}


@router.post("", response_model=CompanyOut)
def create_company(
    payload: CompanyCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    __: None = Depends(require_csrf),
):
    return company_service.create_company(db, payload)


@router.post("/merge-preview")
def merge_preview(
    payload: CompanyMergeRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
    __: None = Depends(require_csrf),
):
    return company_service.merge_preview(
        db, payload.source_company_id, payload.target_company_id
    )


@router.post("/merge")
def merge_companies(
    payload: CompanyMergeRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
    _: None = Depends(require_csrf),
):
    return company_service.merge_companies(
        db, actor, payload.source_company_id, payload.target_company_id
    )


@router.get("/{company_id}")
def get_company(
    company_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    detail = company_service.get_company_detail(db, company_id)
    company = detail["company"]
    return {
        "id": company.id,
        "canonical_name": company.canonical_name,
        "normalized_name": company.normalized_name,
        "aliases": company.aliases,
        "industry": company.industry,
        "phone": company.phone,
        "website": company.website,
        "merged_into_id": company.merged_into_id,
        "created_at": company.created_at,
        "updated_at": company.updated_at,
        "contacts": [ContactOut.model_validate(c) for c in detail["contacts"]],
        "leads": [LeadOut.model_validate(lead) for lead in detail["leads"]],
    }


@router.patch("/{company_id}", response_model=CompanyOut)
def update_company(
    company_id: uuid.UUID,
    payload: CompanyUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    __: None = Depends(require_csrf),
):
    return company_service.update_company(db, company_id, payload)


@router.get("/{company_id}/leads", response_model=list[LeadOut])
def get_company_leads(
    company_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return company_service.get_company_leads(db, company_id)


@router.get("/{company_id}/contacts", response_model=list[ContactOut])
def list_company_contacts(
    company_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return company_service.get_company_detail(db, company_id)["contacts"]


@router.post("/{company_id}/contacts", response_model=ContactOut)
def create_company_contact(
    company_id: uuid.UUID,
    payload: ContactCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    __: None = Depends(require_csrf),
):
    payload.company_id = company_id
    return company_service.create_contact(db, payload)


@contacts_router.patch("/{contact_id}", response_model=ContactOut)
def update_contact(
    contact_id: uuid.UUID,
    payload: ContactUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    __: None = Depends(require_csrf),
):
    return company_service.update_contact(db, contact_id, payload)
