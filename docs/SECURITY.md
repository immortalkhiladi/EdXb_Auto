# Security documentation

> Nothing here claims the application is "secure" or "production-ready" merely because it uses cookies, HTTPS or minification. This file lists what is implemented, how it was verified, and what is still open.

## Controls implemented (and where)

| Area | Control | Code / test |
| --- | --- | --- |
| Passwords | Django **Argon2id** hasher only; default dev accounts `admin`/`user01..user10` use the documented well-known passwords (`seed_users`, refused with production settings: change them, use `create_admin` in production); policy for new/changed passwords **4–6 characters with ≥1 uppercase, ≥1 digit and ≥1 special character** (required by the business; short passwords are weak, so login rate limiting + lockout stay on and MFA is recommended); forgot-password uses a signed, expiring, single-use emailed link (no password is ever sent or stored in clear text); never logged; no hardcoded or default passwords (seed generates random ones) | `settings/base.py`, `security.py`, `test_passwords_are_argon2id_hashed`, `test_no_hardcoded_credentials_in_source` |
| Database credentials | Only from environment variables (`.env` locally, Render environment variables in production); production refuses `localhost`, missing values; SSL to PostgreSQL | `settings/production.py`, `test_production_settings_refuse_insecure_configuration` |
| Sessions | Django DB sessions in an **HttpOnly, SameSite=Strict** cookie (`Secure` in production); idle (30 min, sliding) + absolute (8 h) expiry; destroyed on logout; revoked on password change, deactivation, admin reset | `views/auth.py`, `api.py`, `test_logout_*`, `test_session_absolute_lifetime_enforced`, `test_admin_password_reset_signs_the_user_out_everywhere` |
| CSRF | Django CSRF token (kept in the session, delivered by `GET /api/auth/csrf`) required on every write, Origin checked against `CSRF_TRUSTED_ORIGINS` | `test_csrf_token_required_*`, `test_foreign_origin_rejected` |
| Brute force | per-IP rate limit, per-account lockout (5 failures → 15 min), generic error text, dummy-hash timing equalisation | `test_lockout_*`, `test_login_rate_limit` |
| MFA | TOTP for admins; mandatory in production (`ADMIN_MFA_REQUIRED` enforced); secret encrypted at rest; one-time codes; a pending-MFA session cannot call any API; session rotated after MFA | `test_admin_mfa_enrolment_and_login` |
| RBAC | `@admin_required` / `@api_login_required` on every protected view; role changes only by admins | `test_regular_users_are_forbidden_from_every_admin_endpoint`, `test_user_cannot_escalate_own_role` |
| Ownership / IDOR | owner filter comes from the session identity; one `get_accessible()` for get/view/download/delete; identical 404 for foreign or missing documents; owner never read from the request; random 128-bit ids | `test_idor_*`, `test_client_cannot_pick_the_owner`, `test_listing_params_cannot_widen_scope` |
| Uploads | size limit while reading chunks + request-size middleware; extension allow-list per workflow; **content** checks (PDF header, OOXML structure, OLE signature, text sniffing); zip-slip / entry-count / expansion / ratio checks; sanitised names; random storage keys; failures recorded for admins | `validation.py`, `test_content_is_inspected_*`, `test_zip_bomb_and_zip_slip_rejected`, `test_oversize_upload_rejected` |
| Storage | PostgreSQL chunks (`STORAGE_BACKEND=database`) or a private directory (0700/0600); no public URL; access only through authorised API; path-traversal guard | `storage.py` |
| Preview safety | uploaded HTML served with `CSP: sandbox; default-src 'none'`, XML/CSV as text, `nosniff`; frontend iframe adds `sandbox=""` | `test_view_serves_sandboxed_preview_and_refuses_binary` |
| Tool pages | served only after authentication; response CSP + iframe `sandbox` (scripts, same-origin, downloads, modals, popups, forms); `default-src 'none'`, `connect-src` limited to `blob:`/`data:`, `frame-src 'self' blob: data:`; the session cookie is HttpOnly and the tool pages are first-party code (see `docs/TOOL_FRAME_FIX.md`) | `views/tools.py`, `test_tool_pages_only_*` |
| HTTPS / headers (production) | `SECURE_SSL_REDIRECT`, HSTS (2 y), Secure cookies, `nosniff`, `no-referrer`, COOP, frame control, CSP on app pages, `no-store` on API; `manage.py check --deploy` clean | `settings/production.py`, `middleware.py`, `test_production_enables_https_*`, `test_django_deploy_check_has_no_warnings` |
| Error handling / logging | generic JSON errors (no stack traces/paths to clients), details only in the server log; no request bodies/passwords logged; DEBUG off in production | `middleware.py`, `test_unhandled_errors_do_not_leak_details` |
| Database access | Django ORM only (parameterised); LIKE wildcards escaped | `test_search_filter_and_pagination` (incl. injection string) |
| Audit | actor, action, resource id, outcome, IP, time for login/MFA/logout/password change/processing/view/download/delete/admin changes and cross-user admin access; no secrets or file contents | `services.audit`, `test_audit_log_covers_*` |
| Frontend bundle | production build has **no source maps**; no secrets (asserted); session not readable by JS | `test_frontend_bundle_has_no_secrets_or_sourcemaps` |
| Split hosting | CORS only for configured origins with credentials; frames embeddable only by `FRAME_ANCESTORS` | `test_cors_*`, `test_frame_ancestors_*` |
| Supply chain | `pip-audit` + `npm audit` clean when last run; part of `deploy/render/pre-release-check.sh` | `docs/TEST_RESULTS.md` |

