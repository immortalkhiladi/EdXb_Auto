# Deploying to Render (summary)

> Superseded by **`docs/DEPLOYMENT_GUIDE.md`** (step-by-step, with GitHub, domain, costs). Kept as a short reference.

One web service serves the API **and** the built React app from a single origin (cookies stay `SameSite=Strict`);
PostgreSQL is a Render database and also holds the uploaded/generated files (`STORAGE_BACKEND=database`).

## 1. Create the services
1. Push this repository to GitHub/GitLab and in Render choose **New > Blueprint**; select the repo (`render.yaml`).
2. Fill the `sync: false` variables: `DJANGO_ALLOWED_HOSTS` (custom domain, if any), `FRONTEND_URL`, `EMAIL_*`.
   `DJANGO_SECRET_KEY` is generated once - never change it later (it signs sessions and encrypts MFA secrets).
3. The first deploy runs `deploy/render/build.sh` (pip install, `cd frontend && npm ci && npm run build`, pre-compression) and then
   `backend/startup.sh` (`migrate`, gunicorn with threaded workers). Health check: `/api/health`.
4. Create the first administrator once from the service **Shell**: `cd backend && python manage.py create_admin ...`.

## 2. Persistent storage
The container filesystem is erased on every deploy/restart, so files are stored **inside PostgreSQL**
(`STORAGE_BACKEND=database`, default) and no disk is mounted. Only when migrating files from an older disk-based
deployment: add a disk (`/var/data`), set `STORAGE_LOCAL_DIR=/var/data/storage`, copy the files in, run
`python manage.py migrate_files_to_db`, then remove the disk.

## 3. Variables
Same names as before (`README.md`). Render-specific: `RENDER`, `RENDER_EXTERNAL_HOSTNAME` (set by Render; the host is
allowed automatically), `DB_*` (wired to the database by the blueprint), `WEB_CONCURRENCY`, `GUNICORN_THREADS`.
Removed: `AZURE_STORAGE_*`.

## 4. Release check
`deploy/render/pre-release-check.sh` runs tests, dependency audits and the production build.
