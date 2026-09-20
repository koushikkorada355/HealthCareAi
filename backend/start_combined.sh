#!/bin/bash
# Single-server start: internal Mock EHR + public backend.
# Render routes public traffic to $PORT only; EHR stays on loopback.
set -e
EHR_PORT="${EHR_PORT:-8001}"
APP_PORT="${PORT:-8000}"
echo "starting internal mock EHR on 127.0.0.1:${EHR_PORT}"
uvicorn mock_ehr_app:app --host 127.0.0.1 --port "${EHR_PORT}" &
echo "starting backend on 0.0.0.0:${APP_PORT} (MOCK_EHR_URL=${MOCK_EHR_URL:-http://127.0.0.1:8001})"
exec uvicorn app.main:app --host 0.0.0.0 --port "${APP_PORT}"
