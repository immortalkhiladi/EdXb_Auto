#!/usr/bin/env bash
# Run before every release (replaces a CI pipeline): tests, dependency audits, production build.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
echo "== backend tests =="; (cd backend && python -m pytest tests -q)
echo "== Django deployment check (production settings) =="
(cd backend && DJANGO_SETTINGS_MODULE=config.settings.production DJANGO_SECRET_KEY="$(python -c 'import secrets;print(secrets.token_urlsafe(64))')" \
   DJANGO_ALLOWED_HOSTS=api.example.com ADMIN_MFA_REQUIRED=true DB_NAME=x DB_USER=x DB_PASSWORD=x DB_HOST=db.example.com python manage.py check --deploy)
echo "== python dependency audit =="; (cd backend && python -m pip_audit -r requirements.txt)
echo "== frontend tests =="; (cd frontend && npm test)
echo "== npm dependency audit =="; (cd frontend && npm audit --omit=dev --audit-level=high)
echo "== production build (no source maps) =="; (cd frontend && npm run build)
test -z "$(find frontend/dist -name '*.map')" || { echo "FAIL: source maps found in dist/"; exit 1; }
echo "ALL CHECKS PASSED"
