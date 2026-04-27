"""Render the court-ready PDF packet from a CaseFacts.

Produces a single merged PDF:
  1. Cover sheet   — case summary, filing instructions, checklist
  2. Statement of Claim — mirrors CIV-SC-50 layout
  3. Demand letter — formal pre-litigation notice
  4. Exhibit index — list of evidence files with labels

Design system
  Forest green  #2F4A36  — section headers, rules, accent
  Gold          #D9A441  — callout boxes, highlighted amounts
  Near-black    #1B1A17  — body text
  Cream         #FAF7F2  — callout backgrounds
  Light grey    #E8DFCE  — table alt rows, fine rules
"""

from __future__ import annotations

import io
from datetime import date
from pathlib import Path
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
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

# ── Brand palette ──────────────────────────────────────────────────────────────
GREEN       = colors.HexColor("#2F4A36")
GREEN_LIGHT = colors.HexColor("#638A6B")
GOLD        = colors.HexColor("#D9A441")
GOLD_LIGHT  = colors.HexColor("#FDF3DC")
INK         = colors.HexColor("#1B1A17")
CREAM       = colors.HexColor("#FAF7F2")
RULE_GREY   = colors.HexColor("#E8DFCE")
MID_GREY    = colors.HexColor("#C9BBA0")

BOROUGH_COURT_ADDRESS = {
    "Manhattan":    "111 Centre Street, New York, NY 10013",
    "Bronx":        "851 Grand Concourse, Bronx, NY 10451",
    "Brooklyn":     "141 Livingston Street, Brooklyn, NY 11201",
    "Queens":       "89-17 Sutphin Boulevard, Jamaica, NY 11435",
    "Staten Island":"927 Castleton Avenue, Staten Island, NY 10310",
}

W = 6.5 * inch   # usable text width


# ── Styles ─────────────────────────────────────────────────────────────────────

def _styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "doc_title": ParagraphStyle(
            "doc_title", parent=base["Title"],
            fontName="Helvetica-Bold", fontSize=18,
            textColor=colors.white, alignment=TA_CENTER,
            spaceAfter=0, leading=22,
        ),
        "section": ParagraphStyle(
            "section", parent=base["Heading1"],
            fontName="Helvetica-Bold", fontSize=11,
            textColor=GREEN, spaceAfter=6, spaceBefore=4, leading=14,
        ),
        "sub": ParagraphStyle(
            "sub", parent=base["Heading2"],
            fontName="Helvetica-Bold", fontSize=10,
            textColor=INK, spaceAfter=4, leading=13,
        ),
        "body": ParagraphStyle(
            "body", parent=base["BodyText"],
            fontName="Helvetica", fontSize=10.5,
            textColor=INK, leading=15, alignment=TA_JUSTIFY, spaceAfter=8,
        ),
        "body_left": ParagraphStyle(
            "body_left", parent=base["BodyText"],
            fontName="Helvetica", fontSize=10.5,
            textColor=INK, leading=15, alignment=TA_LEFT, spaceAfter=6,
        ),
        "caption": ParagraphStyle(
            "caption", parent=base["BodyText"],
            fontName="Helvetica", fontSize=10.5,
            textColor=INK, leading=14, alignment=TA_LEFT,
        ),
        "caption_bold": ParagraphStyle(
            "caption_bold", parent=base["BodyText"],
            fontName="Helvetica-Bold", fontSize=10.5,
            textColor=INK, leading=14, alignment=TA_LEFT,
        ),
        "small": ParagraphStyle(
            "small", parent=base["BodyText"],
            fontName="Helvetica", fontSize=8.5,
            textColor=MID_GREY, leading=11, spaceAfter=4,
        ),
        "small_bold": ParagraphStyle(
            "small_bold", parent=base["BodyText"],
            fontName="Helvetica-Bold", fontSize=8.5,
            textColor=GREEN, leading=11, spaceAfter=2,
        ),
        "amount": ParagraphStyle(
            "amount", parent=base["BodyText"],
            fontName="Helvetica-Bold", fontSize=14,
            textColor=INK, leading=18, alignment=TA_CENTER,
        ),
        "court_header": ParagraphStyle(
            "court_header", parent=base["Normal"],
            fontName="Helvetica-Bold", fontSize=11,
            textColor=INK, alignment=TA_CENTER, leading=15, spaceAfter=2,
        ),
        "step_num": ParagraphStyle(
            "step_num", parent=base["Normal"],
            fontName="Helvetica-Bold", fontSize=13,
            textColor=GREEN, leading=16,
        ),
        "step_body": ParagraphStyle(
            "step_body", parent=base["BodyText"],
            fontName="Helvetica", fontSize=10,
            textColor=INK, leading=14, spaceAfter=2,
        ),
        "label": ParagraphStyle(
            "label", parent=base["Normal"],
            fontName="Helvetica-Bold", fontSize=8,
            textColor=MID_GREY, leading=10,
        ),
        "value": ParagraphStyle(
            "value", parent=base["Normal"],
            fontName="Helvetica-Bold", fontSize=10.5,
            textColor=INK, leading=13,
        ),
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _money(x: float) -> str:
    return f"${x:,.2f}"

