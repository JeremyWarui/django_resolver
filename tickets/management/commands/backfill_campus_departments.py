from django.core.management.base import BaseCommand
from tickets.models import Department, CampusDepartment


class Command(BaseCommand):
    help = "Backfill CampusDepartment records from existing Department rows"

    def handle(self, *args, **options):
        created = 0
        updated = 0
        for dept in Department.objects.select_related("campus", "department_type").all():
            if not dept.department_type:
                self.stdout.write(self.style.WARNING(
                    f"Skipping Department id={dept.id} ({dept}) — no department_type"))
                continue

            obj, was_created = CampusDepartment.objects.get_or_create(
                campus=dept.campus,
                department_type=dept.department_type,
                defaults={"hod_user": dept.head_of_department},
            )
            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(
                    f"Created CampusDepartment for {dept.campus.code} / {dept.department_type.code}"))
            else:
                # ensure hod_user is set if missing
                if not obj.hod_user and dept.head_of_department:
                    obj.hod_user = dept.head_of_department
                    obj.save()
                    updated += 1
                    self.stdout.write(self.style.SUCCESS(
                        f"Updated hod_user for CampusDepartment {obj}"))

        self.stdout.write(self.style.NOTICE(
            f"Backfill complete — created={created} updated={updated}"))
