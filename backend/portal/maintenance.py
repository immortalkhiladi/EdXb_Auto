"""Retention jobs (also runnable by hand: python manage.py purge_deleted)."""
from datetime import timedelta

from django.conf import settings
from django.core.management import call_command
from django.utils import timezone

from .models import AuditLog, Document
from .storage import get_storage


def purge_audit_logs() -> int:
    """Deletes audit rows older than AUDIT_RETENTION_DAYS (default 30). Newer rows are never touched. Idempotent."""
    cutoff = timezone.now() - timedelta(days=settings.AUDIT_RETENTION_DAYS)
    total = 0
    while True:  # batched so a large backlog never holds one long lock
        ids = list(AuditLog.objects.filter(created_at__lt=cutoff).values_list("pk", flat=True)[:5000])
        if not ids:
            return total
        total += AuditLog.objects.filter(pk__in=ids).delete()[0]


def purge() -> dict:
    now = timezone.now()
    storage = get_storage()
    files = 0
    cutoff = now - timedelta(days=settings.DELETED_FILE_RETENTION_DAYS)
    for d in Document.objects.filter(deleted_at__isnull=False, deleted_at__lt=cutoff, purged_at__isnull=True):
        for k in (d.output_key, d.original_key):
            if k:
                storage.delete(k)
                files += 1
        d.purged_at = now
        d.save(update_fields=["purged_at"])
    audit_rows = purge_audit_logs()
    call_command("clearsessions")  # expired sessions
    return {"files_purged": files, "audit_rows_deleted": audit_rows}
