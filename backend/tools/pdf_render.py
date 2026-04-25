"""Render the court-ready PDF packet from a CaseFacts.

Produces a single merged PDF:
  1. Cover sheet (case caption + filing instructions)
  2. Statement of Claim (mirrors CIV-SC-50 layout)
  3. Demand letter
  4. Exhibit index

We render everything in ReportLab — controlled, deterministic, no
dependency on the official AcroForm being fillable. The output is
formatted to mirror the official CIV-SC-50 closely enough to walk
into the clerk's office with.
"""

from __future__ import annotations

import io
from datetime import date
from pathlib import Path
from typing import Optional

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from schema import CaseFacts
from tools.jurisdiction import _compute_damages_impl

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

BOROUGH_COURT_ADDRESS = {
    "Manhattan": "111 Centre Street, New York, NY 10013",
    "Bronx": "851 Grand Concourse, Bronx, NY 10451",
    "Brooklyn": "141 Livingston Street, Brooklyn, NY 11201",
    "Queens": "89-17 Sutphin Boulevard, Jamaica, NY 11435",
    "Staten Island": "927 Castleton Avenue, Staten Island, NY 10310",
}


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title", parent=base["Title"], fontSize=14, alignment=TA_CENTER,
            spaceAfter=10, leading=18,
        ),
        "h1": ParagraphStyle(
            "h1", parent=base["Heading1"], fontSize=12, spaceAfter=8, leading=15,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontSize=11, spaceAfter=6, leading=14,
        ),
        "body": ParagraphStyle(
            "body", parent=base["BodyText"], fontSize=10.5, leading=14,
            alignment=TA_JUSTIFY, spaceAfter=8,
        ),
        "caption": ParagraphStyle(
            "caption", parent=base["BodyText"], fontSize=10.5, leading=14,
            alignment=TA_LEFT,
        ),
        "small": ParagraphStyle(
            "small", parent=base["BodyText"], fontSize=9, leading=11,
            textColor=colors.grey,
        ),
    }


def _money(x: float) -> str:
    return f"${x:,.2f}"


def _full_addr(p) -> str:
    parts = [p.address]
    cs = " ".join(s for s in [p.city, p.state] if s)
    if cs:
        parts.append(cs)
    if p.zip_code:
        parts[-1] = f"{parts[-1]} {p.zip_code}".strip()
    return ", ".join(s for s in parts if s)


def _render_cover(story, st, facts: CaseFacts):
    court_addr = BOROUGH_COURT_ADDRESS.get(facts.venue.borough, "[borough address]")
    story.append(Paragraph("SMALL CLAIMS FILING PACKET", st["title"]))
    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph(
        f"<b>Plaintiff:</b> {facts.plaintiff.name or '[name]'}<br/>"
        f"<b>Defendant:</b> {facts.defendant.name or '[name]'}<br/>"
        f"<b>Amount demanded:</b> {_money(facts.damages.total_demanded or facts.damages.principal)}<br/>"
        f"<b>Court:</b> NYC Civil Court, Small Claims Part, {facts.venue.borough or '[borough]'} County<br/>"
        f"<b>Court address:</b> {court_addr}",
        st["body"],
    ))
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph("How to use this packet", st["h1"]))
    story.append(Paragraph(
        "1. <b>Send the demand letter first.</b> It often resolves matters without a filing. "
        "Keep the certified-mail receipt as Exhibit D.<br/>"
        "2. <b>If unpaid after 14 days, walk into the clerk's office above</b> with this packet "
        "and the filing fee ($20 for claims up to $1,000; $25 for $1,000.01–$10,000). "
        "Bring two copies plus the originals.<br/>"
        "3. <b>The clerk will serve the defendant by certified mail</b> at the service-of-process "
        "address on the Statement of Claim. A trial date is typically set within 45 days.<br/>"
        "4. <b>At trial</b>, bring the original exhibits in this packet. The case is decided informally; "
        "you do not need a lawyer.",
        st["body"],
    ))
    if facts.jurisdiction_check.issues:
        story.append(Spacer(1, 0.15 * inch))
        story.append(Paragraph("⚠ Jurisdiction notes", st["h2"]))
        for issue in facts.jurisdiction_check.issues:
            story.append(Paragraph(f"• {issue}", st["body"]))
    if facts.jurisdiction_check.citations:
        story.append(Paragraph(
            "<i>Citations: " + "; ".join(facts.jurisdiction_check.citations) + "</i>",
            st["small"],
        ))
    story.append(PageBreak())


