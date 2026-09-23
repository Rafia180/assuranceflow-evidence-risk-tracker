"""One shared Jinja2 environment, with helper functions available in every template."""
from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.services import is_action_overdue, is_evidence_stale, is_finding_overdue, latest_result

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.globals.update(
    is_action_overdue=is_action_overdue,
    is_finding_overdue=is_finding_overdue,
    is_evidence_stale=is_evidence_stale,
    latest_result=latest_result,
)
