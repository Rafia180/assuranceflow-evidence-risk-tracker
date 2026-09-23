"""Requirements, controls and evidence registers."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models import Control, ControlStatus, EvidenceItem, Requirement
from app.routes.common import get_or_404
from app.services import log_action
from app.templating import templates
from app.validation import FormError, optional_text, parse_date, parse_enum, parse_int, required

router = APIRouter()


# ======================= Requirements =======================
def clean_requirement(form: dict) -> dict:
    return {
        "reference": required(form.get("reference"), "Reference").upper(),
        "title": required(form.get("title"), "Title"),
        "category": required(form.get("category"), "Category"),
        "description": optional_text(form.get("description")),
        "owner": required(form.get("owner"), "Owner"),
        "review_frequency": required(form.get("review_frequency"), "Review frequency"),
    }


@router.get("/requirements")
def list_requirements(request: Request, session: Session = Depends(get_session)):
    items = session.exec(select(Requirement).order_by(Requirement.reference)).all()
    return templates.TemplateResponse(request, "requirements/list.html", {"requirements": items})


@router.get("/requirements/new")
def new_requirement(request: Request):
    return templates.TemplateResponse(
        request, "requirements/form.html", {"item": None, "form": {}, "error": None}
    )


@router.post("/requirements/new")
async def create_requirement(request: Request, session: Session = Depends(get_session)):
    form = dict(await request.form())
    try:
        data = clean_requirement(form)
        exists = session.exec(select(Requirement).where(Requirement.reference == data["reference"])).first()
        if exists:
            raise FormError(f"Reference {data['reference']} already exists.")
    except FormError as e:
        return templates.TemplateResponse(
            request, "requirements/form.html", {"item": None, "form": form, "error": str(e)}, status_code=400
        )
    item = Requirement(**data)
    session.add(item)
    session.commit()
    session.refresh(item)
    log_action(session, "Requirement", item.id, "create", item.reference)
    return RedirectResponse(f"/requirements/{item.id}", status_code=303)


@router.get("/requirements/{req_id}")
def requirement_detail(req_id: int, request: Request, session: Session = Depends(get_session)):
    item = get_or_404(session, Requirement, req_id)
    return templates.TemplateResponse(request, "requirements/detail.html", {"item": item})


@router.get("/requirements/{req_id}/edit")
def edit_requirement(req_id: int, request: Request, session: Session = Depends(get_session)):
    item = get_or_404(session, Requirement, req_id)
    return templates.TemplateResponse(
        request, "requirements/form.html", {"item": item, "form": item.model_dump(), "error": None}
    )


@router.post("/requirements/{req_id}/edit")
async def update_requirement(req_id: int, request: Request, session: Session = Depends(get_session)):
    item = get_or_404(session, Requirement, req_id)
    form = dict(await request.form())
    try:
        data = clean_requirement(form)
        clash = session.exec(
            select(Requirement).where(Requirement.reference == data["reference"], Requirement.id != req_id)
        ).first()
        if clash:
            raise FormError(f"Reference {data['reference']} already exists.")
    except FormError as e:
        return templates.TemplateResponse(
            request, "requirements/form.html", {"item": item, "form": form, "error": str(e)}, status_code=400
        )
    for key, value in data.items():
        setattr(item, key, value)
    session.add(item)
    session.commit()
    log_action(session, "Requirement", item.id, "update", item.reference)
    return RedirectResponse(f"/requirements/{item.id}", status_code=303)


# ======================= Controls =======================
def clean_control(form: dict, session: Session) -> dict:
    requirement_id = parse_int(form.get("requirement_id"), "Requirement")
    if session.get(Requirement, requirement_id) is None:
        raise FormError("Selected requirement does not exist.")
    return {
        "requirement_id": requirement_id,
        "name": required(form.get("name"), "Control name"),
        "description": optional_text(form.get("description")),
        "owner": required(form.get("owner"), "Control owner"),
        "frequency": required(form.get("frequency"), "Frequency"),
        "status": parse_enum(ControlStatus, form.get("status"), "Status"),
    }


def control_form_context(session: Session, item, form: dict, error=None) -> dict:
    return {
        "item": item,
        "form": form,
        "error": error,
        "requirements": session.exec(select(Requirement).order_by(Requirement.reference)).all(),
        "statuses": list(ControlStatus),
    }


@router.get("/controls")
def list_controls(request: Request, session: Session = Depends(get_session)):
    items = session.exec(select(Control)).all()
    items.sort(key=lambda c: c.requirement.reference if c.requirement else "")
    return templates.TemplateResponse(request, "controls/list.html", {"controls": items})


@router.get("/controls/new")
def new_control(request: Request, requirement_id: int | None = None, session: Session = Depends(get_session)):
    form = {"requirement_id": requirement_id, "status": ControlStatus.ACTIVE.value}
    return templates.TemplateResponse(request, "controls/form.html", control_form_context(session, None, form))


@router.post("/controls/new")
async def create_control(request: Request, session: Session = Depends(get_session)):
    form = dict(await request.form())
    try:
        data = clean_control(form, session)
    except FormError as e:
        ctx = control_form_context(session, None, form, str(e))
        return templates.TemplateResponse(request, "controls/form.html", ctx, status_code=400)
    item = Control(**data)
    session.add(item)
    session.commit()
    session.refresh(item)
    log_action(session, "Control", item.id, "create", item.name)
    return RedirectResponse(f"/controls/{item.id}", status_code=303)


@router.get("/controls/{control_id}")
def control_detail(control_id: int, request: Request, session: Session = Depends(get_session)):
    item = get_or_404(session, Control, control_id)
    return templates.TemplateResponse(request, "controls/detail.html", {"item": item})


@router.get("/controls/{control_id}/edit")
def edit_control(control_id: int, request: Request, session: Session = Depends(get_session)):
    item = get_or_404(session, Control, control_id)
    form = item.model_dump()
    form["status"] = item.status.value
    return templates.TemplateResponse(request, "controls/form.html", control_form_context(session, item, form))


@router.post("/controls/{control_id}/edit")
async def update_control(control_id: int, request: Request, session: Session = Depends(get_session)):
    item = get_or_404(session, Control, control_id)
    form = dict(await request.form())
    try:
        data = clean_control(form, session)
    except FormError as e:
        ctx = control_form_context(session, item, form, str(e))
        return templates.TemplateResponse(request, "controls/form.html", ctx, status_code=400)
    for key, value in data.items():
        setattr(item, key, value)
    session.add(item)
    session.commit()
    log_action(session, "Control", item.id, "update", item.name)
    return RedirectResponse(f"/controls/{item.id}", status_code=303)


# ======================= Evidence =======================
def clean_evidence(form: dict, session: Session) -> dict:
    control_id = parse_int(form.get("control_id"), "Control")
    if session.get(Control, control_id) is None:
        raise FormError("Selected control does not exist.")
    collection_date = parse_date(form.get("collection_date"), "Collection date")
    review_date = parse_date(form.get("review_date"), "Review date", is_required=False)
    if review_date and review_date < collection_date:
        raise FormError("Review date cannot be before the collection date.")
    return {
        "control_id": control_id,
        "title": required(form.get("title"), "Evidence title"),
        "evidence_type": required(form.get("evidence_type"), "Evidence type"),
        "collection_date": collection_date,
        "review_date": review_date,
        "owner": required(form.get("owner"), "Evidence owner"),
        "reference_link": required(form.get("reference_link"), "Reference / link"),
    }


EVIDENCE_TYPES = ["Report", "Screenshot", "Ticket", "Sign-off", "Log extract", "Policy document"]


@router.get("/evidence")
def list_evidence(request: Request, session: Session = Depends(get_session)):
    items = session.exec(select(EvidenceItem).order_by(EvidenceItem.collection_date.desc())).all()
    return templates.TemplateResponse(request, "evidence/list.html", {"items": items})


@router.get("/evidence/new")
def new_evidence(request: Request, control_id: int | None = None, session: Session = Depends(get_session)):
    ctx = {
        "form": {"control_id": control_id},
        "error": None,
        "controls": session.exec(select(Control)).all(),
        "types": EVIDENCE_TYPES,
    }
    return templates.TemplateResponse(request, "evidence/form.html", ctx)


@router.post("/evidence/new")
async def create_evidence(request: Request, session: Session = Depends(get_session)):
    form = dict(await request.form())
    try:
        data = clean_evidence(form, session)
    except FormError as e:
        ctx = {"form": form, "error": str(e), "controls": session.exec(select(Control)).all(), "types": EVIDENCE_TYPES}
        return templates.TemplateResponse(request, "evidence/form.html", ctx, status_code=400)
    item = EvidenceItem(**data)
    session.add(item)
    session.commit()
    session.refresh(item)
    log_action(session, "EvidenceItem", item.id, "create", item.title)
    return RedirectResponse(f"/controls/{item.control_id}", status_code=303)
