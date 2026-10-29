# EDGAR Agents LLC — Automation Portal

React (Vite + Tailwind) front end · Django back end · PostgreSQL · deployed on Render. Browser-based SEC tools run
inside the portal: **Redline to GoFiler HTML**, **GoFiler HTML Converter**, **PPT & PDF Converter**, **SEC Form Type
Dashboard**. `backend/tools/` is the source of truth for the tools; `backend/portal/tools.py` registers them.

Longer guides: [`docs/DEPLOYMENT_GUIDE.md`](docs/DEPLOYMENT_GUIDE.md) (step by step, costs, domain),
[`docs/TOOL_FRAME_FIX.md`](docs/TOOL_FRAME_FIX.md) (how the tools are embedded), [`docs/SECURITY.md`](docs/SECURITY.md).

---

## 1. Backend (Django)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate            # Windows PowerShell:  .venv\Scripts\Activate.ps1   (cmd: .venv\Scripts\activate)
pip install -r requirements-dev.txt  # runtime + pytest (production: requirements.txt)
cp .env.example .env                 # Windows: copy .env.example .env
python manage.py migrate
python manage.py seed_users          # creates admin / Admin@123 only (dev). SEED_USER_COUNT=10 also adds md01 + user01..user10
python manage.py runserver 127.0.0.1:8000
```

`backend/.env` (never committed) — the variables that matter locally:

```ini
DJANGO_SETTINGS_MODULE=config.settings.local
DB_ENGINE=postgres            # or: sqlite   (quick start, no PostgreSQL needed)
DB_NAME=myapp_db
DB_USER=myapp_user
DB_PASSWORD=MyApp@123
DB_HOST=localhost
DB_PORT=5432
# FRONTEND_URL=http://localhost:3000     # base URL used in password-reset emails
# EMAIL_HOST= / EMAIL_PORT= / EMAIL_HOST_USER= / EMAIL_HOST_PASSWORD= / EMAIL_USE_TLS=true / DEFAULT_FROM_EMAIL=
```
Full list (production values included): `docs/DEPLOYMENT_GUIDE.md` §3.

Useful commands: `python manage.py create_admin --username <id> --email <email> --name "<Full Name>"` (production admin),
`python -m pytest tests -q` (tests, temporary SQLite), `python manage.py check --deploy` (production settings audit).

## 2. Frontend (React + Vite)

```bash
cd frontend
npm install                 # or: npm ci   (exact lockfile versions)
npm run dev                 # http://127.0.0.1:3000 — Vite proxies /api to Django on :8000
npm test                    # unit tests (node --test)
npm run build               # production build → frontend/dist (Django serves it; no source maps)
```

API base URL: `frontend/src/utils/constants.js` reads `VITE_API_BASE_URL` at **build** time and defaults to `/api`
(same origin — the default on Render, nothing to set). Only for split hosting create `frontend/.env.production`:
```ini
VITE_API_BASE_URL=https://api.example.com/api
```
and set `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, `FRAME_ANCESTORS` on the backend.

## 3. Database (PostgreSQL)

```sql
-- psql as a superuser, once:
CREATE USER myapp_user WITH PASSWORD 'MyApp@123';
CREATE DATABASE myapp_db OWNER myapp_user;
\c myapp_db
GRANT ALL ON SCHEMA public TO myapp_user;
```
Connection = the `DB_*` variables above (equivalent URL: `postgresql://myapp_user:MyApp@123@localhost:5432/myapp_db`).
Check: `psql -h localhost -U myapp_user -d myapp_db -c "\dt"` and http://127.0.0.1:8000/api/health → `{"status":"ok"}`.
Uploaded/generated files are stored **inside** the database (`STORAGE_BACKEND=database`), so one `pg_dump` backs up
everything: `pg_dump -h localhost -U myapp_user -d myapp_db -F c -f backup.dump`. More: `README_POSTGRESQL.md`.

## 4. Tools

| Tool (sidebar) | Route | API slug | File in `backend/tools/` |
| --- | --- | --- | --- |
| Redline to GoFiler HTML | `/redline-gofiler` | `redline-to-gofiler-html` | `Redline_to_GoFiler_HTML_v2.html` |
| GoFiler HTML Converter | `/html-converter` | `html-converter` | `GoFiler HTML Converter.html` |
| PPT & PDF Converter | `/converter` | `ppt-pdf-converter` | `PDF converter.html` |
| SEC Form Type Dashboard | `/sec-forms` | `sec-form-dashboard` | `SEC_Form_Type_Dashboard.html` |

