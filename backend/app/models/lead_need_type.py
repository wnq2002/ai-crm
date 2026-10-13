"""需求类型表（PRD §7 / architecture §5）。"""

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import CreatedAtMixin, UUIDPrimaryKeyMixin


class LeadNeedType(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "lead_need_types"

    name: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
