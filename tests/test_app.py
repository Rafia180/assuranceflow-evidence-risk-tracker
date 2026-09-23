from datetime import date, timedelta

from sqlmodel import select

from app.models import (
    ActionStatus, Assessment, AuditLog, Control, EvidenceItem, Finding,
    FindingStatus, RemediationAction, RiskRating,
)
from app.services import dashboard_stats, is_action_overdue

TODAY = date.today()


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_create_control(client, session, control):
    resp = client.post("/controls/new", data={
        "requirement_id": control.requirement_id, "name": "Quarterly firewall rule review",
        "owner": "Network Lead", "frequency": "Quarterly", "status": "Active",
    }, follow_redirects=False)
    assert resp.status_code == 303
    assert session.exec(select(Control).where(Control.name == "Quarterly firewall rule review")).one()


def test_create_control_requires_owner(client, control):
    resp = client.post("/controls/new", data={
        "requirement_id": control.requirement_id, "name": "No owner", "owner": "",
        "frequency": "Monthly", "status": "Active",
    })
    assert resp.status_code == 400
    assert "Control owner is required" in resp.text


def test_create_evidence(client, session, control):
    resp = client.post("/evidence/new", data={
        "control_id": control.id, "title": "Q3 sign-off", "evidence_type": "Sign-off",
        "collection_date": "2026-09-01", "review_date": "2026-12-01", "owner": "IAM Lead",
        "reference_link": "AUDIT-2026-014",
    }, follow_redirects=False)
    assert resp.status_code == 303
    item = session.exec(select(EvidenceItem)).one()
    assert item.reference_link == "AUDIT-2026-014"


def test_evidence_review_date_cannot_be_before_collection(client, control):
    resp = client.post("/evidence/new", data={
        "control_id": control.id, "title": "Bad dates", "evidence_type": "Report",
        "collection_date": "2026-09-01", "review_date": "2026-08-01", "owner": "X", "reference_link": "REF-1",
    })
    assert resp.status_code == 400
    assert "Review date cannot be before" in resp.text


def test_effective_assessment_creates_no_finding(client, session, control):
    client.post("/assessments/new", data={
        "control_id": control.id, "assessment_date": "2026-09-10", "result": "Effective", "assessor": "Analyst",
    })
    assert session.exec(select(Assessment)).one().result.value == "Effective"
    assert session.exec(select(Finding)).first() is None


def test_not_effective_assessment_creates_linked_finding(client, session, control):
    resp = client.post("/assessments/new", data={
        "control_id": control.id, "assessment_date": "2026-09-10", "result": "Not Effective",
        "assessor": "Analyst", "finding_title": "Access review not performed",
        "risk_rating": "High", "finding_owner": "IAM Lead", "due_date": "2026-10-31",
    }, follow_redirects=False)
    assert resp.status_code == 303
    finding = session.exec(select(Finding)).one()
    assert finding.assessment_id == session.exec(select(Assessment)).one().id
    assert finding.risk_rating == RiskRating.HIGH


def test_not_effective_without_finding_is_rejected(client, control):
    resp = client.post("/assessments/new", data={
        "control_id": control.id, "assessment_date": "2026-09-10", "result": "Not Effective", "assessor": "A",
    })
    assert resp.status_code == 400


def test_overdue_action_flag():
    late = RemediationAction(finding_id=1, action="a", owner="o", target_date=TODAY - timedelta(days=1))
    done = RemediationAction(finding_id=1, action="b", owner="o", target_date=TODAY - timedelta(days=1),
                             status=ActionStatus.COMPLETED)
    future = RemediationAction(finding_id=1, action="c", owner="o", target_date=TODAY + timedelta(days=3))
    assert is_action_overdue(late, TODAY) is True
    assert is_action_overdue(done, TODAY) is False
    assert is_action_overdue(future, TODAY) is False


def test_cannot_verify_action_without_notes(client, session, control):
    f = Finding(control_id=control.id, title="Gap", risk_rating=RiskRating.LOW, owner="o", due_date=TODAY)
    session.add(f)
    session.commit()
    a = RemediationAction(finding_id=f.id, action="Fix", owner="o", target_date=TODAY)
    session.add(a)
    session.commit()
    client.post(f"/actions/{a.id}/update", data={"status": "Verified", "verification_notes": ""})
    session.refresh(a)
    assert a.status == ActionStatus.NOT_STARTED


def test_dashboard_totals(session, control):
    session.add(Control(requirement_id=control.requirement_id, name="Second", owner="o", frequency="Monthly"))
    session.add(EvidenceItem(control_id=control.id, title="e", evidence_type="Report",
                             collection_date=TODAY, owner="o", reference_link="R"))
    f_open = Finding(control_id=control.id, title="Open high", risk_rating=RiskRating.HIGH, owner="o",
                     due_date=TODAY)
    f_closed = Finding(control_id=control.id, title="Closed", risk_rating=RiskRating.CRITICAL, owner="o",
                       due_date=TODAY, status=FindingStatus.CLOSED)
    session.add_all([f_open, f_closed])
    session.commit()
    session.add(RemediationAction(finding_id=f_open.id, action="late", owner="o",
                                  target_date=TODAY - timedelta(days=2)))
    session.commit()

    stats = dashboard_stats(session, TODAY)
    assert stats["total_controls"] == 2
    assert stats["missing_evidence"] == 1
    assert stats["open_findings"] == 1
    assert stats["high_critical_findings"] == 1
    assert stats["overdue_actions"] == 1


def test_audit_log_records_create(client, session, control):
    client.post("/requirements/new", data={
        "reference": "req-new-01", "title": "New", "category": "Resilience",
        "owner": "o", "review_frequency": "Annually",
    })
    entry = session.exec(select(AuditLog).where(AuditLog.entity == "Requirement")).one()
    assert entry.action == "create" and entry.detail == "REQ-NEW-01"


def test_pdf_report(client, control):
    resp = client.get("/report.pdf")
    assert resp.status_code == 200
    assert resp.content.startswith(b"%PDF")