def _render_claim(story, st, facts: CaseFacts):
    story.append(Paragraph("CIVIL COURT OF THE CITY OF NEW YORK", st["title"]))
    story.append(Paragraph(
        f"COUNTY OF {facts.venue.borough.upper() or '[BOROUGH]'} — SMALL CLAIMS PART",
        st["title"],
    ))
    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph("Index No.: ____________________  (assigned by clerk)", st["caption"]))
    story.append(Spacer(1, 0.1 * inch))

    caption = [
        [Paragraph(
            f"<b>{facts.plaintiff.name.upper() or '[PLAINTIFF]'}</b><br/>"
            f"{_full_addr(facts.plaintiff)}",
            st["caption"],
        )],
        [Paragraph("<i>Plaintiff,</i><br/><br/>— against —", st["caption"])],
        [Paragraph(
            f"<b>{(facts.defendant.dos_entity_name or facts.defendant.name).upper() or '[DEFENDANT]'}</b><br/>"
            f"with its registered service-of-process address at:<br/>"
            f"{facts.defendant.service_address or '[service of process address]'}",
            st["caption"],
        )],
        [Paragraph("<i>Defendant.</i>", st["caption"])],
    ]
    t = Table(caption, colWidths=[6.5 * inch])
    t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, colors.black),
                           ("LINEABOVE", (0, 1), (-1, 1), 0.25, colors.grey),
                           ("LINEABOVE", (0, 3), (-1, 3), 0.25, colors.grey),
                           ("LEFTPADDING", (0, 0), (-1, -1), 8),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                           ("TOPPADDING", (0, 0), (-1, -1), 6),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story.append(t)
    story.append(Spacer(1, 0.2 * inch))

    story.append(Paragraph("STATEMENT OF CLAIM", st["h1"]))

    cd = facts.contract.date_formed.isoformat() if facts.contract.date_formed else "[date]"
    pd = facts.performance.delivered_on.isoformat() if facts.performance.delivered_on else "[date]"
    bd = facts.breach.date.isoformat() if facts.breach.date else "[date]"

    paragraphs = [
        f"1. On or about <b>{cd}</b>, Plaintiff and Defendant entered into an agreement under which "
        f"Plaintiff would provide the following services: <b>{facts.contract.scope_of_work or '[scope]'}</b>.",

        f"2. The agreed contract price was <b>{_money(facts.contract.agreed_amount)}</b>"
        + (f", payable per the following terms: {facts.contract.payment_terms}." if facts.contract.payment_terms else "."),

        f"3. Plaintiff performed all services and delivered final work to Defendant on or about <b>{pd}</b>. "
        f"Defendant accepted the deliverables.",

        f"4. Payment became due. Defendant failed and has continued to refuse to pay any portion "
        f"of the amount due, in breach of the agreement (date of breach: <b>{bd}</b>).",

        f"5. Plaintiff has been damaged in the principal amount of <b>{_money(facts.damages.principal)}</b>, "
        f"plus statutory pre-judgment interest at 9% per annum from the date of breach pursuant to CPLR § 5004.",

        f"6. <b>Venue</b> is proper in {facts.venue.borough or '[borough]'} County because "
        f"{facts.venue.basis or '[basis for venue]'}.",
    ]
    for p in paragraphs:
        story.append(Paragraph(p, st["body"]))

    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph(
        f"<b>WHEREFORE</b>, Plaintiff demands judgment against Defendant in the principal amount of "
        f"<b>{_money(facts.damages.principal)}</b>, plus statutory interest of approximately "
        f"<b>{_money(facts.damages.total_demanded - facts.damages.principal)}</b> through the date "
        f"of this filing (continuing to accrue), plus the costs and disbursements of this action.",
        st["body"],
    ))
    story.append(Spacer(1, 0.3 * inch))

    today = date.today().isoformat()
    sig = (
        f"Dated: {facts.venue.borough or '[borough]'}, New York &nbsp; {today}<br/><br/>"
        f"_________________________________<br/>"
        f"<b>{facts.plaintiff.name or '[name]'}</b>, Plaintiff <i>pro se</i><br/>"
        f"{_full_addr(facts.plaintiff)}<br/>"
        f"{facts.plaintiff.phone}{' · ' if facts.plaintiff.phone and facts.plaintiff.email else ''}{facts.plaintiff.email}"
    )
    story.append(Paragraph(sig, st["caption"]))
    story.append(PageBreak())


