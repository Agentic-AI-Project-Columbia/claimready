# Deployment Guide

**Project:** `agentic-ai-487000` | **Region:** `us-east1` | **Model:** Gemini 2.5 Flash via Vertex AI

---

## Prerequisites

- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) installed and authenticated
- Docker (for local image builds, optional)
- Project owner or editor role on `agentic-ai-487000`

---

## One-Time GCP Setup

These APIs and permissions are already enabled — listed here for reference if reproducing from scratch.

```bash
gcloud config set project agentic-ai-487000
gcloud config set run/region us-east1

# Enable required APIs
gcloud services enable \
  aiplatform.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com

# Create Artifact Registry repository
gcloud artifacts repositories create claimready \
  --repository-format=docker \
  --location=us-east1 \
  --description="ClaimReady Docker images"

# Grant Cloud Run service account access to Vertex AI
PROJECT_NUMBER=$(gcloud projects describe agentic-ai-487000 --format='value(projectNumber)')
gcloud projects add-iam-policy-binding agentic-ai-487000 \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/aiplatform.user"

# Grant Cloud Build permission to deploy and act as service account
gcloud projects add-iam-policy-binding agentic-ai-487000 \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/run.admin"
gcloud projects add-iam-policy-binding agentic-ai-487000 \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"
```

---

## Deploy

From the project root (where `cloudbuild.yaml` lives):

```bash
gcloud builds submit \
  --config cloudbuild.yaml \
  --substitutions=_REGION=us-east1,_BACKEND_NAME=claimready-backend,_FRONTEND_NAME=claimready-frontend,_AR_REPO=claimready
```

### What this does

1. **Builds** the backend Docker image and pushes to Artifact Registry
2. **Deploys** the backend to Cloud Run (2 CPU, 2 GiB RAM, 600s timeout, public)
3. **Reads** the backend's public URL from the deployed service
4. **Builds** the frontend Docker image with `NEXT_PUBLIC_BACKEND_URL` baked in
5. **Deploys** the frontend to Cloud Run (1 CPU, 512 MiB RAM, public)

The two Cloud Run URLs are printed in the build log.

### Current live URLs

- **Frontend:** https://claimready-frontend-7pj7nolpla-ue.a.run.app
- **Backend:** https://claimready-backend-7pj7nolpla-ue.a.run.app

---

## Environment Variables

### Backend (set in Cloud Run or `.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `GCP_PROJECT_ID` | `agentic-ai-487000` | Vertex AI project |
| `GCP_REGION` | `us-east1` | Vertex AI region |
| `AGENT_MODEL` | `vertex_ai/gemini-2.5-flash` | LiteLLM model identifier |
| `API_KEY` | *(empty)* | Optional API key for endpoint protection |
| `GCS_EVIDENCE_BUCKET` | *(empty)* | Optional GCS bucket for evidence persistence |
| `PORT` | `8080` | Server port (Cloud Run sets this automatically) |

### Frontend (build-time)

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_BACKEND_URL` | Backend URL (baked into the JS bundle at build time) |

---

## Local Development

```bash
# Backend
cd backend
uv sync
source .venv/bin/activate              # Windows: .venv\Scripts\activate
gcloud auth application-default login  # one-time, for Vertex AI auth
export GCP_PROJECT_ID=agentic-ai-487000
export GCP_REGION=us-east1
uvicorn main:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm install
echo "NEXT_PUBLIC_BACKEND_URL=http://localhost:8000" > .env.local
npm run dev    # http://localhost:3000
```

---

## Cloud Run Resource Configuration

| Service | CPU | Memory | Timeout | Min Instances | Max Instances |
|---------|-----|--------|---------|---------------|---------------|
| Backend | 2 | 2 GiB | 600s | 0 | 3 |
| Frontend | 1 | 512 MiB | 60s | 0 | 3 |

The backend needs higher resources because:
- ChromaDB ingestion runs at startup (~10s)
- Agent pipeline runs can take 30–90s with multiple LLM calls
- PDF rendering is CPU-intensive

---

## Troubleshooting

**Build fails at Vertex AI auth:** Ensure the compute service account has `roles/aiplatform.user`.

**Backend returns 503 on first request:** Cold start takes ~15s (Chroma ingestion + planner warmup). The health check at `/healthz` responds only after startup completes.

**WebSocket disconnects:** Cloud Run has a 600s idle timeout on WebSocket connections. The agent pipeline should complete well within this window.

**Rate limit errors (429):** The backend has a 5/minute rate limit per IP on case creation. LiteLLM is configured with 3 retries and exponential backoff for Vertex AI quota limits.
