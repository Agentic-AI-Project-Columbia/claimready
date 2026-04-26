#!/usr/bin/env bash
# Run backend + frontend locally.
# Usage: ./dev.sh
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

# ── Backend ────────────────────────────────────────────────────────────────────
echo "Starting backend on http://localhost:8000 ..."
cd "$ROOT/backend"
export GCP_PROJECT_ID="${GCP_PROJECT_ID:-agentic-ai-487000}"
export GCP_REGION="${GCP_REGION:-us-east1}"
uv run uvicorn main:app --reload --port 8000 &
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
