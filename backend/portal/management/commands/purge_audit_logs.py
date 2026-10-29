from django.core.management.base import BaseCommand

from portal.maintenance import purge_audit_logs


class Command(BaseCommand):
    help = "Delete audit log rows older than AUDIT_RETENTION_DAYS (default 30). Safe to run from any scheduler."

    def handle(self, *args, **opts):
        self.stdout.write(f"audit rows deleted: {purge_audit_logs()}")
