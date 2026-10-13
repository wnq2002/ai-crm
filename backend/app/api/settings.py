"""配置字典路由（api-contract §10）。

GET 对 market 与 admin 开放；写操作（POST/PATCH/PUT）仅 admin 且需 CSRF，
并写审计日志（操作人/时间/资源/前后值，敏感字段脱敏）。
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_csrf, require_roles
from app.core.db import get_db
from app.core.errors import conflict, not_found
from app.models.department import Department, DepartmentContact
from app.models.lead import Lead
from app.models.lead_event import LeadEvent, LeadHandoff
from app.models.lead_need_type import LeadNeedType
from app.models.lead_source import LeadSourceCategory, LeadSourceDetail
from app.models.user import User
from app.schemas.dictionary import (
    DepartmentContactCreate,
    DepartmentContactOut,
    DepartmentContactUpdate,
    DepartmentCreate,
    DepartmentOut,
    DepartmentUpdate,
    NeedTypeCreate,
    NeedTypeOut,
    NeedTypeUpdate,
    SourceCategoryCreate,
    SourceCategoryOut,
    SourceCategoryUpdate,
    SourceDetailCreate,
    SourceDetailOut,
    SourceDetailUpdate,
)
from app.schemas.setting import AIConfigIn, AIConfigOut
from app.services import app_setting_service, audit_service

settings_router = APIRouter(prefix="/settings", tags=["settings"])


def _all(db: Session, model):
    return list(db.scalars(select(model).order_by(model.created_at.asc())).all())


def _apply_and_diff(obj, payload, fields):
    """应用 `payload` 中的非空字段到 `obj`，返回 (before, after) 变更字典。"""
    before: dict = {}
    after: dict = {}
    for field in fields:
        value = getattr(payload, field)
        if value is not None:
            old = getattr(obj, field)
            if old != value:
                before[field] = old
                setattr(obj, field, value)
                after[field] = value
    return before, after


def _audit_create(db, actor, action, resource_type, resource_id, after):
    audit_service.record(
        db,
        actor_id=actor.id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        after=after,
    )


# ── 部门 ──────────────────────────────────────────────
@settings_router.get("/departments", response_model=list[DepartmentOut])
def list_departments(
    db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    return _all(db, Department)


@settings_router.post("/departments", response_model=DepartmentOut)
def create_department(
    payload: DepartmentCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
    __: None = Depends(require_csrf),
):
    dept = Department(name=payload.name)
    db.add(dept)
    db.flush()
    _audit_create(
        db, actor, "department.create", "department", str(dept.id), {"name": dept.name}
    )
    db.commit()
    return dept


@settings_router.patch("/departments/{dept_id}", response_model=DepartmentOut)
def update_department(
    dept_id: uuid.UUID,
    payload: DepartmentUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
    __: None = Depends(require_csrf),
):
    dept = db.get(Department, dept_id)
    if dept is None:
        raise not_found("部门不存在")
    before, after = _apply_and_diff(dept, payload, ("name", "active"))
    if before:
        audit_service.record(
            db,
            actor_id=actor.id,
            action="department.update",
            resource_type="department",
            resource_id=str(dept.id),
            before=before,
            after=after,
        )
    db.commit()
    return dept


# ── 部门对接人 ──────────────────────────────────────────
@settings_router.get("/department-contacts", response_model=list[DepartmentContactOut])
def list_department_contacts(
    db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    return _all(db, DepartmentContact)


@settings_router.post("/department-contacts", response_model=DepartmentContactOut)
def create_department_contact(
    payload: DepartmentContactCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
    __: None = Depends(require_csrf),
):
    contact = DepartmentContact(
        department_id=payload.department_id,
        name=payload.name,
        is_default=payload.is_default,
        active=payload.active,
    )
    db.add(contact)
    db.flush()
    _audit_create(
        db,
        actor,
        "department_contact.create",
        "department_contact",
        str(contact.id),
        {
            "department_id": str(contact.department_id),
            "name": contact.name,
            "is_default": contact.is_default,
            "active": contact.active,
        },
    )
    db.commit()
    return contact


@settings_router.patch(
    "/department-contacts/{contact_id}", response_model=DepartmentContactOut
)
def update_department_contact(
    contact_id: uuid.UUID,
    payload: DepartmentContactUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
    __: None = Depends(require_csrf),
):
    contact = db.get(DepartmentContact, contact_id)
    if contact is None:
        raise not_found("部门对接人不存在")
    before, after = _apply_and_diff(contact, payload, ("name", "is_default", "active"))
    if before:
        audit_service.record(
            db,
            actor_id=actor.id,
            action="department_contact.update",
            resource_type="department_contact",
            resource_id=str(contact.id),
            before=before,
            after=after,
        )
    db.commit()
    return contact


# ── 来源分类 / 详情 ─────────────────────────────────────
@settings_router.get("/source-categories", response_model=list[SourceCategoryOut])
def list_source_categories(
    db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    return _all(db, LeadSourceCategory)


@settings_router.post("/source-categories", response_model=SourceCategoryOut)
def create_source_category(
    payload: SourceCategoryCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
    __: None = Depends(require_csrf),
):
    cat = LeadSourceCategory(code=payload.code, name=payload.name)
    db.add(cat)
    db.flush()
    _audit_create(
        db,
        actor,
        "source_category.create",
        "source_category",
        str(cat.id),
        {"code": cat.code, "name": cat.name},
    )
    db.commit()
    return cat


@settings_router.patch("/source-categories/{cat_id}", response_model=SourceCategoryOut)
def update_source_category(
    cat_id: uuid.UUID,
    payload: SourceCategoryUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
    __: None = Depends(require_csrf),
):
    cat = db.get(LeadSourceCategory, cat_id)
    if cat is None:
        raise not_found("来源分类不存在")
    before, after = _apply_and_diff(cat, payload, ("name", "active"))
    if before:
        audit_service.record(
            db,
            actor_id=actor.id,
            action="source_category.update",
            resource_type="source_category",
            resource_id=str(cat.id),
            before=before,
            after=after,
        )
    db.commit()
    return cat


@settings_router.get("/source-details", response_model=list[SourceDetailOut])
def list_source_details(
    db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    return _all(db, LeadSourceDetail)


@settings_router.post("/source-details", response_model=SourceDetailOut)
def create_source_detail(
    payload: SourceDetailCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
    __: None = Depends(require_csrf),
):
    detail = LeadSourceDetail(category_id=payload.category_id, name=payload.name)
    db.add(detail)
    db.flush()
    _audit_create(
        db,
        actor,
        "source_detail.create",
        "source_detail",
        str(detail.id),
        {"category_id": str(detail.category_id), "name": detail.name},
    )
    db.commit()
    return detail


@settings_router.patch("/source-details/{detail_id}", response_model=SourceDetailOut)
def update_source_detail(
    detail_id: uuid.UUID,
    payload: SourceDetailUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
    __: None = Depends(require_csrf),
):
    detail = db.get(LeadSourceDetail, detail_id)
    if detail is None:
        raise not_found("来源详情不存在")
    before, after = _apply_and_diff(detail, payload, ("name", "active"))
    if before:
        audit_service.record(
            db,
            actor_id=actor.id,
            action="source_detail.update",
            resource_type="source_detail",
            resource_id=str(detail.id),
            before=before,
            after=after,
        )
    db.commit()
    return detail


# ── 需求类型 ────────────────────────────────────────────
@settings_router.get("/need-types", response_model=list[NeedTypeOut])
def list_need_types(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return _all(db, LeadNeedType)


@settings_router.post("/need-types", response_model=NeedTypeOut)
def create_need_type(
    payload: NeedTypeCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
    __: None = Depends(require_csrf),
):
    need_type = LeadNeedType(name=payload.name)
    db.add(need_type)
    db.flush()
    _audit_create(
        db,
        actor,
        "need_type.create",
        "need_type",
        str(need_type.id),
        {"name": need_type.name},
    )
    db.commit()
    return need_type


@settings_router.patch("/need-types/{need_type_id}", response_model=NeedTypeOut)
def update_need_type(
    need_type_id: uuid.UUID,
    payload: NeedTypeUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
    __: None = Depends(require_csrf),
):
    need_type = db.get(LeadNeedType, need_type_id)
    if need_type is None:
        raise not_found("需求类型不存在")
    before, after = _apply_and_diff(need_type, payload, ("name", "active"))
    if before:
        audit_service.record(
            db,
            actor_id=actor.id,
            action="need_type.update",
            resource_type="need_type",
            resource_id=str(need_type.id),
            before=before,
            after=after,
        )
    db.commit()
    return need_type


# ── AI 配置（ADR-029）──────────────────────────────────
@settings_router.get("/ai", response_model=AIConfigOut)
def get_ai_config(
    db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    return app_setting_service.get_ai_config(db)


@settings_router.put("/ai", response_model=AIConfigOut)
def upsert_ai_config_put(
    payload: AIConfigIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
    __: None = Depends(require_csrf),
):
    return app_setting_service.save_ai_config(db, actor, payload)


@settings_router.post("/ai", response_model=AIConfigOut)
def upsert_ai_config_post(
    payload: AIConfigIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
    __: None = Depends(require_csrf),
):
    return app_setting_service.save_ai_config(db, actor, payload)


# ── 删除（仅未被引用时允许物理删除，否则拦截并建议停用/批量改派）────
def _count_refs(db: Session, model, where) -> int:
    return db.scalar(select(func.count()).select_from(model).where(where)) or 0


@settings_router.delete("/departments/{dept_id}", status_code=204)
def delete_department(
    dept_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
    _: None = Depends(require_csrf),
):
    dept = db.get(Department, dept_id)
    if dept is None:
        raise not_found("部门不存在")
    refs = (
        _count_refs(db, DepartmentContact, DepartmentContact.department_id == dept_id)
        + _count_refs(db, Lead, Lead.department_id == dept_id)
        + _count_refs(
            db,
            LeadHandoff,
            or_(
                LeadHandoff.to_department_id == dept_id,
                LeadHandoff.from_department_id == dept_id,
            ),
        )
    )
    if refs:
        raise conflict(f"该部门已被 {refs} 处引用，无法删除；可改为停用")
    audit_service.record(
        db,
        actor_id=actor.id,
        action="department.delete",
        resource_type="department",
        resource_id=str(dept_id),
        after={"name": dept.name},
    )
    db.delete(dept)
    db.commit()


@settings_router.delete("/department-contacts/{contact_id}", status_code=204)
def delete_department_contact(
    contact_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
    _: None = Depends(require_csrf),
):
    contact = db.get(DepartmentContact, contact_id)
    if contact is None:
        raise not_found("部门对接人不存在")
    refs = _count_refs(db, Lead, Lead.department_contact_id == contact_id) + _count_refs(
        db, LeadHandoff, LeadHandoff.to_contact_id == contact_id
    )
    if refs:
        raise conflict(f"该对接人已被 {refs} 处引用，无法删除；可改为停用或批量改派")
    audit_service.record(
        db,
        actor_id=actor.id,
        action="department_contact.delete",
        resource_type="department_contact",
        resource_id=str(contact_id),
        after={"name": contact.name},
    )
    db.delete(contact)
    db.commit()


@settings_router.delete("/source-categories/{cat_id}", status_code=204)
def delete_source_category(
    cat_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
    _: None = Depends(require_csrf),
):
    cat = db.get(LeadSourceCategory, cat_id)
    if cat is None:
        raise not_found("来源分类不存在")
    refs = _count_refs(db, Lead, Lead.source_category_id == cat_id) + _count_refs(
        db, LeadSourceDetail, LeadSourceDetail.category_id == cat_id
    )
    if refs:
        raise conflict(f"该来源分类已被 {refs} 处引用，无法删除；可改为停用")
    audit_service.record(
        db,
        actor_id=actor.id,
        action="source_category.delete",
        resource_type="source_category",
        resource_id=str(cat_id),
        after={"name": cat.name},
    )
    db.delete(cat)
    db.commit()


@settings_router.delete("/source-details/{detail_id}", status_code=204)
def delete_source_detail(
    detail_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
    _: None = Depends(require_csrf),
):
    detail = db.get(LeadSourceDetail, detail_id)
    if detail is None:
        raise not_found("来源详情不存在")
    refs = _count_refs(db, Lead, Lead.source_detail_id == detail_id)
    if refs:
        raise conflict(f"该来源详情已被 {refs} 处引用，无法删除；可改为停用")
    audit_service.record(
        db,
        actor_id=actor.id,
        action="source_detail.delete",
        resource_type="source_detail",
        resource_id=str(detail_id),
        after={"name": detail.name},
    )
    db.delete(detail)
    db.commit()


@settings_router.delete("/need-types/{need_type_id}", status_code=204)
def delete_need_type(
    need_type_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
    _: None = Depends(require_csrf),
):
    need_type = db.get(LeadNeedType, need_type_id)
    if need_type is None:
        raise not_found("需求类型不存在")
    refs = _count_refs(db, Lead, Lead.need_type_id == need_type_id)
    if refs:
        raise conflict(f"该需求类型已被 {refs} 处引用，无法删除；可改为停用")
    audit_service.record(
        db,
        actor_id=actor.id,
        action="need_type.delete",
        resource_type="need_type",
        resource_id=str(need_type_id),
        after={"name": need_type.name},
    )
    db.delete(need_type)
    db.commit()


class ReassignRequest(BaseModel):
    to_contact_id: uuid.UUID


@settings_router.post("/department-contacts/{contact_id}/reassign")
def reassign_contact_leads(
    contact_id: uuid.UUID,
    payload: ReassignRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
    _: None = Depends(require_csrf),
):
    source = db.get(DepartmentContact, contact_id)
    if source is None:
        raise not_found("部门对接人不存在")
    target = db.get(DepartmentContact, payload.to_contact_id)
    if target is None:
        raise not_found("目标对接人不存在")
    if source.id == target.id:
        raise conflict("不能转给本人")
    if source.department_id != target.department_id:
        raise conflict("只能转给同部门的对接人")

    leads = db.scalars(
        select(Lead).where(Lead.department_contact_id == source.id)
    ).all()
    now = datetime.now(timezone.utc)
    for lead in leads:
        db.add(
            LeadHandoff(
                lead_id=lead.id,
                from_department_id=lead.department_id,
                to_department_id=target.department_id,
                to_contact_id=target.id,
                happened_at=now,
                created_by=actor.id,
                reason="批量改派",
            )
        )
        db.add(
            LeadEvent(
                lead_id=lead.id,
                event_type="lead.handoff",
                before_json={"department_contact_id": str(source.id)},
                after_json={"department_contact_id": str(target.id)},
                created_by=actor.id,
            )
        )
        lead.department_contact_id = target.id
        if lead.department_id is None:
            lead.department_id = target.department_id
    audit_service.record(
        db,
        actor_id=actor.id,
        action="department_contact.reassign",
        resource_type="department_contact",
        resource_id=str(source.id),
        after={"to_contact_id": str(target.id), "moved_leads": len(leads)},
    )
    db.commit()
    return {"moved_leads": len(leads)}