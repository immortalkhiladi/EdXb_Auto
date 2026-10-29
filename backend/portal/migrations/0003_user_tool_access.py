from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone

ALL_TOOLS = ["redline-to-gofiler-html", "html-converter", "ppt-pdf-converter", "sec-form-dashboard"]


def grant_existing_users_all_tools(apps, schema_editor):
    """Until now every USER could use every tool; keep that for existing accounts (the admin can now narrow it)."""
    User = apps.get_model("portal", "User")
    Access = apps.get_model("portal", "UserToolAccess")
    Access.objects.bulk_create([Access(user=u, tool=t) for u in User.objects.filter(role="USER") for t in ALL_TOOLS])


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0002_user_role_md'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserToolAccess',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tool', models.CharField(max_length=40)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tool_access', to='portal.user')),
            ],
        ),
        migrations.AddConstraint(
            model_name='usertoolaccess',
            constraint=models.UniqueConstraint(fields=('user', 'tool'), name='uniq_user_tool'),
        ),
        migrations.RunPython(grant_existing_users_all_tools, migrations.RunPython.noop),
    ]
