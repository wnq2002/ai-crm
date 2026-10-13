"""顶层 API 路由聚合。"""

from fastapi import APIRouter

from app.api import (
    activities,
    admin_users,
    auth,
    companies,
    imports,
    leads,
    reports,
    settings,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(admin_users.router)
api_router.include_router(leads.router)
api_router.include_router(imports.router)
api_router.include_router(settings.settings_router)
api_router.include_router(companies.router)
api_router.include_router(companies.contacts_router)
api_router.include_router(activities.router)
api_router.include_router(reports.dashboard_router)
api_router.include_router(reports.reports_router)
