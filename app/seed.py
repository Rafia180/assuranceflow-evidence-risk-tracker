"""Fictional sample data for Fjordkit Digital A/S. Dates are relative to today,
so the dashboard always shows a realistic mix of on-time and overdue items."""
from datetime import date, timedelta

from sqlmodel import Session, select

from app.models import (
    ActionStatus, Assessment, AssessmentResult, Control, EvidenceItem, Finding,
    FindingStatus, RemediationAction, Requirement, RiskRating,
)

REQUIREMENTS = [
    # reference, title, category, owner, frequency, control name, control owner
    ("REQ-AC-01", "User access to business systems is reviewed quarterly", "Access Management",
     "Head of IT", "Quarterly", "Quarterly access review of finance and HR systems", "IAM Lead"),
    ("REQ-AC-02", "Privileged accounts require multi-factor authentication", "Access Management",
     "Head of IT", "Annually", "MFA enforced on all admin accounts", "IAM Lead"),
    ("REQ-SD-01", "Code changes are peer-reviewed before release", "Secure Development",
     "Engineering Manager", "Continuous", "Mandatory pull-request review in main repositories", "Platform Team Lead"),
    ("REQ-SD-02", "Third-party libraries are scanned for known vulnerabilities", "Secure Development",
     "Engineering Manager", "Monthly", "Automated dependency scanning in CI pipeline", "DevOps Engineer"),
    ("REQ-BC-01", "Backups of critical systems are restore-tested", "Resilience",
     "Infrastructure Manager", "Semi-annually", "Backup restore test for customer database", "Infrastructure Engineer"),
    ("REQ-SR-01", "Critical suppliers undergo a security review", "Third-Party Risk",
     "Procurement Lead", "Annually", "Annual supplier security questionnaire", "Vendor Risk Analyst"),
    ("REQ-SA-01", "Employees complete security awareness training", "Security Awareness",
     "HR Business Partner", "Annually", "Annual awareness e-learning with completion tracking", "Security Awareness Lead"),
    ("REQ-IR-01", "Security incidents follow a documented response process", "Incident Response",
     "CISO", "Annually", "Incident response plan tested via tabletop exercise", "Security Operations Lead"),
    ("REQ-LG-01", "Security logs are retained and monitored", "Logging & Monitoring",
     "CISO", "Monthly", "Central log collection with alert review", "SOC Analyst"),
]


