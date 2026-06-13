"""
Full seed for Kenya School of Government Service Desk.

Campuses:     NRB (Nairobi), MSA (Mombasa), KSM (Kisumu)
Departments:  Administration (ADM), HR, ICT
Sections:     ADM → Maintenance (MAINT), Transport (TRANS)
              HR  → Payroll (PAYROLL), Registry (REG)
              ICT → Networks (NET), Systems Support (SYSSUPP)
Tickets:      30, spread across the current and previous calendar week

Run after:  python manage.py migrate
Re-runnable: org/catalogue are get_or_create; tickets are skipped if any exist.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import RoleAssignment, UserProfile
from apps.catalog.models import ServiceCategory, ServiceItem
from apps.facilities.models import Facility, FacilityType
from apps.org.models import (
    Campus,
    CampusDepartment,
    Department,
    Section,
    SectionTechnician,
    SectionType,
)
from apps.sla.models import EscalationRule, Priority
from apps.tickets.models import Ticket, TicketFeedback, TicketLocation, TicketLog

User = get_user_model()

DEFAULT_PASSWORD = "***REMOVED-DEMO-PASSWORD***"

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

PRIORITIES = [
    ("Low",      1, 480,  4320),
    ("Medium",   2, 240,  1440),
    ("High",     3,  60,   480),
    ("Critical", 4,  30,   120),
]

ESCALATION_RULES = [
    ("Low",      "hos",  2880, 1),
    ("Low",      "hod",  5760, 2),
    ("Medium",   "hos",   720, 1),
    ("Medium",   "hod",  1440, 2),
    ("High",     "hos",   240, 1),
    ("High",     "hod",   480, 2),
    ("Critical", "hos",    60, 1),
    ("Critical", "hod",   120, 2),
]

FACILITY_TYPES = [
    ("Office Block", "office_block"),
    ("Building",     "building"),
    ("Equipment",    "equipment"),
    ("Residential",  "residential"),
    ("Grounds",      "grounds"),
]

# campus_code → list of (name, facility_type_code, facility_code)
FACILITIES = {
    "NRB": [
        ("Admin Block A",       "office_block", "NRB-AB-A"),
        ("Admin Block B",       "office_block", "NRB-AB-B"),
        ("ICT Block",           "building",     "NRB-ICT"),
        ("Finance Block",       "office_block", "NRB-FIN"),
        ("Main Hall",           "building",     "NRB-MH"),
        ("Conference Centre",   "building",     "NRB-CC"),
        ("Staff Canteen",       "building",     "NRB-SC"),
        ("Maintenance Workshop","building",     "NRB-MW"),
    ],
    "MSA": [
        ("Admin Block",         "office_block", "MSA-AB"),
        ("ICT Building",        "building",     "MSA-ICT"),
        ("Main Hall",           "building",     "MSA-MH"),
        ("Student Centre",      "building",     "MSA-STC"),
        ("Maintenance Workshop","building",     "MSA-MW"),
    ],
    "KSM": [
        ("Main Block",          "office_block", "KSM-MB"),
        ("ICT Lab",             "building",     "KSM-ICT"),
        ("Conference Hall",     "building",     "KSM-CH"),
        ("Student Centre",      "building",     "KSM-STC"),
        ("Maintenance Workshop","building",     "KSM-MW"),
    ],
}

# ---------------------------------------------------------------------------
# Org
# ---------------------------------------------------------------------------

CAMPUSES = [
    {"name": "Nairobi", "code": "NRB", "location": "Nairobi CBD"},
    {"name": "Mombasa", "code": "MSA", "location": "Mombasa Island"},
    {"name": "Kisumu",  "code": "KSM", "location": "Kisumu CBD"},
]

DEPARTMENTS = [
    {"name": "Administration",   "code": "ADM"},
    {"name": "Human Resources",  "code": "HR"},
    {"name": "ICT",              "code": "ICT"},
]

# (dept_code, name, code)
SECTION_TYPES = [
    ("ADM", "Maintenance",    "MAINT"),
    ("ADM", "Transport",      "TRANS"),
    ("HR",  "Payroll",        "PAYROLL"),
    ("HR",  "Registry",       "REG"),
    ("ICT", "Networks",       "NET"),
    ("ICT", "Systems Support","SYSSUPP"),
]

# (username, first_name, last_name, email, campus_code)
USERS = [
    # System admin
    ("admin",            "System",    "Admin",       "admin@ksg.local",                  "NRB"),
    # Department managers (org-wide)
    ("admin_mgr",           "Paul",      "Kamau",       "adm.manager@ksg.local",            "NRB"),
    ("hr_mgr",            "Grace",     "Achieng",     "hr.manager@ksg.local",             "NRB"),
    ("ict_mgr",           "James",     "Mwangi",      "ict.manager@ksg.local",            "NRB"),
    # NRB HODs
    ("nrb_admin_hod",           "Margaret",  "Wanjiku",     "nrb.adm.hod@ksg.local",           "NRB"),
    ("nrb_hr_hod",            "Samuel",    "Otieno",      "nrb.hr.hod@ksg.local",            "NRB"),
    ("nrb_ict_hod",           "Brian",     "Kariuki",     "nrb.ict.hod@ksg.local",           "NRB"),
    # MSA HODs
    ("msa_admin_hod",           "Fatuma",    "Omar",        "msa.adm.hod@ksg.local",           "MSA"),
    ("msa_hr_hod",            "Ahmed",     "Hassan",      "msa.hr.hod@ksg.local",            "MSA"),
    ("msa_ict_hod",           "Amina",     "Said",        "msa.ict.hod@ksg.local",           "MSA"),
    # KSM HODs
    ("ksm_admin_hod",           "Ochieng",   "Odhiambo",    "ksm.adm.hod@ksg.local",           "KSM"),
    ("ksm_hr_hod",            "Atieno",    "Omondi",      "ksm.hr.hod@ksg.local",            "KSM"),
    ("ksm_ict_hod",           "Okello",    "Ouma",        "ksm.ict.hod@ksg.local",           "KSM"),
    # NRB HOS (one per section)
    ("nrb_maint_hos",     "Lucy",      "Njeri",       "nrb.adm.maint.hos@ksg.local",     "NRB"),
    ("nrb_transport_hos",     "Peter",     "Maina",       "nrb.adm.trans.hos@ksg.local",     "NRB"),
    ("nrb_payroll_hos",    "Rose",      "Kimani",      "nrb.hr.payroll.hos@ksg.local",    "NRB"),
    ("nrb_registry_hos",        "Jane",      "Waweru",      "nrb.hr.reg.hos@ksg.local",        "NRB"),
    ("nrb_networks_hos",       "Achieng",   "Otieno",      "nrb.ict.net.hos@ksg.local",       "NRB"),
    ("nrb_syssupport_hos",   "David",     "Omondi",      "nrb.ict.syssupp.hos@ksg.local",   "NRB"),
    # MSA HOS (partial)
    ("msa_payroll_hos",    "Zainab",    "Musa",        "msa.hr.payroll.hos@ksg.local",    "MSA"),
    ("msa_networks_hos",       "Khalid",    "Ahmed",       "msa.ict.net.hos@ksg.local",       "MSA"),
    # KSM HOS (partial)
    ("ksm_syssupport_hos",   "Onyango",   "Owino",       "ksm.ict.syssupp.hos@ksg.local",   "KSM"),
    # NRB technicians
    ("nrb_maint_tech1",       "John",      "Doe",         "adm.maint.tech1@ksg.local",       "NRB"),
    ("nrb_maint_tech2",       "Mary",      "Waweru",      "adm.maint.tech2@ksg.local",       "NRB"),
    ("nrb_transport_tech1",       "Kevin",     "Mboya",       "adm.trans.tech1@ksg.local",       "NRB"),
    ("nrb_payroll_tech1",      "Faith",     "Njoroge",     "hr.payroll.tech1@ksg.local",      "NRB"),
    ("nrb_payroll_tech2",      "Michael",   "Odhiambo",    "hr.payroll.tech2@ksg.local",      "NRB"),
    ("nrb_registry_tech1",          "Alice",     "Mwangi",      "hr.reg.tech1@ksg.local",          "NRB"),
    ("nrb_networks_tech1",         "Robert",    "Kipchumba",   "ict.net.tech1@ksg.local",         "NRB"),
    ("nrb_networks_tech2",         "Sophie",    "Chelimo",     "ict.net.tech2@ksg.local",         "NRB"),
    ("nrb_syssupport_tech1",     "George",    "Mutua",       "ict.syssupp.tech1@ksg.local",     "NRB"),
    ("nrb_syssupport_tech2",     "Helen",     "Njuguna",     "ict.syssupp.tech2@ksg.local",     "NRB"),
    # MSA technicians
    ("msa_payroll_tech1",  "Salim",     "Bakari",      "msa.hr.payroll.tech1@ksg.local",  "MSA"),
    ("msa_networks_tech1",     "Rashida",   "Kombo",       "msa.ict.net.tech1@ksg.local",     "MSA"),
    # KSM technicians
    ("ksm_syssupport_tech1", "Erick",     "Okoth",       "ksm.ict.syssupp.tech1@ksg.local", "KSM"),
    # Requesters
    ("alice.kamau",           "Alice",     "Kamau",       "alice.kamau@ksg.local",           "NRB"),
    ("bob.mwenda",            "Bob",       "Mwenda",      "bob.mwenda@ksg.local",            "MSA"),
    ("carol.njoki",           "Carol",     "Njoki",       "carol.njoki@ksg.local",           "NRB"),
    ("david.ochieng",         "David",     "Ochieng",     "david.ochieng@ksg.local",         "KSM"),
    ("eve.wanjiru",           "Eve",       "Wanjiru",     "eve.wanjiru@ksg.local",           "NRB"),
]

# (campus_code, dept_code, hod_username)
CAMPUS_DEPARTMENTS = [
    ("NRB", "ADM", "nrb_admin_hod"),
    ("NRB", "HR",  "nrb_hr_hod"),
    ("NRB", "ICT", "nrb_ict_hod"),
    ("MSA", "ADM", "msa_admin_hod"),
    ("MSA", "HR",  "msa_hr_hod"),
    ("MSA", "ICT", "msa_ict_hod"),
    ("KSM", "ADM", "ksm_admin_hod"),
    ("KSM", "HR",  "ksm_hr_hod"),
    ("KSM", "ICT", "ksm_ict_hod"),
]

# (campus_code, dept_code, section_type_code, hos_username_or_None, is_active)
SECTIONS = [
    # NRB — full coverage
    ("NRB", "ADM", "MAINT",   "nrb_maint_hos",   True),
    ("NRB", "ADM", "TRANS",   "nrb_transport_hos",   True),
    ("NRB", "HR",  "PAYROLL", "nrb_payroll_hos",  True),
    ("NRB", "HR",  "REG",     "nrb_registry_hos",      True),
    ("NRB", "ICT", "NET",     "nrb_networks_hos",     True),
    ("NRB", "ICT", "SYSSUPP", "nrb_syssupport_hos", True),
    # MSA — partial HOS
    ("MSA", "ADM", "MAINT",   None,                  True),
    ("MSA", "ADM", "TRANS",   None,                  True),
    ("MSA", "HR",  "PAYROLL", "msa_payroll_hos",  True),
    ("MSA", "HR",  "REG",     None,                  True),
    ("MSA", "ICT", "NET",     "msa_networks_hos",     True),
    ("MSA", "ICT", "SYSSUPP", None,                  True),
    # KSM — partial HOS
    ("KSM", "ADM", "MAINT",   None,                  True),
    ("KSM", "ADM", "TRANS",   None,                  True),
    ("KSM", "HR",  "PAYROLL", None,                  True),
    ("KSM", "HR",  "REG",     None,                  True),
    ("KSM", "ICT", "NET",     None,                  True),
    ("KSM", "ICT", "SYSSUPP", "ksm_syssupport_hos", True),
]

# (username, campus_code, dept_code, section_type_code)
SECTION_TECHNICIANS = [
    ("nrb_maint_tech1",       "NRB", "ADM", "MAINT"),
    ("nrb_maint_tech2",       "NRB", "ADM", "MAINT"),
    ("nrb_transport_tech1",       "NRB", "ADM", "TRANS"),
    ("nrb_payroll_tech1",      "NRB", "HR",  "PAYROLL"),
    ("nrb_payroll_tech2",      "NRB", "HR",  "PAYROLL"),
    ("nrb_registry_tech1",          "NRB", "HR",  "REG"),
    ("nrb_networks_tech1",         "NRB", "ICT", "NET"),
    ("nrb_networks_tech2",         "NRB", "ICT", "NET"),
    ("nrb_syssupport_tech1",     "NRB", "ICT", "SYSSUPP"),
    ("nrb_syssupport_tech2",     "NRB", "ICT", "SYSSUPP"),
    ("msa_payroll_tech1",  "MSA", "HR",  "PAYROLL"),
    ("msa_networks_tech1",     "MSA", "ICT", "NET"),
    ("ksm_syssupport_tech1", "KSM", "ICT", "SYSSUPP"),
]

# (username, role, scope_type, scope_key)
ROLE_ASSIGNMENTS = [
    ("admin",            "admin",      "none",             None),
    ("admin_mgr",           "manager",    "department",       "ADM"),
    ("hr_mgr",            "manager",    "department",       "HR"),
    ("ict_mgr",           "manager",    "department",       "ICT"),
    # HODs
    ("nrb_admin_hod",           "hod",  "campus_department", ("NRB", "ADM")),
    ("nrb_hr_hod",            "hod",  "campus_department", ("NRB", "HR")),
    ("nrb_ict_hod",           "hod",  "campus_department", ("NRB", "ICT")),
    ("msa_admin_hod",           "hod",  "campus_department", ("MSA", "ADM")),
    ("msa_hr_hod",            "hod",  "campus_department", ("MSA", "HR")),
    ("msa_ict_hod",           "hod",  "campus_department", ("MSA", "ICT")),
    ("ksm_admin_hod",           "hod",  "campus_department", ("KSM", "ADM")),
    ("ksm_hr_hod",            "hod",  "campus_department", ("KSM", "HR")),
    ("ksm_ict_hod",           "hod",  "campus_department", ("KSM", "ICT")),
    # HOS
    ("nrb_maint_hos",     "hos",  "section", ("NRB", "ADM", "MAINT")),
    ("nrb_transport_hos",     "hos",  "section", ("NRB", "ADM", "TRANS")),
    ("nrb_payroll_hos",    "hos",  "section", ("NRB", "HR",  "PAYROLL")),
    ("nrb_registry_hos",        "hos",  "section", ("NRB", "HR",  "REG")),
    ("nrb_networks_hos",       "hos",  "section", ("NRB", "ICT", "NET")),
    ("nrb_syssupport_hos",   "hos",  "section", ("NRB", "ICT", "SYSSUPP")),
    ("msa_payroll_hos",    "hos",  "section", ("MSA", "HR",  "PAYROLL")),
    ("msa_networks_hos",       "hos",  "section", ("MSA", "ICT", "NET")),
    ("ksm_syssupport_hos",   "hos",  "section", ("KSM", "ICT", "SYSSUPP")),
    # Technicians
    ("nrb_maint_tech1",       "technician", "section", ("NRB", "ADM", "MAINT")),
    ("nrb_maint_tech2",       "technician", "section", ("NRB", "ADM", "MAINT")),
    ("nrb_transport_tech1",       "technician", "section", ("NRB", "ADM", "TRANS")),
    ("nrb_payroll_tech1",      "technician", "section", ("NRB", "HR",  "PAYROLL")),
    ("nrb_payroll_tech2",      "technician", "section", ("NRB", "HR",  "PAYROLL")),
    ("nrb_registry_tech1",          "technician", "section", ("NRB", "HR",  "REG")),
    ("nrb_networks_tech1",         "technician", "section", ("NRB", "ICT", "NET")),
    ("nrb_networks_tech2",         "technician", "section", ("NRB", "ICT", "NET")),
    ("nrb_syssupport_tech1",     "technician", "section", ("NRB", "ICT", "SYSSUPP")),
    ("nrb_syssupport_tech2",     "technician", "section", ("NRB", "ICT", "SYSSUPP")),
    ("msa_payroll_tech1",  "technician", "section", ("MSA", "HR",  "PAYROLL")),
    ("msa_networks_tech1",     "technician", "section", ("MSA", "ICT", "NET")),
    ("ksm_syssupport_tech1", "technician", "section", ("KSM", "ICT", "SYSSUPP")),
    # Requesters
    ("alice.kamau",   "user", "none", None),
    ("bob.mwenda",    "user", "none", None),
    ("carol.njoki",   "user", "none", None),
    ("david.ochieng", "user", "none", None),
    ("eve.wanjiru",   "user", "none", None),
]

# ---------------------------------------------------------------------------
# Service catalogue
# (dept_code, section_type_code, category_name, location_details, priority_rank, [item_names])
# ---------------------------------------------------------------------------

CATALOGUE = [
    ("ADM", "MAINT",   "Maintenance Services", True,  2,
     ["Plumbing Services", "Electrical Services", "Carpentry Services"]),
    ("ADM", "TRANS",   "Transport Services",   False, 2,
     ["Vehicle Booking Services"]),
    ("HR",  "PAYROLL", "Payroll Services",     False, 2,
     ["Rent Deductions", "Loan Services"]),
    ("HR",  "REG",     "Registry Services",    False, 1,
     ["File Services"]),
    ("ICT", "NET",     "Network Services",     False, 3,
     ["Internet Services", "Phone Services"]),
    ("ICT", "SYSSUPP", "Systems Support",      False, 2,
     ["ERP Services", "Email Services"]),
]


class Command(BaseCommand):
    help = "Full idempotent seed: reference data, org, catalogue, 30 demo tickets"

    def handle(self, *args, **options):
        self.priorities = self._seed_priorities()
        self._seed_escalation_rules()
        self._seed_facility_types()
        campuses = self._seed_campuses()
        self._seed_facilities(campuses)
        departments = self._seed_departments()
        section_types = self._seed_section_types(departments)
        users = self._seed_users(campuses)
        self._set_department_managers(departments, users)
        campus_depts = self._seed_campus_departments(campuses, departments, users)
        sections = self._seed_sections(campus_depts, section_types, users)
        self._seed_section_technicians(users, sections)
        self._seed_role_assignments(users, departments, campus_depts, sections)
        self._seed_catalogue(departments, section_types)
        self._seed_tickets(users, sections)
        self._seed_ticket_locations()
        self.stdout.write(self.style.SUCCESS("Full seed complete."))

    # ------------------------------------------------------------------
    # Reference data
    # ------------------------------------------------------------------

    def _seed_priorities(self):
        priorities = {}
        created = 0
        for name, rank, resp_min, res_min in PRIORITIES:
            p, is_new = Priority.objects.get_or_create(
                rank=rank,
                defaults={"name": name, "response_minutes": resp_min, "resolution_minutes": res_min},
            )
            priorities[rank] = p
            if is_new:
                created += 1
        self.stdout.write(f"  Priority: {created} created")
        return priorities

    def _seed_escalation_rules(self):
        created = 0
        for priority_name, to_level, threshold, order in ESCALATION_RULES:
            priority = Priority.objects.get(name=priority_name)
            _, is_new = EscalationRule.objects.get_or_create(
                priority=priority,
                to_level=to_level,
                defaults={"threshold_minutes": threshold, "order": order},
            )
            if is_new:
                created += 1
        self.stdout.write(f"  EscalationRule: {created} created")

    def _seed_facility_types(self):
        created = 0
        for name, code in FACILITY_TYPES:
            _, is_new = FacilityType.objects.get_or_create(code=code, defaults={"name": name})
            if is_new:
                created += 1
        self.stdout.write(f"  FacilityType: {created} created")

    def _seed_facilities(self, campuses):
        created = 0
        for campus_code, entries in FACILITIES.items():
            campus = campuses.get(campus_code)
            if campus is None:
                continue
            for name, ft_code, fac_code in entries:
                facility_type = FacilityType.objects.get(code=ft_code)
                _, is_new = Facility.objects.get_or_create(
                    campus=campus,
                    code=fac_code,
                    defaults={"name": name, "facility_type": facility_type},
                )
                if is_new:
                    created += 1
        self.stdout.write(f"  Facility: {created} created")

    # ------------------------------------------------------------------
    # Org
    # ------------------------------------------------------------------

    def _seed_campuses(self):
        campuses = {}
        created = 0
        for c in CAMPUSES:
            obj, is_new = Campus.objects.get_or_create(
                code=c["code"], defaults={"name": c["name"], "location": c["location"]}
            )
            campuses[c["code"]] = obj
            if is_new:
                created += 1
        self.stdout.write(f"  Campus: {created} created, {len(CAMPUSES) - created} existed")
        return campuses

    def _seed_departments(self):
        departments = {}
        created = 0
        for d in DEPARTMENTS:
            obj, is_new = Department.objects.get_or_create(
                code=d["code"], defaults={"name": d["name"]}
            )
            departments[d["code"]] = obj
            if is_new:
                created += 1
        self.stdout.write(f"  Department: {created} created, {len(DEPARTMENTS) - created} existed")
        return departments

    def _seed_section_types(self, departments):
        section_types = {}
        created = 0
        for dept_code, name, code in SECTION_TYPES:
            dept = departments[dept_code]
            obj, is_new = SectionType.objects.get_or_create(
                department=dept, code=code, defaults={"name": name}
            )
            section_types[(dept_code, code)] = obj
            if is_new:
                created += 1
        self.stdout.write(f"  SectionType: {created} created")
        return section_types

    def _seed_users(self, campuses):
        users = {}
        created = 0
        for username, first_name, last_name, email, campus_code in USERS:
            user, is_new = User.objects.get_or_create(
                username=username,
                defaults={"first_name": first_name, "last_name": last_name, "email": email},
            )
            if is_new:
                user.set_password(DEFAULT_PASSWORD)
                user.save()
                created += 1
            UserProfile.objects.get_or_create(user=user, defaults={"campus": campuses[campus_code]})
            users[username] = user
        self.stdout.write(f"  User: {created} created, {len(USERS) - created} existed")
        return users

    def _set_department_managers(self, departments, users):
        manager_map = {"ADM": "admin_mgr", "HR": "hr_mgr", "ICT": "ict_mgr"}
        for dept_code, mgr_username in manager_map.items():
            dept = departments[dept_code]
            mgr = users[mgr_username]
            if dept.manager_user_id != mgr.pk:
                dept.manager_user = mgr
                dept.save(update_fields=["manager_user"])
        self.stdout.write("  Department managers: set")

    def _seed_campus_departments(self, campuses, departments, users):
        campus_depts = {}
        created = 0
        for campus_code, dept_code, hod_username in CAMPUS_DEPARTMENTS:
            hod = users[hod_username] if hod_username else None
            obj, is_new = CampusDepartment.objects.get_or_create(
                campus=campuses[campus_code],
                department=departments[dept_code],
                defaults={"head_of_department": hod},
            )
            campus_depts[(campus_code, dept_code)] = obj
            if is_new:
                created += 1
        self.stdout.write(f"  CampusDepartment: {created} created, {len(CAMPUS_DEPARTMENTS) - created} existed")
        return campus_depts

    def _seed_sections(self, campus_depts, section_types, users):
        sections = {}
        created = 0
        for campus_code, dept_code, st_code, hos_username, is_active in SECTIONS:
            cd = campus_depts[(campus_code, dept_code)]
            st = section_types[(dept_code, st_code)]
            hos = users[hos_username] if hos_username else None
            obj, is_new = Section.objects.get_or_create(
                campus_department=cd,
                section_type=st,
                defaults={"hos": hos, "is_active": is_active},
            )
            sections[(campus_code, dept_code, st_code)] = obj
            if is_new:
                created += 1
        self.stdout.write(f"  Section: {created} created, {len(SECTIONS) - created} existed")
        return sections

    def _seed_section_technicians(self, users, sections):
        created = 0
        for username, campus_code, dept_code, st_code in SECTION_TECHNICIANS:
            _, is_new = SectionTechnician.objects.get_or_create(
                user=users[username],
                section=sections[(campus_code, dept_code, st_code)],
            )
            if is_new:
                created += 1
        self.stdout.write(f"  SectionTechnician: {created} created")

    def _seed_role_assignments(self, users, departments, campus_depts, sections):
        created = 0
        for username, role, scope_type, scope_key in ROLE_ASSIGNMENTS:
            user = users[username]
            kwargs = {"role": role}
            if scope_type == "department":
                kwargs["department"] = departments[scope_key]
                kwargs["section"] = None
                kwargs["campus_department"] = None
            elif scope_type == "campus_department":
                kwargs["campus_department"] = campus_depts[scope_key]
                kwargs["section"] = None
                kwargs["department"] = None
            elif scope_type == "section":
                kwargs["section"] = sections[scope_key]
                kwargs["campus_department"] = None
                kwargs["department"] = None
            else:
                kwargs["section"] = None
                kwargs["campus_department"] = None
                kwargs["department"] = None
            _, is_new = RoleAssignment.objects.get_or_create(
                user=user,
                is_primary=True,
                defaults=kwargs,
            )
            if is_new:
                created += 1
        self.stdout.write(f"  RoleAssignment: {created} created")

    # ------------------------------------------------------------------
    # Service catalogue
    # ------------------------------------------------------------------

    def _seed_catalogue(self, departments, section_types):
        cat_created = item_created = 0
        for dept_code, st_code, cat_name, location_details, priority_rank, items in CATALOGUE:
            st = section_types[(dept_code, st_code)]
            priority = self.priorities[priority_rank]
            category, is_new = ServiceCategory.objects.get_or_create(
                section_type=st,
                name=cat_name,
                defaults={"location_details": location_details, "default_priority": priority},
            )
            if is_new:
                cat_created += 1
            for item_name in items:
                _, item_new = ServiceItem.objects.get_or_create(
                    category=category, name=item_name
                )
                if item_new:
                    item_created += 1
        self.stdout.write(f"  ServiceCategory: {cat_created} created")
        self.stdout.write(f"  ServiceItem: {item_created} created")

    # ------------------------------------------------------------------
    # Tickets — 30 total, spread across current and previous week
    # ------------------------------------------------------------------

    def _seed_tickets(self, users, sections):
        if Ticket.objects.exists():
            self.stdout.write("  Demo tickets already exist — skipping.")
            return

        now = timezone.now()

        # Date shortcuts (days ago from today)
        def d(days_ago, hour=9):
            return now.replace(hour=hour, minute=0, second=0, microsecond=0) - timedelta(days=days_ago)

        # Ticket helper — create, then back-date created_at and updated_at
        def make_ticket(**kwargs):
            created_at = kwargs.pop("created_at", now)
            updated_at = kwargs.pop("updated_at", created_at)
            t = Ticket.objects.create(**kwargs)
            Ticket.objects.filter(pk=t.pk).update(created_at=created_at, updated_at=updated_at)
            t.refresh_from_db()
            return t

        def make_log(ticket, event_type, from_value, to_value, actor=None,
                     reason="", level_user=None, created_at=None):
            log = TicketLog(
                ticket=ticket,
                actor=actor,
                event_type=event_type,
                from_value=from_value,
                to_value=to_value,
                reason=reason,
                level_user=level_user,
            )
            log.save()
            if created_at:
                TicketLog.objects.filter(pk=log.pk).update(created_at=created_at)
            return log

        # Convenience user & section lookups
        u = users
        sec = sections
        p = self.priorities  # {1: Low, 2: Medium, 3: High, 4: Critical}

        # Service item shortcuts
        def item(category_name, item_name):
            return ServiceItem.objects.get(category__name=category_name, name=item_name)

        plumbing     = item("Maintenance Services",  "Plumbing Services")
        electrical   = item("Maintenance Services",  "Electrical Services")
        carpentry    = item("Maintenance Services",  "Carpentry Services")
        vehicle      = item("Transport Services",    "Vehicle Booking Services")
        rent         = item("Payroll Services",      "Rent Deductions")
        loan         = item("Payroll Services",      "Loan Services")
        file_svc     = item("Registry Services",     "File Services")
        internet     = item("Network Services",      "Internet Services")
        phone        = item("Network Services",      "Phone Services")
        erp          = item("Systems Support",       "ERP Services")
        email_svc    = item("Systems Support",       "Email Services")

        nrb = Campus.objects.get(code="NRB")
        msa = Campus.objects.get(code="MSA")
        ksm = Campus.objects.get(code="KSM")

        # Section aliases
        s_adm_maint   = sec[("NRB", "ADM", "MAINT")]
        s_adm_trans   = sec[("NRB", "ADM", "TRANS")]
        s_hr_payroll  = sec[("NRB", "HR",  "PAYROLL")]
        s_hr_reg      = sec[("NRB", "HR",  "REG")]
        s_ict_net     = sec[("NRB", "ICT", "NET")]
        s_ict_syssupp = sec[("NRB", "ICT", "SYSSUPP")]
        s_msa_hr_pay  = sec[("MSA", "HR",  "PAYROLL")]
        s_msa_ict_net = sec[("MSA", "ICT", "NET")]
        s_ksm_syssupp = sec[("KSM", "ICT", "SYSSUPP")]

        # ----------------------------------------------------------------
        # NRB-ADM-MAINT (6 tickets)
        # ----------------------------------------------------------------

        # T01 — open, unassigned (today)
        t01 = make_ticket(
            raised_by=u["alice.kamau"], requester_campus=nrb,
            service_item=plumbing, priority=p[2], section=s_adm_maint,
            status="open", current_level="technician", assigned_to=None,
            response_due_at=d(0) + timedelta(minutes=240),
            resolution_due_at=d(0) + timedelta(minutes=1440),
            description="Water leak from tap in ground-floor washroom — needs urgent plumber.",
            created_at=d(0, hour=8), updated_at=d(0, hour=8),
        )
        make_log(t01, "created", "", "open", created_at=d(0, hour=8))

        # T02 — assigned (yesterday)
        t02 = make_ticket(
            raised_by=u["carol.njoki"], requester_campus=nrb,
            service_item=electrical, priority=p[3], section=s_adm_maint,
            status="assigned", current_level="technician", assigned_to=u["nrb_maint_tech1"],
            response_due_at=d(1) + timedelta(minutes=60),
            resolution_due_at=d(1) + timedelta(minutes=480),
            description="Power socket in Block A Room 204 is sparking — urgent safety hazard.",
            created_at=d(1, hour=9), updated_at=d(1, hour=10),
        )
        make_log(t02, "created",  "", "open",     actor=None,              created_at=d(1, hour=9))
        make_log(t02, "assigned", "open", "assigned", actor=u["nrb_maint_tech1"], created_at=d(1, hour=10))

        # T03 — in_progress (2 days ago)
        t03 = make_ticket(
            raised_by=u["eve.wanjiru"], requester_campus=nrb,
            service_item=carpentry, priority=p[2], section=s_adm_maint,
            status="in_progress", current_level="technician", assigned_to=u["nrb_maint_tech2"],
            response_due_at=d(2) + timedelta(minutes=240),
            resolution_due_at=d(2) + timedelta(minutes=1440),
            description="Broken window frame in Conference Room B — needs replacement.",
            created_at=d(2, hour=10), updated_at=d(2, hour=14),
        )
        make_log(t03, "created",      "", "open",        created_at=d(2, hour=10))
        make_log(t03, "assigned",     "open", "assigned",     actor=u["nrb_maint_tech2"], created_at=d(2, hour=11))
        make_log(t03, "status_changed","assigned", "in_progress", actor=u["nrb_maint_tech2"], created_at=d(2, hour=14))

        # T04 — pending, SLA paused (7 days ago)
        t04 = make_ticket(
            raised_by=u["alice.kamau"], requester_campus=nrb,
            service_item=plumbing, priority=p[2], section=s_adm_maint,
            status="pending", current_level="technician", assigned_to=u["nrb_maint_tech1"],
            paused_at=d(5, hour=16),
            response_due_at=d(7) + timedelta(minutes=240),
            resolution_due_at=d(7) + timedelta(minutes=1440),
            description="Burst pipe in first-floor kitchen — awaiting replacement parts.",
            created_at=d(7, hour=8), updated_at=d(5, hour=16),
        )
        make_log(t04, "created",       "", "open",          created_at=d(7, hour=8))
        make_log(t04, "assigned",      "open", "assigned",      actor=u["nrb_maint_tech1"], created_at=d(7, hour=9))
        make_log(t04, "status_changed","assigned", "in_progress", actor=u["nrb_maint_tech1"], created_at=d(7, hour=11))
        make_log(t04, "status_changed","in_progress", "pending",  actor=u["nrb_maint_tech1"],
                 reason="Awaiting spare pipe fittings delivery", created_at=d(5, hour=16))

        # T05 — resolved with feedback (8 days ago)
        t05 = make_ticket(
            raised_by=u["carol.njoki"], requester_campus=nrb,
            service_item=electrical, priority=p[3], section=s_adm_maint,
            status="resolved", current_level="technician", assigned_to=u["nrb_maint_tech2"],
            response_due_at=d(8) + timedelta(minutes=60),
            resolution_due_at=d(8) + timedelta(minutes=480),
            resolved_at=d(8, hour=16),
            description="Faulty MCB in server room tripping circuit breaker repeatedly.",
            created_at=d(8, hour=9), updated_at=d(8, hour=16),
        )
        make_log(t05, "created",  "", "open",     created_at=d(8, hour=9))
        make_log(t05, "assigned", "open", "assigned", actor=u["nrb_maint_tech2"], created_at=d(8, hour=10))
        make_log(t05, "resolved", "in_progress", "resolved", actor=u["nrb_maint_tech2"], created_at=d(8, hour=16))
        TicketFeedback.objects.create(ticket=t05, rating=5, comment="Fixed within hours, very professional.")

        # T06 — closed (9 days ago)
        t06 = make_ticket(
            raised_by=u["alice.kamau"], requester_campus=nrb,
            service_item=carpentry, priority=p[1], section=s_adm_maint,
            status="closed", current_level="technician", assigned_to=u["nrb_maint_tech1"],
            response_due_at=d(9) + timedelta(minutes=480),
            resolution_due_at=d(9) + timedelta(minutes=4320),
            resolved_at=d(8, hour=15),
            closed_at=d(7, hour=9),
            description="Door hinge on HOD office door broken — needs replacement.",
            created_at=d(9, hour=8), updated_at=d(7, hour=9),
        )
        make_log(t06, "created",  "", "open",       created_at=d(9, hour=8))
        make_log(t06, "assigned", "open", "assigned",  actor=u["nrb_maint_tech1"], created_at=d(9, hour=11))
        make_log(t06, "resolved", "in_progress", "resolved", actor=u["nrb_maint_tech1"], created_at=d(8, hour=15))
        make_log(t06, "closed",   "resolved", "closed",      actor=u["nrb_maint_hos"], created_at=d(7, hour=9))

        # ----------------------------------------------------------------
        # NRB-ADM-TRANS (4 tickets)
        # ----------------------------------------------------------------

        # T07 — open, unassigned (today)
        t07 = make_ticket(
            raised_by=u["eve.wanjiru"], requester_campus=nrb,
            service_item=vehicle, priority=p[2], section=s_adm_trans,
            status="open", current_level="technician", assigned_to=None,
            response_due_at=d(0) + timedelta(minutes=240),
            resolution_due_at=d(0) + timedelta(minutes=1440),
            description="Request for vehicle booking to Nakuru on 2026-06-14 for workshop attendance.",
            created_at=d(0, hour=10), updated_at=d(0, hour=10),
        )
        make_log(t07, "created", "", "open", created_at=d(0, hour=10))

        # T08 — assigned (yesterday)
        t08 = make_ticket(
            raised_by=u["alice.kamau"], requester_campus=nrb,
            service_item=vehicle, priority=p[2], section=s_adm_trans,
            status="assigned", current_level="technician", assigned_to=u["nrb_transport_tech1"],
            response_due_at=d(1) + timedelta(minutes=240),
            resolution_due_at=d(1) + timedelta(minutes=1440),
            description="Vehicle required for official duty to Kiambu County Government on Monday.",
            created_at=d(1, hour=8), updated_at=d(1, hour=11),
        )
        make_log(t08, "created",  "", "open",       created_at=d(1, hour=8))
        make_log(t08, "assigned", "open", "assigned", actor=u["nrb_transport_tech1"], created_at=d(1, hour=11))

        # T09 — pending (5 days ago)
        t09 = make_ticket(
            raised_by=u["carol.njoki"], requester_campus=nrb,
            service_item=vehicle, priority=p[2], section=s_adm_trans,
            status="pending", current_level="technician", assigned_to=u["nrb_transport_tech1"],
            paused_at=d(4, hour=15),
            response_due_at=d(5) + timedelta(minutes=240),
            resolution_due_at=d(5) + timedelta(minutes=1440),
            description="Matatu hire request for staff team building — awaiting finance approval.",
            created_at=d(5, hour=9), updated_at=d(4, hour=15),
        )
        make_log(t09, "created",       "", "open",           created_at=d(5, hour=9))
        make_log(t09, "assigned",      "open", "assigned",      actor=u["nrb_transport_tech1"], created_at=d(5, hour=12))
        make_log(t09, "status_changed","assigned", "pending",    actor=u["nrb_transport_tech1"],
                 reason="Pending Finance department approval for hire charges", created_at=d(4, hour=15))

        # T10 — closed (8 days ago)
        t10 = make_ticket(
            raised_by=u["eve.wanjiru"], requester_campus=nrb,
            service_item=vehicle, priority=p[1], section=s_adm_trans,
            status="closed", current_level="technician", assigned_to=u["nrb_transport_tech1"],
            response_due_at=d(8) + timedelta(minutes=480),
            resolution_due_at=d(8) + timedelta(minutes=4320),
            resolved_at=d(7, hour=17),
            closed_at=d(6, hour=9),
            description="Airport pickup for guest trainer arriving for ICT skills bootcamp.",
            created_at=d(8, hour=7), updated_at=d(6, hour=9),
        )
        make_log(t10, "created",  "", "open",        created_at=d(8, hour=7))
        make_log(t10, "assigned", "open", "assigned",  actor=u["nrb_transport_tech1"], created_at=d(8, hour=9))
        make_log(t10, "resolved", "in_progress", "resolved", actor=u["nrb_transport_tech1"], created_at=d(7, hour=17))
        make_log(t10, "closed",   "resolved", "closed",      actor=u["nrb_transport_hos"], created_at=d(6, hour=9))

        # ----------------------------------------------------------------
        # NRB-HR-PAYROLL (4 tickets)
        # ----------------------------------------------------------------

        # T11 — open, unassigned (today)
        t11 = make_ticket(
            raised_by=u["alice.kamau"], requester_campus=nrb,
            service_item=rent, priority=p[2], section=s_hr_payroll,
            status="open", current_level="technician", assigned_to=None,
            response_due_at=d(0) + timedelta(minutes=240),
            resolution_due_at=d(0) + timedelta(minutes=1440),
            description="Incorrect house rent deduction appearing on May 2026 payslip — needs review.",
            created_at=d(0, hour=9), updated_at=d(0, hour=9),
        )
        make_log(t11, "created", "", "open", created_at=d(0, hour=9))

        # T12 — in_progress (2 days ago)
        t12 = make_ticket(
            raised_by=u["carol.njoki"], requester_campus=nrb,
            service_item=loan, priority=p[2], section=s_hr_payroll,
            status="in_progress", current_level="technician", assigned_to=u["nrb_payroll_tech1"],
            response_due_at=d(2) + timedelta(minutes=240),
            resolution_due_at=d(2) + timedelta(minutes=1440),
            description="Staff loan repayment schedule not updated after balance clearance in April.",
            created_at=d(2, hour=11), updated_at=d(2, hour=15),
        )
        make_log(t12, "created",       "", "open",          created_at=d(2, hour=11))
        make_log(t12, "assigned",      "open", "assigned",    actor=u["nrb_payroll_tech1"], created_at=d(2, hour=12))
        make_log(t12, "status_changed","assigned", "in_progress", actor=u["nrb_payroll_tech1"], created_at=d(2, hour=15))

        # T13 — pending (5 days ago)
        t13 = make_ticket(
            raised_by=u["eve.wanjiru"], requester_campus=nrb,
            service_item=rent, priority=p[2], section=s_hr_payroll,
            status="pending", current_level="technician", assigned_to=u["nrb_payroll_tech2"],
            paused_at=d(3, hour=14),
            response_due_at=d(5) + timedelta(minutes=240),
            resolution_due_at=d(5) + timedelta(minutes=1440),
            description="Rent deduction applied twice in June payroll — awaiting payroll officer confirmation.",
            created_at=d(5, hour=8), updated_at=d(3, hour=14),
        )
        make_log(t13, "created",       "", "open",         created_at=d(5, hour=8))
        make_log(t13, "assigned",      "open", "assigned",   actor=u["nrb_payroll_tech2"], created_at=d(5, hour=10))
        make_log(t13, "status_changed","assigned", "in_progress", actor=u["nrb_payroll_tech2"], created_at=d(5, hour=11))
        make_log(t13, "status_changed","in_progress", "pending",  actor=u["nrb_payroll_tech2"],
                 reason="Pending confirmation from Payroll Officer on deduction category", created_at=d(3, hour=14))

        # T14 — resolved with feedback (7 days ago)
        t14 = make_ticket(
            raised_by=u["alice.kamau"], requester_campus=nrb,
            service_item=loan, priority=p[2], section=s_hr_payroll,
            status="resolved", current_level="technician", assigned_to=u["nrb_payroll_tech1"],
            response_due_at=d(7) + timedelta(minutes=240),
            resolution_due_at=d(7) + timedelta(minutes=1440),
            resolved_at=d(6, hour=16),
            description="Application for staff mortgage-backed loan — first submission for review.",
            created_at=d(7, hour=9), updated_at=d(6, hour=16),
        )
        make_log(t14, "created",  "", "open",      created_at=d(7, hour=9))
        make_log(t14, "assigned", "open", "assigned", actor=u["nrb_payroll_tech1"], created_at=d(7, hour=11))
        make_log(t14, "resolved", "in_progress", "resolved", actor=u["nrb_payroll_tech1"], created_at=d(6, hour=16))
        TicketFeedback.objects.create(ticket=t14, rating=4, comment="Processed efficiently, good follow-up.")

        # ----------------------------------------------------------------
        # NRB-HR-REG (4 tickets)
        # ----------------------------------------------------------------

        # T15 — open, unassigned (yesterday)
        t15 = make_ticket(
            raised_by=u["carol.njoki"], requester_campus=nrb,
            service_item=file_svc, priority=p[1], section=s_hr_reg,
            status="open", current_level="technician", assigned_to=None,
            response_due_at=d(1) + timedelta(minutes=480),
            resolution_due_at=d(1) + timedelta(minutes=4320),
            description="Personal file not found in registry during internal audit — needs tracing.",
            created_at=d(1, hour=14), updated_at=d(1, hour=14),
        )
        make_log(t15, "created", "", "open", created_at=d(1, hour=14))

        # T16 — assigned (2 days ago)
        t16 = make_ticket(
            raised_by=u["eve.wanjiru"], requester_campus=nrb,
            service_item=file_svc, priority=p[2], section=s_hr_reg,
            status="assigned", current_level="technician", assigned_to=u["nrb_registry_tech1"],
            response_due_at=d(2) + timedelta(minutes=240),
            resolution_due_at=d(2) + timedelta(minutes=1440),
            description="Request for certified copy of appointment letter from HR registry.",
            created_at=d(2, hour=9), updated_at=d(2, hour=13),
        )
        make_log(t16, "created",  "", "open",      created_at=d(2, hour=9))
        make_log(t16, "assigned", "open", "assigned", actor=u["nrb_registry_tech1"], created_at=d(2, hour=13))

        # T17 — in_progress (3 days ago)
        t17 = make_ticket(
            raised_by=u["alice.kamau"], requester_campus=nrb,
            service_item=file_svc, priority=p[2], section=s_hr_reg,
            status="in_progress", current_level="technician", assigned_to=u["nrb_registry_tech1"],
            response_due_at=d(3) + timedelta(minutes=240),
            resolution_due_at=d(3) + timedelta(minutes=1440),
            description="Training completion certificates from 2024 needed for promotion application.",
            created_at=d(3, hour=10), updated_at=d(3, hour=15),
        )
        make_log(t17, "created",       "", "open",         created_at=d(3, hour=10))
        make_log(t17, "assigned",      "open", "assigned",   actor=u["nrb_registry_tech1"], created_at=d(3, hour=11))
        make_log(t17, "status_changed","assigned", "in_progress", actor=u["nrb_registry_tech1"], created_at=d(3, hour=15))

        # T18 — closed (9 days ago)
        t18 = make_ticket(
            raised_by=u["carol.njoki"], requester_campus=nrb,
            service_item=file_svc, priority=p[1], section=s_hr_reg,
            status="closed", current_level="technician", assigned_to=u["nrb_registry_tech1"],
            response_due_at=d(9) + timedelta(minutes=480),
            resolution_due_at=d(9) + timedelta(minutes=4320),
            resolved_at=d(7, hour=14),
            closed_at=d(6, hour=10),
            description="Filing of new employee documentation for February 2026 intake.",
            created_at=d(9, hour=9), updated_at=d(6, hour=10),
        )
        make_log(t18, "created",  "", "open",        created_at=d(9, hour=9))
        make_log(t18, "assigned", "open", "assigned",  actor=u["nrb_registry_tech1"], created_at=d(9, hour=12))
        make_log(t18, "resolved", "in_progress", "resolved", actor=u["nrb_registry_tech1"], created_at=d(7, hour=14))
        make_log(t18, "closed",   "resolved", "closed",      actor=u["nrb_registry_hos"], created_at=d(6, hour=10))

        # ----------------------------------------------------------------
        # NRB-ICT-NET (5 tickets)
        # ----------------------------------------------------------------

        # T19 — open, unassigned (today)
        t19 = make_ticket(
            raised_by=u["eve.wanjiru"], requester_campus=nrb,
            service_item=internet, priority=p[3], section=s_ict_net,
            status="open", current_level="technician", assigned_to=None,
            response_due_at=d(0) + timedelta(minutes=60),
            resolution_due_at=d(0) + timedelta(minutes=480),
            description="Internet connectivity completely down in Block B second floor since 7am.",
            created_at=d(0, hour=7), updated_at=d(0, hour=7),
        )
        make_log(t19, "created", "", "open", created_at=d(0, hour=7))

        # T20 — in_progress (yesterday)
        t20 = make_ticket(
            raised_by=u["alice.kamau"], requester_campus=nrb,
            service_item=phone, priority=p[2], section=s_ict_net,
            status="in_progress", current_level="technician", assigned_to=u["nrb_networks_tech1"],
            response_due_at=d(1) + timedelta(minutes=240),
            resolution_due_at=d(1) + timedelta(minutes=1440),
            description="Extension 2045 not receiving incoming calls — dead tone on handset.",
            created_at=d(1, hour=10), updated_at=d(1, hour=14),
        )
        make_log(t20, "created",       "", "open",          created_at=d(1, hour=10))
        make_log(t20, "assigned",      "open", "assigned",    actor=u["nrb_networks_tech1"], created_at=d(1, hour=11))
        make_log(t20, "status_changed","assigned", "in_progress", actor=u["nrb_networks_tech1"], created_at=d(1, hour=14))

        # T21 — in_progress escalated to HOS (5 days ago)
        t21 = make_ticket(
            raised_by=u["carol.njoki"], requester_campus=nrb,
            service_item=internet, priority=p[3], section=s_ict_net,
            status="in_progress", current_level="hos", assigned_to=u["nrb_networks_tech2"],
            response_due_at=d(5) + timedelta(minutes=60),
            resolution_due_at=d(5) + timedelta(minutes=480),
            description="Entire campus network unstable — intermittent dropouts across all buildings.",
            created_at=d(5, hour=8), updated_at=d(4, hour=9),
        )
        make_log(t21, "created",       "", "open",          created_at=d(5, hour=8))
        make_log(t21, "assigned",      "open", "assigned",    actor=u["nrb_networks_tech2"], created_at=d(5, hour=9))
        make_log(t21, "status_changed","assigned", "in_progress", actor=u["nrb_networks_tech2"], created_at=d(5, hour=11))
        make_log(t21, "escalated",     "technician", "hos",    level_user=u["nrb_networks_hos"],
                 reason="Unresolved after 4 hours — escalating to HOS", created_at=d(4, hour=9))

        # T22 — resolved with feedback (6 days ago)
        t22 = make_ticket(
            raised_by=u["eve.wanjiru"], requester_campus=nrb,
            service_item=phone, priority=p[2], section=s_ict_net,
            status="resolved", current_level="technician", assigned_to=u["nrb_networks_tech1"],
            response_due_at=d(6) + timedelta(minutes=240),
            resolution_due_at=d(6) + timedelta(minutes=1440),
            resolved_at=d(5, hour=17),
            description="New IP phone needs configuration and registration on PABX system.",
            created_at=d(6, hour=9), updated_at=d(5, hour=17),
        )
        make_log(t22, "created",  "", "open",      created_at=d(6, hour=9))
        make_log(t22, "assigned", "open", "assigned", actor=u["nrb_networks_tech1"], created_at=d(6, hour=10))
        make_log(t22, "resolved", "in_progress", "resolved", actor=u["nrb_networks_tech1"], created_at=d(5, hour=17))
        TicketFeedback.objects.create(ticket=t22, rating=5, comment="Configured same day, no downtime.")

        # T23 — closed (8 days ago)
        t23 = make_ticket(
            raised_by=u["alice.kamau"], requester_campus=nrb,
            service_item=internet, priority=p[4], section=s_ict_net,
            status="closed", current_level="technician", assigned_to=u["nrb_networks_hos"],
            response_due_at=d(8) + timedelta(minutes=30),
            resolution_due_at=d(8) + timedelta(minutes=120),
            resolved_at=d(8, hour=14),
            closed_at=d(7, hour=10),
            description="NRB campus-wide network outage — fibre cable cut near main gate.",
            created_at=d(8, hour=11), updated_at=d(7, hour=10),
        )
        make_log(t23, "created",  "", "open",         created_at=d(8, hour=11))
        make_log(t23, "assigned", "open", "assigned",   actor=u["nrb_networks_hos"], created_at=d(8, hour=11))
        make_log(t23, "resolved", "in_progress", "resolved", actor=u["nrb_networks_hos"], created_at=d(8, hour=14))
        make_log(t23, "closed",   "resolved", "closed",      actor=u["nrb_ict_hod"], created_at=d(7, hour=10))

        # ----------------------------------------------------------------
        # NRB-ICT-SYSSUPP (5 tickets)
        # ----------------------------------------------------------------

        # T24 — open, unassigned (today)
        t24 = make_ticket(
            raised_by=u["carol.njoki"], requester_campus=nrb,
            service_item=erp, priority=p[3], section=s_ict_syssupp,
            status="open", current_level="technician", assigned_to=None,
            response_due_at=d(0) + timedelta(minutes=60),
            resolution_due_at=d(0) + timedelta(minutes=480),
            description="ERP procurement module throwing error on PO approval — blocking operations.",
            created_at=d(0, hour=11), updated_at=d(0, hour=11),
        )
        make_log(t24, "created", "", "open", created_at=d(0, hour=11))

        # T25 — assigned (yesterday)
        t25 = make_ticket(
            raised_by=u["eve.wanjiru"], requester_campus=nrb,
            service_item=email_svc, priority=p[2], section=s_ict_syssupp,
            status="assigned", current_level="technician", assigned_to=u["nrb_syssupport_tech1"],
            response_due_at=d(1) + timedelta(minutes=240),
            resolution_due_at=d(1) + timedelta(minutes=1440),
            description="Email account not syncing on new laptop after migration to Microsoft 365.",
            created_at=d(1, hour=9), updated_at=d(1, hour=12),
        )
        make_log(t25, "created",  "", "open",      created_at=d(1, hour=9))
        make_log(t25, "assigned", "open", "assigned", actor=u["nrb_syssupport_tech1"], created_at=d(1, hour=12))

        # T26 — in_progress (3 days ago)
        t26 = make_ticket(
            raised_by=u["alice.kamau"], requester_campus=nrb,
            service_item=erp, priority=p[2], section=s_ict_syssupp,
            status="in_progress", current_level="technician", assigned_to=u["nrb_syssupport_tech2"],
            response_due_at=d(3) + timedelta(minutes=240),
            resolution_due_at=d(3) + timedelta(minutes=1440),
            description="Staff cannot log in to ERP leave module — account locked after failed attempts.",
            created_at=d(3, hour=8), updated_at=d(3, hour=13),
        )
        make_log(t26, "created",       "", "open",          created_at=d(3, hour=8))
        make_log(t26, "assigned",      "open", "assigned",    actor=u["nrb_syssupport_tech2"], created_at=d(3, hour=9))
        make_log(t26, "status_changed","assigned", "in_progress", actor=u["nrb_syssupport_tech2"], created_at=d(3, hour=13))

        # T27 — in_progress escalated to HOD (7 days ago)
        t27 = make_ticket(
            raised_by=u["carol.njoki"], requester_campus=nrb,
            service_item=erp, priority=p[3], section=s_ict_syssupp,
            status="in_progress", current_level="hod", assigned_to=u["nrb_syssupport_tech1"],
            response_due_at=d(7) + timedelta(minutes=60),
            resolution_due_at=d(7) + timedelta(minutes=480),
            description="ERP payroll integration broken — salaries not posting to finance module.",
            created_at=d(7, hour=7), updated_at=d(6, hour=8),
        )
        make_log(t27, "created",       "", "open",          created_at=d(7, hour=7))
        make_log(t27, "assigned",      "open", "assigned",    actor=u["nrb_syssupport_tech1"], created_at=d(7, hour=8))
        make_log(t27, "status_changed","assigned", "in_progress", actor=u["nrb_syssupport_tech1"], created_at=d(7, hour=9))
        make_log(t27, "escalated",     "technician", "hos",    level_user=u["nrb_syssupport_hos"],
                 reason="Not resolved in 4 hours — escalating", created_at=d(7, hour=13))
        make_log(t27, "escalated",     "hos", "hod",            level_user=u["nrb_ict_hod"],
                 reason="Requires executive sign-off on ERP vendor engagement", created_at=d(6, hour=8))

        # T28 — resolved, no feedback (5 days ago)
        t28 = make_ticket(
            raised_by=u["eve.wanjiru"], requester_campus=nrb,
            service_item=email_svc, priority=p[2], section=s_ict_syssupp,
            status="resolved", current_level="technician", assigned_to=u["nrb_syssupport_tech2"],
            response_due_at=d(5) + timedelta(minutes=240),
            resolution_due_at=d(5) + timedelta(minutes=1440),
            resolved_at=d(4, hour=15),
            description="Shared mailbox for Finance department not accessible to new members.",
            created_at=d(5, hour=10), updated_at=d(4, hour=15),
        )
        make_log(t28, "created",  "", "open",      created_at=d(5, hour=10))
        make_log(t28, "assigned", "open", "assigned", actor=u["nrb_syssupport_tech2"], created_at=d(5, hour=11))
        make_log(t28, "resolved", "in_progress", "resolved", actor=u["nrb_syssupport_tech2"], created_at=d(4, hour=15))

        # ----------------------------------------------------------------
        # MSA-HR-PAYROLL (1 ticket)
        # ----------------------------------------------------------------

        # T29 — resolved with feedback (6 days ago)
        t29 = make_ticket(
            raised_by=u["bob.mwenda"], requester_campus=msa,
            service_item=loan, priority=p[2], section=s_msa_hr_pay,
            status="resolved", current_level="technician", assigned_to=u["msa_payroll_hos"],
            response_due_at=d(6) + timedelta(minutes=240),
            resolution_due_at=d(6) + timedelta(minutes=1440),
            resolved_at=d(5, hour=16),
            description="Staff loan balance not reflected after recent lump-sum payment at MSA campus.",
            created_at=d(6, hour=10), updated_at=d(5, hour=16),
        )
        make_log(t29, "created",  "", "open",      created_at=d(6, hour=10))
        make_log(t29, "assigned", "open", "assigned", actor=u["msa_payroll_hos"], created_at=d(6, hour=11))
        make_log(t29, "resolved", "in_progress", "resolved", actor=u["msa_payroll_hos"], created_at=d(5, hour=16))
        TicketFeedback.objects.create(ticket=t29, rating=4, comment="Resolved promptly despite cross-campus request.")

        # ----------------------------------------------------------------
        # MSA-ICT-NET (1 ticket)
        # ----------------------------------------------------------------

        # T30 — open, unassigned (2 days ago)
        t30 = make_ticket(
            raised_by=u["bob.mwenda"], requester_campus=msa,
            service_item=internet, priority=p[2], section=s_msa_ict_net,
            status="open", current_level="technician", assigned_to=None,
            response_due_at=d(2) + timedelta(minutes=240),
            resolution_due_at=d(2) + timedelta(minutes=1440),
            description="MSA campus Wi-Fi unreachable in lecture hall LH3 — students unable to access LMS.",
            created_at=d(2, hour=13), updated_at=d(2, hour=13),
        )
        make_log(t30, "created", "", "open", created_at=d(2, hour=13))

        # ----------------------------------------------------------------
        # KSM-ICT-SYSSUPP (1 ticket)
        # ----------------------------------------------------------------

        # T31 — in_progress (1 day ago)  [brings total to 30 NRB + 2 MSA... wait]
        # NOTE: ticket count across sections:
        #   NRB-ADM-MAINT: T01-T06 (6)
        #   NRB-ADM-TRANS: T07-T10 (4)
        #   NRB-HR-PAYROLL: T11-T14 (4)
        #   NRB-HR-REG: T15-T18 (4)
        #   NRB-ICT-NET: T19-T23 (5)
        #   NRB-ICT-SYSSUPP: T24-T28 (5)   ← 28 so far
        #   MSA-HR-PAYROLL: T29 (1)
        #   MSA-ICT-NET: T30 (1)
        #   KSM-ICT-SYSSUPP: T31-T32 below (2)  → total 32... need to trim 2
        # We'll stop at T30; total is already 30. KSM skipped in tickets.

        # (No KSM tickets — org structure present, tickets TBD after more data)

        count = Ticket.objects.count()
        self.stdout.write(f"  Ticket: {count} created with logs and feedback")

    # ------------------------------------------------------------------
    # Ticket locations (maintenance tickets → campus facilities)
    # ------------------------------------------------------------------

    def _seed_ticket_locations(self):
        """Attach maintenance-section tickets to campus facilities via TicketLocation.

        Maintenance Services has location_details=True, so every maintenance
        ticket should have a TicketLocation. We assign NRB tickets to NRB
        facilities. MSA / KSM maintenance sections have no demo tickets yet.

        Idempotent — skips tickets that already have a location.
        """
        from apps.facilities.models import Facility, FacilityType

        try:
            ft_office  = FacilityType.objects.get(code="office_block")
            ft_building = FacilityType.objects.get(code="building")
        except FacilityType.DoesNotExist:
            self.stdout.write("  TicketLocation: FacilityType not found — skipping")
            return

        # NRB facility lookup by code
        def fac(code):
            return Facility.objects.get(code=code)

        # (ticket_no, facility_code, facility_type, location values JSON)
        LOCATIONS = [
            ("TKT-NRB-ADM-0001", "NRB-AB-A",  ft_office,   {"floor": "1", "room": "101", "area": "Plumbing riser"}),
            ("TKT-NRB-ADM-0002", "NRB-FIN",   ft_office,   {"floor": "2", "room": "Finance Lab", "area": "Server room"}),
            ("TKT-NRB-ADM-0003", "NRB-MH",    ft_building, {"floor": "Ground", "room": "Stage", "area": "Roof support"}),
            ("TKT-NRB-ADM-0004", "NRB-CC",    ft_building, {"floor": "1", "room": "Board Room", "area": "Washroom"}),
            ("TKT-NRB-ADM-0005", "NRB-AB-B",  ft_office,   {"floor": "3", "room": "305", "area": "Electrical panel"}),
            ("TKT-NRB-ADM-0006", "NRB-SC",    ft_building, {"floor": "Ground", "room": "Kitchen", "area": "Ceiling boards"}),
        ]

        created = 0
        for ticket_no, fac_code, fac_type, values in LOCATIONS:
            try:
                ticket = Ticket.objects.get(ticket_no=ticket_no)
            except Ticket.DoesNotExist:
                continue
            if hasattr(ticket, "location"):
                continue  # already has a location
            facility = fac(fac_code)
            TicketLocation.objects.create(
                ticket=ticket,
                facility_type=fac_type,
                facility=facility,
                values=values,
            )
            created += 1

        self.stdout.write(f"  TicketLocation: {created} created")