def _short_scope(text: str, max_len: int = 100) -> str:
    """Return a concise version of scope_of_work for Re: lines and body paragraphs."""
    if not text:
        return "[services rendered]"
    # Strip leading boilerplate phrases agents sometimes copy verbatim from contracts
    for prefix in ("Designer agrees to create and deliver:", "Contractor shall provide:",
                   "Plaintiff agrees to provide:", "Services include:"):
        if text.strip().startswith(prefix):
            text = text.strip()[len(prefix):].strip()
            break
    # Take the first sentence if it fits; otherwise truncate at a word boundary
    first = text.split(".")[0].strip()
    if len(first) <= max_len:
        return first
    cut = text[:max_len].rsplit(" ", 1)[0]
    return cut + "…"

def _full_addr(p) -> str:
    parts = [p.address]
    cs = " ".join(s for s in [p.city, p.state] if s)
    if cs:
        parts.append(cs)
    if p.zip_code:
        parts[-1] = f"{parts[-1]} {p.zip_code}".strip()
    return ", ".join(s for s in parts if s)

def _hr(color=RULE_GREY, thickness=0.5):
    return HRFlowable(width="100%", thickness=thickness, color=color, spaceAfter=8, spaceBefore=4)

def _section_header(text: str, st: dict):
    """Green-underlined section heading."""
    return KeepTogether([
        Paragraph(text, st["section"]),
        HRFlowable(width="100%", thickness=1, color=GREEN, spaceAfter=8, spaceBefore=0),
    ])

def _info_row(label: str, value: str, st: dict):
    """Two-cell label / value row for info tables."""
    return [Paragraph(label, st["label"]), Paragraph(value, st["value"])]


# ── Page template (header + footer on every page) ─────────────────────────────

def _make_page_decorator(total_pages_ref: list):
    """Returns onPage callback. total_pages_ref[0] is set after build."""
    def _decorate(canvas, doc):
        canvas.saveState()
        w, h = LETTER

        # Top rule — thin green line
        canvas.setStrokeColor(GREEN)
        canvas.setLineWidth(1.5)
        canvas.line(0.9 * inch, h - 0.55 * inch, w - 0.9 * inch, h - 0.55 * inch)

        # Footer rule
        canvas.setStrokeColor(RULE_GREY)
        canvas.setLineWidth(0.5)
        canvas.line(0.9 * inch, 0.65 * inch, w - 0.9 * inch, 0.65 * inch)

        # Footer left — branding
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MID_GREY)
        canvas.drawString(0.9 * inch, 0.45 * inch, "QuietCase · NYC Small Claims Filing Packet")

        # Footer right — page number
        canvas.drawRightString(w - 0.9 * inch, 0.45 * inch, f"Page {doc.page}")

        canvas.restoreState()

    return _decorate


# ── Cover sheet ────────────────────────────────────────────────────────────────

