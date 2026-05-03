"""Tests for the CaseFacts Pydantic schema."""

from __future__ import annotations

import pytest

from schema import (
    CaseFacts,
    Contract,
    Damages,
    Defendant,
    Exhibit,
    Party,
    Venue,
)


class TestCaseFactsDefaults:
    def test_empty_casefacts_has_defaults(self):
        facts = CaseFacts()
        assert facts.plaintiff.name == ""
        assert facts.defendant.name == ""
        assert facts.damages.principal == 0.0
        assert facts.exhibits == []
        assert facts.notes == []

    def test_default_interest_rate(self):
        facts = CaseFacts()
        assert facts.damages.interest_rate == 0.09


class TestMissingRequired:
    def test_empty_reports_all_required(self):
        facts = CaseFacts()
        missing = facts.missing_required()
        assert "plaintiff.name" in missing
        assert "plaintiff.address" in missing
        assert "defendant.name" in missing
        assert "defendant.service_address" in missing
        assert "damages.principal" in missing
        assert "contract.scope_of_work" in missing
        assert "breach.date" in missing
        assert "venue.borough" in missing
        assert len(missing) == 8

    def test_fully_populated_reports_none(self, fully_populated_facts):
        missing = fully_populated_facts.missing_required()
        assert missing == []

    def test_partial_population(self):
        facts = CaseFacts.model_validate({
            "plaintiff": {"name": "Jane", "address": "123 Main"},
            "defendant": {"name": "Acme", "service_address": "456 Broad"},
            "damages": {"principal": 1000.0},
            "contract": {"scope_of_work": "Web dev"},
            "breach": {"date": "2024-01-01"},
            "venue": {"borough": "Manhattan"},
        })
        assert facts.missing_required() == []

    def test_zero_principal_is_missing(self):
        facts = CaseFacts(damages=Damages(principal=0.0))
        assert "damages.principal" in facts.missing_required()

    def test_negative_principal_is_missing(self):
        facts = CaseFacts(damages=Damages(principal=-100.0))
        assert "damages.principal" in facts.missing_required()


class TestPydanticValidation:
    def test_venue_borough_literal_accepts_valid(self):
        v = Venue(borough="Manhattan")
        assert v.borough == "Manhattan"

    def test_venue_borough_literal_rejects_invalid(self):
        with pytest.raises(Exception):
            Venue(borough="Hoboken")

    def test_exhibit_requires_all_fields(self):
        with pytest.raises(Exception):
            Exhibit(label="A")  # type: ignore[call-arg]

    def test_exhibit_valid(self):
        ex = Exhibit(label="A", description="Contract", file_ref="contract.pdf")
        assert ex.label == "A"

    def test_defendant_inherits_party_fields(self):
        d = Defendant(name="Acme", dos_entity_name="ACME LLC")
        assert d.name == "Acme"
        assert d.dos_entity_name == "ACME LLC"
        assert d.address == ""

    def test_casefacts_serialization_roundtrip(self, fully_populated_facts):
        data = fully_populated_facts.model_dump(mode="json")
        restored = CaseFacts.model_validate(data)
        assert restored.plaintiff.name == fully_populated_facts.plaintiff.name
        assert restored.damages.principal == fully_populated_facts.damages.principal
        assert len(restored.exhibits) == len(fully_populated_facts.exhibits)
