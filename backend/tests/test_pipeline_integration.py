"""Integration test: full agent pipeline with the demo scenario.

Requires live Gemini API credentials (Google ADC). Mark with
@pytest.mark.integration so it can be skipped in CI without creds.

Run with:  pytest tests/test_pipeline_integration.py -m integration -v
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

pytestmark = pytest.mark.integration


@pytest.fixture()
def base_url():
    return "http://testserver"


@pytest.fixture()
async def client():
    from main import app
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as c:
        yield c


class TestFullPipeline:
    async def test_healthz(self, client: httpx.AsyncClient):
        resp = await client.get("/healthz")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    async def test_demo_scenario_endpoint(self, client: httpx.AsyncClient):
        resp = await client.get("/api/demo/scenario")
        assert resp.status_code == 200
        data = resp.json()
        assert "title" in data
        assert "intake" in data

    async def test_demo_run_produces_events_and_pdf(self, client: httpx.AsyncClient):
        resp = await client.post("/api/demo/run")
        assert resp.status_code == 200
        case_id = resp.json()["case_id"]
        assert case_id

        await asyncio.sleep(90)

        facts_resp = await client.get(f"/api/case/{case_id}/facts")
        assert facts_resp.status_code == 200
        facts_data = facts_resp.json()
        assert facts_data["status"] in {"done", "done_with_errors"}

        pdf_resp = await client.get(f"/api/case/{case_id}/pdf")
        assert pdf_resp.status_code == 200
        assert pdf_resp.headers["content-type"] == "application/pdf"
        assert pdf_resp.content[:5] == b"%PDF-"

    async def test_create_case_returns_case_id(self, client: httpx.AsyncClient):
        intake = {
            "plaintiff": {"name": "Test User", "address": "123 Test St"},
            "defendant": {"name": "Test Corp"},
            "contract": {"scope_of_work": "Testing", "agreed_amount": 1000},
            "breach": {"date": "2025-01-01", "amount_owed": 1000},
            "venue": {"borough": "Manhattan"},
        }
        resp = await client.post("/api/case", json=intake)
        assert resp.status_code == 200
        assert "case_id" in resp.json()