def _render_cover(story, st, facts: CaseFacts):
    court_addr = BOROUGH_COURT_ADDRESS.get(facts.venue.borough, "[see clerk]")
    total = facts.damages.total_demanded or facts.damages.principal
    principal = facts.damages.principal

    # ── Dark green title banner ───────────────────────────────────────────────
    banner = Table(
        [[Paragraph("SMALL CLAIMS FILING PACKET", st["doc_title"])]],
        colWidths=[W],
    )
    banner.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), GREEN),
        ("TOPPADDING",    (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
    ]))
    story.append(banner)
    story.append(Spacer(1, 0.25 * inch))

    # ── Case summary card (two-column grid) ───────────────────────────────────
    def info_cell(label, value):
        return [
            Paragraph(label, st["label"]),
            Paragraph(value or "—", st["value"]),
        ]

    def divider():
        return [Paragraph("", st["label"]), Paragraph("", st["label"])]

    summary_data = [
        info_cell("PLAINTIFF", facts.plaintiff.name or "[name]"),
        info_cell("", _full_addr(facts.plaintiff)),
        divider(),
        info_cell("DEFENDANT", (facts.defendant.dos_entity_name or facts.defendant.name) or "[name]"),
        info_cell("SERVICE ADDRESS", facts.defendant.service_address or "To be resolved via NY DOS"),
        divider(),
        info_cell("COURT", f"NYC Civil Court, Small Claims Part — {facts.venue.borough or '[borough]'} County"),
        info_cell("COURT ADDRESS", court_addr),
    ]
    sum_t = Table(summary_data, colWidths=[1.5 * inch, 5.0 * inch])
    sum_t.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(sum_t)
    story.append(Spacer(1, 0.2 * inch))

    # ── Gold amount callout ───────────────────────────────────────────────────
    interest = total - principal
    amt_data = [
        [
            Paragraph("PRINCIPAL", st["label"]),
            Paragraph("9% INTEREST (CPLR § 5004)", st["label"]),
            Paragraph("TOTAL DEMANDED", st["label"]),
        ],
        [
            Paragraph(_money(principal), st["amount"]),
            Paragraph(_money(interest), st["amount"]),
            Paragraph(_money(total), st["amount"]),
        ],
    ]
    amt_t = Table(amt_data, colWidths=[W / 3, W / 3, W / 3])
    amt_t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), GOLD_LIGHT),
        ("BACKGROUND",    (2, 0), (2, -1), colors.HexColor("#FDE8A0")),
        ("BOX",           (0, 0), (-1, -1), 1, GOLD),
        ("LINEAFTER",     (0, 0), (1, -1), 0.5, GOLD),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(amt_t)
    story.append(Spacer(1, 0.3 * inch))

    # ── Filing steps ──────────────────────────────────────────────────────────
    story.append(_section_header("HOW TO FILE", st))

    steps = [
        ("1", "Send the demand letter first.",
         "Mail it via USPS Certified Mail. Keep the green card receipt — it becomes Exhibit D."),
        ("2", "Wait 14 days.",
         "If unpaid, proceed to the clerk's office at the address above with this packet. "
         f"Filing fee: $20 for claims ≤ $1,000 · $25 for claims up to $10,000. Bring two copies."),
        ("3", "The clerk serves the defendant.",
         "The court mails a summons to the service-of-process address on the Statement of Claim. "
         "A trial date is typically set within 45 days."),
        ("4", "Appear at trial.",
         "Bring the originals of every exhibit. The hearing is informal — no lawyer needed. "
         "The judge decides based on your documents and testimony."),
    ]
    for num, bold, detail in steps:
        step_t = Table(
            [[Paragraph(num, st["step_num"]),
              [Paragraph(f"<b>{bold}</b>", st["step_body"]),
               Paragraph(detail, st["step_body"])]]],
            colWidths=[0.35 * inch, 6.15 * inch],
        )
        step_t.setStyle(TableStyle([
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING",    (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING",   (0, 0), (0, -1), 0),
            ("RIGHTPADDING",  (0, 0), (0, -1), 8),
        ]))
        story.append(KeepTogether(step_t))

    # ── Jurisdiction notes (if any) ───────────────────────────────────────────
    if facts.jurisdiction_check.issues:
        story.append(Spacer(1, 0.2 * inch))
        warn_rows = [[Paragraph("⚠  JURISDICTION NOTES", st["small_bold"])]]
        for issue in facts.jurisdiction_check.issues:
            warn_rows.append([Paragraph(f"• {issue}", st["small"])])
        warn_t = Table(warn_rows, colWidths=[W])
        warn_t.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#FFF8E1")),
            ("BOX",           (0, 0), (-1, -1), 0.75, GOLD),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(warn_t)

    if facts.jurisdiction_check.citations:
        story.append(Spacer(1, 0.1 * inch))
        story.append(Paragraph(
            "Citations: " + " · ".join(facts.jurisdiction_check.citations),
            st["small"],
        ))

    story.append(PageBreak())


# ── Statement of Claim ─────────────────────────────────────────────────────────

