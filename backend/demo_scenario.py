"""Bundled demo scenario for the one-click grader path.

A realistic NYC freelancer-vs-LLC unpaid-invoice case. The intake fields
match the wizard, and the evidence is a small bundle of text extracts
that exercises every agent in the pipeline:

  - Extractor    sees 4 distinct evidence pieces (contract, invoice,
                 emails, demand-letter follow-up) and pulls scope, dates,
                 and amounts.
  - Defendant    looks up the LLC against the NY DOS SODA dataset.
  - Jurisdiction validates the $4,800 claim against the $10k cap and the
                 6-year SOL, then computes statutory 9% interest.
  - Drafter      renders the PDF packet.
"""

from __future__ import annotations

from typing import Any, Dict, List

DEMO_TITLE = "Freelance designer vs. NYC marketing LLC — $4,800 unpaid"
DEMO_BLURB = (
    "Jane Q. Doe is a Brooklyn-based graphic designer who completed a full "
    "illustration package for Vanguard Marketing LLC's Spring 2025 product launch. "
    "She delivered every file on time on March 1, 2025. The client's own "
    "operations manager emailed to confirm receipt and said it looked great. "
    "Then — nothing. The Net-30 invoice came due on March 31, 2025 and was "
    "never paid. Two follow-up emails and two phone calls later, the client "
    "stopped responding entirely. Jane has four pieces of evidence: a signed "
    "services agreement, the invoice, the email thread showing delivery "
    "confirmation and subsequent silence, and her own dated notes from the "
    "phone calls. Total owed: $4,800."
)

DEMO_INTAKE: Dict[str, Any] = {
    "plaintiff": {
        "name": "Jane Q. Doe",
        "address": "123 Smith Street",
        "city": "Brooklyn",
        "state": "NY",
        "zip_code": "11201",
        "phone": "(718) 555-0100",
        "email": "jane@janedoedesign.example",
    },
    "defendant": {
        "name": "Vanguard Marketing LLC",
        "address": "",
        "city": "",
        "state": "NY",
        "zip_code": "",
        "phone": "",
        "email": "",
    },
    "contract": {
        "date_formed": "2025-01-15",
        "scope_of_work": (
            "Twelve (12) original illustrations and a one-page brand-color "
            "guideline for Vanguard Marketing LLC's Spring 2025 product launch, "
            "delivered as print-ready PDF + editable AI files."
        ),
        "agreed_amount": 4800.0,
        "payment_terms": "Net 30 from delivery.",
    },
    "performance": {
        "delivered_on": "2025-03-01",
        "deliverables": [
            "12 illustrations (PDF + AI)",
            "1 brand-color guideline (PDF)",
        ],
    },
    "breach": {
        "date": "2025-03-31",
        "nature": "non-payment",
        "amount_owed": 4800.0,
    },
    "venue": {
        "borough": "Brooklyn",
        "basis": (
            "Defendant's principal place of business is in Brooklyn, "
            "and the parties' agreement was performed there."
        ),
    },
}

