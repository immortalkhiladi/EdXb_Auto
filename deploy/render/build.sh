#!/usr/bin/env bash
# Render build command:  bash deploy/render/build.sh   (see render.yaml)
# Installs the Python packages (backend/), builds the React app (frontend/; single-origin: the UI calls /api on its own host)
# and pre-compresses it so WhiteNoise can serve gzip/brotli files.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
pip install --upgrade pip
pip install -r backend/requirements.txt
if command -v npm >/dev/null 2>&1; then
  (cd frontend && npm ci && npm run build)
elif [ ! -f frontend/dist/index.html ]; then
  echo "npm is not available and frontend/dist is missing: set the service's Node version." >&2
  exit 1
else
  echo "npm not found: using the existing frontend/dist build."
fi
python -m whitenoise.compress frontend/dist || true   # gzip only unless brotli is installed; failure here is not fatal
