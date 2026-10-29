"""Create a user from the command line (the FIRST administrator in staging/production).

    python manage.py create_admin --username jane --email jane@corp.com --name "Jane Doe" --role ADMIN|MD|USER
The password is read from a hidden prompt (or the FF_NEW_PASSWORD environment variable for automation)."""
import getpass
import os

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from portal.models import User
from portal.security import password_error


class Command(BaseCommand):
    help = "Create an administrator or user."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--email", required=True)
        parser.add_argument("--name", required=True)
        parser.add_argument("--role", choices=["ADMIN", "MD", "USER"], default="ADMIN")

    def handle(self, *args, **o):
        pw = os.environ.get("FF_NEW_PASSWORD")
        if not pw:
            pw = getpass.getpass("Password: ")
            if getpass.getpass("Repeat password: ") != pw:
                raise CommandError("Passwords do not match.")
        problem = password_error(pw)
        if problem:
            raise CommandError(problem)
        if User.objects.filter(Q(username=o["username"].lower()) | Q(email=o["email"].lower())).exists():
            raise CommandError("A user with that User ID or email already exists.")
        User.objects.create_user(o["username"], o["email"], o["name"], pw, o["role"])
        self.stdout.write(f"Created {o['role']} '{o['username'].lower()}'.")
