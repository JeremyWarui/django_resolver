"""
Idempotent seed for reference data (Phase 1).

Seeds:
  - FacilityType: the 5 fixed types from SoT §9.4
  - Priority: 4 standard priorities with response/resolution minutes
  - EscalationRule: 2 rungs per priority (hos → hod)

Safe to run multiple times (get_or_create by natural key).
"""

from django.core.management.base import BaseCommand

from apps.facilities.models import FacilityType
from apps.sla.models import EscalationRule, Priority

FACILITY_TYPES = [
    {"name": "Office Block", "code": "office_block"},
    {"name": "Building", "code": "building"},
    {"name": "Equipment", "code": "equipment"},
    {"name": "Residential", "code": "residential"},
    {"name": "Grounds", "code": "grounds"},
]

# (name, rank, response_minutes, resolution_minutes)
PRIORITIES = [
    ("Low", 1, 480, 4320),  # 8h response, 3d resolution
    ("Medium", 2, 240, 1440),  # 4h response, 1d resolution
    ("High", 3, 60, 480),  # 1h response, 8h resolution
    ("Critical", 4, 30, 120),  # 30m response, 2h resolution
]

# (priority_name, to_level, threshold_minutes, order)
ESCALATION_RULES = [
    ("Low", "hos", 2880, 1),  # escalate to HOS after 2d
    ("Low", "hod", 5760, 2),  # escalate to HOD after 4d
    ("Medium", "hos", 720, 1),  # after 12h
    ("Medium", "hod", 1440, 2),  # after 1d
    ("High", "hos", 240, 1),  # after 4h
    ("High", "hod", 480, 2),  # after 8h
    ("Critical", "hos", 60, 1),  # after 1h
    ("Critical", "hod", 120, 2),  # after 2h
]


class Command(BaseCommand):
    help = "Seed reference data: FacilityType, Priority, EscalationRule (idempotent)"

    def handle(self, *args, **options):
        self._seed_facility_types()
        priorities = self._seed_priorities()
        self._seed_escalation_rules(priorities)
        self.stdout.write(self.style.SUCCESS("Reference data seeded successfully."))

    def _seed_facility_types(self):
        created = 0
        for ft in FACILITY_TYPES:
            _, is_new = FacilityType.objects.get_or_create(
                code=ft["code"], defaults={"name": ft["name"]}
            )
            if is_new:
                created += 1
        self.stdout.write(
            f"  FacilityType: {created} created, {len(FACILITY_TYPES) - created} already existed"
        )

    def _seed_priorities(self):
        created = 0
        priorities = {}
        for name, rank, response_min, resolution_min in PRIORITIES:
            p, is_new = Priority.objects.get_or_create(
                rank=rank,
                defaults={
                    "name": name,
                    "response_minutes": response_min,
                    "resolution_minutes": resolution_min,
                },
            )
            priorities[name] = p
            if is_new:
                created += 1
        self.stdout.write(
            f"  Priority: {created} created, {len(PRIORITIES) - created} already existed"
        )
        return priorities

    def _seed_escalation_rules(self, priorities):
        created = 0
        for priority_name, to_level, threshold_min, order in ESCALATION_RULES:
            priority = priorities[priority_name]
            _, is_new = EscalationRule.objects.get_or_create(
                priority=priority,
                to_level=to_level,
                defaults={"threshold_minutes": threshold_min, "order": order},
            )
            if is_new:
                created += 1
        self.stdout.write(
            f"  EscalationRule: {created} created, {len(ESCALATION_RULES) - created} already existed"
        )
