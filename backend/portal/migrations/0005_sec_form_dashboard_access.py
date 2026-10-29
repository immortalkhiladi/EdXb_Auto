from django.db import migrations

NEW_TOOL = "sec-form-dashboard"


def grant_existing_users(apps, schema_editor):
    """New tool: existing USER accounts get it like every other tool (the admin can narrow it in Tool Access)."""
    User = apps.get_model("portal", "User")
    Access = apps.get_model("portal", "UserToolAccess")
    have = set(Access.objects.filter(tool=NEW_TOOL).values_list("user_id", flat=True))
    Access.objects.bulk_create([Access(user=u, tool=NEW_TOOL) for u in User.objects.filter(role="USER") if u.id not in have])


class Migration(migrations.Migration):
    dependencies = [("portal", "0004_stored_files")]
    operations = [migrations.RunPython(grant_existing_users, migrations.RunPython.noop)]
