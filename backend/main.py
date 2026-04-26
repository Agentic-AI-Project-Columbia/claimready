"""FastAPI backend for the small claims complaint generator.

Endpoints:
  POST /api/case                   — kick off a run, returns case_id
  WS   /api/case/{case_id}/events  — stream agent events
  GET  /api/case/{case_id}/pdf     — download the rendered PDF packet
  GET  /healthz                    — liveness

The WebSocket emits JSON messages like:
  {"type": "agent_started", "name": "Extractor"}
  {"type": "tool_called", "name": "lookup_ny_business", "args": {...}}
  {"type": "tool_result", "name": "lookup_ny_business", "preview": "..."}
  {"type": "handoff", "from": "Planner", "to": "JurisdictionChecker"}
  {"type": "facts_partial", "facts": {...}}
  {"type": "done", "facts": {...}, "pdf_ready": true}
  {"type": "error", "message": "..."}
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List

from agents import Runner
from fastapi import FastAPI, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from demo_scenario import (
    DEMO_BLURB,
    DEMO_EVIDENCE,
    DEMO_INTAKE,
    DEMO_TITLE,
    build_demo_intake,
)
from runtime import get_planner
from schema import CaseFacts
from tools.pdf_render import render_packet
from tools.rag import ingest

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("complaintgen")

DATA_DIR = Path(__file__).resolve().parent / "data"
CASES_DIR = DATA_DIR / "cases"
CASES_DIR.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Ingesting legal corpus into Chroma…")
    n = ingest()
    log.info("Ingested %d documents.", n)
    log.info("Warming up planner…")
    get_planner()
    log.info("Backend ready.")
    yield


app = FastAPI(title="Small Claims Complaint Generator", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# In-memory queues per case_id. Cloud Run single-instance for the demo.
_event_queues: Dict[str, asyncio.Queue] = {}
_case_state: Dict[str, Dict[str, Any]] = {}


def _case_dir(case_id: str) -> Path:
    d = CASES_DIR / case_id
    d.mkdir(parents=True, exist_ok=True)
    return d


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.post("/api/case")
async def create_case(intake: Dict[str, Any]):
    """Start a new case. `intake` is the partial CaseFacts JSON from the wizard.

    Evidence files should already have been POSTed via /api/case/{id}/evidence,
    but for the demo simplest path the intake also includes "evidence" as a list
    of { filename, mime_type, text } objects (text already extracted client-side
    or via /api/case/{id}/evidence which also fills text).
    """
    case_id = uuid.uuid4().hex[:12]
    _event_queues[case_id] = asyncio.Queue()
    _case_state[case_id] = {"intake": intake, "status": "queued"}
    asyncio.create_task(_run_case(case_id, intake))
    return {"case_id": case_id}


@app.get("/api/demo/scenario")
def demo_scenario():
    """Return the bundled grader-demo scenario (intake + evidence + blurb)."""
    return {
        "title": DEMO_TITLE,
        "blurb": DEMO_BLURB,
        "intake": DEMO_INTAKE,
        "evidence_filenames": [e["filename"] for e in DEMO_EVIDENCE],
    }


@app.post("/api/demo/run")
async def demo_run():
    """One-click grader path: spawn a case from the bundled scenario.

    Returns the case_id; the client opens the WebSocket as usual to watch
    the agent run and download the resulting PDF.
    """
    case_id = uuid.uuid4().hex[:12]
    _event_queues[case_id] = asyncio.Queue()
    intake = build_demo_intake()
    _case_state[case_id] = {"intake": intake, "status": "queued", "demo": True}
    asyncio.create_task(_run_case(case_id, intake))
    return {
        "case_id": case_id,
        "title": DEMO_TITLE,
        "blurb": DEMO_BLURB,
    }


@app.post("/api/case/{case_id}/evidence")
async def upload_evidence(case_id: str, files: List[UploadFile]):
    """Upload one or more evidence files; returns extracted text per file."""
    items = []
    for f in files:
        raw = await f.read()
        path = _case_dir(case_id) / f.filename
        path.write_bytes(raw)
        text = _extract_text(path, f.content_type or "")
        items.append({
            "filename": f.filename,
            "mime_type": f.content_type,
            "size": len(raw),
            "text": text[:20_000],
        })
    return {"items": items}


def _extract_text(path: Path, mime: str) -> str:
    """Best-effort text extraction. Returns empty string on unknown types
    (the LLM can still see images via the agent input)."""
    try:
        if path.suffix.lower() == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            return "\n".join((p.extract_text() or "") for p in reader.pages)
        if path.suffix.lower() in {".txt", ".md", ".eml"}:
            return path.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:
        log.warning("text extraction failed for %s: %s", path, exc)
    return ""


@app.websocket("/api/case/{case_id}/events")
async def case_events(websocket: WebSocket, case_id: str):
    await websocket.accept()
    q = _event_queues.get(case_id)
    if q is None:
        await websocket.send_json({"type": "error", "message": f"unknown case {case_id}"})
        await websocket.close()
        return
    try:
        while True:
            msg = await q.get()
            await websocket.send_json(msg)
            if msg.get("type") in {"done", "error"}:
                break
    except WebSocketDisconnect:
        pass


@app.get("/api/case/{case_id}/pdf")
def case_pdf(case_id: str):
    pdf_path = _case_dir(case_id) / "packet.pdf"
    if not pdf_path.exists():
        raise HTTPException(404, "PDF not yet rendered")
    return FileResponse(pdf_path, media_type="application/pdf", filename="small-claims-packet.pdf")


@app.get("/api/case/{case_id}/facts")
def case_facts(case_id: str):
    state = _case_state.get(case_id)
    if not state:
        raise HTTPException(404, "unknown case")
    return JSONResponse({"status": state.get("status"), "facts": state.get("facts")})


# --------------------------------------------------------------------------- #
#                              Agent driver                                   #
# --------------------------------------------------------------------------- #


async def _emit(case_id: str, msg: Dict[str, Any]) -> None:
    q = _event_queues.get(case_id)
    if q is not None:
        await q.put(msg)


async def _run_case(case_id: str, intake: Dict[str, Any]) -> None:
    """Drive the planner, stream events, render PDF when done."""
    try:
        await _emit(case_id, {"type": "agent_started", "name": "Planner"})
        _case_state[case_id]["status"] = "running"

        planner = get_planner()
        prompt = _build_prompt(intake)

        result = Runner.run_streamed(planner, prompt, max_turns=50)
        async for event in result.stream_events():
            await _forward_event(case_id, event)

        final = result.final_output
        if not isinstance(final, CaseFacts):
            try:
                final = CaseFacts.model_validate(final)
            except Exception:
                final = _facts_from_intake(intake)

        # Render PDF
        pdf_path = _case_dir(case_id) / "packet.pdf"
        render_packet(final, output_path=pdf_path)

        _case_state[case_id]["status"] = "done"
        _case_state[case_id]["facts"] = final.model_dump(mode="json")
        await _emit(case_id, {
            "type": "done",
            "facts": _case_state[case_id]["facts"],
            "pdf_ready": True,
        })
    except Exception as exc:
        log.exception("case %s failed", case_id)
        # Even on failure, render whatever we have so the demo always produces a PDF.
        try:
            facts = _facts_from_intake(intake)
            render_packet(facts, output_path=_case_dir(case_id) / "packet.pdf")
            _case_state[case_id]["status"] = "done_with_errors"
            _case_state[case_id]["facts"] = facts.model_dump(mode="json")
        except Exception:
            pass
        await _emit(case_id, {"type": "error", "message": str(exc)})


def _build_prompt(intake: Dict[str, Any]) -> str:
    """Compose the planner prompt from intake JSON + evidence summaries."""
    evidence = intake.pop("evidence", []) if isinstance(intake, dict) else []
    intake_json = json.dumps(intake, indent=2, default=str)
    evid = "\n\n".join(
        f"--- EVIDENCE id={i+1} filename={e.get('filename')} ---\n{e.get('text', '')[:6000]}"
        for i, e in enumerate(evidence or [])
    ) or "(no text evidence supplied)"
    return (
        "Run the full small-claims pipeline.\n\n"
        "USER INTAKE (partial CaseFacts JSON):\n```json\n" + intake_json + "\n```\n\n"
        "EVIDENCE:\n" + evid + "\n\n"
        "Return the finalized CaseFacts."
    )


def _facts_from_intake(intake: Dict[str, Any]) -> CaseFacts:
    """Last-resort: build CaseFacts directly from the wizard intake.

    Strips fields the schema can't accept (e.g. `evidence`)."""
    clean = {k: v for k, v in (intake or {}).items() if k != "evidence"}
    try:
        return CaseFacts.model_validate(clean)
    except Exception:
        return CaseFacts()


