#!/bin/bash
set -e

# Run database migrations
echo "Running database migrations..."
alembic upgrade head

# Start the application
echo "Starting uvicorn server..."
exec uvicorn app.server:app --host 0.0.0.0 --port 8080
