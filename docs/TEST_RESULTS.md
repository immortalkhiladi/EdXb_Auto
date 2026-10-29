# Test results and acceptance checklist

Run date: 2026-10-12. Environment: Python 3.12, Django 5.2 LTS, Node 22.

| Check | Result |
| --- | --- |
| `pytest backend/tests` (temporary SQLite) | **128 passed, 0 failed** (66 existing + new: roles, password policy, forgot/reset, default accounts, tool-page deterrent, tool access incl. migration) |
| Same suite against a **real PostgreSQL** (`TEST_DB_ENGINE=postgres`) | **66 passed** |
| `manage.py migrate` + `seed_users` on PostgreSQL via `config.settings.local` and `DB_*` variables | OK |
| **End-to-end smoke test**: `startup.sh` (migrate + **gunicorn**, 2 workers) on `config.settings.production`, real PostgreSQL, Azure-style HTTPS headers | **all 41 checks passed** — DB connectivity (`/api/health`), admin MFA enrolment, user login, **all four workflows** (upload/process/list/download/preview + tool pages), role permissions (user→admin API 403, cross-user 404), audit log, overview, CSRF origin rejection, no API docs exposed, HSTS/nosniff, **navigation to all 10 app routes** |
| `manage.py check --deploy` (production settings) | no issues (2 reviewed warnings silenced, documented in `settings/production.py`) |
| `npm test` (DevTools-shortcut guard) | 5 passed |
| `pip-audit` / `npm audit --omit=dev` | no known vulnerabilities / 0 vulnerabilities |
| `deploy/azure/pre-release-check.sh` | **ALL CHECKS PASSED** |
| Packaged `build/backend.zip` | contains `manage.py`, `startup.sh`, `config/`, `portal/`, `tools/`, merged `requirements.txt`; no tests/.env/data |
| `deploy/vm/backup-source.sh` | archive created, `.env`/`node_modules` excluded, checksum verifies |

## Automated tests executed

**test_admin.py**

- `test_admin_sees_all_documents_and_can_filter_by_user`
- `test_admin_can_view_download_delete_any_document_and_it_is_audited`
- `test_regular_users_are_forbidden_from_every_admin_endpoint`
- `test_user_cannot_escalate_own_role`
- `test_admin_user_management`
- `test_admin_password_reset_signs_the_user_out_everywhere`
- `test_admin_cannot_lock_themselves_out`
- `test_audit_log_covers_privileged_and_document_operations`
- `test_overview_reports_health_storage_and_failed_jobs`

**test_auth.py**

- `test_all_eleven_accounts_authenticate_separately[admin]`
- `test_all_eleven_accounts_authenticate_separately[user01]`
- `test_all_eleven_accounts_authenticate_separately[user02]`
- `test_all_eleven_accounts_authenticate_separately[user03]`
- `test_all_eleven_accounts_authenticate_separately[user04]`
- `test_all_eleven_accounts_authenticate_separately[user05]`
- `test_all_eleven_accounts_authenticate_separately[user06]`
- `test_all_eleven_accounts_authenticate_separately[user07]`
- `test_all_eleven_accounts_authenticate_separately[user08]`
- `test_all_eleven_accounts_authenticate_separately[user09]`
- `test_all_eleven_accounts_authenticate_separately[user10]`
- `test_wrong_password_and_unknown_user_get_same_generic_error`
- `test_lockout_after_repeated_failures_then_correct_password_rejected`
- `test_login_rate_limit`
- `test_logout_destroys_server_side_session`
- `test_deactivated_user_is_logged_out_and_cannot_login`
- `test_session_cookie_flags`
- `test_passwords_are_argon2id_hashed`
- `test_csrf_token_required_for_state_changing_requests`
- `test_foreign_origin_rejected`
- `test_change_password_policy_and_revokes_other_sessions`
- `test_session_absolute_lifetime_enforced`
- `test_admin_mfa_enrolment_and_login`
- `test_auth_events_are_audited`

**test_documents.py**

