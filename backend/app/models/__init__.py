"""ORM 模型汇总，供 Alembic autogenerate 与 `Base.metadata` 发现。"""

from app.models.audit_log import AuditLog
from app.models.app_setting import AppSetting
from app.models.company import Company
from app.models.contact import Contact
from app.models.department import Department, DepartmentContact
from app.models.import_job import ImportJob, ImportRow
from app.models.lead import Lead
from app.models.lead_activity import LeadActivity
from app.models.lead_event import LeadEvent, LeadHandoff, LeadOutcomeEvent
from app.models.lead_event_revision import LeadEventRevision
from app.models.lead_need_type import LeadNeedType
from app.models.lead_parse_record import LeadParseRecord
from app.models.lead_source import LeadSourceCategory, LeadSourceDetail
from app.models.user import User
from app.models.user_session import UserSession

__all__ = [
    "User",
    "UserSession",
    "AuditLog",
    "AppSetting",
    "Company",
    "Contact",
    "LeadSourceCategory",
    "LeadSourceDetail",
    "LeadNeedType",
    "Department",
    "DepartmentContact",
    "Lead",
    "LeadActivity",
    "LeadHandoff",
    "LeadOutcomeEvent",
    "LeadEvent",
    "LeadEventRevision",
    "LeadParseRecord",
    "ImportJob",
    "ImportRow",
]
