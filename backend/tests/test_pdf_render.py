"""Tests for PDF rendering."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from tools.pdf_render import render_packet


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

    def test_minimal_facts_still_renders(self):
        from schema import CaseFacts
        facts = CaseFacts()
        data = render_packet(facts)
        assert isinstance(data, bytes)
        assert data[:5] == b"%PDF-"

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