def _render_claim(story, st, facts: CaseFacts):
    # Court caption header
    story.append(Paragraph("CIVIL COURT OF THE CITY OF NEW YORK", st["court_header"]))
    story.append(Paragraph(
        f"COUNTY OF {(facts.venue.borough or '[BOROUGH]').upper()} — SMALL CLAIMS PART",
        st["court_header"],
    ))
    story.append(_hr(GREEN, 1))
    story.append(Spacer(1, 0.05 * inch))
    story.append(Paragraph(
        "Index No.: ____________________  (to be assigned by clerk)",
        st["small"],
    ))
    story.append(Spacer(1, 0.15 * inch))

    # Plaintiff vs Defendant caption box
    p_name  = facts.plaintiff.name.upper() if facts.plaintiff.name else "[PLAINTIFF]"
    p_addr  = _full_addr(facts.plaintiff)
    def_name = (facts.defendant.dos_entity_name or facts.defendant.name or "[DEFENDANT]").upper()
    def_addr = facts.defendant.service_address or "[service of process address]"

    caption_data = [
        [Paragraph(f"<b>{p_name}</b><br/>{p_addr}", st["caption"]),
         Paragraph("<i>Plaintiff,</i>", st["caption"])],
        [Paragraph("— against —", st["caption"]), Paragraph("", st["caption"])],
        [Paragraph(f"<b>{def_name}</b><br/>"
                   f"Service of process address:<br/>{def_addr}", st["caption"]),
         Paragraph("<i>Defendant.</i>", st["caption"])],
    ]
    cap_t = Table(caption_data, colWidths=[5.2 * inch, 1.3 * inch])
    cap_t.setStyle(TableStyle([
        ("BOX",           (0, 0), (-1, -1), 0.75, INK),
        ("LINEBELOW",     (0, 0), (-1, 0), 0.25, RULE_GREY),
        ("LINEBELOW",     (0, 1), (-1, 1), 0.25, RULE_GREY),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(cap_t)
    story.append(Spacer(1, 0.25 * inch))

    story.append(_section_header("STATEMENT OF CLAIM", st))

    cd = facts.contract.date_formed.isoformat() if facts.contract.date_formed else "[date]"
    pd = facts.performance.delivered_on.isoformat() if facts.performance.delivered_on else "[date]"
    bd = facts.breach.date.isoformat() if facts.breach.date else "[date]"
    scope_short = _short_scope(facts.contract.scope_of_work)

    paragraphs = [
        f"1.  On or about <b>{cd}</b>, Plaintiff and Defendant entered into an agreement under "
        f"which Plaintiff would provide: <b>{scope_short}</b>.",

        f"2.  The agreed contract price was <b>{_money(facts.contract.agreed_amount)}</b>"
        + (f", payable {facts.contract.payment_terms}." if facts.contract.payment_terms else "."),

        f"3.  Plaintiff performed all obligations and delivered final work on or about "
        f"<b>{pd}</b>. Defendant accepted the deliverables without objection.",

        f"4.  Payment became due on <b>{bd}</b>. Defendant has failed and refused to pay "
        f"any portion of the amount owed, in material breach of the agreement.",

        f"5.  Plaintiff has been damaged in the principal amount of "
        f"<b>{_money(facts.damages.principal)}</b>, plus statutory pre-judgment interest "
        f"at 9% per annum from the date of breach pursuant to CPLR § 5004.",

        f"6.  <b>Venue</b> is proper in {facts.venue.borough or '[borough]'} County "
        f"because {facts.venue.basis or '[basis for venue]'}.",
    ]
    for p in paragraphs:
        story.append(KeepTogether(Paragraph(p, st["body"])))

    # WHEREFORE in a shaded box
    total = facts.damages.total_demanded or facts.damages.principal
    interest = total - facts.damages.principal
    wf_data = [[Paragraph(
        f"<b>WHEREFORE</b>, Plaintiff demands judgment against Defendant in the principal "
        f"amount of <b>{_money(facts.damages.principal)}</b>, plus statutory interest of "
        f"approximately <b>{_money(interest)}</b> through the date of this filing "
        f"(continuing to accrue), for a total of <b>{_money(total)}</b>, plus costs and "
        f"disbursements of this action.",
        st["body_left"],
    )]]
    wf_t = Table(wf_data, colWidths=[W])
    wf_t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), CREAM),
        ("BOX",           (0, 0), (-1, -1), 0.5, RULE_GREY),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    today = date.today().isoformat()
    story.append(KeepTogether([
        wf_t,
        Spacer(1, 0.3 * inch),
        Paragraph(
            f"Dated: {facts.venue.borough or '[borough]'}, New York &nbsp;&nbsp; {today}",
            st["caption"],
        ),
        Spacer(1, 0.4 * inch),
        _hr(),
        Paragraph(
            f"<b>{facts.plaintiff.name or '[name]'}</b>, Plaintiff <i>pro se</i><br/>"
            f"{_full_addr(facts.plaintiff)}<br/>"
            f"{facts.plaintiff.phone}"
            f"{'&nbsp; · &nbsp;' if facts.plaintiff.phone and facts.plaintiff.email else ''}"
            f"{facts.plaintiff.email}",
            st["caption"],
        ),
    ]))
    story.append(PageBreak())


# ── Demand letter ──────────────────────────────────────────────────────────────

def _render_demand_letter(story, st, facts: CaseFacts):
    dmg = _compute_damages_impl(
        facts.damages.principal,
        facts.breach.date.isoformat() if facts.breach.date else date.today().isoformat(),
    )
    today = date.today().strftime("%B %d, %Y")
    bd_str = facts.breach.date.strftime("%B %d, %Y") if facts.breach.date else "[breach date]"
    cd_str = facts.contract.date_formed.strftime("%B %d, %Y") if facts.contract.date_formed else "[contract date]"
    scope_short = _short_scope(facts.contract.scope_of_work)

    # Sender block
    story.append(Paragraph(
        f"<b>{facts.plaintiff.name or '[name]'}</b><br/>"
        f"{_full_addr(facts.plaintiff)}<br/>"
        f"{facts.plaintiff.email}&nbsp; · &nbsp;{facts.plaintiff.phone}",
        st["body_left"],
    ))
    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph(today, st["body_left"]))
    story.append(Spacer(1, 0.1 * inch))

    # Delivery notice
    via_data = [[Paragraph(
        "VIA CERTIFIED MAIL — RETURN RECEIPT REQUESTED", st["small_bold"]
    )]]
    via_t = Table(via_data, colWidths=[W])
    via_t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), CREAM),
        ("BOX",           (0, 0), (-1, -1), 0.5, GREEN_LIGHT),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(via_t)
    story.append(Spacer(1, 0.15 * inch))

    # Recipient block
    def_name = facts.defendant.dos_entity_name or facts.defendant.name or "[defendant]"
    story.append(Paragraph(
        f"<b>{def_name}</b><br/>"
        f"{facts.defendant.service_address or '[service address]'}",
        st["body_left"],
    ))
    story.append(Spacer(1, 0.05 * inch))
    story.append(Paragraph(
        f"<b>Re: Final Demand for Payment — {scope_short}</b>",
        st["body_left"],
    ))
    story.append(_hr())

    # Body
    story.append(Paragraph("Dear Sir or Madam:", st["body_left"]))
    story.append(Paragraph(
        f"This letter constitutes a formal, final pre-litigation demand for the payment of "
        f"<b>${dmg.total_demanded:,.2f}</b> owed by <b>{def_name}</b> to me.",
        st["body"],
    ))
    story.append(Paragraph(
        f"On or about <b>{cd_str}</b>, we entered into an agreement under which I agreed to "
        f"provide: <b>{scope_short}</b>. "
        f"I performed all my obligations in full. Payment of <b>${dmg.principal:,.2f}</b> "
        f"became due on <b>{bd_str}</b> and has not been received.",
        st["body"],
    ))

    # Amount breakdown — plain black & white table (this is a formal legal letter)
    story.append(Spacer(1, 0.05 * inch))
    r_style = ParagraphStyle("r", parent=st["body_left"], alignment=TA_RIGHT)
    r_bold  = ParagraphStyle("rb", parent=st["caption_bold"], alignment=TA_RIGHT)
    amt_rows = [
        [Paragraph("Principal (contract price)", st["body_left"]),
         Paragraph(_money(dmg.principal), r_style)],
        [Paragraph(f"Pre-judgment interest at 9% per annum (CPLR § 5004),\n"
                   f"{dmg.days_elapsed} days from {bd_str}",
                   st["body_left"]),
         Paragraph(_money(dmg.interest_accrued), r_style)],
        [Paragraph("<b>TOTAL DUE</b>", st["caption_bold"]),
         Paragraph(f"<b>{_money(dmg.total_demanded)}</b>", r_bold)],
    ]
    amt_t = Table(amt_rows, colWidths=[4.8 * inch, 1.7 * inch])
    amt_t.setStyle(TableStyle([
        ("BOX",           (0, 0), (-1, -1), 0.5, INK),
        ("LINEBELOW",     (0, 1), (-1, 1), 0.5, INK),
        ("LINEABOVE",     (0, 2), (-1, 2), 0.5, INK),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(KeepTogether(amt_t))
    story.append(Spacer(1, 0.2 * inch))

    story.append(Paragraph(
        f"If full payment is not received within <b>fourteen (14) days</b> of your receipt of "
        f"this letter, I will commence an action against {def_name} in the NYC Civil Court, "
        f"Small Claims Part, <b>{facts.venue.borough or '[borough]'} County</b>, without further "
        f"notice. You will additionally be liable for costs and statutory interest accruing "
        f"through the date of judgment.",
        st["body"],
    ))
    story.append(KeepTogether([
        Paragraph(
            "I would prefer to resolve this matter without court intervention. Please contact me "
            "promptly if you wish to discuss payment or a settlement.",
            st["body"],
        ),
        Spacer(1, 0.3 * inch),
        Paragraph("Sincerely,", st["body_left"]),
        Spacer(1, 0.45 * inch),
        _hr(),
        Paragraph(f"<b>{facts.plaintiff.name or '[name]'}</b>", st["caption"]),
    ]))
    story.append(PageBreak())


# ── Exhibit index ──────────────────────────────────────────────────────────────

def _render_exhibit_index(story, st, facts: CaseFacts):
    story.append(_section_header("EXHIBIT INDEX", st))
    story.append(Paragraph(
        "Bring the originals of each exhibit below to the clerk's office when filing and to "
        "trial. If an exhibit is not yet printed, note its description for the judge.",
        st["body"],
    ))
    story.append(Spacer(1, 0.1 * inch))

    if not facts.exhibits:
        story.append(Paragraph(
            "<i>No exhibits have been indexed. Bring your signed contract, invoices, "
            "email threads, screenshots, and the demand-letter certified-mail receipt.</i>",
            st["body"],
        ))
        return

    rows = [[
        Paragraph("LABEL", st["small_bold"]),
        Paragraph("DESCRIPTION", st["small_bold"]),
        Paragraph("FILE", st["small_bold"]),
    ]]
    for i, ex in enumerate(facts.exhibits):
        bg = CREAM if i % 2 == 0 else colors.white
        rows.append([
            Paragraph(ex.label, st["caption_bold"]),
            Paragraph(ex.description, st["caption"]),
            Paragraph(ex.file_ref or "—", st["small"]),
        ])

    t = Table(rows, colWidths=[0.75 * inch, 4.25 * inch, 1.5 * inch])
    style = [
        ("BACKGROUND",    (0, 0), (-1, 0), GREEN),
        ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0), 8),
        ("BOX",           (0, 0), (-1, -1), 0.5, RULE_GREY),
        ("INNERGRID",     (0, 0), (-1, -1), 0.25, RULE_GREY),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 7),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 7),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for i in range(1, len(rows)):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), CREAM))
    t.setStyle(TableStyle(style))
    story.append(t)


# ── Public API ─────────────────────────────────────────────────────────────────

def render_packet(facts: CaseFacts, output_path: Optional[Path] = None) -> bytes:
    """Render the full PDF packet. Returns bytes; optionally writes to output_path."""
    buf = io.BytesIO()
    page_decorator = _make_page_decorator([])
    doc = SimpleDocTemplate(
        buf,
        pagesize=LETTER,
        leftMargin=0.9 * inch,
        rightMargin=0.9 * inch,
        topMargin=0.85 * inch,
        bottomMargin=0.85 * inch,
        title=f"Small Claims Packet — {facts.plaintiff.name or 'Plaintiff'} v. "
              f"{facts.defendant.dos_entity_name or facts.defendant.name or 'Defendant'}",
        author="QuietCase",
        subject="NYC Small Claims Court Filing Packet",
    )
    st = _styles()
    story: list = []
    _render_cover(story, st, facts)
    _render_claim(story, st, facts)
    _render_demand_letter(story, st, facts)
    _render_exhibit_index(story, st, facts)
    doc.build(story, onFirstPage=page_decorator, onLaterPages=page_decorator)
    data = buf.getvalue()
    if output_path:
        Path(output_path).write_bytes(data)
    return data
