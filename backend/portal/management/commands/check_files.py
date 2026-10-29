"""Reports the active storage backend and every document whose stored file is missing:
    python manage.py check_files
Documents listed here show "File not available" in the UI; they were saved before database storage and must be re-processed."""
from django.conf import settings
from django.core.management.base import BaseCommand

from portal.models import Document, StoredFile
from portal.storage import get_storage


class Command(BaseCommand):
    help = "Show storage backend and documents whose file is missing."

    def handle(self, *a, **o):
        st = get_storage()
        self.stdout.write(f"STORAGE_BACKEND={settings.STORAGE_BACKEND} ({type(st).__name__}); files in database: {StoredFile.objects.count()}")
        ok = bad = 0
        for d in Document.objects.filter(status="completed", deleted_at__isnull=True, purged_at__isnull=True).order_by("created_at"):
            if d.output_key and not st.exists(d.output_key):
                bad += 1
                self.stdout.write(self.style.WARNING(f"MISSING  {d.created_at:%Y-%m-%d %H:%M}  {d.output_filename}  (id {d.id})"))
            else:
                ok += 1
        self.stdout.write(self.style.SUCCESS(f"ok={ok}") + "  " + (self.style.ERROR(f"missing={bad}") if bad else "missing=0"))
