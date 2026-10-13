"""初始化种子测试：admin 账号 + V1.3 业务字典（幂等）。"""

from sqlalchemy import func, select

from app.core.config import settings
from app.models.department import Department, DepartmentContact
from app.models.lead_need_type import LeadNeedType
from app.models.lead_source import LeadSourceCategory
from app.models.user import User
from app.seed import seed_admin, seed_dictionaries


def test_seed_admin_creates_initial_admin(db, monkeypatch):
    monkeypatch.setattr(settings, "admin_initial_password", "AdminPass123!")
    monkeypatch.setattr(settings, "admin_username", "admin")

    seed_admin(db)

    user = db.scalar(select(User).where(User.username == "admin"))
    assert user is not None
    assert user.role == "admin"
    assert user.is_active is True
    assert user.must_change_password is True


def test_seed_admin_idempotent(db, monkeypatch):
    monkeypatch.setattr(settings, "admin_initial_password", "AdminPass123!")
    monkeypatch.setattr(settings, "admin_username", "admin")

    seed_admin(db)
    seed_admin(db)

    count = db.scalar(select(func.count()).select_from(User)) or 0
    assert count == 1


def test_seed_admin_skips_without_password(db, monkeypatch):
    monkeypatch.setattr(settings, "admin_initial_password", None)

    seed_admin(db)

    assert db.scalar(select(User).where(User.username == "admin")) is None


def test_seed_dictionaries(db):
    seed_dictionaries(db)

    depts = db.scalars(select(Department)).all()
    assert {d.name for d in depts} == {"GDC", "Token 供应链", "润效营"}

    contacts = db.scalars(select(DepartmentContact)).all()
    assert len(contacts) == 3
    assert all(c.is_default for c in contacts)

    cats = db.scalars(select(LeadSourceCategory)).all()
    assert len(cats) == 2
    assert {c.code for c in cats} == {"website", "other"}

    need_types = db.scalars(select(LeadNeedType)).all()
    assert {n.name for n in need_types} == {"AI Agent", "OPC Team"}


def test_seed_dictionaries_idempotent(db):
    seed_dictionaries(db)
    seed_dictionaries(db)

    assert db.scalar(select(func.count()).select_from(Department)) == 3
    assert db.scalar(select(func.count()).select_from(LeadSourceCategory)) == 2
    assert db.scalar(select(func.count()).select_from(LeadNeedType)) == 2
