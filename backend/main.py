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
from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

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
from tracing import get_tracer, setup_tracing

try:
    from pythonjsonlogger.json import JsonFormatter
    _handler = logging.StreamHandler()
    _handler.setFormatter(JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "severity"},
    ))
    logging.basicConfig(level=logging.INFO, handlers=[_handler])
except ImportError:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("complaintgen")

DATA_DIR = Path(__file__).resolve().parent / "data"
CASES_DIR = DATA_DIR / "cases"
CASES_DIR.mkdir(parents=True, exist_ok=True)

API_KEY = os.environ.get("API_KEY", "")
limiter = Limiter(key_func=get_remote_address)


def _check_api_key(request: Request) -> None:
    """Validate API key if one is configured via the API_KEY env var."""
    if not API_KEY:
        return
    key = request.headers.get("X-API-Key", "")
    if key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_tracing()
    log.info("Ingesting legal corpus into Chroma…")
    n = ingest()
    log.info("Ingested %d documents.", n)
    log.info("Warming up planner…")
    get_planner()
    log.info("Backend ready. API_KEY configured: %s", bool(API_KEY))
    yield


app = FastAPI(title="ClaimReady backend", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, lambda req, exc: JSONResponse(
    status_code=429, content={"detail": "Rate limit exceeded. Try again in a moment."},
))
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


@app.post("/api/case", dependencies=[Depends(_check_api_key)])
@limiter.limit("5/minute")
async def create_case(request: Request, intake: Dict[str, Any]):
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


@app.post("/api/demo/run", dependencies=[Depends(_check_api_key)])
@limiter.limit("5/minute")
async def demo_run(request: Request):
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


GCS_BUCKET = os.environ.get("GCS_EVIDENCE_BUCKET", "")


def _upload_to_gcs(case_id: str, filename: str, data: bytes) -> None:
    """Upload evidence to GCS if a bucket is configured."""
    if not GCS_BUCKET:
        return
    try:
        from google.cloud import storage
        client = storage.Client()
        bucket = client.bucket(GCS_BUCKET)
        blob = bucket.blob(f"{case_id}/{filename}")
        blob.upload_from_string(data)
        log.info("Uploaded %s to gs://%s/%s/%s", filename, GCS_BUCKET, case_id, filename)
    except Exception as exc:
        log.warning("GCS upload failed for %s: %s", filename, exc)


@app.post("/api/case/{case_id}/evidence")
async def upload_evidence(case_id: str, files: List[UploadFile]):
    """Upload one or more evidence files; returns extracted text per file."""
    items = []
    for f in files:
        raw = await f.read()
        path = _case_dir(case_id) / f.filename
        path.write_bytes(raw)
        _upload_to_gcs(case_id, f.filename, raw)
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


def _persist_event(case_id: str, msg: Dict[str, Any]) -> None:
    """Append event to a JSON-lines file for replay after restarts."""
    events_file = _case_dir(case_id) / "events.jsonl"
    with events_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(msg, default=str) + "\n")


async def _emit(case_id: str, msg: Dict[str, Any]) -> None:
    _persist_event(case_id, msg)
    q = _event_queues.get(case_id)
    if q is not None:
        await q.put(msg)


