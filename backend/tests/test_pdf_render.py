"""Tests for PDF rendering."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

import fitz
import pytest

from schema import CaseFacts, Damages
from tools.pdf_render import prepare_for_render, render_packet


def _extract_text(pdf_bytes: bytes) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = "".join(page.get_text() for page in doc)
    doc.close()
    return text


class TestRenderPacket:
    def test_returns_valid_pdf_bytes(self, fully_populated_facts):
        data = render_packet(fully_populated_facts)
        assert isinstance(data, bytes)
        assert data[:5] == b"%PDF-"
        assert len(data) > 1000

    def test_writes_to_output_path(self, fully_populated_facts):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            path = Path(f.name)
        try:
            data = render_packet(fully_populated_facts, output_path=path)
            assert path.exists()
            assert path.read_bytes() == data
        finally:
            path.unlink(missing_ok=True)

    def test_minimal_facts_raises_on_zero_principal(self):
        with pytest.raises(ValueError, match="damages.principal"):
            render_packet(CaseFacts())

    def test_facts_with_no_exhibits(self, fully_populated_facts):
        fully_populated_facts.exhibits = []
        data = render_packet(fully_populated_facts)
        assert data[:5] == b"%PDF-"

    def test_facts_with_jurisdiction_issues(self, fully_populated_facts):
        fully_populated_facts.jurisdiction_check.issues = [
            "Amount exceeds cap",
            "Breach beyond SOL",
        ]
        data = render_packet(fully_populated_facts)
        assert data[:5] == b"%PDF-"
        assert len(data) > 1000


class TestPrepareForRender:
    def test_rejects_zero_principal(self):
        facts = CaseFacts()
        with pytest.raises(ValueError, match="damages.principal"):
            prepare_for_render(facts)

    def test_rejects_missing_plaintiff(self):
        facts = CaseFacts(damages=Damages(principal=1000.0))
        with pytest.raises(ValueError, match="plaintiff.name"):
            prepare_for_render(facts)

    def test_rejects_missing_defendant(self):
        facts = CaseFacts(
            damages=Damages(principal=1000.0),
            plaintiff={"name": "Jane Doe"},
        )
        with pytest.raises(ValueError, match="defendant name"):
            prepare_for_render(facts)


class TestPdfContent:
    def test_no_bracket_placeholders(self, fully_populated_facts):
        data = render_packet(fully_populated_facts)
        text = _extract_text(data)
        brackets = re.findall(r"\[[^\]]+\]", text)
        allowed = [b for b in brackets if not b.startswith("[Exhibit")]
        assert allowed == [], f"Found bracket placeholders: {allowed}"

    def test_no_zero_dollar_amounts(self, fully_populated_facts):
        data = render_packet(fully_populated_facts)
        text = _extract_text(data)
        zeros = [m for m in re.findall(r"\$0\.00", text)]
        assert zeros == [], "Found $0.00 in populated PDF"

    def test_principal_appears_consistently(self, fully_populated_facts):
        data = render_packet(fully_populated_facts)
        text = _extract_text(data)
        count = text.count("$4,800.00")
        assert count >= 3, (
            f"Principal $4,800.00 should appear in cover, claim, and demand letter "
            f"but found {count} times"
        )

    def test_branding_says_claimready(self, fully_populated_facts):
        data = render_packet(fully_populated_facts)
        text = _extract_text(data)
        assert "ClaimReady" in text
        assert "QuietCase" not in text

    def test_disclaimer_says_not_legal_advice(self, fully_populated_facts):
        data = render_packet(fully_populated_facts)
        text = _extract_text(data)
        assert "does not provide legal advice" in text
        assert "not a law firm" in text