A tool page is served by `GET /api/tools/<slug>/frame` (signed-in users only) with the bridge script and the brand
theme (`backend/portal/tool_theme.css`) injected; results are saved via `POST /api/process/<slug>`. To add or rename a
tool: put the file in `backend/tools/`, update the `Tool(...)` line in `backend/portal/tools.py`, and the matching
entries in `frontend/src/utils/rbac.js`, `components/layout/Sidebar.jsx`, `pages/Dashboard.jsx`, `routes/AppRoutes.jsx`.
The PPT & PDF Converter renders **PDFs**; for a `.ppt/.pptx` it asks you to export the deck to PDF first (browsers
cannot render PowerPoint).

## 5. Git / GitHub workflow

```bash
git status                                   # what changed
git add .                                    # stage everything (.gitignore keeps .env, .venv, node_modules, dist out)
git commit -m "feat: describe the change"
git pull origin main                         # bring in teammates' work first (rebase variant: git pull --rebase origin main)
git push origin main

# first time only (the folder is not a repository yet)
git init -b main
git remote add origin https://github.com/<org-or-user>/edgar-agents-portal.git
git push -u origin main

# branches
git checkout -b feature/login-panel          # create + switch
git switch main                              # switch back
git merge feature/login-panel                # merge into the current branch
git push origin feature/login-panel          # publish the branch (open a Pull Request on github.com)

# basic merge conflict
git pull origin main                         # "CONFLICT (content): Merge conflict in frontend/src/pages/Login.jsx"
#   open the file, keep what you want between <<<<<<< HEAD … ======= … >>>>>>> and delete the markers
git add frontend/src/pages/Login.jsx
git commit                                   # completes the merge (or: git merge --abort to back out)

# stash (park uncommitted work)
git stash                                    # save and clean the working tree
git pull origin main
git stash pop                                # bring the work back
git stash list / git stash drop              # inspect / discard
```
Every push runs `.github/workflows/ci.yml` (pytest, `npm test`, `npm run build`).

## 6. Deployment (Render)

`render.yaml` defines one **web service** (`edgar-agents-portal`, Python runtime) and one **PostgreSQL** database (`ea-db`).

| Setting | Value |
| --- | --- |
| Build command | `bash deploy/render/build.sh` (pip install → `npm ci && npm run build` → pre-compress) |
| Start command | `bash backend/startup.sh` (`python manage.py migrate` → gunicorn on `$PORT`) |
| Health check | `/api/health` |
| Required env vars | `DJANGO_ALLOWED_HOSTS` (your domain), `FRONTEND_URL`, `EMAIL_*` (password-reset mail). `DJANGO_SECRET_KEY` is generated by Render — never change it. `DB_*`, `ADMIN_MFA_REQUIRED=true`, `STORAGE_BACKEND=database` come from the blueprint |

Render → **New → Blueprint** → select the GitHub repo → fill the prompted variables → **Apply**. Afterwards, in the
service **Shell**: `cd backend && python manage.py create_admin --username <id> --email <email> --name "<Full Name>"`.
Every push to the connected branch redeploys; roll back from *Events*. Custom domain, HTTPS, costs (~$13–50/month)
and troubleshooting: `docs/DEPLOYMENT_GUIDE.md` §7–11.

## 7. How to update a password

| Who | How |
| --- | --- |
| Your own password | sign in → **Settings → Security → Change password** (`POST /api/auth/change-password`) |
| Forgot it | login page → **Forgot password?** → reset link by email (needs `EMAIL_*` configured) → `/reset-password` |
| Admin resets a user | **Admin Console → Users → Reset password** (also unlocks the account and signs it out everywhere) |
| From the terminal (any account) | `cd backend && python manage.py changepassword <username>` (Django built-in; Render: run it in the service Shell) |
| Lost every admin | `python manage.py create_admin --username <id> --email <email> --name "<Full Name>"` |
| Database password | change it in Render (database page) or `ALTER USER myapp_user WITH PASSWORD '…';` locally, then update `DB_PASSWORD` |

Dev accounts created by `seed_users` use well-known passwords and are refused under production settings.

## 8. Branding

Design tokens live in `frontend/src/index.css` (`@theme`): navy `#0B1F3A` / `#14284B` for backgrounds, header and
sidebar; turquoise `#1DC8CD` / `#2EE6D6` for accents, buttons and active states; light neutrals for content.
The tool pages are themed through `backend/portal/tool_theme.css`. Login-page company updates are read from
`backend/portal/linkedin_updates.json` (`GET /api/linkedin-updates`) — edit that file to publish a new item
(`title`, `date`, `text`, `link`); the "Follow us on LinkedIn" button points at the company page.
