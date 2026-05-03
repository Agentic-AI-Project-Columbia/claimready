"""Shared fixtures for backend tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from schema import CaseFacts


@pytest.fixture()
def fully_populated_facts() -> CaseFacts:
    """Build a fully populated CaseFacts via model_validate to avoid the
    Breach.date field-name shadowing the date type in Pydantic v2."""
    return CaseFacts.model_validate({
        "plaintiff": {
            "name": "Jane Doe",
            "address": "123 Main St",
            "city": "New York",
            "state": "NY",
            "zip_code": "10001",
            "phone": "212-555-0100",
            "email": "jane@example.com",
        },
        "defendant": {
            "name": "Acme LLC",
            "address": "456 Broadway",
            "city": "New York",
            "state": "NY",
            "zip_code": "10002",
            "dos_entity_name": "ACME SERVICES LLC",
            "dos_id": "1234567",
            "service_address": "456 Broadway, New York, NY 10002",
            "registered_agent": "John Smith",
            "entity_status": "Active",
        },
        "contract": {
            "date_formed": "2024-01-15",
            "scope_of_work": "Web development services",
            "agreed_amount": 4800.00,
            "payment_terms": "Net 30",
        },
        "performance": {
            "delivered_on": "2024-03-01",
            "deliverables": ["Website", "Admin panel"],
        },
        "breach": {
            "date": "2024-04-01",
            "nature": "non-payment",
            "amount_owed": 4800.00,
        },
        "damages": {
            "principal": 4800.00,
            "interest_from": "2024-04-01",
            "interest_rate": 0.09,
            "total_demanded": 5100.00,
        },
        "venue": {
            "borough": "Manhattan",
            "basis": "Defendant's principal office is in Manhattan",
        },
        "exhibits": [
            {"label": "A", "description": "Signed contract", "file_ref": "contract.pdf"},
            {"label": "B", "description": "Invoice #1001", "file_ref": "invoice.pdf"},
        ],
        "jurisdiction_check": {
            "in_monetary_limit": True,
            "within_statute_of_limitations": True,
            "venue_proper": True,
            "citations": ["NYC Civil Court Act § 1805"],
        },
    })
