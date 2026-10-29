# Targeted performance / preview / Render / audit / upload update

* **Speed:** no session DB write on every request (idle timeout slides at most once a minute); tool access read once per request;
  tool pages cached and gzipped; hashed assets cached for a year; threaded gunicorn workers; one `/auth/me` on focus instead of two.
* **Eye icon:** ZIP output packages (PPT/PDF converter) now preview: the stored HTML is shown with its images embedded.
  Text/XML/HTML previews carry the real charset. Stored and downloaded files are never modified.
* **Render:** `render.yaml`, `deploy/render/`, `docs/RENDER_DEPLOYMENT.md`; uploads on a persistent disk. Removed `deploy/azure/*`
  (deploy scripts, Static Web Apps config), `requirements-azure.txt`, `AzureBlobStorage`, `STORAGE_BACKEND`/`AZURE_STORAGE_*`, Azure doc.
* **Audit Log page:** lists only successful login/logout (user, event, time). Other events are still recorded, not listed. MFA sign-ins now log `auth.login`.
* **Uploads:** files validated in place and streamed to disk once (fsync, size check) before success; one DB insert instead of insert + update.

# List of code changes (what was changed and why)

## Admin-controlled tool access (latest)
* **Who may use which tool** is stored in the database (new table `portal_usertoolaccess`, migration `0003_user_tool_access.py`: one row per user + tool, unique together). The migration gives every existing USER all four tools, so nothing changes until the admin edits it. New users get all four unless the admin picks others. ADMIN and MD always have all four (nothing stored, they cannot be restricted).
* **Admin Console > Tool Access** (`components/admin/ToolAccessPanel.jsx`, `GET/PUT /api/admin/tool-access`, ADMIN only): every user with a checkbox per tool, Save Changes (all-or-nothing, audited as `admin.user.tools`), Reset (discard edits), search, success/error messages. MD gets no permission-management rights.
* **Enforced by Django on every request** (`User.allowed_tool_slugs()`, `services.ensure_tool_access`): opening a tool (`GET /api/tools/<slug>/frame` -> 403), uploading/processing (`POST /api/process/<slug>` -> 403 before anything is read or stored), `GET /api/tools` (only your tools), and the documents of a tool (list hides them; view/download/delete -> 403) while access is revoked. Checked against the database each time, so a revoke works at once, also for signed-in users. Denied attempts are written to the audit log (`tool.access`). MD/ADMIN document rules are unchanged.
* **React** only reflects it: sidebar, dashboard cards and tool routes use `user.tools` (refreshed on focus and when a tool is opened).
* `seed_users`: `user01` gets only the first two tools (the example); everyone else all of them.

## Default accounts + DevTools deterrent
* `seed_users` now creates `admin` / `Admin@123`, `user01`–`user10` / `User@123` (and `md01` / `Md@123`); `python manage.py seed_users --reset` resets those passwords (and unlocks) on a database that already has users. Refused with production settings. These defaults are longer than the 4–6 character policy: the policy applies when a password is created or changed, so the first change must follow it.
* The F12 / Ctrl+Shift+I/J/C / Ctrl+U / right-click deterrent is now on in `npm run dev` too (opt out with `VITE_DEVTOOLS_DETERRENT=false`); the four tool pages get it from the server-injected bridge (new test for each tool). Production builds have no source maps (`sourcemap: false`, plus `css.devSourcemap: false`); this is a UI deterrent only, security stays on the backend.

## Earlier update: access control, password policy, forgot password, table fit
* **Roles ADMIN / MD / USER** (`models.py` + migration `0002_user_role_md.py`, `api.py`, `views/documents.py`, `views/admin_api.py`, `src/utils/rbac.js`): ADMIN and MD can list/view/download every user's documents (`GET /api/admin/documents`, new **All Documents** page); only ADMIN can delete other users' documents, manage users, see the audit log and the overview; USER sees only their own documents. Every check is on the server; the React route guards are convenience only.
* **Password policy 4–6 chars + uppercase + digit + special** (`security.py` backend, `src/utils/passwordPolicy.js` frontend), applied to change-password, admin create/reset user, forgot-password reset, `create_admin`, `seed_users`. Messages say exactly what is missing / the length problem. Existing users keep their current password until it is changed (login does not re-check the policy).
* **Forgot password** (`views/auth.py`, `ForgotPasswordModal.jsx`, `pages/ResetPassword.jsx`): `POST /api/auth/forgot-password` emails a signed link (Django token bound to the password hash, 30 min, single use); `POST /api/auth/reset-password` validates link + policy, stores an Argon2id hash, signs the user out everywhere and unlocks the account. Errors for invalid email / unknown account / delivery failure; rate limited per IP and per account. New env settings: `EMAIL_*`, `FRONTEND_URL`, `PASSWORD_RESET_*` (see `.env.example`).
* **Documents table** (`components/documents/DocumentsTable.jsx`): fixed layout with percentage columns, wrapping/ellipsis, no `overflow-x-auto` from tablet width up; phones scroll sideways inside the card. Filters, search, dates, Apply/Reset and badges unchanged.
* Shortcut/right-click deterrent and `sourcemap: false` were already in place and are unchanged. `seed_users` now creates admin + `md01` + 50 users. Removed: the old "ask your administrator" reset text in `Login.jsx`.

