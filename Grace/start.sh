#!/usr/bin/env bash
# Exit on error
set -e

echo "=== Environment Diagnostics ==="
echo "Python path:"
which python
echo "Alembic in pip freeze:"
python -m pip freeze | grep alembic
echo "Alembic path:"
which alembic || echo "alembic not found on PATH"
echo "==============================="

echo "Running migrations..."
if command -v alembic &> /dev/null; then
    echo "Running alembic from PATH..."
    alembic upgrade head
else
    echo "Alembic not in PATH, falling back to absolute venv path..."
    /opt/render/project/src/.venv/bin/alembic upgrade head
fi

echo "Starting Uvicorn server..."
# Use exec so uvicorn takes over the process and handles shutdowns properly
exec python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
