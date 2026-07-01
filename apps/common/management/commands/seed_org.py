"""
Idempotent seed for org structure (campuses, departments, sections, users, roles).

Seeds:
  - Campus: NRB, MSA
  - Department: ICT, FAC (with global managers)
  - SectionType: per department
  - CustomUser + UserProfile: operational users
  - CampusDepartment: campus×department mappings with HODs
  - Section: campus-specific section instances with HOS
  - SectionTechnician: technician→section memberships
  - RoleAssignment: primary role assignments

Safe to run multiple times (get_or_create by natural key throughout).
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.accounts.models import RoleAssignment, UserProfile
from apps.org.models import (
    Campus,
    CampusDepartment,
    Department,
    Section,
    SectionTechnician,
    SectionType,
)

User = get_user_model()

# ---------------------------------------------------------------------------
# Static data tables
# ---------------------------------------------------------------------------

CAMPUSES = [
    {"name": "Nairobi", "code": "NRB", "location": "Nairobi CBD"},
    {"name": "Mombasa", "code": "MSA", "location": "Mombasa Island"},
]

DEPARTMENTS = [
    {"name": "ICT",        "code": "ICT"},
    {"name": "Facilities", "code": "FAC"},
]

# (dept_code, name, code)
SECTION_TYPES = [
    ("ICT", "ICT Support", "ICTSUPP"),
    ("ICT", "Networks",    "NET"),
    ("FAC", "Maintenance", "MAINT"),
    ("FAC", "Grounds",     "GRND"),
]

# (username, first_name, last_name, email, campus_code)
USERS = [
    ("admin_user",          "System",  "Admin",   "admin@resolver.local",             "NRB"),
    ("ict_manager",         "James",   "Mwangi",  "ict.manager@resolver.local",        "NRB"),
    ("fac_manager",         "Grace",   "Otieno",  "fac.manager@resolver.local",        "NRB"),
    ("nrb_ict_hod",         "Brian",   "Kariuki", "nrb.ict.hod@resolver.local",        "NRB"),
    ("nrb_fac_hod",         "Sarah",   "Wanjiku", "nrb.fac.hod@resolver.local",        "NRB"),
    ("msa_ict_hod",         "Ahmed",   "Hassan",  "msa.ict.hod@resolver.local",        "MSA"),
    ("nrb_ict_supp_hos",    "Achieng", "Otieno",  "nrb.ict.supp.hos@resolver.local",   "NRB"),
    ("nrb_ict_net_hos",     "Peter",   "Maina",   "nrb.ict.net.hos@resolver.local",    "NRB"),
    ("nrb_fac_maint_hos",   "Lucy",    "Njeri",   "nrb.fac.maint.hos@resolver.local",  "NRB"),
    ("tech1",               "John",    "Doe",     "tech1@resolver.local",              "NRB"),
    ("tech2",               "Jane",    "Smith",   "tech2@resolver.local",              "NRB"),
    ("senior_tech",         "David",   "Omondi",  "senior.tech@resolver.local",        "NRB"),
    ("tech3",               "Mary",    "Waweru",  "tech3@resolver.local",              "NRB"),
    ("requester1",          "Alice",   "Kamau",   "requester1@resolver.local",         "NRB"),
    ("requester2",          "Bob",     "Mwenda",  "requester2@resolver.local",         "MSA"),
]

DEFAULT_PASSWORD = "***REMOVED-DEMO-PASSWORD***"

# (campus_code, dept_code, hod_username_or_None)
CAMPUS_DEPARTMENTS = [
    ("NRB", "ICT", "nrb_ict_hod"),
    ("NRB", "FAC", "nrb_fac_hod"),
    ("MSA", "ICT", "msa_ict_hod"),
    ("MSA", "FAC", None),
]

# (campus_code, dept_code, section_type_code, hos_username_or_None, is_active)
SECTIONS = [
    ("NRB", "ICT", "ICTSUPP", "nrb_ict_supp_hos",  True),
    ("NRB", "ICT", "NET",     "nrb_ict_net_hos",    True),
    ("NRB", "FAC", "MAINT",   "nrb_fac_maint_hos",  True),
    ("NRB", "FAC", "GRND",    None,                  True),
    ("MSA", "ICT", "ICTSUPP", None,                  True),
]

# (username, campus_code, dept_code, section_type_code)
SECTION_TECHNICIANS = [
    ("tech1",      "NRB", "ICT", "ICTSUPP"),
    ("tech2",      "NRB", "ICT", "ICTSUPP"),
    ("senior_tech","NRB", "ICT", "ICTSUPP"),
    ("tech3",      "NRB", "FAC", "MAINT"),
]

# (username, role, scope_type, scope_key)
# scope_type: "none" | "department" | "campus_department" | "section"
# scope_key for department: dept_code
# scope_key for campus_department: (campus_code, dept_code)
# scope_key for section: (campus_code, dept_code, section_type_code)
ROLE_ASSIGNMENTS = [
    ("admin_user",        "admin",      "none",             None),
    ("requester1",        "user",       "none",             None),
    ("requester2",        "user",       "none",             None),
    ("ict_manager",       "manager",    "department",       "ICT"),
    ("fac_manager",       "manager",    "department",       "FAC"),
    ("nrb_ict_hod",       "hod",        "campus_department",("NRB", "ICT")),
    ("nrb_fac_hod",       "hod",        "campus_department",("NRB", "FAC")),
    ("msa_ict_hod",       "hod",        "campus_department",("MSA", "ICT")),
    ("nrb_ict_supp_hos",  "hos",        "section",          ("NRB", "ICT", "ICTSUPP")),
    ("nrb_ict_net_hos",   "hos",        "section",          ("NRB", "ICT", "NET")),
    ("nrb_fac_maint_hos", "hos",        "section",          ("NRB", "FAC", "MAINT")),
    ("tech1",             "technician", "section",          ("NRB", "ICT", "ICTSUPP")),
    ("tech2",             "technician", "section",          ("NRB", "ICT", "ICTSUPP")),
    ("senior_tech",       "technician", "section",          ("NRB", "ICT", "ICTSUPP")),
    ("tech3",             "technician", "section",          ("NRB", "FAC", "MAINT")),
]


class Command(BaseCommand):
    help = "Seed org structure: campuses, departments, sections, users, roles (idempotent)"

    def handle(self, *args, **options):
        campuses = self._seed_campuses()
        departments = self._seed_departments()
        section_types = self._seed_section_types(departments)
        users = self._seed_users(campuses)
        self._set_department_managers(departments, users)
        campus_departments = self._seed_campus_departments(campuses, departments, users)
        sections = self._seed_sections(campus_departments, section_types, users)
        self._seed_section_technicians(users, sections)
        self._seed_role_assignments(users, departments, campus_departments, sections)
        self.stdout.write(self.style.SUCCESS("Org data seeded successfully."))

    # ------------------------------------------------------------------
    # Campuses
    # ------------------------------------------------------------------

    def _seed_campuses(self):
        created = 0
        campuses = {}
        for c in CAMPUSES:
            obj, is_new = Campus.objects.get_or_create(
                code=c["code"],
                defaults={"name": c["name"], "location": c["location"]},
            )
            campuses[c["code"]] = obj
            if is_new:
                created += 1
        self.stdout.write(
            f"  Campus: {created} created, {len(CAMPUSES) - created} already existed"
        )
        return campuses

    # ------------------------------------------------------------------
    # Departments
    # ------------------------------------------------------------------

    def _seed_departments(self):
        created = 0
        departments = {}
        for d in DEPARTMENTS:
            obj, is_new = Department.objects.get_or_create(
                code=d["code"],
                defaults={"name": d["name"]},
            )
            departments[d["code"]] = obj
            if is_new:
                created += 1
        self.stdout.write(
            f"  Department: {created} created, {len(DEPARTMENTS) - created} already existed"
        )
        return departments

    # ------------------------------------------------------------------
    # SectionTypes
    # ------------------------------------------------------------------

    def _seed_section_types(self, departments):
        created = 0
        section_types = {}
        for dept_code, name, code in SECTION_TYPES:
            dept = departments[dept_code]
            obj, is_new = SectionType.objects.get_or_create(
                department=dept,
                name=name,
                defaults={"code": code},
            )
            # key: (dept_code, section_type_code)
            section_types[(dept_code, code)] = obj
            if is_new:
                created += 1
        self.stdout.write(
            f"  SectionType: {created} created, {len(SECTION_TYPES) - created} already existed"
        )
        return section_types

    # ------------------------------------------------------------------
    # Users + UserProfiles
    # ------------------------------------------------------------------

    def _seed_users(self, campuses):
        created = 0
        users = {}
        for username, first_name, last_name, email, campus_code in USERS:
            user, is_new = User.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": email,
                },
            )
            if is_new:
                user.set_password(DEFAULT_PASSWORD)
                user.save()
                created += 1

            campus = campuses[campus_code]
            UserProfile.objects.get_or_create(user=user, defaults={"campus": campus})

            users[username] = user

        self.stdout.write(
            f"  CustomUser: {created} created, {len(USERS) - created} already existed"
        )
        return users

    # ------------------------------------------------------------------
    # Department managers (post-user step)
    # ------------------------------------------------------------------

    def _set_department_managers(self, departments, users):
        dept_manager_map = {
            "ICT": "ict_manager",
            "FAC": "fac_manager",
        }
        for dept_code, manager_username in dept_manager_map.items():
            dept = departments[dept_code]
            manager = users[manager_username]
            if dept.manager_user_id != manager.pk:
                dept.manager_user = manager
                dept.save(update_fields=["manager_user"])
        self.stdout.write("  Department managers: set")

    # ------------------------------------------------------------------
    # CampusDepartments
    # ------------------------------------------------------------------

    def _seed_campus_departments(self, campuses, departments, users):
        created = 0
        campus_departments = {}
        for campus_code, dept_code, hod_username in CAMPUS_DEPARTMENTS:
            campus = campuses[campus_code]
            dept = departments[dept_code]
            hod = users[hod_username] if hod_username else None
            obj, is_new = CampusDepartment.objects.get_or_create(
                campus=campus,
                department=dept,
                defaults={"head_of_department": hod},
            )
            campus_departments[(campus_code, dept_code)] = obj
            if is_new:
                created += 1
        self.stdout.write(
            f"  CampusDepartment: {created} created, {len(CAMPUS_DEPARTMENTS) - created} already existed"
        )
        return campus_departments

    # ------------------------------------------------------------------
    # Sections
    # ------------------------------------------------------------------

    def _seed_sections(self, campus_departments, section_types, users):
        created = 0
        sections = {}
        for campus_code, dept_code, st_code, hos_username, is_active in SECTIONS:
            cd = campus_departments[(campus_code, dept_code)]
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
        self.stdout.write(
            f"  Section: {created} created, {len(SECTIONS) - created} already existed"
        )
        return sections

    # ------------------------------------------------------------------
    # SectionTechnicians
    # ------------------------------------------------------------------

    def _seed_section_technicians(self, users, sections):
        created = 0
        for username, campus_code, dept_code, st_code in SECTION_TECHNICIANS:
            user = users[username]
            section = sections[(campus_code, dept_code, st_code)]
            _, is_new = SectionTechnician.objects.get_or_create(
                user=user,
                section=section,
            )
            if is_new:
                created += 1
        self.stdout.write(
            f"  SectionTechnician: {created} created, {len(SECTION_TECHNICIANS) - created} already existed"
        )

    # ------------------------------------------------------------------
    # RoleAssignments
    # ------------------------------------------------------------------

    def _seed_role_assignments(self, users, departments, campus_departments, sections):
        created = 0
        for username, role, scope_type, scope_key in ROLE_ASSIGNMENTS:
            user = users[username]

            kwargs = {"role": role, "is_primary": True}

            if scope_type == "department":
                kwargs["department"] = departments[scope_key]
                kwargs["section"] = None
                kwargs["campus_department"] = None
            elif scope_type == "campus_department":
                kwargs["campus_department"] = campus_departments[scope_key]
                kwargs["section"] = None
                kwargs["department"] = None
            elif scope_type == "section":
                kwargs["section"] = sections[scope_key]
                kwargs["campus_department"] = None
                kwargs["department"] = None
            else:  # "none" — admin
                kwargs["section"] = None
                kwargs["campus_department"] = None
                kwargs["department"] = None

            _, is_new = RoleAssignment.objects.get_or_create(
                user=user,
                is_primary=True,
                defaults={k: v for k, v in kwargs.items() if k not in ("is_primary",)},
            )
            if is_new:
                created += 1

        self.stdout.write(
            f"  RoleAssignment: {created} created, {len(ROLE_ASSIGNMENTS) - created} already existed"
        )
