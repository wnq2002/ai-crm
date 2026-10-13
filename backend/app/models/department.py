"""部门与部门对接人表（PRD §7 / architecture §5）。"""

import uuid

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import CreatedAtMixin, UUIDPrimaryKeyMixin


class Department(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "departments"

    name: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class DepartmentContact(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "department_contacts"

    department_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
