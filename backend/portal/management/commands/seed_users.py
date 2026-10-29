"""Creates the LOCAL/DEV admin account (admin / Admin@123). SEED_USER_COUNT=N additionally creates md01 (Md@123) and
user01..userNN (User@123); by default no other accounts exist and the dashboard starts empty.
Tools: every USER gets all of them, except user01 (example) who gets only Redline to GoFiler HTML and GoFiler HTML Converter.
Use --reset to (re)set those accounts' passwords on a database that already has users (unlocks them, signs them out).
SEED_PASSWORD overrides the user password.
These are well-known passwords: development only. Refused when running with production settings.
Production: use `create_admin` instead."""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from portal.models import User, UserToolAccess
from portal.tools import TOOLS

ADMIN_PASSWORD = "Admin@123"
MD_PASSWORD = "Md@123"
USER_PASSWORD = "User@123"
EXAMPLE_LIMITED = {"user01": ["redline-to-gofiler-html", "html-converter"]}  # example: user01 may use only the first two tools


class Command(BaseCommand):
    help = "Create the default admin account (SEED_USER_COUNT=N adds md01 + N users; --reset resets existing ones)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="set the default password on accounts that already exist (and create missing ones)")
        parser.add_argument("--force", action="store_true", help="alias of --reset")

    def handle(self, *args, **opts):
        if settings.SESSION_COOKIE_SECURE:
            raise CommandError("seed_users uses well-known default passwords and is refused with production settings. Use create_admin.")
        reset = opts["reset"] or opts["force"]
        if User.objects.exists() and not reset:
            self.stdout.write("Users already exist - nothing to do. Run with --reset to set the default passwords again.")
            return
        user_pw = settings.SEED_PASSWORD or USER_PASSWORD
        accounts = [(settings.SEED_ADMIN_USERNAME, "Administrator", "ADMIN", ADMIN_PASSWORD)]
        if settings.SEED_USER_COUNT:
            accounts.append(("md01", "MD 01", "MD", MD_PASSWORD))
            accounts += [(f"user{i:02d}", f"User {i:02d}", "USER", user_pw) for i in range(1, settings.SEED_USER_COUNT + 1)]
        lines = ["User ID".ljust(14) + "Role".ljust(8) + "Password"]
        for username, name, role, pw in accounts:
            u = User.objects.filter(username=username).first()
            tools = EXAMPLE_LIMITED.get(username, list(TOOLS))
            if u is None:
                User.objects.create_user(username, f"{username}@example.com", name, pw, role, tools=tools)
            else:
                u.set_password(pw)  # Argon2id
                u.role, u.is_active, u.failed_attempts, u.locked_until = role, True, 0, None
                u.session_epoch += 1
                u.save()
                if role == "USER":
                    UserToolAccess.objects.filter(user=u).delete()
                    UserToolAccess.objects.bulk_create([UserToolAccess(user=u, tool=t) for t in tools])
            lines.append(username.ljust(14) + role.ljust(8) + pw)
        self.stdout.write("\n=== DEFAULT ACCOUNTS READY ===\n" + "\n".join(lines) + "\nChange these passwords before any real use.\n")