DEMO_EVIDENCE: List[Dict[str, str]] = [
    {
        "filename": "01_services_agreement.txt",
        "mime_type": "text/plain",
        "text": (
            "══════════════════════════════════════════════════\n"
            "              FREELANCE SERVICES AGREEMENT\n"
            "══════════════════════════════════════════════════\n"
            "Agreement date:  January 15, 2025\n"
            "Designer:        Jane Q. Doe\n"
            "                 123 Smith Street, Brooklyn, NY 11201\n"
            "                 jane@janedoedesign.example\n"
            "Client:          Vanguard Marketing LLC\n"
            "                 a New York limited liability company\n"
            "                 (Derek Chan, Operations Manager, signing on behalf)\n"
            "──────────────────────────────────────────────────\n\n"
            "1. SCOPE OF WORK\n"
            "   Designer agrees to create and deliver:\n"
            "     • Twelve (12) original illustrations for the Spring 2025\n"
            "       product-launch campaign\n"
            "     • One (1) brand-color guideline (one page, print-ready PDF)\n"
            "   All deliverables shall be provided as print-ready PDF files\n"
            "   together with fully editable Adobe Illustrator (.ai) source files.\n\n"
            "2. CONTRACT PRICE\n"
            "   Client shall pay Designer a flat fee of:\n"
            "       FOUR THOUSAND EIGHT HUNDRED DOLLARS ($4,800.00 USD)\n"
            "   No additional fees apply unless Client requests out-of-scope revisions\n"
            "   in writing.\n\n"
            "3. PAYMENT TERMS\n"
            "   Full payment is due within thirty (30) days of delivery of the\n"
            "   final files (Net 30). Designer will issue an invoice on the\n"
            "   delivery date. Payment may be made by ACH transfer or by check\n"
            "   payable to 'Jane Q. Doe'.\n\n"
            "4. DELIVERY DEADLINE\n"
            "   Designer will deliver the completed files via email no later than\n"
            "   March 1, 2025. Late delivery caused by Client-side delays (e.g.,\n"
            "   late feedback) will extend this deadline day-for-day.\n\n"
            "5. INTELLECTUAL PROPERTY\n"
            "   Upon receipt of full payment, Designer assigns all rights in the\n"
            "   deliverables to Client. Prior to full payment, Designer retains\n"
            "   all ownership.\n\n"
            "6. GOVERNING LAW\n"
            "   This Agreement is governed by the laws of the State of New York.\n"
            "   Any dispute shall be resolved in a court of competent jurisdiction\n"
            "   in Kings County (Brooklyn), New York.\n\n"
            "──────────────────────────────────────────────────\n"
            "SIGNATURES\n\n"
            "/s/ Jane Q. Doe                    Date: January 15, 2025\n"
            "Jane Q. Doe, Designer\n\n"
            "/s/ D. Chan                        Date: January 15, 2025\n"
            "Derek Chan, Operations Manager\n"
            "on behalf of Vanguard Marketing LLC\n"
            "══════════════════════════════════════════════════\n"
        ),
    },
    {
        "filename": "02_invoice_2025_001.txt",
        "mime_type": "text/plain",
        "text": (
            "══════════════════════════════════════════════════\n"
            "                    INVOICE\n"
            "══════════════════════════════════════════════════\n"
            "Invoice #:   2025-001\n"
            "Issued:      March 1, 2025\n"
            "Due date:    March 31, 2025  (Net 30)\n\n"
            "FROM\n"
            "  Jane Q. Doe Design\n"
            "  123 Smith Street\n"
            "  Brooklyn, NY 11201\n"
            "  jane@janedoedesign.example\n"
            "  (718) 555-0100\n\n"
            "BILL TO\n"
            "  Vanguard Marketing LLC — Accounts Payable\n"
            "  Attn: Derek Chan, Operations Manager\n"
            "  dchan@vanguardmarketing.example\n\n"
            "──────────────────────────────────────────────────\n"
            "  QTY  DESCRIPTION                              AMOUNT\n"
            "──────────────────────────────────────────────────\n"
            "   12  Original illustrations                $3,600.00\n"
            "        (Spring 2025 product-launch campaign)\n"
            "        Delivered: March 1, 2025\n\n"
            "    1  Brand-color guideline (1-page PDF)      $600.00\n"
            "        Delivered: March 1, 2025\n\n"
            "    1  Source files — Adobe Illustrator (.ai)  $600.00\n"
            "        (editable originals, all 12 illustrations)\n"
            "──────────────────────────────────────────────────\n"
            "                               TOTAL DUE:   $4,800.00\n"
            "══════════════════════════════════════════════════\n\n"
            "Payment instructions\n"
            "  ACH:   Routing 021000021 · Account 987654321\n"
            "  Check: Payable to 'Jane Q. Doe', mail to address above\n\n"
            "Please reference Invoice #2025-001 with your payment.\n"
            "Questions? Email jane@janedoedesign.example or call (718) 555-0100.\n"
            "══════════════════════════════════════════════════\n"
        ),
    },
    {
        "filename": "03_email_thread.eml",
        "mime_type": "message/rfc822",
        "text": (
            "====== MESSAGE 1 OF 5 — Delivery confirmation ======\n"
            "From:    Jane Q. Doe <jane@janedoedesign.example>\n"
            "To:      Derek Chan <dchan@vanguardmarketing.example>\n"
            "Date:    Saturday, March 1, 2025  11:47 AM\n"
            "Subject: Spring launch — final files delivered + Invoice #2025-001\n\n"
            "Hi Derek,\n\n"
            "All done! Attached you'll find:\n"
            "  • 12_illustrations_final.pdf  — print-ready, CMYK, 300 dpi\n"
            "  • 12_illustrations_final.ai   — fully editable Illustrator source\n"
            "  • brand_color_guide.pdf        — one-page guideline\n\n"
            "I've also attached Invoice #2025-001 for $4,800.00, due March 31\n"
            "(Net 30 as per our agreement).\n\n"
            "It was a pleasure working on this project. Let me know if you need\n"
            "any tweaks before your launch.\n\n"
            "Best,\n"
            "Jane\n\n\n"
            "====== MESSAGE 2 OF 5 — Client confirms receipt ======\n"
            "From:    Derek Chan <dchan@vanguardmarketing.example>\n"
            "To:      Jane Q. Doe <jane@janedoedesign.example>\n"
            "Date:    Monday, March 3, 2025  10:14 AM\n"
            "Subject: Re: Spring launch — final files delivered + Invoice #2025-001\n\n"
            "Jane —\n\n"
            "Got everything, thanks. The illustrations look fantastic — exactly\n"
            "what we needed for the launch. Forwarding the invoice to accounting\n"
            "today so you should be all set.\n\n"
            "— Derek\n\n\n"
            "====== MESSAGE 3 OF 5 — First payment reminder (day after due date) ======\n"
            "From:    Jane Q. Doe <jane@janedoedesign.example>\n"
            "To:      Derek Chan <dchan@vanguardmarketing.example>\n"
            "Date:    Tuesday, April 1, 2025  9:02 AM\n"
            "Subject: Invoice #2025-001 — payment due yesterday\n\n"
            "Hi Derek,\n\n"
            "Just a friendly nudge — Invoice #2025-001 for $4,800.00 had a\n"
            "due date of March 31 (Net 30) and it looks like it's still\n"
            "outstanding.\n\n"
            "Could you check with accounting and let me know an expected\n"
            "payment date? Happy to resend the invoice if that helps.\n\n"
            "Thanks,\n"
            "Jane\n\n\n"
            "====== MESSAGE 4 OF 5 — No reply; second follow-up ======\n"
            "From:    Jane Q. Doe <jane@janedoedesign.example>\n"
            "To:      Derek Chan <dchan@vanguardmarketing.example>\n"
            "Date:    Monday, April 14, 2025  11:30 AM\n"
            "Subject: Re: Invoice #2025-001 — now 14 days overdue\n\n"
            "Derek,\n\n"
            "Following up again. It has now been two weeks since the due date\n"
            "and I haven't received a response to my April 1 email. The invoice\n"
            "total of $4,800.00 remains unpaid.\n\n"
            "Please respond by Friday, April 18 with a payment date. If I don't\n"
            "hear back I'll need to pursue other options to collect what's owed.\n\n"
            "Jane Doe\n\n\n"
            "====== MESSAGE 5 OF 5 — Final email; no response ever received ======\n"
            "From:    Jane Q. Doe <jane@janedoedesign.example>\n"
            "To:      Derek Chan <dchan@vanguardmarketing.example>\n"
            "Date:    Monday, April 21, 2025  2:15 PM\n"
            "Subject: Re: Invoice #2025-001 — final notice before formal demand\n\n"
            "Derek,\n\n"
            "I have not received any reply to my previous two emails or any\n"
            "payment toward Invoice #2025-001 ($4,800.00, due March 31, 2025).\n\n"
            "This is my final notice. If full payment is not received by\n"
            "April 30, 2025, I will send a formal demand letter and file a\n"
            "claim in NYC Civil Court Small Claims Part for the full amount\n"
            "plus statutory interest.\n\n"
            "Jane Q. Doe\n"
            "jane@janedoedesign.example  |  (718) 555-0100\n"
        ),
    },
    {
        "filename": "04_followup_note.txt",
        "mime_type": "text/plain",
        "text": (
            "══════════════════════════════════════════════════\n"
            "  PERSONAL LOG — Vanguard Marketing LLC / Invoice #2025-001\n"
            "══════════════════════════════════════════════════\n\n"
            "April 14, 2025 — Tried Derek's direct line at (212) 555-0200.\n"
            "  Rang 4x, went to voicemail. Left a message asking him to call\n"
            "  back re: outstanding invoice. No return call.\n\n"
            "April 17, 2025 — Called Vanguard Marketing main line at (212) 555-0134.\n"
            "  Receptionist said 'someone from accounting will get back to you\n"
            "  within 24 hours.' As of April 22, no one has called.\n\n"
            "April 21, 2025 — Sent final email warning of small-claims filing\n"
            "  (see email thread, Message 5). Read receipt never returned.\n\n"
            "April 22, 2025 — Invoice is now 22 days overdue. Total owed:\n"
            "  $4,800.00. Client has confirmed receipt of all deliverables\n"
            "  in writing (see Derek's March 3 email) but has stopped\n"
            "  responding entirely.\n\n"
            "  Next step: send certified demand letter, then file in\n"
            "  Kings County (Brooklyn) Civil Court Small Claims Part.\n"
            "  Monetary claim ($4,800) is within the $10,000 NYC cap.\n"
            "  Breach date March 31, 2025 — well within the 6-year SOL\n"
            "  under CPLR § 213(2).\n"
            "══════════════════════════════════════════════════\n"
        ),
    },
]


def build_demo_intake() -> Dict[str, Any]:
    """Return the demo intake with the bundled evidence inlined under `evidence`."""
    intake = {**DEMO_INTAKE, "evidence": DEMO_EVIDENCE}
    return intake
