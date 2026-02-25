#!/usr/bin/env sh
set -e

echo "Requirements file content:"
cat requirements.txt
alembic upgrade head
cd /opt/render/project/src

echo "Python executable:"
python -c "import sys; print(sys.executable)"

echo "Alembic installed?"
python -m pip show alembic || true

echo "Running migrations..."
python -m pip install alembic
python -m alembic upgrade head

echo "Starting server..."
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-10000}"
