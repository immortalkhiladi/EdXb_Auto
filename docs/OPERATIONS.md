# Operations: backup, recovery, monitoring, maintenance

> Authoritative step-by-step material: **`docs/RENDER_DEPLOYMENT.md`**. Targets below are **proposed objectives, not measured results**; rehearse restores quarterly.

| Data | Mechanism | Retention |
| --- | --- | --- |
| PostgreSQL | Flexible Server automatic backups + point-in-time restore | 35 days |
| Uploaded/generated files | Blob versioning + soft delete | 30 days |
| Source code (shared dev VM, no Git) | nightly `ff-backup` archive + SHA-256 → immutable blob container; Azure Backup of the VM; manual `sudo ff-backup "<label>"` | 14 days on VM, 30+ days immutable off-VM |
| Release artefacts | `build/releases/` (kept by the deploy scripts) | with VM backups |

## Recovery
* **Database:** restore a Render PostgreSQL backup (dashboard) → update `DB_HOST`/`DB_PASSWORD` on the web service if the database changed → redeploy → verify. Files live in the database, so the database backup covers them.
* **File deleted/overwritten:** restore blob version / un-delete; clear `deleted_at`/`purged_at` on the `portal_document` row if it had been purged.
* **Bad release:** swap the staging slot back (`az webapp deployment slot swap …`); redeploy the previous `frontend-*.tar.gz` for a separate UI. Reverse a migration with `python manage.py migrate portal <previous>` only if needed.
* **Source code:** download the dated archive + `.sha256`, verify with `sha256sum -c`, extract and compare; or restore the whole VM from the Recovery Services vault.
* **After any restore:** `GET /api/health` → 200 (checks the database); sign in as admin; *Admin Console → Overview* healthy; download one document; review the audit log for the restore window.

## Monitoring and logging
* Django logs to stdout (Render log stream); no passwords/tokens/bodies are logged. Audit trail → `portal_auditlog` (*Admin Console → Audit Log*).
* Alerts in Render (service failures, restarts, disk usage) and on the database.  Failed-login spikes: Admin Console overview (24 h) and the audit log.
* Health endpoint: `GET /api/health`.

## Retention
* User delete → hidden immediately → files removed after `DELETED_FILE_RETENTION_DAYS` (30) by the in-app daily purge (`RUN_PURGE_SCHEDULER`; by hand: `python manage.py purge_deleted`). Admin can purge at once: `DELETE /api/documents/{id}?purge=true`.
* Audit rows older than `AUDIT_RETENTION_DAYS` (365) and expired sessions are removed by the same job. Export first if your records policy requires longer retention.

## Routine maintenance
* Before every release: `deploy/render/pre-release-check.sh`.
* Monthly: update dependencies/runtime, re-run the checks, deploy through the staging slot.
* Quarterly: review Render team members and VM accounts (`sudo ff-user list`), rotate secrets (DB password freely; `DJANGO_SECRET_KEY` only with a plan — it signs sessions and encrypts MFA secrets, so rotating signs everyone out and forces admins to re-enrol MFA), rehearse a restore, review the audit log, confirm nightly backups arrive.