def _render_demand_letter(story, st, facts: CaseFacts):
    story.append(Paragraph("DEMAND LETTER (send first; keep certified-mail receipt)", st["h1"]))
    story.append(Spacer(1, 0.1 * inch))

    dmg = _compute_damages_impl(facts.damages.principal, facts.breach.date.isoformat() if facts.breach.date else date.today().isoformat())
    today = date.today().isoformat()
    short = facts.contract.scope_of_work or "Outstanding invoice"

    template = (TEMPLATES_DIR / "demand_letter.txt").read_text(encoding="utf-8")
    body = template.format(
        plaintiff_name=facts.plaintiff.name or "[name]",
        plaintiff_address=facts.plaintiff.address or "[address]",
        plaintiff_city=facts.plaintiff.city or "",
        plaintiff_state=facts.plaintiff.state or "NY",
        plaintiff_zip=facts.plaintiff.zip_code or "",
        plaintiff_email=facts.plaintiff.email or "",
        plaintiff_phone=facts.plaintiff.phone or "",
        today_date=today,
        defendant_legal_name=facts.defendant.dos_entity_name or facts.defendant.name or "[defendant]",
        defendant_service_name=facts.defendant.dos_process_name if hasattr(facts.defendant, "dos_process_name") else "Service of Process",
        defendant_service_address=facts.defendant.service_address or "[service address]",
        short_description=short,
        total_demanded=f"{dmg.total_demanded:,.2f}",
        principal=f"{dmg.principal:,.2f}",
        interest_accrued=f"{dmg.interest_accrued:,.2f}",
        days_elapsed=dmg.days_elapsed,
        contract_date=facts.contract.date_formed.isoformat() if facts.contract.date_formed else "[contract date]",
        scope_of_work=facts.contract.scope_of_work or "[scope]",
        payment_due_date=facts.breach.date.isoformat() if facts.breach.date else "[due date]",
        breach_date=facts.breach.date.isoformat() if facts.breach.date else "[breach date]",
        borough=facts.venue.borough or "[borough]",
    )
    for para in body.split("\n\n"):
        story.append(Paragraph(para.replace("\n", "<br/>"), st["body"]))
    story.append(PageBreak())


def _render_exhibit_index(story, st, facts: CaseFacts):
    story.append(Paragraph("EXHIBIT INDEX", st["h1"]))
    if not facts.exhibits:
        story.append(Paragraph(
            "<i>No exhibits attached. Bring originals (contract, invoices, emails, screenshots, "
            "demand-letter receipt) to the clerk's office and to trial.</i>",
            st["body"],
        ))
        return
    rows = [["Label", "Description", "File"]]
    for ex in facts.exhibits:
        rows.append([ex.label, ex.description, ex.file_ref])
    t = Table(rows, colWidths=[0.7 * inch, 4.0 * inch, 1.8 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t)


def render_packet(facts: CaseFacts, output_path: Optional[Path] = None) -> bytes:
    """Render the full PDF packet for a case. Returns the PDF bytes.

    If `output_path` is given, also writes the file there.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=LETTER,
        leftMargin=0.9 * inch, rightMargin=0.9 * inch,
        topMargin=0.9 * inch, bottomMargin=0.9 * inch,
        title="Small Claims Filing Packet",
    )
    st = _styles()
    story = []
    _render_cover(story, st, facts)
    _render_claim(story, st, facts)
    _render_demand_letter(story, st, facts)
    _render_exhibit_index(story, st, facts)
    doc.build(story)
    data = buf.getvalue()
    if output_path:
        Path(output_path).write_bytes(data)
    return data
