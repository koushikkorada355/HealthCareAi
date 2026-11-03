#!/bin/bash
# Single-server start: backend only.
set -e
APP_PORT="${PORT:-8000}"
echo "starting backend on 0.0.0.0:${APP_PORT}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${APP_PORT}"
