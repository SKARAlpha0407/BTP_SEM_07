#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

./backend/.venv/bin/python -m uvicorn backend.app.main:app \
  --host 0.0.0.0 --port 8000 --reload --reload-dir backend/app &

BACKEND_PID=$!
trap "kill $BACKEND_PID 2>/dev/null || true" EXIT

cd frontend
npx next dev --webpack
