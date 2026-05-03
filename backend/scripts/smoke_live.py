"""Live smoke verification for ClaimReady backend endpoints.

This intentionally calls the real backend pipeline and can invoke live model
traffic. Keep it separate from unit tests.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import zlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx
import websockets


DONE_STATUSES = {"done", "done_with_errors"}


class SmokeFailure(RuntimeError):
    """Raised when a live smoke assertion fails."""


@dataclass(frozen=True)
class FlowResult:
    name: str
    case_id: str
    status: str
    elapsed_seconds: float
    pdf_bytes: int
    facts_keys: list[str]
    pdf_path: str | None = None
    event_count: int | None = None
    handoffs: list[str] | None = None
    tools: list[str] | None = None


@dataclass(frozen=True)
class SmokeReport:
    base_url: str
    timeout_seconds: float
    flows: list[FlowResult]


def run_smoke(
    *,
    base_url: str,
    api_key: str = "",
    timeout_seconds: float = 90.0,
    poll_interval_seconds: float = 5.0,
    output_dir: Path | None = None,
    run_demo_flow: bool = True,
    run_upload_flow: bool = True,
    run_event_flow: bool = True,
) -> SmokeReport:
    """Run the opt-in live smoke checks and return measured results."""
    base_url = _normalize_base_url(base_url)
    flows: list[FlowResult] = []

    timeout = httpx.Timeout(timeout=max(10.0, timeout_seconds))
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        if run_demo_flow:
            flows.append(
                _run_demo_flow(
                    client=client,
                    base_url=base_url,
                    api_key=api_key,
                    timeout_seconds=timeout_seconds,
                    poll_interval_seconds=poll_interval_seconds,
                    output_dir=output_dir,
                )
            )
        if run_event_flow:
            flows.append(
                _run_demo_event_stream_flow(
                    client=client,
                    base_url=base_url,
                    api_key=api_key,
                    timeout_seconds=timeout_seconds,
                    output_dir=output_dir,
                )
            )
        if run_upload_flow:
            flows.append(
                _run_prepare_upload_start_flow(
                    client=client,
                    base_url=base_url,
                    api_key=api_key,
                    timeout_seconds=timeout_seconds,
                    poll_interval_seconds=poll_interval_seconds,
                    output_dir=output_dir,
                )
            )

    if not flows:
        raise SmokeFailure("No smoke flows selected.")

    return SmokeReport(base_url=base_url, timeout_seconds=timeout_seconds, flows=flows)


def _run_demo_event_stream_flow(
    *,
    client: httpx.Client,
    base_url: str,
    api_key: str,
    timeout_seconds: float,
    output_dir: Path | None,
) -> FlowResult:
    started = time.perf_counter()
    response = client.post(
        f"{base_url}/api/demo/run",
        headers=_auth_headers(api_key),
        content=b"",
    )
    _assert_success(response, "POST /api/demo/run for event stream")
    case_id = _case_id_from(response.json(), "demo event stream")

    events = asyncio.run(
        _collect_event_stream(
            url=_events_url(base_url, case_id),
            timeout_seconds=timeout_seconds,
        )
    )
    done_event = next((e for e in events if e.get("type") == "done"), None)
    if done_event is None:
        raise SmokeFailure("Event stream ended without a done event.")
    if done_event.get("pdf_ready") is not True:
        raise SmokeFailure("Done event did not report pdf_ready=true.")

    tools = [str(e.get("tool_name")) for e in events if e.get("type") == "tool_called"]
    required_tools = {
        "lookup_ny_business",
        "validate_jurisdiction",
        "compute_damages",
        "search_legal_kb",
    }
    missing_tools = sorted(required_tools - set(tools))
    if missing_tools:
        raise SmokeFailure(f"Event stream missing tool calls: {missing_tools}")

    facts_payload = {
        "status": done_event.get("status") or "done",
        "facts": done_event.get("facts") or {},
    }
    case_facts = facts_payload["facts"]
    defendant = case_facts.get("defendant") if isinstance(case_facts, dict) else {}
    jurisdiction = case_facts.get("jurisdiction_check") if isinstance(case_facts, dict) else {}
    if not defendant.get("dos_id") or not defendant.get("service_address"):
        raise SmokeFailure("Done facts are missing DOS id or service address.")
    if not all(
        jurisdiction.get(k) is True
        for k in ["in_monetary_limit", "within_statute_of_limitations", "venue_proper"]
    ):
        raise SmokeFailure(f"Jurisdiction booleans were not all true: {jurisdiction}")
    if not jurisdiction.get("citations"):
        raise SmokeFailure("Jurisdiction citations are empty.")

    pdf = _download_pdf(client, base_url, api_key, case_id)
    elapsed = time.perf_counter() - started
    _assert_elapsed("demo_event_stream", elapsed, timeout_seconds)
    pdf_path = _write_pdf(output_dir, "events", case_id, pdf)
    result = _flow_result(
        name="demo_event_stream",
        case_id=case_id,
        facts=facts_payload,
        elapsed_seconds=elapsed,
        pdf=pdf,
        pdf_path=pdf_path,
    )
    data = asdict(result)
    data.update({
        "event_count": len(events),
        "handoffs": [
            str(e.get("to_agent") or e.get("name"))
            for e in events
            if e.get("type") in {"agent_started", "handoff"}
        ],
        "tools": tools,
    })
    return FlowResult(**data)


async def _collect_event_stream(*, url: str, timeout_seconds: float) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    deadline = time.perf_counter() + timeout_seconds
    try:
        async with websockets.connect(url, open_timeout=20, ping_timeout=20) as ws:
            while time.perf_counter() < deadline:
                remaining = max(0.1, deadline - time.perf_counter())
                raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
                event = json.loads(raw)
                events.append(event)
                if event.get("type") == "error":
                    raise SmokeFailure(f"Event stream emitted error: {event.get('message')}")
                if event.get("type") == "done":
                    return events
    except SmokeFailure:
        raise
    except Exception as exc:
        raise SmokeFailure(f"Event stream failed before done: {type(exc).__name__}: {exc}") from exc
    raise SmokeFailure(f"Event stream did not finish within {timeout_seconds:.1f}s.")


def _run_demo_flow(
    *,
    client: httpx.Client,
    base_url: str,
    api_key: str,
    timeout_seconds: float,
    poll_interval_seconds: float,
    output_dir: Path | None,
) -> FlowResult:
    started = time.perf_counter()
    response = client.post(
        f"{base_url}/api/demo/run",
        headers=_auth_headers(api_key),
        content=b"",
    )
    _assert_success(response, "POST /api/demo/run")
    case_id = _case_id_from(response.json(), "demo run")

    facts = _poll_facts(
        client=client,
        base_url=base_url,
        api_key=api_key,
        case_id=case_id,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
    )
    pdf = _download_pdf(client, base_url, api_key, case_id)
    elapsed = time.perf_counter() - started
    _assert_elapsed("demo_pdf", elapsed, timeout_seconds)
    pdf_path = _write_pdf(output_dir, "demo", case_id, pdf)

    return _flow_result(
        name="demo_pdf",
        case_id=case_id,
        facts=facts,
        elapsed_seconds=elapsed,
        pdf=pdf,
        pdf_path=pdf_path,
    )


def _run_prepare_upload_start_flow(
    *,
    client: httpx.Client,
    base_url: str,
    api_key: str,
    timeout_seconds: float,
    poll_interval_seconds: float,
    output_dir: Path | None,
) -> FlowResult:
    started = time.perf_counter()
    response = client.post(
        f"{base_url}/api/case/prepare",
        headers=_auth_headers(api_key),
        content=b"",
    )
    _assert_success(response, "POST /api/case/prepare")
    case_id = _case_id_from(response.json(), "prepare")

    upload_response = client.post(
        f"{base_url}/api/case/{case_id}/evidence",
        headers=_auth_headers(api_key),
        files=_smoke_evidence_files(),
    )
    _assert_success(upload_response, f"POST /api/case/{case_id}/evidence")
    items = upload_response.json().get("items")
    if not isinstance(items, list) or len(items) < 2:
        raise SmokeFailure("Evidence upload did not return both smoke evidence items.")

    intake = _smoke_intake()
    intake["evidence"] = items
    start_response = client.post(
        f"{base_url}/api/case/{case_id}/start",
        headers=_auth_headers(api_key),
        json=intake,
    )
    _assert_success(start_response, f"POST /api/case/{case_id}/start")
    returned_case_id = _case_id_from(start_response.json(), "start")
    if returned_case_id != case_id:
        raise SmokeFailure(
            f"Start returned case_id {returned_case_id!r}, expected {case_id!r}."
        )

    facts = _poll_facts(
        client=client,
        base_url=base_url,
        api_key=api_key,
        case_id=case_id,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
    )
    pdf = _download_pdf(client, base_url, api_key, case_id)
    elapsed = time.perf_counter() - started
    _assert_elapsed("prepare_upload_start_pdf", elapsed, timeout_seconds)
    pdf_path = _write_pdf(output_dir, "upload", case_id, pdf)

    return _flow_result(
        name="prepare_upload_start_pdf",
        case_id=case_id,
        facts=facts,
        elapsed_seconds=elapsed,
        pdf=pdf,
        pdf_path=pdf_path,
    )


def _poll_facts(
    *,
    client: httpx.Client,
    base_url: str,
    api_key: str,
    case_id: str,
    timeout_seconds: float,
    poll_interval_seconds: float,
) -> dict[str, Any]:
    deadline = time.perf_counter() + timeout_seconds
    last_status = "not polled"

    while time.perf_counter() < deadline:
        response = client.get(
            f"{base_url}/api/case/{case_id}/facts",
            headers=_auth_headers(api_key),
        )
        if response.status_code == 404:
            last_status = "facts endpoint returned 404"
        else:
            _assert_success(response, f"GET /api/case/{case_id}/facts")
            facts = response.json()
            status = str(facts.get("status") or "")
            last_status = status or "missing status"
            if status in DONE_STATUSES:
                return facts

        sleep_for = min(poll_interval_seconds, max(0.1, deadline - time.perf_counter()))
        time.sleep(sleep_for)

    raise SmokeFailure(
        f"Case {case_id} did not finish within {timeout_seconds:.1f}s; "
        f"last status was {last_status!r}."
    )


def _download_pdf(
    client: httpx.Client,
    base_url: str,
    api_key: str,
    case_id: str,
) -> bytes:
    response = client.get(
        f"{base_url}/api/case/{case_id}/pdf",
        headers=_auth_headers(api_key),
    )
    _assert_success(response, f"GET /api/case/{case_id}/pdf")

    content_type = response.headers.get("content-type", "").split(";")[0].lower()
    if content_type != "application/pdf":
        raise SmokeFailure(
            f"PDF endpoint returned content-type {content_type!r}, not application/pdf."
        )
    if not response.content.startswith(b"%PDF-"):
        raise SmokeFailure("Downloaded packet does not start with %PDF-.")
    return response.content


def _flow_result(
    *,
    name: str,
    case_id: str,
    facts: dict[str, Any],
    elapsed_seconds: float,
    pdf: bytes,
    pdf_path: Path | None,
) -> FlowResult:
    status = str(facts.get("status") or "")
    case_facts = facts.get("facts") or {}
    keys = sorted(case_facts.keys()) if isinstance(case_facts, dict) else []
    return FlowResult(
        name=name,
        case_id=case_id,
        status=status,
        elapsed_seconds=round(elapsed_seconds, 2),
        pdf_bytes=len(pdf),
        facts_keys=keys,
        pdf_path=str(pdf_path) if pdf_path else None,
    )


def _smoke_intake() -> dict[str, Any]:
    return {
        "plaintiff": {
            "name": "Alex Smoke",
            "address": "123 Smith Street",
            "city": "Brooklyn",
            "state": "NY",
            "zip_code": "11201",
            "phone": "718-555-0111",
            "email": "alex.smoke@example.com",
        },
        "defendant": {
            "name": "Vanguard Marketing LLC",
            "address": "14929 115 Street",
            "city": "South Ozone Park",
            "state": "NY",
            "zip_code": "11420",
            "service_address": "14929 115 Street, South Ozone Park, NY 11420",
            "dos_entity_name": "VANGUARD MARKETING LLC",
            "dos_id": "3568461",
            "entity_status": "Active",
        },
        "contract": {
            "date_formed": "2025-01-10",
            "scope_of_work": "Invoice design and launch collateral cleanup.",
            "agreed_amount": 1250.0,
            "payment_terms": "Net 15 from invoice.",
        },
        "performance": {
            "delivered_on": "2025-02-20",
            "deliverables": ["Invoice design files", "Launch collateral cleanup"],
        },
        "breach": {
            "date": "2025-03-07",
            "nature": "non-payment",
            "amount_owed": 1250.0,
        },
        "damages": {
            "principal": 1250.0,
            "interest_from": "2025-03-07",
            "interest_rate": 0.09,
            "total_demanded": 1250.0,
        },
        "venue": {
            "borough": "Queens",
            "basis": "Defendant's service address is in Queens.",
        },
        "exhibits": [
            {
                "label": "A",
                "description": "Uploaded invoice screenshot",
                "file_ref": "smoke_invoice_screenshot.png",
            },
            {
                "label": "B",
                "description": "Uploaded follow-up note",
                "file_ref": "smoke_followup.txt",
            },
        ],
        "jurisdiction_check": {
            "in_monetary_limit": True,
            "within_statute_of_limitations": True,
            "venue_proper": True,
            "citations": ["NYC Civil Court Act Section 1805"],
        },
    }


def _smoke_evidence_files() -> list[tuple[str, tuple[str, bytes, str]]]:
    note = (
        "Subject: Past due invoice CR-SMOKE-001\n\n"
        "Alex Smoke delivered invoice design and launch collateral cleanup on "
        "February 20, 2025. Vanguard Marketing LLC acknowledged receipt but "
        "has not paid the $1,250 invoice due March 7, 2025.\n"
    ).encode("utf-8")
    return [
        (
            "files",
            ("smoke_invoice_screenshot.png", _invoice_screenshot_png(), "image/png"),
        ),
        ("files", ("smoke_followup.txt", note, "text/plain")),
    ]


def _invoice_screenshot_png() -> bytes:
    """Create a small screenshot-like PNG with invoice text."""
    try:
        import fitz

        doc = fitz.open()
        page = doc.new_page(width=640, height=420)
        lines = [
            "CLAIMREADY SMOKE INVOICE",
            "Invoice: CR-SMOKE-001",
            "Client: Vanguard Marketing LLC",
            "Service: Invoice design and launch collateral cleanup",
            "Delivered: February 20, 2025",
            "Due: March 7, 2025",
            "Amount due: $1,250.00",
        ]
        y = 48
        for index, line in enumerate(lines):
            size = 22 if index == 0 else 16
            page.insert_text((36, y), line, fontsize=size, fontname="helv")
            y += 42 if index == 0 else 34
        pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
        return pix.tobytes("png")
    except Exception:
        return _fallback_png()


def _fallback_png() -> bytes:
    """Return a minimal valid PNG if PyMuPDF is unavailable."""
    width, height = 2, 2
    raw = b"".join(b"\x00" + b"\xff\xff\xff" * width for _ in range(height))

    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(kind + data) & 0xFFFFFFFF
        return len(data).to_bytes(4, "big") + kind + data + crc.to_bytes(4, "big")

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(
            b"IHDR",
            width.to_bytes(4, "big")
            + height.to_bytes(4, "big")
            + b"\x08\x02\x00\x00\x00",
        )
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def _write_pdf(
    output_dir: Path | None,
    flow_name: str,
    case_id: str,
    pdf: bytes,
) -> Path | None:
    if output_dir is None:
        return None
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{flow_name}-{case_id}.pdf"
    path.write_bytes(pdf)
    return path


def _auth_headers(api_key: str) -> dict[str, str]:
    return {"X-API-Key": api_key} if api_key else {}


def _assert_success(response: httpx.Response, context: str) -> None:
    if response.is_success:
        return
    preview = response.text[:500].replace("\n", " ")
    raise SmokeFailure(f"{context} failed with HTTP {response.status_code}: {preview}")


def _assert_elapsed(flow_name: str, elapsed_seconds: float, timeout_seconds: float) -> None:
    if elapsed_seconds <= timeout_seconds:
        return
    raise SmokeFailure(
        f"{flow_name} took {elapsed_seconds:.2f}s, exceeding "
        f"the {timeout_seconds:.2f}s smoke timeout."
    )


def _case_id_from(payload: dict[str, Any], context: str) -> str:
    case_id = payload.get("case_id")
    if not isinstance(case_id, str) or not case_id:
        raise SmokeFailure(f"{context} response did not include a case_id.")
    return case_id


def _normalize_base_url(base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")
    if not normalized:
        raise SmokeFailure("A backend base URL is required.")
    if not normalized.startswith(("http://", "https://")):
        raise SmokeFailure("Base URL must start with http:// or https://.")
    return normalized


def _events_url(base_url: str, case_id: str) -> str:
    if base_url.startswith("https://"):
        return f"wss://{base_url.removeprefix('https://')}/api/case/{case_id}/events"
    return f"ws://{base_url.removeprefix('http://')}/api/case/{case_id}/events"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("CLAIMREADY_SMOKE_BASE_URL")
        or os.environ.get("CLAIMREADY_BASE_URL")
        or "",
        help="Backend URL, for example https://claimready-backend-...run.app",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("CLAIMREADY_API_KEY") or os.environ.get("API_KEY") or "",
        help="Optional API key sent as X-API-Key.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.environ.get("CLAIMREADY_SMOKE_TIMEOUT", "90")),
        help="Maximum seconds to wait for each flow.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=float(os.environ.get("CLAIMREADY_SMOKE_POLL_INTERVAL", "5")),
        help="Seconds between facts polling attempts.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=(
            Path(os.environ["CLAIMREADY_SMOKE_OUTPUT_DIR"])
            if os.environ.get("CLAIMREADY_SMOKE_OUTPUT_DIR")
            else None
        ),
        help="Optional directory where downloaded PDFs are saved.",
    )
    parser.add_argument("--skip-demo", action="store_true", help="Skip /api/demo/run.")
    parser.add_argument(
        "--skip-upload",
        action="store_true",
        help="Skip prepare/evidence/start upload flow.",
    )
    parser.add_argument(
        "--skip-events",
        action="store_true",
        help="Skip WebSocket event-stream assertions.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = run_smoke(
            base_url=args.base_url,
            api_key=args.api_key,
            timeout_seconds=args.timeout,
            poll_interval_seconds=args.poll_interval,
            output_dir=args.output_dir,
            run_demo_flow=not args.skip_demo,
            run_upload_flow=not args.skip_upload,
            run_event_flow=not args.skip_events,
        )
    except (SmokeFailure, httpx.HTTPError) as exc:
        print(f"SMOKE FAILED: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(asdict(report), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