### DevTools shortcuts and right-click (deterrent — not security)
On every page (`src/hooks/useDevToolsProtection.js`, logic in `src/utils/devtoolsGuard.js`, unit-tested) and inside each tool page (injected bridge script) the app blocks **F12, Ctrl+Shift+I / J / C (Cmd+Option on Mac), Ctrl+U, Ctrl+Shift+K** and the **context menu**. This does **not** stop anyone: the browser menu, `view-source:` URLs, browser extensions or network tools still work, and the code the browser receives can always be read. It is intentionally not relied upon; confidential logic, authentication, authorisation, database access and secrets stay on the Django backend, source maps are disabled, and storage is private. Not covered: the sandboxed *document preview* iframe (it must not run scripts at all).

## Known gaps and residual risks
1. **Workflow conversion logic still runs in the browser** (the tools are unchanged, as requested); only outputs are validated and stored server-side. A user could submit a fabricated output for their own account (still content-validated; visible only to them/admin). Server-side conversion would require porting the tool code.
2. **Processing status** is tracked around upload/validation, not around the conversion itself.
3. **No malware scanning** of uploads (use Microsoft Defender for Storage / ClamAV).
4. **Rate limiting is in-memory per worker process**; behind several workers/instances the effective limit multiplies (use Front Door/WAF or a shared store).
5. **No self-service email password reset**; admin-initiated reset only. No forced password change for seeded users; no MFA recovery codes (admins can reset MFA).
6. **Tool frames need `unsafe-inline`/`unsafe-eval`** because the supplied tools use them; contained by the sandbox CSP (`connect-src` limited to `blob:`/`data:`, no `frame-ancestors` beyond the UI origin).
7. **Render deployment is untested here**: `render.yaml` and the build/start scripts were validated locally (settings checks, tests) but not run on Render, and the dev-VM scripts were never run. The Django app itself was run locally on production settings with gunicorn + `startup.sh` + real PostgreSQL.
8. **The tool frames were not exercised in a real browser** here (iframe sandbox + CSP + bridge + cross-origin `postMessage`); HTTP behaviour is tested.
9. **No Git / no CI**: history is nightly archives + VM backup; concurrent edits of one file can overwrite each other; releases are manual (`pre-release-check.sh`).
10. Audit log immutability: rows live in the application database; forward them to a write-once store for tamper-resistance.
11. Login-page marketing/help text is carried over from the original project.
