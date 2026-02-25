#!/bin/bash
# Exit on error
set -e

echo "Ensuring alembic is installed..."
python -m pip install alembic

echo "Running migrations..."
# Alembic doesn't support 'python -m alembic', so we run its main function directly:
python -c "import sys; from alembic.config import main; sys.argv[0] = 'alembic'; sys.exit(main())" upgrade head

echo "Starting Uvicorn server..."
# Use exec so uvicorn takes over the process and handles shutdowns properly
exec python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
