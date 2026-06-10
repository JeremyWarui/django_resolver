"""
Backfill a primary RoleAssignment(role='user') for every user that has none.

After this migration every user in the system has at least one primary
assignment, so build_tokens_for_assignment never receives None and the JWT
'role' claim is always a non-empty string.
"""

from django.db import migrations


def backfill_floor_assignments(apps, schema_editor):
    User = apps.get_model("accounts", "CustomUser")
    RoleAssignment = apps.get_model("accounts", "RoleAssignment")

    # Users who have no primary assignment at all.
    users_without_primary = User.objects.exclude(
        role_assignments__is_primary=True
    )

    assignments = [
        RoleAssignment(user=user, role="user", is_primary=True)
        for user in users_without_primary
    ]
    if assignments:
        RoleAssignment.objects.bulk_create(assignments)


def reverse_backfill(apps, schema_editor):
    RoleAssignment = apps.get_model("accounts", "RoleAssignment")
    RoleAssignment.objects.filter(role="user", is_primary=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_add_user_role_choice"),
    ]

    operations = [
        migrations.RunPython(backfill_floor_assignments, reverse_code=reverse_backfill),
    ]
