"""企业匹配、关联与客户管理服务（PRD §3.1/§5.5，api-contract §5）。"""

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.errors import conflict, not_found
from app.models.company import Company
from app.models.contact import Contact
from app.models.lead import Lead
from app.models.user import User
from app.repositories import company_repository
from app.schemas.company import (
    CompanyCreate,
    CompanyUpdate,
    ContactCreate,
    ContactUpdate,
)
from app.services import audit_service
from app.services.normalization import normalize_name


def match_company(
    db: Session, company_name_raw: str | None
) -> tuple[Company | None, list[Company]]:
    """按规范化企业名匹配：唯一完全匹配 → 自动关联；否则返回疑似候选（非阻塞）。"""
    if not company_name_raw:
        return None, []

    normalized = normalize_name(company_name_raw)
    if not normalized:
        return None, []

    exact_matches = company_repository.get_companies_by_normalized_name(db, normalized)
    if len(exact_matches) == 1:
        return exact_matches[0], []

    candidates = company_repository.search_companies_by_name(db, normalized)
    return None, candidates


def link_company(
    db: Session, lead: Lead, company_id: uuid.UUID, contact_id: uuid.UUID | None = None
) -> Company:
    company = company_repository.get_company_by_id(db, company_id)
    if company is None:
        raise not_found("企业不存在")

    lead.company_id = company.id
    if contact_id is not None:
        lead.contact_id = contact_id
    return company


def unlink_company(lead: Lead) -> None:
    lead.company_id = None


def list_companies(db: Session, page: int, page_size: int):
    rows, total = company_repository.list_companies(db, page, page_size)
    items = []
    for company, lead_count, recent_lead_at in rows:
        items.append(
            {
                "id": company.id,
                "canonical_name": company.canonical_name,
                "normalized_name": company.normalized_name,
                "aliases": company.aliases,
                "industry": company.industry,
                "phone": company.phone,
                "website": company.website,
                "created_at": company.created_at,
                "updated_at": company.updated_at,
                "lead_count": lead_count or 0,
                "recent_inquiry_at": recent_lead_at,
            }
        )
    return items, total


def create_company(db: Session, payload: CompanyCreate) -> Company:
    company = Company(
        canonical_name=payload.canonical_name,
        normalized_name=normalize_name(payload.canonical_name)
        or payload.canonical_name,
        aliases=payload.aliases,
        industry=payload.industry,
        phone=payload.phone,
        website=payload.website,
    )
    company_repository.create_company(db, company)
    db.commit()
    return company


def get_company_detail(db: Session, company_id: uuid.UUID) -> dict:
    company = company_repository.get_company_by_id(db, company_id)
    if company is None or company.merged_into_id is not None:
        raise not_found("企业不存在")
    contacts = company_repository.get_company_contacts(db, company_id)
    leads = company_repository.get_company_leads(db, company_id)
    return {"company": company, "contacts": contacts, "leads": leads}


def update_company(
    db: Session, company_id: uuid.UUID, payload: CompanyUpdate
) -> Company:
    company = company_repository.get_company_by_id(db, company_id)
    if company is None or company.merged_into_id is not None:
        raise not_found("企业不存在")

    if payload.canonical_name is not None:
        company.canonical_name = payload.canonical_name
        company.normalized_name = (
            normalize_name(payload.canonical_name) or payload.canonical_name
        )
    if payload.aliases is not None:
        company.aliases = payload.aliases
    if payload.industry is not None:
        company.industry = payload.industry
    if payload.phone is not None:
        company.phone = payload.phone
    if payload.website is not None:
        company.website = payload.website
    db.commit()
    return company


def get_company_leads(db: Session, company_id: uuid.UUID) -> list[Lead]:
    company = company_repository.get_company_by_id(db, company_id)
    if company is None:
        raise not_found("企业不存在")
    return company_repository.get_company_leads(db, company_id)


def merge_companies(
    db: Session, actor: User, source_id: uuid.UUID, target_id: uuid.UUID
) -> dict:
    source = company_repository.get_company_by_id(db, source_id)
    target = company_repository.get_company_by_id(db, target_id)
    if source is None or target is None:
        raise not_found("企业不存在")
    if source.id == target.id:
        raise conflict("不能将企业合并到自身")

    moved_leads = (
        db.execute(
            update(Lead)
            .where(Lead.company_id == source.id)
            .values(company_id=target.id)
        ).rowcount
        or 0
    )
    moved_contacts = (
        db.execute(
            update(Contact)
            .where(Contact.company_id == source.id)
            .values(company_id=target.id)
        ).rowcount
        or 0
    )

    source.merged_into_id = target.id
    audit_service.record(
        db,
        actor_id=actor.id,
        action="company.merge",
        resource_type="company",
        resource_id=str(source.id),
        after={
            "merged_into": str(target.id),
            "moved_leads": moved_leads,
            "moved_contacts": moved_contacts,
        },
    )
    db.commit()
    return {
        "merged_company_id": str(target.id),
        "moved_leads": moved_leads,
        "moved_contacts": moved_contacts,
    }


def merge_preview(db: Session, source_id: uuid.UUID, target_id: uuid.UUID) -> dict:
    source = company_repository.get_company_by_id(db, source_id)
    target = company_repository.get_company_by_id(db, target_id)
    if source is None or target is None:
        raise not_found("企业不存在")

    lead_relink = (
        db.scalar(
            select(func.count()).select_from(Lead).where(Lead.company_id == source.id)
        )
        or 0
    )
    contact_merge = (
        db.scalar(
            select(func.count())
            .select_from(Contact)
            .where(Contact.company_id == source.id)
        )
        or 0
    )
    return {
        "lead_relink_count": lead_relink,
        "contact_merge_count": contact_merge,
        "alias_destination": target.canonical_name,
    }


def create_contact(db: Session, payload: ContactCreate) -> Contact:
    contact = Contact(
        company_id=payload.company_id,
        name=payload.name,
        phone=payload.phone,
        email=payload.email,
        wechat_id=payload.wechat_id,
    )
    db.add(contact)
    db.commit()
    return contact


def update_contact(
    db: Session, contact_id: uuid.UUID, payload: ContactUpdate
) -> Contact:
    contact = db.get(Contact, contact_id)
    if contact is None:
        raise not_found("联系人不存在")

    for field in ("name", "phone", "email", "wechat_id"):
        new_value = getattr(payload, field)
        if new_value is not None:
            setattr(contact, field, new_value)
    db.commit()
    return contact