- `test_all_four_process_endpoints_store_list_and_download[html-converter-out0-orig0]`
- `test_all_four_process_endpoints_store_list_and_download[sec-form-dashboard-out1-orig1]`
- `test_all_four_process_endpoints_store_list_and_download[redline-to-gofiler-html-out2-orig2]`
- `test_all_four_process_endpoints_store_list_and_download[ppt-pdf-converter-out3-orig3]`
- `test_users_only_see_their_own_documents`
- `test_idor_other_users_document_cannot_be_read_viewed_downloaded_or_deleted`
- `test_client_cannot_pick_the_owner`
- `test_listing_params_cannot_widen_scope`
- `test_unauthenticated_access_is_rejected`
- `test_delete_is_soft_then_hidden_and_purged_by_retention`
- `test_search_filter_and_pagination`
- `test_view_serves_sandboxed_preview_and_refuses_binary`
- `test_content_is_inspected_not_just_extension`
- `test_failed_jobs_are_recorded_for_review`
- `test_oversize_upload_rejected`
- `test_zip_bomb_and_zip_slip_rejected`
- `test_path_traversal_filename_is_neutralised`
- `test_storage_keys_never_exposed_and_ids_are_random`

**test_platform.py**

- `test_security_headers_health_and_generic_404`
- `test_unhandled_errors_do_not_leak_details`
- `test_tool_pages_only_for_authenticated_users_and_carry_sandbox_csp`
- `test_tool_html_not_reachable_as_static_files`
- `test_csrf_endpoint_returns_token`
- `test_cors_allows_only_configured_origins_with_credentials`
- `test_frame_ancestors_setting_controls_who_may_embed_tool_and_preview_frames`
- `test_production_settings_refuse_insecure_configuration`
- `test_production_enables_https_secure_cookies_and_ssl_to_database`
- `test_django_deploy_check_has_no_warnings`
- `test_no_missing_migrations`
- `test_list_environment_values_accept_comma_separated_and_json`
- `test_create_admin_and_seed_commands`
- `test_frontend_bundle_has_no_secrets_or_sourcemaps`
- `test_no_hardcoded_credentials_in_source`

## Requirement checklist (your prompt) — honest status

| Requirement | Status |
| --- | --- |
| Azure deployment without Docker/GitHub | ✅ procedure + scripts (zip deploy, SWA CLI, shared VM). ⚠️ **Never run against Azure** |
| Django + React production configuration, startup | ✅ `config.settings.production`, `startup.sh` (gunicorn); tested locally exactly as Azure would start it |
| PostgreSQL, env-based credentials, no hardcoded passwords, local/production separated | ✅ tested on real PostgreSQL; source scanned for hardcoded credentials |
| Migrations, connectivity, permissions | ✅ Django migrations; `/api/health` checks the DB; `GRANT` steps in `README_POSTGRESQL.md` |
| F12 / Ctrl+Shift+I / Ctrl+Shift+J / Ctrl+U / right-click blocked on all pages | ✅ implemented + unit-tested logic; tool pages get the same via injected script. ⚠️ not clicked through in a real browser; deterrent only |
| Backend auth/roles/DB/credentials server-side, source maps off, HTTPS + secure cookies, upload validation, generic errors, logging | ✅ tested (see list above) |
| All four workflows integrated, logic unchanged, uploads/processing/results/downloads/navigation, roles preserved | ✅ HTTP-level end-to-end on production settings. ⚠️ **the tool UIs themselves were not run in a real browser** — see manual checklist |
| "Verify that all pages work on the deployed website" | ❌ **not possible here** (no Azure/browser) — do the checklist below on staging |

## Manual verification still required (first deployment)
1. Sign in as a user; open each of the four tools; run a real file through each; confirm the green "Saved to My Documents" notice, then view/download/delete in *My Documents*.
2. Sign in as a second user: the first user's documents are not listed. Sign in as admin: both users' files are visible; *Audit Log* shows the downloads.
3. Press F12, Ctrl+Shift+I, Ctrl+Shift+J, Ctrl+U and right-click on the login page, dashboard and inside each tool.
4. Admin first login: set up the authenticator app (MFA).
5. Azure: `AZURE_DEPLOYMENT.md` §8; restore a PostgreSQL backup, a deleted blob and a source archive; slot-swap rollback.
