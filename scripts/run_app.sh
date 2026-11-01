#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$DIR"

echo "=========================================================="
echo " Starting Manuscript Integrity Studio..."
echo "=========================================================="

# Activate python virtual environment
source backend/venv/bin/activate

# Start backend FastAPI server in background
echo "-> Starting Backend API on http://127.0.0.1:8000"
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

# Trap signals to clean up background processes
trap "echo 'Stopping servers...'; kill $BACKEND_PID 2>/dev/null || true; exit 0" SIGINT SIGTERM EXIT

# Wait a second for backend to bind
sleep 1

# Start frontend Vite server
echo "-> Starting Frontend UI on http://localhost:5173"
cd frontend
npx vite --host 127.0.0.1 --port 5173
