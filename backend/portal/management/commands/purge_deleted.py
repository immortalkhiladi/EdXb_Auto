from django.core.management.base import BaseCommand

from portal.maintenance import purge


class Command(BaseCommand):
    help = "Remove files of documents deleted longer than DELETED_FILE_RETENTION_DAYS ago, old audit rows and expired sessions."

    def handle(self, *args, **opts):
        self.stdout.write(str(purge()))
