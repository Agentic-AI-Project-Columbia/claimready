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
    "Jane Doe, a Brooklyn-based graphic designer, completed a 12-illustration "
    "package for Acme Widgets LLC. Net-30 payment came due on March 31, 2025 "
    "and was never paid. She has the signed agreement, an invoice, and the "
    "email thread where the client confirmed receipt and then went silent."
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
        "name": "Acme Widgets LLC",
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
            "guideline for Acme Widgets LLC's Spring 2025 product launch, "
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
            "SERVICES AGREEMENT\n"
            "Date: January 15, 2025\n\n"
            "This Agreement is entered into between Jane Q. Doe (the \"Designer\") "
            "and Acme Widgets LLC, a New York limited liability company (the \"Client\").\n\n"
            "1. SCOPE. Designer will produce twelve (12) original illustrations and "
            "a one-page brand-color guideline for Client's Spring 2025 product launch.\n\n"
            "2. PRICE. Client shall pay Designer the sum of Four Thousand Eight Hundred "
            "Dollars ($4,800.00) for the work described above.\n\n"
            "3. PAYMENT TERMS. Net 30 from delivery of the final files.\n\n"
            "4. DELIVERY. Designer will deliver final files via email no later than "
            "March 1, 2025.\n\n"
            "Signed: Jane Q. Doe (Designer)\n"
            "Signed: M. Patel, Operations Manager (Client, on behalf of Acme Widgets LLC)\n"
        ),
    },
    {
        "filename": "02_invoice_2025_001.txt",
        "mime_type": "text/plain",
        "text": (
            "INVOICE #2025-001\n"
            "From: Jane Q. Doe Design — 123 Smith St, Brooklyn NY 11201\n"
            "Bill to: Acme Widgets LLC — Accounts Payable\n"
            "Issued: March 1, 2025\n"
            "Due: March 31, 2025 (Net 30)\n\n"
            "Description: Spring 2025 launch — 12 illustrations + brand guideline\n"
            "Amount: $4,800.00\n"
            "Total due: $4,800.00\n\n"
            "Remit by ACH or check payable to Jane Q. Doe.\n"
        ),
    },
    {
        "filename": "03_email_thread.eml",
        "mime_type": "message/rfc822",
        "text": (
            "From: M. Patel <mpatel@acmewidgets.example>\n"
            "To: Jane Q. Doe <jane@janedoedesign.example>\n"
            "Date: Mon, 03 Mar 2025 10:14:00 -0500\n"
            "Subject: Re: Spring launch — final files\n\n"
            "Jane — got everything, thanks. These look great. Forwarding to "
            "accounting today.\n— Mihir\n\n"
            "----------\n"
            "From: Jane Q. Doe <jane@janedoedesign.example>\n"
            "To: M. Patel <mpatel@acmewidgets.example>\n"
            "Date: Tue, 01 Apr 2025 09:02:00 -0400\n"
            "Subject: Invoice #2025-001 past due\n\n"
            "Hi Mihir — just a friendly nudge that #2025-001 (Net 30) was "
            "due yesterday. Could you check with accounting?\n— Jane\n\n"
            "----------\n"
            "From: Jane Q. Doe <jane@janedoedesign.example>\n"
            "To: M. Patel <mpatel@acmewidgets.example>\n"
            "Date: Mon, 14 Apr 2025 11:30:00 -0400\n"
            "Subject: Re: Invoice #2025-001 past due\n\n"
            "Following up again on this. It's been two weeks. Please let me "
            "know when I can expect payment of the $4,800 owed.\n— Jane\n"
        ),
    },
    {
        "filename": "04_followup_note.txt",
        "mime_type": "text/plain",
        "text": (
            "Personal note — April 22, 2025.\n\n"
            "Phone call with Mihir's voicemail. No reply. Phone call with "
            "main Acme line — receptionist said \"someone will get back to you\". "
            "Nobody did. As of today the invoice is 22 days past due and the "
            "client has stopped responding. Time to send a formal demand and "
            "prepare to file in Kings County Civil Court Small Claims Part.\n"
        ),
    },
]


def build_demo_intake() -> Dict[str, Any]:
    """Return the demo intake with the bundled evidence inlined under `evidence`."""
    intake = {**DEMO_INTAKE, "evidence": DEMO_EVIDENCE}
    return intake
