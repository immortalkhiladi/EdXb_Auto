#!/usr/bin/env bash
# Start the Django app for YOUR testing from the shared project, with YOUR own data folder (no collisions).
#   ff-run [port]      then forward the port:   ssh -L 8000:127.0.0.1:8000 <you>@<vm>   -> http://127.0.0.1:8000
# Database: by default a private SQLite file in ~/ff-data. For the dev PostgreSQL put DB_ENGINE=postgres, DB_NAME, DB_USER,
# DB_PASSWORD, DB_HOST, DB_SSLMODE=require in ~/ff-data/.env (mode 600) - never inside the shared project folder.
set -euo pipefail
PORT="${1:-8000}"
export DATA_DIR="$HOME/ff-data"
export DB_ENGINE="${DB_ENGINE:-sqlite}"
[ -f "$DATA_DIR/.env" ] && set -a && . "$DATA_DIR/.env" && set +a
cd /srv/ff/project/backend
/srv/ff/venv/bin/python manage.py migrate --noinput
/srv/ff/venv/bin/python manage.py seed_users
exec /srv/ff/venv/bin/python manage.py runserver "127.0.0.1:$PORT"
