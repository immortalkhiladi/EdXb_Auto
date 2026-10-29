# Architecture and data flow

```mermaid
flowchart LR
  B[Browser] -->|HTTPS| UI[React UI<br/>served by Django (Layout B)<br/>or a separate static host (Layout A)]
  B -->|HTTPS + HttpOnly SameSite=Strict session cookie + CSRF token| API[Render web service<br/>Django + gunicorn<br/>auth - roles - validation - audit]
  API -->|TLS, private network| PG[(Render PostgreSQL<br/>users - sessions - documents - audit log)]
  B -. sandboxed iframe .-> TOOL[Tool page served by Django<br/>opaque origin, no cookie access]
  TOOL -- postMessage(file) --> B
```
Locally the same code runs with `config.settings.local` and a local PostgreSQL (or SQLite). Render layout: `docs/RENDER_DEPLOYMENT.md`.

## Layers
| Layer | Where | Responsibility |
| --- | --- | --- |
| Frontend | `frontend/src/` → `frontend/dist/` | UI, client-side validation, API calls, route guards (usability only), DevTools-shortcut deterrent |
| API | `backend/portal/` | authentication, authorisation (roles, ownership), upload validation, audit, retention |
| Settings | `backend/config/settings/` | `base` (shared) · `local` · `production` (refuses insecure config) · `test` |
| Tool pages | `backend/tools/` | the four browser tools, served only to authenticated users inside a sandbox |
| Database | PostgreSQL (SQLite optional locally) | metadata, users, sessions, audit — no file bytes |
| File storage | PostgreSQL chunks (`STORAGE_BACKEND=database`); local directory optional | original + output files under random keys |

## Flow: running a workflow
1. `GET /api/tools/{slug}/frame` (session required) returns the tool HTML with an injected bridge script and a sandbox CSP.
2. The tool converts the file **in the browser** (original, unchanged logic). The bridge forwards the generated file (and the matching source file) to the parent page via `postMessage`; the tool frame has no cookie/storage access.
3. The parent page uploads both with `POST /api/process/{slug}` (session cookie + CSRF header).
4. Django sets the owner **from the session**, checks size, extension **and content signature**, stores the files under random keys, writes a `Document` row and an audit record.
5. `GET /api/documents` always filters by the signed-in user. View/download/delete share one function (`get_accessible`) that returns 404 for other users' documents; admins pass it and cross-user access is audited.

## Flow: login
`POST /api/auth/login` → IP rate limit → Argon2id check (dummy hash for unknown users) → lockout counter → for MFA users a *pending* marker is stored in a fresh session → `POST /api/auth/mfa/verify` (TOTP, one-time use) → `login()` rotates the session key and CSRF token. Sessions are Django database sessions: sliding idle timeout (30 min), absolute lifetime (8 h), revoked by logout, password change, deactivation and admin reset (`session_epoch`).

## Roles
`USER`: own documents. `ADMIN`: all documents, users, audit logs, health. Developer / cloud-operator access is **not** an application role — it is Render team access + the dev VM groups, so website admins get no access to code or servers.
