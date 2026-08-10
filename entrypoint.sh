#!/bin/sh
set -e

PORT="${PORT:-8080}"

echo "ScreensaverKindle starting on 0.0.0.0:${PORT}"
python -c "from app.main import app; print('app import ok')"

exec gunicorn \
  --bind "0.0.0.0:${PORT}" \
  --workers 1 \
  --threads 4 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile - \
  app.main:app
