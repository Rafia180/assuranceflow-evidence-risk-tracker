"""Business rules: overdue logic, dashboard numbers and the audit log."""
from collections import defaultdict
from datetime import date
from typing import Optional

from sqlmodel import Session, select

from app.models import (
    ActionStatus, AssessmentResult, AuditLog, Control, ControlStatus,
    EvidenceItem, Finding, FindingStatus, RemediationAction, RiskRating,
)

OPEN_FINDING_STATUSES = {FindingStatus.OPEN, FindingStatus.IN_PROGRESS}
DONE_ACTION_STATUSES = {ActionStatus.COMPLETED, ActionStatus.VERIFIED}


def is_action_overdue(action: RemediationAction, today: Optional[date] = None) -> bool:
    today = today or date.today()
    return action.status not in DONE_ACTION_STATUSES and action.target_date < today


def is_finding_overdue(finding: Finding, today: Optional[date] = None) -> bool:
    today = today or date.today()
    return finding.status in OPEN_FINDING_STATUSES and finding.due_date < today


def is_evidence_stale(item: EvidenceItem, today: Optional[date] = None) -> bool:
    today = today or date.today()
    return item.review_date is not None and item.review_date < today


def latest_result(control: Control) -> Optional[AssessmentResult]:
    if not control.assessments:
        return None
    return max(control.assessments, key=lambda a: (a.assessment_date, a.id or 0)).result


def log_action(session: Session, entity: str, entity_id: int, action: str, detail: str = "") -> None:
    session.add(AuditLog(entity=entity, entity_id=entity_id, action=action, detail=detail))
    session.commit()


def dashboard_stats(session: Session, today: Optional[date] = None) -> dict:
    today = today or date.today()
    controls = session.exec(select(Control)).all()
    findings = session.exec(select(Finding)).all()
    actions = session.exec(select(RemediationAction)).all()
    evidence = session.exec(select(EvidenceItem)).all()

    active_controls = [c for c in controls if c.status == ControlStatus.ACTIVE]
    open_findings = [f for f in findings if f.status in OPEN_FINDING_STATUSES]

    result_counts = {r.value: 0 for r in AssessmentResult}
    result_counts["Never assessed"] = 0
    for c in active_controls:
        r = latest_result(c)
        result_counts[r.value if r else "Never assessed"] += 1

    by_category = defaultdict(lambda: {"controls": 0, "missing_evidence": 0, "open_findings": 0})
    for c in active_controls:
        cat = c.requirement.category if c.requirement else "Uncategorised"
        by_category[cat]["controls"] += 1
        if not c.evidence_items:
            by_category[cat]["missing_evidence"] += 1
    for f in open_findings:
        cat = f.control.requirement.category if f.control and f.control.requirement else "Uncategorised"
        by_category[cat]["open_findings"] += 1

    return {
        "today": today,
        "total_controls": len(active_controls),
        "missing_evidence": len([c for c in active_controls if not c.evidence_items]),
        "stale_evidence": len([e for e in evidence if is_evidence_stale(e, today)]),
        "open_findings": len(open_findings),
        "high_critical_findings": len(
            [f for f in open_findings if f.risk_rating in (RiskRating.HIGH, RiskRating.CRITICAL)]
        ),
        "overdue_actions": len([a for a in actions if is_action_overdue(a, today)]),
        "completed_actions": len([a for a in actions if a.status in DONE_ACTION_STATUSES]),
        "total_actions": len(actions),
        "result_counts": result_counts,
        "by_category": dict(sorted(by_category.items())),
    }