Requested: Azure deployment **without Docker and GitHub**, PostgreSQL with Django, DevTools-shortcut/right-click deterrents on all pages, production security, all four workflows preserved.

## Backend — now Django (`backend/`)
* New Django project: `config/settings/{base,local,production,test}.py`, `portal/` app (models, views, middleware, validation, storage, management commands), `manage.py`, `startup.sh` (Azure startup: migrate + gunicorn).
* **Replaces the FastAPI backend delivered earlier in this conversation** (same API paths and JSON shapes, so the React app needed only small changes). Roles `ADMIN`/`USER`, ownership rules, MFA, audit log, retention behave as before.
* PostgreSQL via environment variables (`DB_*`); local and production settings separated; production refuses `localhost`, weak/missing secrets, `ADMIN_MFA_REQUIRED=false`.
* Django migrations replace Alembic (`portal/migrations/0001_initial.py`).
* Docker files removed; GitHub workflow removed (`deploy/azure/*.sh` deploy by zip / Static Web Apps CLI).

## The four workflows (`backend/tools/*.html`)
* **Original tool HTML files are unchanged on disk.** At serve time Django injects a small bridge script that (a) forwards generated files to the parent page for upload and (b) applies the shortcut/right-click deterrent. Processing logic is untouched.
* Served only to signed-in users, in a sandboxed frame; outputs recorded per user (`POST /api/process/<tool>`), downloadable from *My Documents*.

## Frontend (`src/`)
* `services/api.js`: Django CSRF handling (token from `/auth/csrf`, `X-CSRFToken` header, one automatic retry); `authService.js` clears the token on login/logout.
* `utils/devtoolsGuard.js` + `hooks/useDevToolsProtection.js` (applied in `App.jsx` for every page) + 5 unit tests; off in `npm run dev` unless `VITE_DEVTOOLS_DETERRENT=true`.
* `utils/constants.js`: `VITE_API_BASE_URL` for split hosting. Home/About pages removed earlier; login-first routing; Admin Console; My Documents.
* Production build: source maps disabled (`vite.config.js`), no secrets (test-verified).

## Added
* `deploy/azure/` (package/deploy backend, deploy frontend, pre-release checks, Static Web Apps config), `deploy/vm/` (shared dev VM, developer accounts, source backups), `README_AZURE.md`, `README_POSTGRESQL.md`, `docs/`.

## Audit retention, delete user, frontend/backend split
* Audit rows older than `AUDIT_RETENTION_DAYS` (default **30**) are deleted automatically by the in-process scheduler (`middleware.PurgeSchedulerMiddleware`, every `AUDIT_CLEANUP_INTERVAL_HOURS`, default 6, plus once shortly after start). Manual/cron run: `python manage.py purge_audit_logs`.
* `DELETE /api/admin/users/<id>` (ADMIN only) + **Delete** button with confirmation in Admin Console > Users. Refuses own account and the last active admin; removes the user's documents (and stored files) and tool-access rows; audit rows are kept. Audited as `admin.user.delete`.
* React app now lives in `frontend/` (`npm` commands run there, build output `frontend/dist`); Django in `backend/`. `render.yaml` is unchanged (it calls `deploy/render/build.sh`).


## Documents are now stored in the database
* Root cause of "eye icon works, then fails after 1-2 days": files were written only to the server's local disk
  (`LocalStorage`). Any restart/redeploy/instance change (or a missing persistent disk) erased them, while the database
  row still existed, so the preview returned "File not available".
* `portal/storage.py` now has `DatabaseStorage` (default, `STORAGE_BACKEND=database`): files are saved in
  `StoredFile` / `StoredFileChunk` tables (1 MB chunks, one transaction per file). Migration `0004_stored_files`.
* Old files still on disk keep working (read fallback). Copy them into the DB once with
  `python manage.py migrate_files_to_db`. Files already deleted from disk cannot be recovered; re-process those documents.
* Tests: `test_files_are_stored_in_the_database_and_survive_loss_of_local_disk`, `test_legacy_local_files_still_served_and_migrated`.
* `python manage.py check_files` lists documents whose file is missing and shows the active storage backend.

## Tool UI redesign (frontend only)
* Restyled the four tool pages in `backend/tools/` (EDGAR Deck Converter,
  Redline to GoFiler HTML) with a shared plain HTML/CSS design system: gradient brand, soft cards, icon set (inline SVG),
  light + dark themes (system preference, `data-theme`, and Redline's own Light/Dark switch), responsive layouts.
* No React or new dependency: still vanilla HTML/CSS/JS, one font family added (Plus Jakarta Sans via the already-allowed
  Google Fonts host). Every original `<script>` block, element id, API call and the bridge are byte-for-byte unchanged;
  backend, database, authentication and the React app were not touched.
