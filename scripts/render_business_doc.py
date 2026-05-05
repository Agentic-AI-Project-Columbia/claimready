"""Render business_document.pdf via ReportLab.

The .tex file is the canonical source. This script is a fallback renderer
for environments without a LaTeX toolchain (no pdflatex / xelatex / tectonic).
For the camera-ready render, prefer pdflatex business_document.tex or Overleaf;
the visual fidelity of the LaTeX rendering is slightly higher.

Run:
    python scripts/render_business_doc.py

Writes business_document.pdf in the project root.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ── Brand palette (matches business_document.tex) ──────────────────────────
INK = colors.HexColor("#1F2421")
GREEN = colors.HexColor("#355E3B")
RULE_GREY = colors.HexColor("#9C9C92")

SERIF = "Times-Roman"
SERIF_BOLD = "Times-Bold"
SERIF_ITALIC = "Times-Italic"

# 8.5" - 0.5" margins each side
W = 7.5 * inch

base = getSampleStyleSheet()


def _para(name, *, font=SERIF, size=11, leading=14, color=INK,
          align=TA_JUSTIFY, after=4, before=0, indent=0):
    return ParagraphStyle(
        name, parent=base["BodyText"],
        fontName=font, fontSize=size, leading=leading,
        textColor=color, alignment=align,
        spaceAfter=after, spaceBefore=before,
        leftIndent=indent, firstLineIndent=0,
    )


title_style = _para("title", font=SERIF_BOLD, size=18, leading=22,
                    align=TA_LEFT, after=1)
tagline_style = _para("tagline", font=SERIF_BOLD, size=13, leading=16,
                      color=GREEN, align=TA_LEFT, after=3)
body = _para("body", after=4)
body_compact = _para("body_compact", after=2)
sub_body = _para("sub_body", after=4)
small_style = _para("small", size=8.5, leading=11, after=2)
table_cell = _para("tcell", size=10, leading=12.5, align=TA_LEFT, after=0)
table_cell_bold = _para("tcellb", font=SERIF_BOLD, size=10, leading=12.5,
                        align=TA_LEFT, after=0)
table_header = _para("thead", font=SERIF_BOLD, size=10, leading=12.5,
                     color=GREEN, align=TA_LEFT, after=0)


def section_p(lead: str, rest: str) -> Paragraph:
    """Bold inline lead + justified body."""
    return Paragraph(
        f'<font name="{SERIF_BOLD}">{lead}</font> {rest}',
        body,
    )


def sub_section_p(lead: str, rest: str) -> Paragraph:
    """Italic inline lead (used for sub-sections under Economics)."""
    return Paragraph(
        f'<font name="{SERIF_ITALIC}">{lead}</font> {rest}',
        body,
    )


# ── Content (mirrors business_document.tex) ────────────────────────────────

story: list = []

story.append(Paragraph("ClaimReady: Small Claims, Filed Right", title_style))
story.append(HRFlowable(width="100%", thickness=1.0, color=GREEN,
                        spaceBefore=0, spaceAfter=2))
story.append(Paragraph(
    "For the invoice too small for a lawyer and too large to write off.",
    tagline_style,
))
story.append(Paragraph(
    "ClaimReady helps NYC freelancers turn messy contracts, invoices, "
    "emails, and screenshots into a court-ready small-claims packet for "
    "unpaid service work.",
    body,
))
story.append(HRFlowable(width="100%", thickness=0.35, color=GREEN,
                        spaceBefore=2, spaceAfter=5))

story.append(section_p(
    "The user.",
    "The concrete user is a New York City freelancer or solo service "
    "provider owed $1,000–$10,000 by a NY-registered LLC or corporation: a "
    "designer, developer, photographer, writer, tutor, consultant, or "
    "marketer with a contract, invoice, emails, screenshots, or notes "
    "showing completed work and nonpayment. This is not a niche edge case. "
    "Upwork estimates that 64 million Americans freelanced in 2023, or 38% "
    "of the U.S. workforce. A New York freelancer survey found that 62% "
    "experienced nonpayment; among those who lost income, 51% lost more "
    "than $1,000 and 22% lost more than $5,000.",
))

story.append(section_p(
    "The problem.",
    "Today, the user sends awkward follow-up emails, copies a generic "
    "demand-letter template, gives up, or tries to file in small claims "
    "alone. Hiring counsel rarely makes sense: Clio reports the average "
    "New York lawyer hourly rate at $426, which can consume the economics "
    "of a $2,000–$5,000 claim. Small claims is designed for this gap, but "
    "filing still requires the user to identify the correct legal "
    "defendant, find a service address, choose venue, organize exhibits, "
    "calculate damages, and create forms the clerk can process. NYC Small "
    "Claims allows claims up to $10,000 with only a $15–$20 filing fee, "
    "but the paperwork and confidence gap stop many people before they "
    "start.",
))

story.append(section_p(
    "The economics.",
    "For one user-month, assume one case packet: about 120k input tokens "
    "for intake, evidence, retrieval, and tool context, plus 15k output "
    "tokens for extracted facts, agent outputs, and final drafting. With "
    "Gemini 2.5 Flash pricing around $0.30 per 1M input tokens and $2.50 "
    "per 1M output tokens, model cost is about $0.07 per case. Cloud Run, "
    "storage, PDF generation, logs, failed runs, payment fees, and light "
    "support add an estimated $3–$5 of variable cost; the model is not "
    "the cost driver — infrastructure and Stripe fees are.",
))

story.append(sub_section_p(
    "Pricing ladder.",
    f'ClaimReady charges $29 per packet at launch and layers in revenue '
    f'capture as volume justifies the operational lift. '
    f'<font name="{SERIF_BOLD}">Phase 1</font> is flat $29 to validate '
    f'willingness-to-pay and accumulate the first thousand cases of '
    f'testimonials and defendant patterns; the asymmetry it accepts is real '
    f'(a $1,000 claim pays a 2.9% rate while a $10,000 claim pays only '
    f'0.3%), but a single price keeps the funnel simple while the product '
    f'earns trust. <font name="{SERIF_BOLD}">Phase 2</font> adds '
    f'<font name="{SERIF_BOLD}">1–2% of the claim value at filing</font> '
    f'on top of the $29 base, charged upfront rather than as a contingency '
    f'on recovery so there is no collection risk and no '
    f'unauthorized-practice-of-law framing issue; the trigger is roughly '
    f'500 cases/month sustained, by which point Stripe metering and '
    f'value-based capture are worth the engineering work. '
    f'<font name="{SERIF_BOLD}">Phase 3</font> is B2B distribution: '
    f'ClaimReady\'s engine white-labeled inside freelancer-facing '
    f'platforms — Upwork, Fiverr, FreshBooks, QuickBooks Self-Employed — '
    f'at a $10–$15 wholesale price, with the partner paying acquisition '
    f'and capturing the freelancer-retention benefit, unlocked once '
    f'consumer-channel CAC and packet-quality metrics are proven.',
))

# ── Pricing-ladder table ───────────────────────────────────────────────────
def tc(text, bold=False):
    return Paragraph(text, table_cell_bold if bold else table_cell)


table_rows = [
    [Paragraph("Item", table_header),
     Paragraph("Phase 1 (Launch)", table_header),
     Paragraph("Phase 2 (Scale)", table_header),
     Paragraph("Phase 3 (Distribution)", table_header)],
    [tc("Price", bold=True),
     tc("$29 / packet"),
     tc("$29 + 1.5% of claim value"),
     tc("$10–$15 wholesale")],
    [tc("Avg revenue / case", bold=True),
     tc("$29"),
     tc("~$81 (avg claim $3.5k)"),
     tc("~$12")],
    [tc("Variable cost", bold=True),
     tc("$3–$5"),
     tc("$3–$5"),
     tc("$3–$5")],
    [tc("Contribution / case", bold=True),
     tc("~$25 (~85%)"),
     tc("~$76 (~94%)"),
     tc("~$8 (~67%)")],
    [tc("CAC payback", bold=True),
     tc("&lt;1.5× / case"),
     tc("~3× / case"),
     tc("Partner-paid CAC")],
]
econ_table = Table(
    table_rows,
    colWidths=[1.42 * inch, 1.55 * inch, 1.85 * inch, 1.85 * inch],
)
econ_table.setStyle(TableStyle([
    ("LINEABOVE",     (0, 0), (-1, 0), 1.0, INK),     # toprule
    ("LINEBELOW",     (0, 0), (-1, 0), 0.5, INK),     # midrule
    ("LINEBELOW",     (0, -1), (-1, -1), 1.0, INK),   # bottomrule
    ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ("LEFTPADDING",   (0, 0), (-1, -1), 4),
    ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
    ("TOPPADDING",    (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
]))
story.append(Spacer(1, 2))
story.append(econ_table)
story.append(Spacer(1, 4))

story.append(sub_section_p(
    "CAC and payback.",
    "Blended CAC at launch is estimated at $15–$30: SEO on the \"how do I "
    "sue an LLC in NY\" long-tail with borough-specific landing pages, "
    "presence in r/freelance and freelancer Twitter, and partnerships with "
    "coworking spaces and small-business accountants. That gives "
    "contribution-margin payback of under 1.5× per case at the $29 flat "
    "price and roughly 3× per case once Phase 2 take-rate pricing is live. "
    "Per-case payback matters more than LTV here — small claims is "
    "fundamentally episodic, and a business that pays back every "
    "transaction does not depend on retention assumptions to be solvent.",
))

story.append(sub_section_p(
    "Breakeven and margin risks.",
    "Fixed monthly burn at launch is roughly $8–$12k (Cloud Run minimums, "
    "Vertex AI baseline, part-time-equivalent founder time), so breakeven "
    "sits near 400 cases/month at flat $29 and roughly 150 cases/month "
    "once Phase 2 is live — the take-rate transition is what makes the "
    "business compound rather than just survive. The margin killers are "
    "concentrated and known: huge evidence sets that explode token cost "
    "beyond the $0.07 baseline, refund and chargeback exposure if packet "
    "quality slips, Stripe fees of about 4% on a $29 ticket, high-touch "
    "support when service-of-process bounces, and jurisdiction-expansion "
    "engineering when the wedge moves outside NYC.",
))

story.append(section_p(
    "Why these technical choices.",
    "The agent design mirrors the real filing workflow. The Next.js "
    "wizard collects only the facts the court needs, reducing user "
    "confusion. The Extractor reads messy contracts, invoices, emails, "
    "and screenshots so users do not have to translate evidence into "
    "legal structure. The DefendantResolver calls the NY Department of "
    "State dataset because suing the wrong entity or using the wrong "
    "service address can sink the case. The JurisdictionChecker uses "
    "deterministic tools and a small Chroma RAG corpus to validate the "
    "$10,000 cap, statute-of-limitations fit, venue, and citations "
    "without expensive broad research. Structured Pydantic outputs make "
    "the PDF renderer reliable. Gemini 2.5 Flash is the right model "
    "because it supports multimodal, long-context evidence review while "
    "keeping per-case token cost far below the $29 price.",
))

story.append(section_p(
    "Risks and mitigations.",
    f'<font name="{SERIF_ITALIC}">Bar and UPL risk:</font> ClaimReady is '
    f'positioned as form preparation and educational guidance, not legal '
    f'advice; every output carries an explicit disclaimer, and complex '
    f'cases are flagged for attorney review rather than handled. '
    f'<font name="{SERIF_ITALIC}">Data dependency:</font> the NY DOS '
    f'Active Corporations API is single-source for defendant resolution '
    f'today, mitigated by response caching, manual-entry fallback with '
    f'verification, and a per-state plug architecture so expansion states '
    f'can use their own registries. '
    f'<font name="{SERIF_ITALIC}">Model and quality risk:</font> '
    f'structured Pydantic outputs and deterministic tools for jurisdiction '
    f'and damages bound the LLM\'s surface area, RAG citations make legal '
    f'claims auditable, and a packet-review checkpoint keeps the human in '
    f'the loop before filing. '
    f'<font name="{SERIF_ITALIC}">Refund and chargeback risk:</font> a '
    f'"court-ready or your money back" guarantee is feasible because '
    f'failure modes are concrete and observable, and the $29 ticket caps '
    f'fraud exposure relative to the trust-signal benefit.',
))

story.append(Paragraph(
    f'<font name="{SERIF_BOLD}">Go-to-market.</font> Three channels at launch '
    f'with a partnership path layered on top.<br/>'
    f'<font name="{SERIF_BOLD}">1.</font> SEO on the "how do I sue an LLC in NY" '
    f'long-tail, with borough-specific landing pages and anonymized case-study posts.<br/>'
    f'<font name="{SERIF_BOLD}">2.</font> Community presence in r/freelance, '
    f'r/personalfinance, freelancer Twitter, and the Freelancers Union mailing list.<br/>'
    f'<font name="{SERIF_BOLD}">3.</font> Local partnerships with coworking spaces, '
    f'small-business accountants, and freelance-friendly co-ops, where ClaimReady '
    f'is offered at a member-benefit discount.<br/>'
    f'<font name="{SERIF_BOLD}">4.</font> The Phase 3 path: B2B distribution inside '
    f'freelancer-facing platforms where the partner pays acquisition and ClaimReady '
    f'captures the engine economics — unlocked once consumer-channel CAC and '
    f'packet-quality metrics are proven.',
    body,
))

story.append(section_p(
    "MVP and wedge.",
    "The product as scoped is an MVP: NYC small-claims, unpaid-invoice "
    "disputes against NY-registered entities. That narrowness is the "
    "whole point. Winning one workflow gives ClaimReady real users, real "
    "packet data, real defendant patterns, and a defensible filing "
    "engine, all of which generalize. From there, expansion follows two "
    "axes. First, claim types: security-deposit recovery, breach of "
    "consumer-services contract, unreturned property, and small-business "
    "vendor disputes share the same intake-extract-validate-render "
    "skeleton and only require new templates and rule modules. Second, "
    "jurisdictions: every U.S. small-claims court has its own cap, venue "
    "rules, forms, and entity registry, but the agent architecture, "
    "JurisdictionChecker, and DefendantResolver swap cleanly per state. "
    "NYC is the wedge because it has the highest density of freelancers, "
    "a generous $10,000 cap, and a public DOS entity dataset; once the "
    "unit economics are proven there, the same engine extends to CA, TX, "
    "IL, and FL with incremental rule work rather than a rewrite.",
))

story.append(section_p(
    "Close.",
    "ClaimReady wins by being deliberately small at launch: not \"AI "
    "lawyer for everything,\" but a cheap, focused filing assistant for "
    "one painful, common, economically underserved workflow, designed "
    "from day one as the wedge for a broader civil-claims platform.",
))

# ── Sources ─────────────────────────────────────────────────────────────────
def link(text: str, url: str) -> str:
    return (f'<a href="{url}"><font color="#355E3B">'
            f'<u>{text}</u></font></a>')


sources_para = (
    f'Sources: {link("Upwork Freelance Forward 2023", "https://www.upwork.com/press/releases/upwork-study-finds-64-million-americans-freelanced-in-2023-adding-1-27-trillion-to-u-s-economy")}; '
    f'{link("NY freelancer nonpayment survey", "https://nwu.org/survey-shows-that-62-of-ny-freelancers-experience-non-payment-need-freelance-isnt-free-law-statewide/")}; '
    f'{link("NYC Small Claims filing instructions", "https://nycourts.gov/courts/nyc/smallclaims/forms/instructionsforfiling.pdf")}; '
    f'{link("Clio NY lawyer rates", "https://www.clio.com/resources/legal-trends/compare-lawyer-rates/ny/")}; '
    f'{link("Google Vertex AI pricing", "https://cloud.google.com/vertex-ai/generative-ai/pricing")}.'
)
story.append(Spacer(1, 4))
story.append(Paragraph(sources_para, small_style))


# ── Build ───────────────────────────────────────────────────────────────────
def main():
    out = Path(__file__).resolve().parent.parent / "business_document.pdf"
    doc = SimpleDocTemplate(
        str(out),
        pagesize=LETTER,
        leftMargin=0.5 * inch,
        rightMargin=0.5 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
        title="ClaimReady — Business Document",
        author="Arjun Varma & Oranich Jamkachornkiat",
    )
    doc.build(story)
    print(f"Wrote {out} ({out.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
