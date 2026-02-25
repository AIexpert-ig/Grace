#!/usr/bin/env bash
set -e

echo "Running database migrations..."
python -m alembic upgrade head

echo "Starting uvicorn server..."
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