def seed_if_empty(session: Session) -> None:
    if session.exec(select(Requirement)).first():
        return
    today = date.today()
    d = lambda days: today + timedelta(days=days)  # noqa: E731

    controls = []
    for ref, title, cat, owner, freq, c_name, c_owner in REQUIREMENTS:
        req = Requirement(reference=ref, title=title, category=cat, owner=owner,
                          review_frequency=freq, description=f"Fictional requirement: {title.lower()}.")
        session.add(req)
        session.flush()
        ctrl = Control(requirement_id=req.id, name=c_name, owner=c_owner, frequency=freq,
                       description=f"Fictional control supporting {ref}.")
        session.add(ctrl)
        session.flush()
        controls.append(ctrl)

    ac1, mfa, pr, deps, backup, supplier, awareness, ir, logs = controls

    # Evidence (text references only - no real files). Two controls deliberately have none.
    session.add_all([
        EvidenceItem(control_id=ac1.id, title="Q3 access review sign-off", evidence_type="Sign-off",
                     collection_date=d(-40), review_date=d(50), owner="IAM Lead",
                     reference_link="SharePoint/demo/access-review-q3.pdf"),
        EvidenceItem(control_id=mfa.id, title="MFA policy configuration export", evidence_type="Screenshot",
                     collection_date=d(-200), review_date=d(-20), owner="IAM Lead",
                     reference_link="AUDIT-2026-014"),
        EvidenceItem(control_id=pr.id, title="Branch protection settings", evidence_type="Screenshot",
                     collection_date=d(-15), review_date=d(165), owner="Platform Team Lead",
                     reference_link="DEMO-REPO/settings/branches.png"),
        EvidenceItem(control_id=deps.id, title="Dependency scan summary", evidence_type="Report",
                     collection_date=d(-10), review_date=d(20), owner="DevOps Engineer",
                     reference_link="CI/demo/dependency-report-latest"),
        EvidenceItem(control_id=backup.id, title="Restore test ticket", evidence_type="Ticket",
                     collection_date=d(-120), review_date=d(60), owner="Infrastructure Engineer",
                     reference_link="ITSM-DEMO-4521"),
        EvidenceItem(control_id=awareness.id, title="Training completion export", evidence_type="Report",
                     collection_date=d(-30), review_date=d(335), owner="Security Awareness Lead",
                     reference_link="LMS/demo/completion-2026.csv"),
        EvidenceItem(control_id=logs.id, title="Alert review log extract", evidence_type="Log extract",
                     collection_date=d(-5), review_date=d(25), owner="SOC Analyst",
                     reference_link="SIEM/demo/weekly-review"),
    ])

    assessments = [
        (ac1, AssessmentResult.EFFECTIVE, "Review completed and signed off on time."),
        (mfa, AssessmentResult.PARTIALLY_EFFECTIVE, "Two service admin accounts found without MFA."),
        (pr, AssessmentResult.EFFECTIVE, "Branch protection enabled on all sampled repositories."),
        (deps, AssessmentResult.NOT_EFFECTIVE, "Critical alerts not triaged within agreed time."),
        (backup, AssessmentResult.EFFECTIVE, "Restore completed within target time."),
        (supplier, AssessmentResult.NOT_EFFECTIVE, "Three critical suppliers not reviewed this year."),
        (awareness, AssessmentResult.PARTIALLY_EFFECTIVE, "Completion at 86% against 95% target."),
        (ir, AssessmentResult.NOT_TESTED, "Tabletop exercise planned for next quarter."),
    ]
    saved = {}
    for ctrl, result, notes in assessments:
        a = Assessment(control_id=ctrl.id, assessment_date=d(-25), result=result,
                       assessor="Assurance Analyst (demo)", notes=notes)
        session.add(a)
        session.flush()
        saved[ctrl.id] = a

    f_mfa = Finding(control_id=mfa.id, assessment_id=saved[mfa.id].id, title="Admin accounts without MFA",
                    description="Two service admin accounts bypass MFA.", risk_rating=RiskRating.HIGH,
                    owner="IAM Lead", due_date=d(-5), status=FindingStatus.IN_PROGRESS)
    f_deps = Finding(control_id=deps.id, assessment_id=saved[deps.id].id,
                     title="Dependency alerts not triaged", description="Critical alerts older than 30 days.",
                     risk_rating=RiskRating.CRITICAL, owner="DevOps Engineer", due_date=d(14))
    f_sup = Finding(control_id=supplier.id, assessment_id=saved[supplier.id].id,
                    title="Critical supplier reviews missing", description="3 of 7 critical suppliers not reviewed.",
                    risk_rating=RiskRating.MEDIUM, owner="Vendor Risk Analyst", due_date=d(45))
    f_aw = Finding(control_id=awareness.id, assessment_id=saved[awareness.id].id,
                   title="Awareness completion below target", description="Completion 86% vs 95% target.",
                   risk_rating=RiskRating.LOW, owner="Security Awareness Lead", due_date=d(30),
                   status=FindingStatus.IN_PROGRESS)
    session.add_all([f_mfa, f_deps, f_sup, f_aw])
    session.flush()

    session.add_all([
        RemediationAction(finding_id=f_mfa.id, action="Enable MFA on remaining service admin accounts",
                          owner="IAM Lead", target_date=d(-7), status=ActionStatus.IN_PROGRESS),
        RemediationAction(finding_id=f_mfa.id, action="Add MFA check to monthly admin account report",
                          owner="IAM Lead", target_date=d(20)),
        RemediationAction(finding_id=f_deps.id, action="Triage and patch open critical dependency alerts",
                          owner="DevOps Engineer", target_date=d(10), status=ActionStatus.IN_PROGRESS),
        RemediationAction(finding_id=f_sup.id, action="Send questionnaires to the three missing suppliers",
                          owner="Vendor Risk Analyst", target_date=d(-2)),
        RemediationAction(finding_id=f_aw.id, action="Send reminder to teams below target",
                          owner="Security Awareness Lead", target_date=d(-10), status=ActionStatus.VERIFIED,
                          verification_notes="Reminder sent; completion rose to 91% (demo)."),
    ])
    session.commit()
