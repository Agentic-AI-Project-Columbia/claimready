# Deploy to GCP Cloud Run

Project: `csee4121-s26-492100` · Region: `us-east1` · Model: Gemini 2.5 Flash via Vertex AI.

## One-time setup (already done if `gcloud services list` shows the four APIs)

```bash
gcloud config set project csee4121-s26-492100
gcloud config set run/region us-east1

# Enable APIs (already enabled — listed for reference)
gcloud services enable \
  aiplatform.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com

# Create the Artifact Registry repo
gcloud artifacts repositories create quietcase \
  --repository-format=docker \
  --location=us-east1 \
  --description="Quietcase Docker images"

# Grant Cloud Run runtime SA access to Vertex AI
PROJECT_NUMBER=$(gcloud projects describe csee4121-s26-492100 --format='value(projectNumber)')
gcloud projects add-iam-policy-binding csee4121-s26-492100 \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/aiplatform.user"

# Grant Cloud Build SA the deploy + service-account-user roles
gcloud projects add-iam-policy-binding csee4121-s26-492100 \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/run.admin"
gcloud projects add-iam-policy-binding csee4121-s26-492100 \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"
```

## Deploy

From the project root (where `cloudbuild.yaml` lives):

```bash
gcloud builds submit \
  --config cloudbuild.yaml \
  --substitutions=_REGION=us-east1,_BACKEND_NAME=quietcase-backend,_FRONTEND_NAME=quietcase-frontend,_AR_REPO=quietcase
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
python -m venv .venv && source .venv/bin/activate     # or: .venv\Scripts\activate on Windows
pip install -r requirements.txt
gcloud auth application-default login                  # one-time, for Vertex AI auth
export GCP_PROJECT_ID=csee4121-s26-492100
export GCP_REGION=us-east1
uvicorn main:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm install
echo "NEXT_PUBLIC_BACKEND_URL=http://localhost:8000" > .env.local
npm run dev    # opens http://localhost:3000
```
