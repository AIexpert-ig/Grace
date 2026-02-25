#!/bin/bash
# Exit on error
set -e

echo "Ensuring alembic is installed..."
python -m pip install alembic

echo "Running migrations..."
python -m alembic upgrade head

echo "Starting Uvicorn server..."
# Use exec so uvicorn takes over the process and handles shutdowns properly
exec python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
