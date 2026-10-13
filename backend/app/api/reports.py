"""工作台与报表路由（api-contract §9）。"""

import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.core.db import get_db
from app.models.user import User
from app.services import audit_service, report_service

dashboard_router = APIRouter(prefix="/dashboard", tags=["dashboard"])
reports_router = APIRouter(prefix="/reports", tags=["reports"])


def _csv_response(headers: list[str], rows: list[list[str]]) -> Response:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([report_service.safe_csv(v) for v in row])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="export.csv"'},
    )


@dashboard_router.get("/summary")
def summary(
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return report_service.dashboard_summary(db, from_, to)


@dashboard_router.get("/trend")
def trend(
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return report_service.trend(db, from_, to)


@reports_router.get("/overview")
def overview(
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return report_service.overview(db, from_, to)


@reports_router.get("/sources")
def sources(
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return report_service.sources(db, from_, to)


@reports_router.get("/activities")
def activities(
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return report_service.activities(db, from_, to)


@reports_router.get("/handoffs")
def handoffs(
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return report_service.handoffs(db, from_, to)


@reports_router.get("/export")
def export_report(
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    audit_service.record(
        db,
        actor_id=actor.id,
        action="report.export",
        resource_type="report",
        resource_id=None,
    )
    db.commit()
    overview = report_service.overview(db, from_, to)
    headers = list(overview.keys())
    rows = [[str(overview[k]) for k in headers]]
    return _csv_response(headers, rows)
