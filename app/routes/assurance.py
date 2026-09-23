"""Assessments, findings and remediation actions."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models import (
    ActionStatus, Assessment, AssessmentResult, Control, Finding,
    FindingStatus, RemediationAction, RiskRating,
)
from app.routes.common import get_or_404
from app.services import is_action_overdue, log_action
from app.templating import templates
from app.validation import FormError, optional_text, parse_date, parse_enum, parse_int, required

router = APIRouter()

GAP_RESULTS = {AssessmentResult.NOT_EFFECTIVE, AssessmentResult.PARTIALLY_EFFECTIVE}


# ======================= Assessments =======================
def assessment_ctx(session, form, error=None):
    return {
        "form": form,
        "error": error,
        "controls": session.exec(select(Control)).all(),
        "results": list(AssessmentResult),
        "ratings": list(RiskRating),
    }


@router.get("/assessments")
def list_assessments(request: Request, session: Session = Depends(get_session)):
    items = session.exec(select(Assessment).order_by(Assessment.assessment_date.desc())).all()
    return templates.TemplateResponse(request, "assessments/list.html", {"items": items})


@router.get("/assessments/new")
def new_assessment(request: Request, control_id: int | None = None, session: Session = Depends(get_session)):
    return templates.TemplateResponse(
        request, "assessments/form.html", assessment_ctx(session, {"control_id": control_id})
    )


@router.post("/assessments/new")
async def create_assessment(request: Request, session: Session = Depends(get_session)):
    """Save an assessment. If the control is not (fully) effective, also raise a finding."""
    form = dict(await request.form())
    try:
        control_id = parse_int(form.get("control_id"), "Control")
        if session.get(Control, control_id) is None:
            raise FormError("Selected control does not exist.")
        result = parse_enum(AssessmentResult, form.get("result"), "Result")
        assessment_data = {
            "control_id": control_id,
            "assessment_date": parse_date(form.get("assessment_date"), "Assessment date"),
            "result": result,
            "assessor": required(form.get("assessor"), "Assessor"),
            "notes": optional_text(form.get("notes")),
        }
        finding_data = None
        wants_finding = bool(optional_text(form.get("finding_title")))
        if result == AssessmentResult.NOT_EFFECTIVE and not wants_finding:
            raise FormError("A 'Not Effective' result must raise a finding: fill in the finding fields.")
        if wants_finding:
            if result not in GAP_RESULTS:
                raise FormError("Findings can only be raised for Not Effective or Partially Effective results.")
            finding_data = {
                "control_id": control_id,
                "title": required(form.get("finding_title"), "Finding title"),
                "description": optional_text(form.get("finding_description")),
                "risk_rating": parse_enum(RiskRating, form.get("risk_rating"), "Risk rating"),
                "owner": required(form.get("finding_owner"), "Finding owner"),
                "due_date": parse_date(form.get("due_date"), "Finding due date"),
            }
    except FormError as e:
        return templates.TemplateResponse(
            request, "assessments/form.html", assessment_ctx(session, form, str(e)), status_code=400
        )

    assessment = Assessment(**assessment_data)
    session.add(assessment)
    session.commit()
    session.refresh(assessment)
    log_action(session, "Assessment", assessment.id, "create", assessment.result.value)

    if finding_data:
        finding = Finding(assessment_id=assessment.id, **finding_data)
        session.add(finding)
        session.commit()
        session.refresh(finding)
        log_action(session, "Finding", finding.id, "create", finding.title)
        return RedirectResponse(f"/findings/{finding.id}", status_code=303)
    return RedirectResponse(f"/controls/{control_id}", status_code=303)


# ======================= Findings =======================
@router.get("/findings")
def list_findings(request: Request, status: str | None = None, session: Session = Depends(get_session)):
    query = select(Finding).order_by(Finding.due_date)
    if status:
        query = query.where(Finding.status == FindingStatus(status))
    items = session.exec(query).all()
    return templates.TemplateResponse(
        request, "findings/list.html", {"items": items, "statuses": list(FindingStatus), "selected": status}
    )


@router.get("/findings/{finding_id}")
def finding_detail(finding_id: int, request: Request, session: Session = Depends(get_session)):
    item = get_or_404(session, Finding, finding_id)
    ctx = {"item": item, "statuses": list(FindingStatus), "action_statuses": list(ActionStatus),
           "error": request.query_params.get("error")}
    return templates.TemplateResponse(request, "findings/detail.html", ctx)


@router.post("/findings/{finding_id}/status")
async def update_finding_status(finding_id: int, request: Request, session: Session = Depends(get_session)):
    item = get_or_404(session, Finding, finding_id)
    form = dict(await request.form())
    try:
        new_status = parse_enum(FindingStatus, form.get("status"), "Status")
        if new_status == FindingStatus.CLOSED and any(
            a.status != ActionStatus.VERIFIED for a in item.actions
        ):
            raise FormError("All remediation actions must be Verified before the finding can be closed.")
    except FormError as e:
        return RedirectResponse(f"/findings/{finding_id}?error={e}", status_code=303)
    item.status = new_status
    session.add(item)
    session.commit()
    log_action(session, "Finding", item.id, "update", f"status -> {new_status.value}")
    return RedirectResponse(f"/findings/{finding_id}", status_code=303)


# ======================= Remediation actions =======================
@router.post("/findings/{finding_id}/actions")
async def create_action(finding_id: int, request: Request, session: Session = Depends(get_session)):
    finding = get_or_404(session, Finding, finding_id)
    form = dict(await request.form())
    try:
        data = {
            "finding_id": finding.id,
            "action": required(form.get("action"), "Action"),
            "owner": required(form.get("owner"), "Action owner"),
            "target_date": parse_date(form.get("target_date"), "Target date"),
        }
    except FormError as e:
        return RedirectResponse(f"/findings/{finding_id}?error={e}", status_code=303)
    action = RemediationAction(**data)
    session.add(action)
    if finding.status == FindingStatus.OPEN:
        finding.status = FindingStatus.IN_PROGRESS
        session.add(finding)
    session.commit()
    session.refresh(action)
    log_action(session, "RemediationAction", action.id, "create", action.action)
    return RedirectResponse(f"/findings/{finding_id}", status_code=303)


@router.get("/actions")
def list_actions(request: Request, overdue: bool = False, session: Session = Depends(get_session)):
    items = session.exec(select(RemediationAction).order_by(RemediationAction.target_date)).all()
    if overdue:
        items = [a for a in items if is_action_overdue(a)]
    return templates.TemplateResponse(request, "actions/list.html", {"items": items, "overdue": overdue})


@router.post("/actions/{action_id}/update")
async def update_action(action_id: int, request: Request, session: Session = Depends(get_session)):
    action = get_or_404(session, RemediationAction, action_id)
    form = dict(await request.form())
    try:
        new_status = parse_enum(ActionStatus, form.get("status"), "Status")
        notes = optional_text(form.get("verification_notes"))
        if new_status == ActionStatus.VERIFIED and not notes:
            raise FormError("Verification notes are required to mark an action as Verified.")
    except FormError as e:
        return RedirectResponse(f"/findings/{action.finding_id}?error={e}", status_code=303)
    action.status = new_status
    action.verification_notes = notes
    session.add(action)
    session.commit()
    log_action(session, "RemediationAction", action.id, "update", f"status -> {new_status.value}")
    return RedirectResponse(f"/findings/{action.finding_id}", status_code=303)
