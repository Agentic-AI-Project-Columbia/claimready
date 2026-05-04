"""Render the court-ready PDF packet from a CaseFacts.

Produces a single merged PDF, split into two clearly-labeled parts:

  Cover sheet       — case caption, parties, court, total demanded
  ─ FOR THE COURT (submit these pages to the clerk) ─
  Statement of Claim — mirrors CIV-SC-50 layout
  Demand letter      — formal pre-litigation notice (mail first)
  Exhibit index      — list of evidence files with labels
  ─ FOR YOU (reference material, keep for your records) ─
  How to File        — quick 4-step overview
  Filing guide       — borough-specific, step-by-step pro-se walkthrough

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
from tools.jurisdiction import DamagesResult, _compute_damages_impl

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

from config import BOROUGH_COURT_ADDRESS, BOROUGH_FILING_INFO, CIVIL_COURT_INFO_URL

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
    """Return a concise version of a scope/basis field.

    Strips boilerplate contract prefixes, takes the first sentence if short
    enough, otherwise truncates at the last semicolon or comma before max_len
    so the cut point looks intentional rather than mid-word.
    """
    if not text:
        return "services rendered"
    for prefix in (
        "Designer agrees to create and deliver:",
        "Contractor shall provide:",
        "Plaintiff agrees to provide:",
        "Services include:",
        "Scope of work:",
    ):
        if text.strip().lower().startswith(prefix.lower()):
            text = text.strip()[len(prefix):].strip()
            break
    # Use the first sentence if it fits
    first = text.split(".")[0].strip()
    if len(first) <= max_len:
        return first
    # Truncate at the last semicolon or comma before max_len for a clean break
    chunk = text[:max_len]
    for sep in (";", ","):
        idx = chunk.rfind(sep)
        if idx > max_len // 2:
            return chunk[:idx].strip() + "…"
    return chunk.rsplit(" ", 1)[0] + "…"


def prepare_for_render(facts: CaseFacts) -> DamagesResult:
    """Normalize damages once and validate minimum fields before rendering."""
    errors: list[str] = []
    if facts.damages.principal <= 0:
        errors.append("damages.principal must be > 0")
    if not facts.plaintiff.name:
        errors.append("plaintiff.name is required")
    if not (facts.defendant.name or facts.defendant.dos_entity_name):
        errors.append("defendant name is required")
    if errors:
        raise ValueError("Cannot render court-ready packet: " + "; ".join(errors))

    breach_iso = (
        facts.breach.date.isoformat()
        if facts.breach.date
        else date.today().isoformat()
    )
    dmg = _compute_damages_impl(facts.damages.principal, breach_iso)
    facts.damages.principal = dmg.principal
    facts.damages.total_demanded = dmg.total_demanded
    return dmg


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
        canvas.drawString(0.9 * inch, 0.45 * inch, "ClaimReady · NYC Small Claims Filing Packet")

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

    disclaimer = Table(
        [[Paragraph(
            "<b>Important:</b> ClaimReady generates documents and educational filing guidance "
            "from public statutes and court forms. It is not a law firm and does not provide "
            "legal advice. For a complex case, consult a licensed attorney.",
            st["small"],
        )]],
        colWidths=[W],
    )
    disclaimer.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#F7F7F2")),
        ("BOX",           (0, 0), (-1, -1), 0.5, RULE_GREY),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(disclaimer)
    story.append(Spacer(1, 0.25 * inch))

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

    def _fmt_date(d) -> str:
        return d.strftime("%B %d, %Y") if d else "[date]"

    cd = _fmt_date(facts.contract.date_formed)
    pd = _fmt_date(facts.performance.delivered_on)
    bd = _fmt_date(facts.breach.date)
    scope_short = _short_scope(facts.contract.scope_of_work, max_len=120)

    paragraphs = [
        f"1.  On or about <b>{cd}</b>, Plaintiff and Defendant entered into an agreement under "
        f"which Plaintiff would provide: <b>{scope_short}</b>.",

        f"2.  The agreed contract price was <b>{_money(facts.contract.agreed_amount)}</b>"
        + (f", payable {_short_scope(facts.contract.payment_terms, max_len=60)}."
           if facts.contract.payment_terms else "."),

        f"3.  Plaintiff performed all obligations and delivered final work on or about "
        f"<b>{pd}</b>. Defendant accepted the deliverables without objection.",

        f"4.  Payment became due on <b>{bd}</b>. Defendant has failed and refused to pay "
        f"any portion of the amount owed, in material breach of the agreement.",

        f"5.  Plaintiff has been damaged in the principal amount of "
        f"<b>{_money(facts.damages.principal)}</b>, plus statutory pre-judgment interest "
        f"at 9% per annum from the date of breach pursuant to CPLR § 5004.",

        f"6.  <b>Venue</b> is proper in {facts.venue.borough or '[borough]'} County "
        f"because {_short_scope(facts.venue.basis, max_len=120) if facts.venue.basis else '[basis for venue]'}.",
    ]
    # Tighter style for numbered paragraphs so WHEREFORE fits on the same page
    claim_body = ParagraphStyle(
        "claim_body", parent=st["body"], spaceAfter=5, leading=14,
    )
    for p in paragraphs:
        story.append(KeepTogether(Paragraph(p, claim_body)))

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

def _render_demand_letter(story, st, facts: CaseFacts, dmg: DamagesResult):
    today = date.today().strftime("%B %d, %Y")
    bd_str = facts.breach.date.strftime("%B %d, %Y") if facts.breach.date else None
    cd_str = facts.contract.date_formed.strftime("%B %d, %Y") if facts.contract.date_formed else "[contract date]"
    scope_short = _short_scope(facts.contract.scope_of_work, max_len=120)

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
    due_str = f", due {bd_str}" if bd_str else ""
    story.append(Paragraph(
        f"<b>Re: Final Demand for Payment — {_money(dmg.total_demanded)} outstanding{due_str}</b>",
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
        f"became due on <b>{bd_str or '[due date]'}</b> and has not been received.",
        st["body"],
    ))

    # Amount breakdown — plain black & white table (formal legal letter)
    r_style = ParagraphStyle("r", parent=st["body_left"], alignment=TA_RIGHT)
    r_bold  = ParagraphStyle("rb", parent=st["caption_bold"], alignment=TA_RIGHT)
    interest_row_label = (
        f"Pre-judgment interest at 9% per annum (CPLR § 5004)"
        + (f", {dmg.days_elapsed} days from {bd_str}" if bd_str else "")
    )
    amt_rows = [
        [Paragraph("Principal (contract price)", st["body_left"]),
         Paragraph(_money(dmg.principal), r_style)],
        [Paragraph(interest_row_label, st["body_left"]),
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
    story.append(Spacer(1, 0.1 * inch))
    story.append(KeepTogether([
        Paragraph("AMOUNT CURRENTLY DUE", st["small_bold"]),
        Spacer(1, 0.04 * inch),
        amt_t,
    ]))
    story.append(Spacer(1, 0.2 * inch))

    story.append(KeepTogether([
        Paragraph(
            f"If full payment is not received within <b>fourteen (14) days</b> of your receipt of "
            f"this letter, I will commence an action against {def_name} in the NYC Civil Court, "
            f"Small Claims Part, <b>{facts.venue.borough or '[borough]'} County</b>, without "
            f"further notice. You will additionally be liable for costs and statutory interest "
            f"accruing through the date of judgment.",
            st["body"],
        ),
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

    # Header row
    rows = [[
        Paragraph("EXHIBIT", st["small_bold"]),
        Paragraph("DESCRIPTION", st["small_bold"]),
    ]]
    for ex in facts.exhibits:
        rows.append([
            Paragraph(ex.label, st["caption_bold"]),
            Paragraph(ex.description, st["caption"]),
        ])

    t = Table(rows, colWidths=[1.1 * inch, 5.4 * inch])
    style = [
        # Header row: light green background, green text
        ("BACKGROUND",    (0, 0), (-1, 0), colors.HexColor("#DCE6DC")),
        ("TEXTCOLOR",     (0, 0), (-1, 0), GREEN),
        # Outer border + row separators only (no inner vertical grid)
        ("BOX",           (0, 0), (-1, -1), 0.5, RULE_GREY),
        ("LINEBELOW",     (0, 0), (-1, -2), 0.25, RULE_GREY),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    # Alternating row backgrounds (skip header row 0)
    for i in range(1, len(rows)):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), CREAM))
    t.setStyle(TableStyle(style))
    story.append(t)


# ── Section dividers ──────────────────────────────────────────────────────────

def _render_section_divider(
    story,
    st,
    *,
    eyebrow: str,
    title: str,
    subtitle: str,
    contents: list[tuple[str, str]],
    accent: colors.HexColor,
    accent_bg: colors.HexColor,
):
    """Full-page divider that introduces a major section of the packet."""
    story.append(PageBreak())
    story.append(Spacer(1, 1.2 * inch))

    eyebrow_p = Paragraph(eyebrow, ParagraphStyle(
        "divider_eyebrow", parent=st["label"],
        fontName="Helvetica-Bold", fontSize=10,
        textColor=accent, alignment=TA_CENTER, leading=12, spaceAfter=8,
    ))
    story.append(eyebrow_p)

    banner = Table(
        [[Paragraph(title, st["doc_title"])]],
        colWidths=[W],
    )
    banner.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), accent),
        ("TOPPADDING",    (0, 0), (-1, -1), 22),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 22),
    ]))
    story.append(banner)
    story.append(Spacer(1, 0.25 * inch))

    sub = Paragraph(subtitle, ParagraphStyle(
        "divider_sub", parent=st["body"],
        fontName="Helvetica", fontSize=12,
        textColor=INK, alignment=TA_CENTER, leading=16, spaceAfter=18,
    ))
    story.append(sub)
    story.append(Spacer(1, 0.3 * inch))

    in_this_section = Paragraph(
        "<b>IN THIS SECTION</b>",
        ParagraphStyle(
            "divider_label", parent=st["label"],
            fontName="Helvetica-Bold", fontSize=8,
            textColor=MID_GREY, leading=10, spaceAfter=8,
        ),
    )
    story.append(in_this_section)

    for item_title, item_desc in contents:
        row = Table(
            [[
                Paragraph("<b>·</b>", ParagraphStyle(
                    "bullet", parent=st["step_num"],
                    fontName="Helvetica-Bold", fontSize=14, textColor=accent,
                )),
                [
                    Paragraph(f"<b>{item_title}</b>", st["step_body"]),
                    Paragraph(item_desc, st["small"]),
                ],
            ]],
            colWidths=[0.25 * inch, W - 0.25 * inch],
        )
        row.setStyle(TableStyle([
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ]))
        story.append(KeepTogether(row))

    story.append(PageBreak())


def _render_court_divider(story, st):
    _render_section_divider(
        story,
        st,
        eyebrow="PART 1 OF 2",
        title="FOR THE COURT",
        subtitle="Submit these pages to the clerk when you file.",
        contents=[
            ("Statement of Claim",
             "The official form (mirrors CIV-SC-50). The clerk uses this to open the case and serve the defendant."),
            ("Demand Letter",
             "Mail this first via USPS Certified Mail. Wait 14 days before filing; keep the green-card receipt as Exhibit D."),
            ("Exhibit Index",
             "List of supporting evidence (contract, invoice, emails). Bring the originals to the trial."),
        ],
        accent=GREEN,
        accent_bg=CREAM,
    )


def _render_user_divider(story, st):
    _render_section_divider(
        story,
        st,
        eyebrow="PART 2 OF 2",
        title="FOR YOU",
        subtitle="Reference material — keep these pages. Do not submit to the court.",
        contents=[
            ("How to File",
             "Quick 4-step overview of the filing process — read this first."),
            ("Filing Guide",
             "Borough-specific walkthrough with the courthouse address, filing fees, hours, and what happens after you file."),
        ],
        accent=GOLD,
        accent_bg=GOLD_LIGHT,
    )


# ── How to File (quick steps, lives in the FOR YOU section) ───────────────────

def _render_how_to_file(story, st, facts: CaseFacts):
    """Quick 4-step overview. Was on page 1; now lives in the user-only section."""
    story.append(_section_header("HOW TO FILE", st))
    story.append(Paragraph(
        "Four steps from packet in hand to a trial date. The Filing Guide that follows "
        "has the borough-specific addresses, fees, and timing.",
        st["body"],
    ))
    story.append(Spacer(1, 0.1 * inch))

    steps = [
        ("1", "Send the demand letter first.",
         "Mail it via USPS Certified Mail. Keep the green card receipt — it becomes Exhibit D."),
        ("2", "Wait 14 days.",
         "If unpaid, proceed to the clerk's office with this packet. "
         "Filing fee: $20 for claims ≤ $1,000 · $25 for claims up to $10,000. Bring two copies."),
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
            colWidths=[0.35 * inch, W - 0.35 * inch],
        )
        step_t.setStyle(TableStyle([
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING",   (0, 0), (0, -1), 0),
            ("RIGHTPADDING",  (0, 0), (0, -1), 8),
        ]))
        story.append(KeepTogether(step_t))

    story.append(PageBreak())


# ── Filing guide ───────────────────────────────────────────────────────────────

def _guide_section(story, st, title: str, body_blocks: list):
    """Render a guide section: green heading + a stack of body paragraphs/tables."""
    story.append(_section_header(title, st))
    for block in body_blocks:
        story.append(block)
    story.append(Spacer(1, 0.12 * inch))


def _bullet(text: str, st: dict, indent: float = 0.18) -> Paragraph:
    style = ParagraphStyle(
        "bullet", parent=st["body_left"], leftIndent=indent * inch,
        bulletIndent=0.04 * inch, spaceAfter=3, leading=14,
    )
    return Paragraph(f"•&nbsp;&nbsp;{text}", style)


def _render_filing_guide(story, st, facts: CaseFacts):
    borough = facts.venue.borough or "[borough]"
    court_addr = BOROUGH_COURT_ADDRESS.get(borough, "[verify with the clerk]")
    info = BOROUGH_FILING_INFO.get(borough, {})
    clerk_room = info.get("clerk_room", "Small Claims Clerk's office")
    evening_part = info.get("evening_part", "Verify trial-part hours with the clerk.")
    principal = facts.damages.principal
    fee = "$20.00" if principal <= 1000 else "$25.00"
    def_name = facts.defendant.dos_entity_name or facts.defendant.name or "[defendant]"

    # Banner header for the filing guide
    banner = Table(
        [[Paragraph(f"FILING GUIDE — {borough.upper()} COUNTY", st["doc_title"])]],
        colWidths=[W],
    )
    banner.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), GREEN),
        ("TOPPADDING",    (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
    ]))
    story.append(banner)
    story.append(Spacer(1, 0.18 * inch))

    intro = (
        f"This guide walks you through filing your Statement of Claim against "
        f"<b>{def_name}</b> in NYC Civil Court, Small Claims Part, "
        f"<b>{borough} County</b>. The Statement of Claim, demand letter, and "
        f"exhibits in this packet are the documents you will reference. "
        f"Verify any specifics with the clerk or at "
        f"<a href='{CIVIL_COURT_INFO_URL}'>{CIVIL_COURT_INFO_URL}</a>."
    )
    story.append(Paragraph(intro, st["body"]))
    story.append(Spacer(1, 0.1 * inch))

    # ── Section 1: Before you file ────────────────────────────────────────────
    _guide_section(story, st, "1.  BEFORE YOU FILE — SEND THE DEMAND LETTER", [
        Paragraph(
            "Mail the demand letter (Section 3 of this packet) to the defendant via "
            "<b>USPS Certified Mail with Return Receipt Requested</b>. Keep the green "
            "card and the certified-mail receipt — they prove the defendant received "
            "notice and become Exhibit D at trial.",
            st["body"],
        ),
        Paragraph(
            "Wait <b>14 days</b> from the day the defendant signs for the letter. "
            "If payment does not arrive in that window, proceed to file.",
            st["body"],
        ),
    ])

    # ── Section 2: Where & when ───────────────────────────────────────────────
    where_rows = [
        _info_row("COURT", f"NYC Civil Court — Small Claims Part, {borough} County", st),
        _info_row("ADDRESS", court_addr, st),
        _info_row("CLERK", clerk_room, st),
        _info_row("FILING HOURS", "Daytime: typically 9:00 AM – 4:30 PM, Mon–Fri (confirm with clerk)", st),
        _info_row("EVENING PART", evening_part, st),
        _info_row("FILING FEE", f"{fee} (your principal is {_money(principal)})", st),
        _info_row("PAYMENT", "Cash, money order, or certified check payable to 'Clerk of the Civil Court'. Most courts also accept credit/debit at the cashier.", st),
    ]
    where_t = Table(where_rows, colWidths=[1.3 * inch, 5.2 * inch])
    where_t.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND",    (0, 0), (-1, -1), CREAM),
        ("BOX",           (0, 0), (-1, -1), 0.5, RULE_GREY),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    _guide_section(story, st, "2.  WHERE & WHEN TO FILE", [where_t])

    # ── Section 3: Filling out CIV-SC-50 ──────────────────────────────────────
    _guide_section(story, st, "3.  COMPLETING THE STATEMENT OF CLAIM (CIV-SC-50)", [
        Paragraph(
            "The clerk gives you a blank CIV-SC-50 form. Section 2 of this packet is the "
            "filled-out version you will copy from. Match the fields exactly:",
            st["body"],
        ),
        _bullet("<b>Plaintiff name & address</b> — your full legal name and home/business address.", st),
        _bullet(f"<b>Defendant name</b> — use the exact NY DOS entity name: <b>{def_name}</b>. Do not abbreviate or guess.", st),
        _bullet(
            f"<b>Service-of-process address</b> — the address on file with NY DOS: "
            f"<b>{facts.defendant.service_address or '[from packet cover]'}</b>. "
            f"This is where the clerk mails the summons.",
            st,
        ),
        _bullet("<b>Brief statement of claim</b> — one or two plain-English sentences (e.g., \"Unpaid invoice for design services performed under written contract.\"). The full numbered allegations are in your packet.", st),
        _bullet(f"<b>Amount</b> — enter the <b>principal only</b> ({_money(principal)}). The court calculates statutory interest; do <i>not</i> add it on the form.", st),
        _bullet("<b>Place where claim arose</b> — the borough where the contract was performed, signed, or where the defendant has its principal office. This is the basis for venue stated in your packet.", st),
        Paragraph(
            "<b>If you cannot afford the fee:</b> ask the clerk for a <i>Poor Person's "
            "Order</i> motion (CPLR § 1101). You file an affidavit of indigence and "
            "the fee is waived if granted.",
            st["body"],
        ),
    ])

    # ── Section 4: After filing ───────────────────────────────────────────────
    _guide_section(story, st, "4.  AFTER YOU FILE", [
        _bullet("The clerk assigns an <b>Index Number</b> — write it on every page of your packet.", st),
        _bullet("The clerk mails a <b>Notice of Claim</b> to the defendant by certified mail at the service-of-process address.", st),
        _bullet("If the certified mail is returned undelivered, the clerk will notify you. You may need to re-serve at a different address — call the clerk's office for next steps.", st),
        _bullet("A <b>trial date</b> is typically set within <b>45 days</b>. You will receive the date by mail.", st),
        _bullet("If you need to reschedule, file a written request with the clerk <i>at least 7 days</i> before the trial date.", st),
    ])

    story.append(PageBreak())

    # ── Section 5: Trial day ──────────────────────────────────────────────────
    _guide_section(story, st, "5.  ON YOUR TRIAL DATE", [
        _bullet("Arrive <b>30 minutes early</b>. Bring photo ID, this packet, and the <b>originals</b> of every exhibit (the clerk and judge inspect originals, not copies).", st),
        _bullet("Bring <b>two extra copies</b> of each exhibit — one for the judge, one for the defendant.", st),
        _bullet("Check in with the courtroom clerk. The clerk may offer <b>arbitration</b> (a volunteer attorney decides the case the same day, the decision is final). Trial before a judge takes longer but the decision can be appealed. You choose.", st),
        _bullet("When called, state your case briefly: <i>what was promised, what you delivered, what was not paid, what you are owed.</i> Hand exhibits to the judge in the order they appear in your packet.", st),
        _bullet("Address the judge as <b>\"Your Honor.\"</b> Speak only when asked. Do not interrupt the defendant.", st),
        _bullet("If the defendant <b>does not appear</b>, ask the judge for a <b>default judgment</b>. You still must briefly prove your case.", st),
    ])

    # ── Section 6: After judgment ─────────────────────────────────────────────
    _guide_section(story, st, "6.  IF YOU WIN — COLLECTING THE JUDGMENT", [
        Paragraph(
            "A judgment is not a check. It is a court order saying the defendant owes "
            "you money. If they do not pay voluntarily, you must collect.",
            st["body"],
        ),
        _bullet("Wait <b>30 days</b> after entry of judgment for the appeal window to close.", st),
        _bullet("Send a <b>written demand for payment</b> to the defendant referencing the index number and judgment amount.", st),
        _bullet("If unpaid, serve an <b>Information Subpoena with Restraining Notice</b> on the defendant's bank to freeze the account, or on the defendant directly to compel disclosure of assets.", st),
        _bullet("Hire a <b>NYC Marshal</b> (not the Sheriff) to levy on bank accounts or business receivables. Marshals charge a fee but are paid out of what they collect.", st),
        _bullet("A judgment is enforceable for <b>20 years</b> and accrues interest at 9% per annum until paid.", st),
    ])

    # ── Section 7: Quick checklist ────────────────────────────────────────────
    checklist_rows = [
        [Paragraph("☐", st["caption"]), Paragraph("Demand letter mailed via certified mail (green-card receipt saved)", st["body_left"])],
        [Paragraph("☐", st["caption"]), Paragraph("14 days elapsed since defendant received the letter", st["body_left"])],
        [Paragraph("☐", st["caption"]), Paragraph("Two extra copies of every exhibit printed", st["body_left"])],
        [Paragraph("☐", st["caption"]), Paragraph(f"Filing fee ready: {fee} (cash, money order, or certified check)", st["body_left"])],
        [Paragraph("☐", st["caption"]), Paragraph("Photo ID for the courthouse security check", st["body_left"])],
        [Paragraph("☐", st["caption"]), Paragraph("Index number written on every page after the clerk assigns it", st["body_left"])],
        [Paragraph("☐", st["caption"]), Paragraph("Trial date noted — arrive 30 minutes early", st["body_left"])],
    ]
    cl_t = Table(checklist_rows, colWidths=[0.3 * inch, 6.2 * inch])
    cl_t.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    _guide_section(story, st, "7.  QUICK CHECKLIST", [cl_t])

    # ── Footer disclaimer ─────────────────────────────────────────────────────
    disclaimer = Table(
        [[Paragraph(
            "<b>Reminder:</b> ClaimReady is not a law firm and does not provide legal "
            "advice. This guide reflects standard NYC Small Claims procedure as of the "
            "render date and may not capture every borough-specific quirk or recent "
            "change. When in doubt, call the clerk's office or consult an attorney.",
            st["small"],
        )]],
        colWidths=[W],
    )
    disclaimer.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#F7F7F2")),
        ("BOX",           (0, 0), (-1, -1), 0.5, RULE_GREY),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(Spacer(1, 0.1 * inch))
    story.append(disclaimer)


# ── Public API ─────────────────────────────────────────────────────────────────

def render_packet(facts: CaseFacts, output_path: Optional[Path] = None) -> bytes:
    """Render the full PDF packet. Returns bytes; optionally writes to output_path."""
    dmg = prepare_for_render(facts)
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
        author="ClaimReady",
        subject="NYC Small Claims Court Filing Packet",
    )
    st = _styles()
    story: list = []
    _render_cover(story, st, facts)
    _render_court_divider(story, st)
    _render_claim(story, st, facts)
    _render_demand_letter(story, st, facts, dmg)
    _render_exhibit_index(story, st, facts)
    _render_user_divider(story, st)
    _render_how_to_file(story, st, facts)
    _render_filing_guide(story, st, facts)
    doc.build(story, onFirstPage=page_decorator, onLaterPages=page_decorator)
    data = buf.getvalue()
    if output_path:
        Path(output_path).write_bytes(data)
    return data
