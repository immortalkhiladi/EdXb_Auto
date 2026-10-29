"""Copies files that still live only on local disk into the database (run once after switching to database storage):
    python manage.py migrate_files_to_db
Safe to repeat: files already in the database are skipped. Reports documents whose file is already gone."""
from django.core.management.base import BaseCommand

from portal.models import Document, StoredFile
from portal.storage import DatabaseStorage, LocalStorage
from django.conf import settings


class Command(BaseCommand):
    help = "Copy locally stored document files into the database."

    def handle(self, *a, **o):
        local, db = LocalStorage(settings.STORAGE_LOCAL_DIR), DatabaseStorage()
        copied = missing = skipped = 0
        for d in Document.objects.filter(purged_at__isnull=True):
            for key in (d.output_key, d.original_key):
                if not key:
                    continue
                if StoredFile.objects.filter(key=key).exists():
                    skipped += 1
                elif local.exists(key):
                    class _Up:  # adapts the local file to the .chunks() API
                        def chunks(self, n): return local.stream(key)
                    db.put_file(key, _Up())
                    copied += 1
                else:
                    missing += 1
                    self.stdout.write(self.style.WARNING(f"file missing on disk, cannot recover: document {d.id} ({key})"))
        self.stdout.write(self.style.SUCCESS(f"copied={copied} already_in_db={skipped} missing={missing}"))
