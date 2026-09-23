"""Monthly assurance status report as a PDF (fpdf2)."""
from fpdf import FPDF
from fpdf.enums import XPos, YPos

RISK_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}


def _t(text) -> str:
    """Built-in PDF fonts only support Latin-1, so replace anything else."""
    return str(text).encode("latin-1", "replace").decode("latin-1")


def _heading(pdf: FPDF, text: str) -> None:
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, _t(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)


def _row(pdf: FPDF, cells, widths, bold=False) -> None:
    pdf.set_font("Helvetica", "B" if bold else "", 9)
    for text, width in zip(cells, widths):
        pdf.cell(width, 7, _t(text)[: int(width / 1.75)], border=1)
    pdf.ln()


def build_status_report(stats: dict, open_findings: list, overdue_actions: list) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "AssuranceFlow - Monthly Assurance Status", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, _t(f"Fictional company: Fjordkit Digital A/S | Report date: {stats['today']:%d %B %Y}"),
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(0, 5, "Fictional learning project. Not a security assessment or compliance certification.")

    _heading(pdf, "1. Summary")
    summary = [
        ("Active controls", stats["total_controls"]),
        ("Controls with no evidence", stats["missing_evidence"]),
        ("Evidence past review date", stats["stale_evidence"]),
        ("Open findings", stats["open_findings"]),
        ("Open High/Critical findings", stats["high_critical_findings"]),
        ("Overdue remediation actions", stats["overdue_actions"]),
        ("Completed / verified actions", f"{stats['completed_actions']} of {stats['total_actions']}"),
    ]
    for label, value in summary:
        _row(pdf, [label, value], [90, 40])

    _heading(pdf, "2. Status by category")
    widths = [70, 30, 40, 35]
    _row(pdf, ["Category", "Controls", "Missing evidence", "Open findings"], widths, bold=True)
    for cat, v in stats["by_category"].items():
        _row(pdf, [cat, v["controls"], v["missing_evidence"], v["open_findings"]], widths)

    _heading(pdf, "3. Open findings (highest risk first)")
    widths = [75, 22, 38, 28, 27]
    _row(pdf, ["Finding", "Risk", "Owner", "Due", "Status"], widths, bold=True)
    for f in sorted(open_findings, key=lambda f: (RISK_ORDER.get(f.risk_rating.value, 9), f.due_date)):
        _row(pdf, [f.title, f.risk_rating.value, f.owner, f"{f.due_date:%Y-%m-%d}", f.status.value], widths)
    if not open_findings:
        pdf.cell(0, 7, "No open findings.", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    _heading(pdf, "4. Overdue remediation actions")
    widths = [85, 40, 30, 35]
    _row(pdf, ["Action", "Owner", "Target", "Status"], widths, bold=True)
    for a in overdue_actions:
        _row(pdf, [a.action, a.owner, f"{a.target_date:%Y-%m-%d}", a.status.value], widths)
    if not overdue_actions:
        pdf.cell(0, 7, "No overdue actions.", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    _heading(pdf, "5. Decisions / support needed")
    pdf.multi_cell(0, 5, _t(
        "Owners of overdue High/Critical items to confirm new target dates or request formal "
        "risk acceptance before the next review."
    ))
    return bytes(pdf.output())
