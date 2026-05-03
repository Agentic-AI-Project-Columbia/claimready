# Deploy to GCP Cloud Run

Project: `agentic-ai-487000` · Region: `us-east1` · Model: Gemini 2.5 Flash via Vertex AI.

## One-time setup (already done if `gcloud services list` shows the four APIs)

```bash
gcloud config set project agentic-ai-487000
gcloud config set run/region us-east1

# Enable APIs (already enabled — listed for reference)
gcloud services enable \
  aiplatform.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com

# Create the Artifact Registry repo
gcloud artifacts repositories create claimready \
  --repository-format=docker \
  --location=us-east1 \
  --description="ClaimReady Docker images"

# Grant Cloud Run runtime SA access to Vertex AI
PROJECT_NUMBER=$(gcloud projects describe agentic-ai-487000 --format='value(projectNumber)')
gcloud projects add-iam-policy-binding agentic-ai-487000 \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/aiplatform.user"

# Grant Cloud Build SA the deploy + service-account-user roles
gcloud projects add-iam-policy-binding agentic-ai-487000 \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/run.admin"
gcloud projects add-iam-policy-binding agentic-ai-487000 \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"
```

## Deploy

From the project root (where `cloudbuild.yaml` lives):

```bash
gcloud builds submit \
  --config cloudbuild.yaml \
  --substitutions=_REGION=us-east1,_BACKEND_NAME=claimready-backend,_FRONTEND_NAME=claimready-frontend,_AR_REPO=claimready
```

That single command:

1. Builds & pushes the backend image to Artifact Registry
2. Deploys the backend to Cloud Run (2 CPU, 2 GiB, 600 s timeout, public)
3. Reads the backend's URL
4. Builds the frontend with `NEXT_PUBLIC_BACKEND_URL` baked in
5. Deploys the frontend (1 CPU, 512 MiB, public)

The two Cloud Run URLs are printed in the build log. Hit the frontend URL in a browser.

## Local dev

```bash
# Backend
cd backend
uv sync                                                # creates .venv and installs from uv.lock
source .venv/bin/activate                              # or: .venv\Scripts\activate on Windows
gcloud auth application-default login                  # one-time, for Vertex AI auth
export GCP_PROJECT_ID=agentic-ai-487000
export GCP_REGION=us-east1
uvicorn main:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm install
echo "NEXT_PUBLIC_BACKEND_URL=http://localhost:8000" > .env.local
npm run dev    # opens http://localhost:3000
```
