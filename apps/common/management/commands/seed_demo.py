"""
Idempotent seed for demo data (service catalogue, facilities, sample tickets).

Prerequisites: seed_reference and seed_org must have run first.

Seeds:
  - ServiceCategory + ServiceItem: four categories across ICTSUPP, NET, MAINT, GRND
  - Facility: four demo facilities across NRB and MSA campuses
  - Ticket (x8): one per status/level combination, plus a pending and a resolved-with-feedback
  - RoleAssignment (non-primary): senior_tech acting as HOS cover for NRB-ICT-ICTSUPP

Safe to re-run: catalogue and facilities use get_or_create; tickets section skips if any
Ticket already exists.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import RoleAssignment
from apps.catalog.models import ServiceCategory, ServiceItem
from apps.facilities.models import Facility, FacilityType
from apps.org.models import Campus, Section, SectionType
from apps.sla.models import Priority
from apps.tickets.models import Ticket, TicketFeedback, TicketLog


class Command(BaseCommand):
    help = "Seed demo data: service catalogue, facilities, sample tickets (idempotent)"

    def handle(self, *args, **options):
        priorities = self._load_priorities()
        self._seed_catalogue(priorities)
        self._seed_facilities()
        self._seed_tickets(priorities)
        self._seed_hos_cover()
        self.stdout.write(self.style.SUCCESS("Demo data seeded successfully."))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load_priorities(self):
        """Return a dict keyed by rank: {1: Low, 2: Medium, 3: High, 4: Critical}."""
        return {p.rank: p for p in Priority.objects.all()}

    # ------------------------------------------------------------------
    # Service Catalogue
    # ------------------------------------------------------------------

    def _seed_catalogue(self, priorities):
        low = priorities[1]
        medium = priorities[2]
        high = priorities[3]
        critical = priorities[4]

        # Item entries are either a plain string (no override) or a (name, priority) tuple.
        # The tuple form sets item.default_priority, overriding the category default (R7/R16).
        catalogue_data = [
            # (dept_code, section_type_code, category_name, location_details, priority, [item_entries])
            (
                "ICT", "ICTSUPP",
                "ICT Support Requests", False, medium,
                ["Password Reset", "Software Installation", "Hardware Issue"],
            ),
            (
                "ICT", "NET",
                "Network Issues", False, high,
                # Network Outage → Critical override (category default is High); VPN → inherits High.
                [("Network Outage Report", critical), "VPN Access Request"],
            ),
            (
                "FAC", "MAINT",
                "Facility Maintenance", True, medium,
                ["Plumbing Repair", "Electrical Issue", "Door/Window Repair"],
            ),
            (
                "FAC", "GRND",
                "Grounds Management", True, low,
                ["Lawn Mowing Request", "Drainage Issue"],
            ),
        ]

        cat_created = 0
        item_created = 0

        for dept_code, st_code, cat_name, location_details, priority, item_entries in catalogue_data:
            section_type = SectionType.objects.get(
                code=st_code,
                department__code=dept_code,
            )
            category, is_new = ServiceCategory.objects.get_or_create(
                section_type=section_type,
                name=cat_name,
                defaults={
                    "location_details": location_details,
                    "default_priority": priority,
                },
            )
            if is_new:
                cat_created += 1

            for entry in item_entries:
                if isinstance(entry, tuple):
                    item_name, override_priority = entry
                else:
                    item_name, override_priority = entry, None
                if override_priority is not None:
                    # update_or_create so re-runs sync the explicit override.
                    _, item_new = ServiceItem.objects.update_or_create(
                        category=category,
                        name=item_name,
                        defaults={"default_priority": override_priority},
                    )
                else:
                    _, item_new = ServiceItem.objects.get_or_create(
                        category=category,
                        name=item_name,
                    )
                if item_new:
                    item_created += 1

        self.stdout.write(
            f"  ServiceCategory: {cat_created} created, "
            f"{len(catalogue_data) - cat_created} already existed"
        )
        self.stdout.write(
            f"  ServiceItem: {item_created} created"
        )

    # ------------------------------------------------------------------
    # Facilities
    # ------------------------------------------------------------------

    def _seed_facilities(self):
        office_block = FacilityType.objects.get(code="office_block")
        building     = FacilityType.objects.get(code="building")
        equipment    = FacilityType.objects.get(code="equipment")
        residential  = FacilityType.objects.get(code="residential")
        grounds      = FacilityType.objects.get(code="grounds")

        nrb = Campus.objects.get(code="NRB")
        msa = Campus.objects.get(code="MSA")

        facilities_data = [
            # (campus, facility_type, name, code)
            # NRB — office blocks (for office_block location form)
            (nrb, office_block, "Admin Block A",    "BLKA"),
            (nrb, office_block, "Admin Block B",    "BLKB"),
            (nrb, office_block, "ICT Block",        "ICTBLK"),
            (nrb, office_block, "Finance Block",    "FINBLK"),
            # NRB — buildings (laundries, kitchens, utility)
            (nrb, building,     "Main Hall",        "MHALL"),
            (nrb, building,     "Conference Centre","CONFCTR"),
            (nrb, building,     "Staff Canteen",    "CANTEEN"),
            # MSA campus
            (msa, office_block, "Block 1",          "MBLK1"),
            (msa, building,     "MSA Main Hall",    "MMHALL"),
        ]

        created = 0
        for campus, facility_type, name, code in facilities_data:
            _, is_new = Facility.objects.get_or_create(
                campus=campus,
                name=name,
                defaults={"facility_type": facility_type, "code": code},
            )
            if is_new:
                created += 1

        self.stdout.write(
            f"  Facility: {created} created, "
            f"{len(facilities_data) - created} already existed"
        )

    # ------------------------------------------------------------------
    # Sample Tickets
    # ------------------------------------------------------------------

    def _seed_tickets(self, priorities):
        if Ticket.objects.exists():
            self.stdout.write("  Demo tickets already seeded, skipping.")
            return

        User = get_user_model()
        now = timezone.now()

        # ------ look up users ------
        requester1         = User.objects.get(username="requester1")
        tech1              = User.objects.get(username="tech1")
        tech2              = User.objects.get(username="tech2")
        tech3              = User.objects.get(username="tech3")
        nrb_ict_net_hos    = User.objects.get(username="nrb_ict_net_hos")
        nrb_fac_maint_hos  = User.objects.get(username="nrb_fac_maint_hos")
        nrb_ict_hod        = User.objects.get(username="nrb_ict_hod")  # noqa: F841 — used as HOD level_user placeholder

        # HOD-level user for NRB-FAC (used in ticket 6 log)
        nrb_fac_hod        = User.objects.get(username="nrb_fac_hod")

        # ------ look up campuses ------
        nrb_campus = Campus.objects.get(code="NRB")

        # ------ look up sections ------
        nrb_ict_ictsupp = Section.objects.get(
            campus_department__campus__code="NRB",
            section_type__code="ICTSUPP",
        )
        nrb_fac_maint = Section.objects.get(
            campus_department__campus__code="NRB",
            section_type__code="MAINT",
        )
        nrb_ict_net = Section.objects.get(
            campus_department__campus__code="NRB",
            section_type__code="NET",
        )

        # ------ look up priorities ------
        medium = priorities[2]
        high   = priorities[3]

        # ------ look up service items ------
        item_password_reset      = ServiceItem.objects.get(category__name="ICT Support Requests", name="Password Reset")
        item_software_install    = ServiceItem.objects.get(category__name="ICT Support Requests", name="Software Installation")
        item_hardware_issue      = ServiceItem.objects.get(category__name="ICT Support Requests", name="Hardware Issue")
        item_plumbing            = ServiceItem.objects.get(category__name="Facility Maintenance", name="Plumbing Repair")
        item_electrical          = ServiceItem.objects.get(category__name="Facility Maintenance", name="Electrical Issue")
        item_door_window         = ServiceItem.objects.get(category__name="Facility Maintenance", name="Door/Window Repair")
        item_vpn                 = ServiceItem.objects.get(category__name="Network Issues",       name="VPN Access Request")
        item_network_outage      = ServiceItem.objects.get(category__name="Network Issues",       name="Network Outage Report")

        # ----------------------------------------------------------------
        # Ticket 1 — open, technician-level
        # ----------------------------------------------------------------
        t1 = Ticket.objects.create(
            raised_by=requester1,
            requester_campus=nrb_campus,
            service_item=item_password_reset,
            priority=medium,
            section=nrb_ict_ictsupp,
            status="open",
            current_level="technician",
            assigned_to=None,
            response_due_at=now + timedelta(minutes=medium.response_minutes),
            resolution_due_at=now + timedelta(minutes=medium.resolution_minutes),
            description="User cannot log in — password expired.",
        )
        TicketLog.objects.create(
            ticket=t1,
            actor=None,
            event_type="created",
            from_value="",
            to_value="open",
        )

        # ----------------------------------------------------------------
        # Ticket 2 — assigned, technician-level
        # ----------------------------------------------------------------
        t2 = Ticket.objects.create(
            raised_by=requester1,
            requester_campus=nrb_campus,
            service_item=item_software_install,
            priority=medium,
            section=nrb_ict_ictsupp,
            status="assigned",
            current_level="technician",
            assigned_to=tech1,
            response_due_at=now + timedelta(minutes=medium.response_minutes),
            resolution_due_at=now + timedelta(minutes=medium.resolution_minutes),
            description="Need MS Office installed on new workstation.",
        )
        TicketLog.objects.create(
            ticket=t2, actor=None,
            event_type="created", from_value="", to_value="open",
        )
        TicketLog.objects.create(
            ticket=t2, actor=tech1,
            event_type="assigned", from_value="open", to_value="assigned",
        )

        # ----------------------------------------------------------------
        # Ticket 3 — in_progress, technician-level
        # ----------------------------------------------------------------
        t3 = Ticket.objects.create(
            raised_by=requester1,
            requester_campus=nrb_campus,
            service_item=item_hardware_issue,
            priority=medium,
            section=nrb_ict_ictsupp,
            status="in_progress",
            current_level="technician",
            assigned_to=tech2,
            response_due_at=now + timedelta(minutes=medium.response_minutes),
            resolution_due_at=now + timedelta(minutes=medium.resolution_minutes),
            description="Monitor not displaying — suspected cable or GPU fault.",
        )
        TicketLog.objects.create(
            ticket=t3, actor=None,
            event_type="created", from_value="", to_value="open",
        )
        TicketLog.objects.create(
            ticket=t3, actor=tech2,
            event_type="assigned", from_value="open", to_value="assigned",
        )
        TicketLog.objects.create(
            ticket=t3, actor=tech2,
            event_type="status_changed", from_value="assigned", to_value="in_progress",
        )

        # ----------------------------------------------------------------
        # Ticket 4 — pending (SLA paused)
        # ----------------------------------------------------------------
        t4 = Ticket.objects.create(
            raised_by=requester1,
            requester_campus=nrb_campus,
            service_item=item_plumbing,
            priority=medium,
            section=nrb_fac_maint,
            status="pending",
            current_level="technician",
            assigned_to=tech3,
            paused_at=now,
            response_due_at=now + timedelta(minutes=medium.response_minutes),
            resolution_due_at=now + timedelta(minutes=medium.resolution_minutes),
            description="Burst pipe in first-floor washroom — awaiting spare parts.",
        )
        TicketLog.objects.create(
            ticket=t4, actor=None,
            event_type="created", from_value="", to_value="open",
        )
        TicketLog.objects.create(
            ticket=t4, actor=tech3,
            event_type="assigned", from_value="open", to_value="assigned",
        )
        TicketLog.objects.create(
            ticket=t4, actor=tech3,
            event_type="status_changed", from_value="assigned", to_value="in_progress",
        )
        TicketLog.objects.create(
            ticket=t4, actor=tech3,
            event_type="status_changed",
            from_value="in_progress",
            to_value="pending",
            reason="Awaiting spare parts delivery",
        )

        # ----------------------------------------------------------------
        # Ticket 5 — in_progress, current_level=hos
        # ----------------------------------------------------------------
        t5 = Ticket.objects.create(
            raised_by=requester1,
            requester_campus=nrb_campus,
            service_item=item_electrical,
            priority=high,
            section=nrb_fac_maint,
            status="in_progress",
            current_level="hos",
            assigned_to=tech3,
            response_due_at=now + timedelta(minutes=high.response_minutes),
            resolution_due_at=now + timedelta(minutes=high.resolution_minutes),
            description="Power socket sparking in server room — urgent.",
        )
        TicketLog.objects.create(
            ticket=t5, actor=None,
            event_type="created", from_value="", to_value="open",
        )
        TicketLog.objects.create(
            ticket=t5, actor=tech3,
            event_type="assigned", from_value="open", to_value="assigned",
        )
        TicketLog.objects.create(
            ticket=t5, actor=tech3,
            event_type="status_changed", from_value="assigned", to_value="in_progress",
        )
        TicketLog.objects.create(
            ticket=t5, actor=None,
            event_type="escalated",
            from_value="technician",
            to_value="hos",
            level_user=nrb_fac_maint_hos,
        )

        # ----------------------------------------------------------------
        # Ticket 6 — in_progress, current_level=hod
        # ----------------------------------------------------------------
        t6 = Ticket.objects.create(
            raised_by=requester1,
            requester_campus=nrb_campus,
            service_item=item_door_window,
            priority=high,
            section=nrb_fac_maint,
            status="in_progress",
            current_level="hod",
            assigned_to=None,
            response_due_at=now + timedelta(minutes=high.response_minutes),
            resolution_due_at=now + timedelta(minutes=high.resolution_minutes),
            description="Main entrance door lock broken — security risk.",
        )
        TicketLog.objects.create(
            ticket=t6, actor=None,
            event_type="created", from_value="", to_value="open",
        )
        TicketLog.objects.create(
            ticket=t6, actor=None,
            event_type="escalated",
            from_value="technician",
            to_value="hos",
            level_user=nrb_fac_maint_hos,
        )
        TicketLog.objects.create(
            ticket=t6, actor=None,
            event_type="escalated",
            from_value="hos",
            to_value="hod",
            level_user=nrb_fac_hod,
        )

        # ----------------------------------------------------------------
        # Ticket 7 — resolved with feedback
        # ----------------------------------------------------------------
        t7 = Ticket.objects.create(
            raised_by=requester1,
            requester_campus=nrb_campus,
            service_item=item_vpn,
            priority=high,
            section=nrb_ict_net,
            status="resolved",
            current_level="technician",
            assigned_to=nrb_ict_net_hos,
            response_due_at=now + timedelta(minutes=high.response_minutes),
            resolution_due_at=now + timedelta(minutes=high.resolution_minutes),
            resolved_at=now - timedelta(hours=1),
            description="Need remote VPN access for work from home.",
        )
        TicketLog.objects.create(
            ticket=t7, actor=None,
            event_type="created", from_value="", to_value="open",
        )
        TicketLog.objects.create(
            ticket=t7, actor=nrb_ict_net_hos,
            event_type="assigned", from_value="open", to_value="assigned",
        )
        TicketLog.objects.create(
            ticket=t7, actor=nrb_ict_net_hos,
            event_type="resolved", from_value="assigned", to_value="resolved",
        )
        TicketFeedback.objects.create(
            ticket=t7,
            rating=4,
            comment="Good service, resolved quickly.",
        )

        # ----------------------------------------------------------------
        # Ticket 8 — closed
        # ----------------------------------------------------------------
        t8 = Ticket.objects.create(
            raised_by=requester1,
            requester_campus=nrb_campus,
            service_item=item_network_outage,
            priority=high,
            section=nrb_ict_net,
            status="closed",
            current_level="technician",
            assigned_to=nrb_ict_net_hos,
            response_due_at=now + timedelta(minutes=high.response_minutes),
            resolution_due_at=now + timedelta(minutes=high.resolution_minutes),
            resolved_at=now - timedelta(hours=3),
            closed_at=now - timedelta(hours=1),
            description="Entire NRB campus network down — all users affected.",
        )
        TicketLog.objects.create(
            ticket=t8, actor=None,
            event_type="created", from_value="", to_value="open",
        )
        TicketLog.objects.create(
            ticket=t8, actor=nrb_ict_net_hos,
            event_type="assigned", from_value="open", to_value="assigned",
        )
        TicketLog.objects.create(
            ticket=t8, actor=nrb_ict_net_hos,
            event_type="status_changed", from_value="assigned", to_value="resolved",
        )
        TicketLog.objects.create(
            ticket=t8, actor=nrb_ict_net_hos,
            event_type="closed", from_value="resolved", to_value="closed",
        )

        self.stdout.write("  Ticket: 8 created (open, assigned, in_progress, pending, hos-level, hod-level, resolved, closed)")

    # ------------------------------------------------------------------
    # HOS Cover RoleAssignment
    # ------------------------------------------------------------------

    def _seed_hos_cover(self):
        User = get_user_model()

        senior_tech       = User.objects.get(username="senior_tech")
        nrb_ict_hod_user  = User.objects.get(username="nrb_ict_hod")
        nrb_ict_supp_section = Section.objects.get(
            campus_department__campus__code="NRB",
            section_type__code="ICTSUPP",
        )

        _, is_new = RoleAssignment.objects.get_or_create(
            user=senior_tech,
            role="hos",
            section=nrb_ict_supp_section,
            is_primary=False,
            defaults={
                "valid_from": timezone.now(),
                "valid_until": timezone.now() + timedelta(days=14),
                "assigned_by": nrb_ict_hod_user,
            },
        )
        status = "created" if is_new else "already existed"
        self.stdout.write(f"  HOS cover RoleAssignment (senior_tech @ NRB-ICT-ICTSUPP): {status}")