async def _forward_event(case_id: str, event: Any) -> None:
    """Translate a Runner stream event into our wire-format JSON."""
    try:
        et = getattr(event, "type", None) or event.__class__.__name__
        payload: Dict[str, Any] = {"type": et}

        for attr in ("name", "agent", "from_agent", "to_agent", "tool_name"):
            v = getattr(event, attr, None)
            if v is not None:
                payload[attr] = v if isinstance(v, (str, int, float, bool, dict, list)) else str(v)

        # Tool call arguments — show full args so the UI can display what was searched
        args = getattr(event, "args", None)
        if args is not None:
            try:
                payload["args"] = args if isinstance(args, dict) else json.loads(str(args))
            except Exception:
                payload["args"] = str(args)[:300]

        # Result / data preview — increased to 1200 chars for richer display
        if hasattr(event, "data") and event.data is not None:
            try:
                raw = str(event.data)
                payload["preview"] = raw[:1200]
                payload["preview_truncated"] = len(raw) > 1200
            except Exception:
                pass

        # Surface the current agent name wherever possible
        item = getattr(event, "item", None)
        if item is not None:
            agent_name = getattr(item, "agent", None) or getattr(item, "name", None)
            if agent_name and "agent" not in payload:
                payload["agent"] = str(agent_name)

        await _emit(case_id, payload)
    except Exception as exc:
        log.warning("event forward failed: %s", exc)
