"""Opt-in live smoke tests for deployed or locally served ClaimReady backend."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from scripts.smoke_live import run_smoke


pytestmark = [pytest.mark.integration, pytest.mark.smoke]


def test_live_demo_and_upload_flows(tmp_path: Path):
    base_url = os.environ.get("CLAIMREADY_SMOKE_BASE_URL") or os.environ.get(
        "CLAIMREADY_BASE_URL", ""
    )
    if not base_url:
        pytest.skip("Set CLAIMREADY_SMOKE_BASE_URL to run live smoke tests.")

    timeout = float(os.environ.get("CLAIMREADY_SMOKE_TIMEOUT", "90"))
    report = run_smoke(
        base_url=base_url,
        api_key=os.environ.get("CLAIMREADY_API_KEY") or os.environ.get("API_KEY", ""),
        timeout_seconds=timeout,
        poll_interval_seconds=float(
            os.environ.get("CLAIMREADY_SMOKE_POLL_INTERVAL", "5")
        ),
        output_dir=tmp_path,
    )

    assert {flow.name for flow in report.flows} == {
        "demo_pdf",
        "demo_event_stream",
        "prepare_upload_start_pdf",
    }
    for flow in report.flows:
        assert flow.status in {"done", "done_with_errors"}
        assert flow.pdf_bytes > 1000
        assert flow.elapsed_seconds <= timeout
        assert flow.pdf_path
        assert Path(flow.pdf_path).read_bytes().startswith(b"%PDF-")
