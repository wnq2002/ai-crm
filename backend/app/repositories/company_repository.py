"""企业数据访问。"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.contact import Contact
from app.models.lead import Lead


def get_company_by_id(db: Session, company_id: uuid.UUID) -> Company | None:
    return db.get(Company, company_id)


def get_companies_by_normalized_name(
    db: Session, normalized_name: str
) -> list[Company]:
    return list(
        db.scalars(
            select(Company).where(Company.normalized_name == normalized_name)
        ).all()
    )


def search_companies_by_name(db: Session, fragment: str) -> list[Company]:
    like = f"%{fragment}%"
    return list(
        db.scalars(
            select(Company).where(Company.normalized_name.ilike(like)).limit(10)
        ).all()
    )


def create_company(db: Session, company: Company) -> Company:
    db.add(company)
    db.flush()
    return company


def list_companies(db: Session, page: int, page_size: int):
    lead_agg = (
        select(
            Lead.company_id,
            func.count(Lead.id).label("lead_count"),
            func.max(Lead.occurred_at).label("recent_lead_at"),
        )
        .where(Lead.company_id.isnot(None), Lead.archived_at.is_(None))
        .group_by(Lead.company_id)
        .subquery()
    )

    base = select(Company).where(Company.merged_into_id.is_(None))
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0

    rows = db.execute(
        select(Company, lead_agg.c.lead_count, lead_agg.c.recent_lead_at)
        .outerjoin(lead_agg, Company.id == lead_agg.c.company_id)
        .where(Company.merged_into_id.is_(None))
        .order_by(Company.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return rows, total


def get_company_leads(db: Session, company_id: uuid.UUID) -> list[Lead]:
    return list(
        db.scalars(
            select(Lead)
            .where(Lead.company_id == company_id, Lead.archived_at.is_(None))
            .order_by(Lead.occurred_at.desc())
        ).all()
    )


def get_company_contacts(db: Session, company_id: uuid.UUID) -> list[Contact]:
    return list(
        db.scalars(
            select(Contact)
            .where(Contact.company_id == company_id)
            .order_by(Contact.created_at.asc())
        ).all()
    )
