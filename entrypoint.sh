#!/bin/bash
set -euo pipefail

# Start the hardened backend wrapper. The wrapper preserves the original API
# while adding authentication, rate limiting, body limits and bounded sockets.
echo "Starting Backend..."
cd /app/backend
uv run uvicorn src.api.hardened:app --host 0.0.0.0 --port 8000 --proxy-headers &
BACKEND_PID=$!

# Start the Frontend
echo "Starting Frontend..."
cd /app/frontend
npm run preview -- --host 0.0.0.0 --port 5173 &
FRONTEND_PID=$!

cleanup() {
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup SIGINT SIGTERM EXIT

wait -n "$BACKEND_PID" "$FRONTEND_PID"