async def _run_case(case_id: str, intake: Dict[str, Any]) -> None:
    """Drive the planner, stream events, render PDF when done."""
    extra = {"case_id": case_id}
    tracer = get_tracer()
    with tracer.start_as_current_span("pipeline.run", attributes={"case_id": case_id}):
        try:
            log.info("Starting agent pipeline", extra=extra)
            await _emit(case_id, {"type": "agent_started", "name": "Planner"})
            _case_state[case_id]["status"] = "running"

            planner = get_planner()
            prompt = _build_prompt(intake)

            result = Runner.run_streamed(planner, prompt, max_turns=50)
            event_count = 0
            async for event in result.stream_events():
                await _forward_event(case_id, event)
                event_count += 1

            log.info("Agent pipeline completed, %d events streamed", event_count, extra=extra)

            final = result.final_output
            if not isinstance(final, CaseFacts):
                try:
                    final = CaseFacts.model_validate(final)
                except Exception:
                    log.warning("Could not parse final output as CaseFacts, using intake fallback", extra=extra)
                    final = _facts_from_intake(intake)

            pdf_path = _case_dir(case_id) / "packet.pdf"
            render_packet(final, output_path=pdf_path)
            log.info("PDF rendered to %s", pdf_path, extra=extra)

            _case_state[case_id]["status"] = "done"
            _case_state[case_id]["facts"] = final.model_dump(mode="json")
            await _emit(case_id, {
                "type": "done",
                "facts": _case_state[case_id]["facts"],
                "pdf_ready": True,
            })
        except Exception as exc:
            log.exception("Case failed: %s", exc, extra=extra)
            try:
                facts = _facts_from_intake(intake)
                render_packet(facts, output_path=_case_dir(case_id) / "packet.pdf")
                _case_state[case_id]["status"] = "done_with_errors"
                _case_state[case_id]["facts"] = facts.model_dump(mode="json")
                log.info("Fallback PDF rendered from intake", extra=extra)
            except ValueError as ve:
                log.warning("Fallback PDF validation failed: %s", ve, extra=extra)
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
    """Translate OpenAI Agents SDK stream events into frontend-friendly JSON.

    SDK emits three kinds:
      agent_updated_stream_event  — agent changed (handoff)
      run_item_stream_event       — tool_called / tool_output / message_output
      raw_response_event          — per-token deltas (skipped; too chatty)
    """
    try:
        et = getattr(event, "type", None) or ""

        # ── Skip per-token streaming noise ───────────────────────────────────
        if et == "raw_response_event":
            return

        # ── Agent handoff ─────────────────────────────────────────────────────
        if et == "agent_updated_stream_event":
            new_agent = getattr(event, "new_agent", None)
            name = getattr(new_agent, "name", None) if new_agent else None
            if name:
                await _emit(case_id, {"type": "handoff", "to_agent": name})
            return

        # ── Run item (tool call / tool result / message) ──────────────────────
        if et == "run_item_stream_event":
            item_name = getattr(event, "name", None)   # "tool_called", "tool_output", …
            item      = getattr(event, "item", None)

            # Agent name attached to this item
            item_agent = getattr(item, "agent", None)
            agent_str  = getattr(item_agent, "name", None) if item_agent else None

            if item_name == "tool_called":
                raw = getattr(item, "raw_item", None)
                tool_name = getattr(raw, "name", "") if raw else ""
                arguments = getattr(raw, "arguments", None) if raw else None
                args: Any = None
                if arguments:
                    try:
                        args = json.loads(arguments)
                    except Exception:
                        args = str(arguments)[:300]
                payload: Dict[str, Any] = {
                    "type": "tool_called",
                    "tool_name": tool_name,
                }
                if args is not None:
                    payload["args"] = args
                if agent_str:
                    payload["agent"] = agent_str
                await _emit(case_id, payload)

            elif item_name == "tool_output":
                raw = getattr(item, "raw_item", None)
                output = getattr(raw, "output", None) if raw else None
                result = str(output)[:1200] if output else ""
                payload = {
                    "type": "tool_result",
                    "tool_name": "",  # populated by call_id matching if needed
                    "preview": result,
                    "preview_truncated": len(str(output or "")) > 1200,
                }
                if agent_str:
                    payload["agent"] = agent_str
                await _emit(case_id, payload)

            # Ignore message_output and other item types (not useful for UI)
            return

        # ── Anything else (e.g. legacy custom events) — forward as-is ─────────
        payload = {"type": et}
        for attr in ("name", "agent", "from_agent", "to_agent", "tool_name"):
            v = getattr(event, attr, None)
            if v is not None:
                payload[attr] = v if isinstance(v, (str, int, float, bool, dict, list)) else str(v)

        await _emit(case_id, payload)

    except Exception as exc:
        log.warning("event forward failed: %s", exc)
