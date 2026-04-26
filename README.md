# Quietcase — Small Claims, Filed Right

A planner-executor agent that turns your messy unpaid-invoice evidence
(emails, contracts, screenshots) into a court-ready NYC Civil Court small-claims
packet: a filled Statement of Claim mirroring CIV-SC-50, a demand letter, an
exhibit index, and a borough filing guide.

**Locked scope:** NYC small claims · breach of contract for unpaid services ·
defendant is a NY-registered LLC or corp · output is PDF (no e-filing).

---

## Live URLs

- **Frontend:** https://quietcase-frontend-xo2itdlc3a-ue.a.run.app
- **Backend (API):** https://quietcase-backend-xo2itdlc3a-ue.a.run.app
- **Demo scenario JSON:** https://quietcase-backend-xo2itdlc3a-ue.a.run.app/api/demo/scenario

---

## For graders — one-click demo

Open the frontend URL above. The home page has a highlighted **"Run the
sample case"** card. One click runs the entire pipeline on a pre-baked
scenario — no typing, no signup. You'll see:

1. The four agents handing off in real time (Extractor → Defendant →
   Jurisdiction → Drafter)
2. Tool calls hitting the live NY DOS SODA API and the local Chroma RAG
3. A downloadable court-ready PDF packet at the end (~30–60 s total)

The bundled scenario: a Brooklyn freelance designer owed $4,800 by an
NYC marketing LLC, with a signed contract, invoice, email thread, and
follow-up note as evidence.

Programmatic demo (no UI):

```bash
# 1. Kick off a run
CASE=$(curl -sS -X POST -H "Content-Length: 0" \
  https://quietcase-backend-xo2itdlc3a-ue.a.run.app/api/demo/run \
  | python -c "import sys,json; print(json.load(sys.stdin)['case_id'])")

# 2. Poll until the PDF is ready (~60–90s for the four-agent run)
until curl -fsS -o packet.pdf \
  "https://quietcase-backend-xo2itdlc3a-ue.a.run.app/api/case/$CASE/pdf"; do
  sleep 5
done && open packet.pdf
```

Source: [backend/demo_scenario.py](backend/demo_scenario.py).

---

## Quick start (local dev)

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
gcloud auth application-default login
export GCP_PROJECT_ID=csee4121-s26-492100
export GCP_REGION=us-east1
uvicorn main:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm install
echo "NEXT_PUBLIC_BACKEND_URL=http://localhost:8000" > .env.local
npm run dev    # http://localhost:3000
```

Deploy to GCP Cloud Run: see [deploy.md](deploy.md).

---

## Architecture

```
   Next.js wizard (TurboTax-style)
            │  upload + intake
            ▼
        FastAPI                (POST /api/case → spawns run, WS streams events)
            │
            ▼
   ┌─────────────────────┐
   │      Planner        │  ← OpenAI Agents SDK (Vertex AI Gemini 2.5 Flash via LiteLLM)
   └─────────┬───────────┘
             │ handoff()
   ┌─────────┼─────────────────────────────┐
   ▼         ▼                  ▼          ▼
 Extractor  Defendant       Jurisdiction  Drafter
 (vision +  (NY DOS SODA    (RAG +        (finalize
 schema)    lookup)         validators)   CaseFacts)
                                  │
                                  ▼
                        ReportLab → PDF packet
```

---

## Class concepts (with file references)

| Concept | Where it lives |
|---|---|
| **Agent framework** — multi-agent + handoffs | [backend/runtime.py](backend/runtime.py) — `build_planner` defines a `Planner` Agent with `handoffs=[extractor, defendant, jurisdiction, drafter]`. Built on the OpenAI Agents SDK. |
| **Tool use** | [backend/tools/dos_lookup.py](backend/tools/dos_lookup.py) (`@function_tool lookup_ny_business`), [backend/tools/jurisdiction.py](backend/tools/jurisdiction.py) (`validate_jurisdiction`, `compute_damages`), [backend/tools/rag.py](backend/tools/rag.py) (`search_legal_kb`). |
| **RAG** — retrieval over a legal knowledge base | [backend/tools/rag.py](backend/tools/rag.py) — Chroma persistent index over `backend/corpus/*.md` (NYC CCA § 1805, CPLR § 213(2), CPLR § 5004, venue rules, filing procedure, sample complaint). Ingested at container build time. |
| **Structured outputs** | [backend/schema.py](backend/schema.py) — Pydantic `CaseFacts` is the `output_type` of every agent. |
| **Multimodal** | Gemini 2.5 Flash (vision-capable) inside the Extractor agent reads screenshots and scanned contracts via the same chat interface as text. |
| **Streaming** | `Runner.run_streamed(...)` in [backend/main.py](backend/main.py:_run_case) → forwarded over WebSocket → rendered in [frontend/components/AgentTimeline.tsx](frontend/components/AgentTimeline.tsx). |

---

## Stack

- **Agent framework:** OpenAI Agents SDK (`openai-agents[litellm]`)
- **LLM:** Google Vertex AI · Gemini 2.5 Flash (via LiteLLM, ADC auth)
- **Vector DB:** Chroma (local, persisted)
- **Backend:** FastAPI + uvicorn
- **PDF:** ReportLab + pypdf
- **External data:** [NY Open Data SODA API](https://data.ny.gov/resource/n9v6-gdp6.json) — Active Corporations dataset
- **Frontend:** Next.js 15 (App Router) + Tailwind + lucide-react
- **Deploy:** Cloud Build → two Cloud Run services (backend + frontend) in `us-east1`

---

## Repo layout

```
.
├── backend/
│   ├── main.py            # FastAPI + WebSocket
│   ├── runtime.py         # Planner + 4 specialist agents
│   ├── schema.py          # Pydantic CaseFacts
│   ├── tools/             # @function_tool implementations
│   ├── corpus/            # legal corpus (markdown) for RAG
│   ├── templates/         # demand_letter.txt
│   └── Dockerfile
├── frontend/
│   ├── app/               # Next.js wizard (page.tsx)
│   ├── components/        # StepShell, EvidenceUpload, AgentTimeline, …
│   ├── lib/               # api client + types
│   └── Dockerfile
├── cloudbuild.yaml        # one-shot deploy of both services
└── deploy.md              # GCP setup + deploy commands
```

---

## Disclaimer

Quietcase generates documents and educational guidance from public statutes
and court forms. It is not a law firm and does not provide legal advice. For
a complex case, see a licensed attorney.
