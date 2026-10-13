"""初始化种子：管理员账号 + V1.3 业务字典。

- 管理员：仅在「无 admin 且 ADMIN_INITIAL_PASSWORD 已设置」时创建，凭据环境变量注入。
- 字典：部门/默认对接人/来源分类/需求类型，幂等（按唯一键查重后插入），可编辑配置不写死。
可用 `python -m app.seed` 手动执行，或由应用启动 lifespan 触发。
"""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.department import Department, DepartmentContact
from app.models.lead_need_type import LeadNeedType
from app.models.lead_source import LeadSourceCategory
from app.models.user import ROLE_ADMIN, User

logger = logging.getLogger(__name__)

# 初始化字典数据（可编辑，非写死）
DEFAULT_DEPARTMENTS = ["GDC", "Token 供应链", "润效营"]
DEFAULT_DEPARTMENT_CONTACTS = {
    "GDC": "同事A",
    "Token 供应链": "同事B",
    "润效营": "同事C",
}
DEFAULT_SOURCE_CATEGORIES = [
    ("website", "官网"),
    ("other", "其他"),
]
DEFAULT_NEED_TYPES = ["AI Agent", "OPC Team"]


def seed_admin(db: Session) -> None:
    password = settings.admin_initial_password
    if not password:
        logger.warning("ADMIN_INITIAL_PASSWORD 未设置，跳过初始管理员创建")
        return

    existing = db.scalar(select(User).where(User.username == settings.admin_username))
    if existing is not None:
        return

    db.add(
        User(
            username=settings.admin_username,
            display_name=settings.admin_display_name,
            role=ROLE_ADMIN,
            password_hash=hash_password(password),
            is_active=True,
            must_change_password=settings.admin_must_change_password,
        )
    )
    db.commit()
    logger.info("已创建初始管理员账号 %s", settings.admin_username)


def seed_dictionaries(db: Session) -> None:
    # 部门
    for name in DEFAULT_DEPARTMENTS:
        if db.scalar(select(Department).where(Department.name == name)) is None:
            db.add(Department(name=name))
    db.flush()

    # 默认对接人
    for dept_name, contact_name in DEFAULT_DEPARTMENT_CONTACTS.items():
        dept = db.scalar(select(Department).where(Department.name == dept_name))
        if dept is None:
            continue
        exists = db.scalar(
            select(DepartmentContact).where(
                DepartmentContact.department_id == dept.id,
                DepartmentContact.name == contact_name,
            )
        )
        if exists is None:
            db.add(
                DepartmentContact(
                    department_id=dept.id, name=contact_name, is_default=True
                )
            )

    # 来源分类
    for code, name in DEFAULT_SOURCE_CATEGORIES:
        if (
            db.scalar(select(LeadSourceCategory).where(LeadSourceCategory.code == code))
            is None
        ):
            db.add(LeadSourceCategory(code=code, name=name))

    # 需求类型
    for name in DEFAULT_NEED_TYPES:
        if db.scalar(select(LeadNeedType).where(LeadNeedType.name == name)) is None:
            db.add(LeadNeedType(name=name))

    db.commit()
    logger.info("业务字典初始化完成")


def seed_all() -> None:
    db = SessionLocal()
    try:
        seed_admin(db)
        seed_dictionaries(db)
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    seed_all()
