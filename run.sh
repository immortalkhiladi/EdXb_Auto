#!/usr/bin/env bash
# One-command local start (macOS / Linux): Python env, database migrations, sample users, server.
set -e
cd "$(dirname "$0")"
PY=${PYTHON:-python3}
[ -d backend/.venv ] || "$PY" -m venv backend/.venv
backend/.venv/bin/pip install -q -r backend/requirements.txt
if [ ! -f backend/.env ]; then
  cp backend/.env.example backend/.env
  echo "Created backend/.env with the local PostgreSQL settings. Edit it if your database differs."
fi
if [ ! -f frontend/dist/index.html ]; then
  command -v npm >/dev/null || { echo "frontend/dist is missing and Node.js is not installed. Install Node 18+."; exit 1; }
  (cd frontend && npm install && npm run build)
fi
cd backend
if ! .venv/bin/python manage.py migrate --noinput; then
  echo
  echo "Could not prepare the database. Check backend/.env (DB_HOST, DB_NAME, DB_USER, DB_PASSWORD) and that PostgreSQL is running."
  echo "See README_POSTGRESQL.md - or set DB_ENGINE=sqlite in backend/.env for a quick start without PostgreSQL."
  exit 1
fi
.venv/bin/python manage.py seed_users
echo "Starting on http://127.0.0.1:8000  (Ctrl+C to stop)"
exec .venv/bin/python manage.py runserver 127.0.0.1:8000 --noreload
