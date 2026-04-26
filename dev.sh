#!/usr/bin/env bash
# Run backend + frontend locally.
# Usage: ./dev.sh
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

# ── Backend ────────────────────────────────────────────────────────────────────
echo "Starting backend on http://localhost:8000 ..."
cd "$ROOT/backend"
# Use whatever gcloud project is active on this machine
GCP_PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
export GCP_PROJECT_ID
export GCP_REGION="${GCP_REGION:-us-east1}"
export VERTEXAI_PROJECT="${GCP_PROJECT_ID}"
export GOOGLE_CLOUD_QUOTA_PROJECT="${GCP_PROJECT_ID}"
export OPENAI_AGENTS_DISABLE_TRACING=1   # no OpenAI key needed; disable SDK tracing
echo "Using GCP project: $GCP_PROJECT_ID"
uv run uvicorn main:app --reload \
  --reload-dir "$ROOT/backend" \
  --reload-exclude "$ROOT/backend/.venv" \
  --reload-exclude "*.pyc" \
  --port 8000 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

# ── Frontend ───────────────────────────────────────────────────────────────────
echo "Starting frontend on http://localhost:3000 ..."
cd "$ROOT/frontend"
echo "NEXT_PUBLIC_BACKEND_URL=http://localhost:8000" > .env.local

# Install npm deps if needed
if [ ! -d node_modules ]; then
  echo "Installing frontend dependencies..."
  npm install
fi

npm run dev &
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"

echo ""
echo "══════════════════════════════════════════"
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:3000"
echo "  Press Ctrl+C to stop both."
echo "══════════════════════════════════════════"

# Wait and kill both on Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
