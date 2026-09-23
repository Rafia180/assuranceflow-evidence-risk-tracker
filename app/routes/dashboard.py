"""Dashboard, PDF status report and audit log."""
from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlmodel import Session, select

from app.database import get_session
from app.models import AuditLog, Finding, RemediationAction
from app.report import build_status_report
from app.services import OPEN_FINDING_STATUSES, dashboard_stats, is_action_overdue
from app.templating import templates

router = APIRouter()


@router.get("/")
def dashboard(request: Request, session: Session = Depends(get_session)):
    stats = dashboard_stats(session)
    return templates.TemplateResponse(request, "dashboard.html", {"stats": stats})


@router.get("/report.pdf")
def status_report(session: Session = Depends(get_session)):
    today = date.today()
    stats = dashboard_stats(session, today)
    findings = [f for f in session.exec(select(Finding)).all() if f.status in OPEN_FINDING_STATUSES]
    overdue = [a for a in session.exec(select(RemediationAction)).all() if is_action_overdue(a, today)]
    pdf_bytes = build_status_report(stats, findings, overdue)
    filename = f"assurance-status-{today:%Y-%m}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/audit-log")
def audit_log(request: Request, session: Session = Depends(get_session)):
    entries = session.exec(select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(200)).all()
    return templates.TemplateResponse(request, "audit_log.html", {"entries": entries})
