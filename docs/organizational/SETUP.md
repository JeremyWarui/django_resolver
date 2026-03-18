# Organizational Implementation - Setup & Testing Guide

⚠️ **STATUS**: For new setup, see:
- **Complete Setup Guide** → [First Time Setup](../FIRST_TIME_SETUP.md) (master guide, recommended)
- **Testing Guide** → [Testing Guide](../testing/TESTING.md) (complete test documentation)
- **Test Credentials** → [Default Credentials](../DEFAULT_CREDENTIALS.md) (single source of truth)

## Quick Start (5 minutes)

### Step 1: Backup Original Fixture
```bash
cd /home/jeremy/Desktop/portfolio/django_resolver
cp tickets/fixtures/tickets_initial_data.json tickets/fixtures/tickets_initial_data_original.json
```

### Step 2: Replace with Organizational Data
```bash
# Replace the old fixture with the new one with organizational hierarchy
cp tickets/fixtures/tickets_initial_data_org.json tickets/fixtures/tickets_initial_data.json
```

### Step 3: Reset Database & Load Data
```bash
# Apply migrations (if not already done)
python manage.py migrate

# Reset and reload with organizational data
python manage.py flush --noinput
python manage.py loaddata tickets/fixtures/tickets_initial_data.json
```

### Step 4: Verify Data Loaded
```bash
python manage.py shell
from tickets.models import Organization, Campus, Department, Section, CustomUser, Ticket
print(f"Organizations: {Organization.objects.count()}")
print(f"Campuses: {Campus.objects.count()}")
print(f"Departments: {Department.objects.count()}")
print(f"Sections: {Section.objects.count()}")
print(f"Users: {CustomUser.objects.count()}")
print(f"Tickets: {Ticket.objects.count()}")
exit()
```

---

## Test Users & Credentials

> 📌 **For complete list of test users and credentials, see [Default Credentials](../DEFAULT_CREDENTIALS.md)**

Quick reference of user roles (passwords available in Default Credentials):

- **User** (user_sarah) - Personal ticket access only
- **Technician** (tech_alex, tech_john, tech_carol, tech_mike) - Section-level access
- **Section Head** (section_head_ben, section_head_mike, etc.) - Department-level access  
- **HOD** (hod_alex, hod_maria) - Campus-level access
- **Director** (director_jane) - Organization-wide analytics
- **Admin** (admin_user) - Complete system access

---

## Set Test User Passwords

```bash
python manage.py shell

from tickets.models import CustomUser

# See Default Credentials document for all passwords
# Setting example admin user:
user = CustomUser.objects.get(username='admin_user')
user.set_password('adminuser123')  # From DEFAULT_CREDENTIALS.md
user.save()
print('✓ Password set')
```

For complete password setup, reference [Default Credentials](../DEFAULT_CREDENTIALS.md)

---

## Run All Tests

```bash
# 1. Run organizational tests
python manage.py test tickets.tests.test_organizational -v 2

# 2. Run service tests
python manage.py test tickets.tests.test_organizational_phase4_5 -v 2

# 3. Run all ticket tests
python manage.py test tickets -v 2

# Expected: All tests should pass ✅
```

---

## Manual API Testing

### Start Development Server
```bash
python manage.py runserver
```

### Test Admin Access (Login & List All Tickets)
```bash
# 1. Login as admin
curl -X POST http://localhost:8000/api/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin_user",
    "password": "adminuser123"
  }'

# Response will contain token. Copy it.
# Expected response:
# {
#   "token": "...",
#   "user_id": 1,
#   "username": "admin_user",
#   "role": "admin"
# }

# 2. Use token to list tickets
curl -H "Authorization: Token <YOUR_TOKEN_HERE>" \
  http://localhost:8000/api/tickets/

# Expected: 25 tickets from both campuses
```

### Test Role-Based Access (Section Head)
```bash
# 1. Login as section head
curl -X POST http://localhost:8000/api/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "section_head_ben",
    "password": "section_head_ben123"
  }'

# Copy token

# 2. List accessible tickets (should be department-level)
curl -H "Authorization: Token <YOUR_TOKEN>" \
  http://localhost:8000/api/tickets/

# Expected: Only IT department tickets (~10 from the fixture)
```

### Test Technician Access (Section-level)
```bash
# 1. Login as technician
curl -X POST http://localhost:8000/api/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "tech_alex",
    "password": "tech_alex123"
  }'

# 2. List accessible tickets
curl -H "Authorization: Token <YOUR_TOKEN>" \
  http://localhost:8000/api/tickets/

# Expected: Only Network Services section tickets + assigned tickets
```

### Test Director Dashboard
```bash
# 1. Login as director
curl -X POST http://localhost:8000/api/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "director_jane",
    "password": "director123"
  }'

# 2. Get analytics dashboard
curl -H "Authorization: Token <YOUR_TOKEN>" \
  http://localhost:8000/api/analytics/director-dashboard/

# Expected: Organization-wide metrics
# {
#   "organization_overview": {
#     "total_tickets": 25,
#     "open": 8,
#     "in_progress": 4,
#     ...
#   },
#   "campus_stats": [...],
#   "department_performance": [...],
#   ...
# }
```

---

## Test Auto-Escalation

### Dry Run (Safe - No Changes)
```bash
# See what WOULD be escalated without executing
python manage.py process_auto_escalations --dry-run --verbose

# Expected Output:
# 🔄 Starting auto-escalation processing... (DRY RUN)
# ... ticket analysis ...
# Summary: X tickets due for escalation
```

### Live Run with Limit
```bash
# Actually escalate, but limit to first 3 tickets
python manage.py process_auto_escalations --limit 3 --verbose

# Expected: Some tickets escalated from level 0 → 1 (to Section Head)
```

### Check Escalation State
```bash
python manage.py shell

from tickets.models import Ticket

# See escalation levels
escalated = Ticket.objects.filter(escalation_level__gt=0)
for ticket in escalated:
    print(f"{ticket.ticket_no}: Level {ticket.escalation_level} → {ticket.escalated_to}")

exit()
```

---

## Organizational Structure Summary

**Organization**: Test University (UNIV)
```
├── Main Campus (MAIN)
│   ├── IT Department (IT)
│   │   └── Network Services Section (NET) [6 tickets]
│   │       ├── tech_alex (technician)
│   │       └── section_head_ben (head)
│   │
│   └── Facilities & Maintenance Department (MAINT) [16 tickets]
│       ├── Plumbing Section (PLB)
│       │   ├── tech_john
│       │   └── section_head_mike
│       ├── Electrical Section (ELO)
│       │   ├── tech_carol
│       │   └── section_head_linda
│       ├── HVAC Section (HVAC)
│       │   └── section_head_david
│       ├── Carpentry Section (CARP)
│       │   ├── tech_mike
│       │   └── section_head_emily
│       └── General Section (GEN)
│           └── section_head_general
│
└── North Branch Campus (NORTH) [1 ticket]
    └── Operations Department (OPS)
        └── General Maintenance Section
            └── hod_maria (campus HOD)

Director: director_jane (org-wide analytics access)
```

---

## Fixture File Comparison

### What Changed in JSON

**NEW**: Organization entries
```json
{
  "model": "tickets.organization",
  "pk": 1,
  "fields": {
    "name": "Test University",
    "code": "UNIV",
    "organization_type": "education",
    "headquarters": "Main Campus, City Center"
  }
}
```

**NEW**: Campus entries (linked to organization)
```json
{
  "model": "tickets.campus",
  "pk": 1,
  "fields": {
    "organization": 1,
    "name": "Main Campus",
    "code": "MAIN",
    "location": "City Center"
  }
}
```

**NEW**: Department entries (linked to campus & HOD)
```json
{
  "model": "tickets.department",
  "pk": 1,
  "fields": {
    "campus": 1,
    "name": "Information Technology",
    "code": "IT",
    "head_of_department": 3,  # Links to HOD user
    "is_active": true
  }
}
```

**UPDATED**: Section entries (now link to department)
```json
{
  "model": "tickets.section",
  "pk": 1,
  "fields": {
    "department": 1,  # NEW: Links to department
    "name": "Network Services",
    "code": "NET",    # NEW: Code field
    "section_head": 6,  # NEW: Links to section head user
    ...
  }
}
```

**UPDATED**: CustomUser entries
```json
{
  "model": "tickets.customuser",
  "pk": 1,
  "fields": {
    "role": "admin",  # NEW: Full organizational role system
    "primary_campus": 1,  # NEW: Org assignment
    "primary_department": 1,  # NEW: Org assignment
    "sections": [1],  # NEW: Multi-section for technicians
    "phone_number": "",  # NEW: Contact info
    "can_assign_tickets": true,  # NEW: Permission flags
    "can_escalate_tickets": true,
    "can_view_analytics": true,
    ...
  }
}
```

**UPDATED**: Ticket entries
```json
{
  "model": "tickets.ticket",
  "pk": 1,
  "fields": {
    "ticket_no": "MAIN-IT-00001",  # NEW: Org-prefixed numbering
    "priority": "critical",  # NEW: Priority field
    "escalation_level": 0,  # NEW: Escalation tracking
    "escalated_to": null,  # NEW: Who escalated to
    "escalated_at": null,  # NEW: When escalated
    "auto_escalation_enabled": true,  # NEW: Auto-escalation flag
    "next_escalation_due": "2025-10-12T08:00:00Z",  # NEW: Scheduled escalation
    "escalation_threshold_hours": 48,  # NEW: SLA hours
    "escalation_reason": "",  # NEW: Why escalated
    ...
  }
}
```

**NEW**: Facility entries linked to campus/department
```json
{
  "model": "tickets.facility",
  "pk": 1,
  "fields": {
    "facility_code": "MOB-001",  # NEW: Facility codes
    "campus": 1,  # NEW: Org context
    "department": 1,  # NEW: Org context
    ...
  }
}
```

---

## Validation Checklist

After loading new fixture, verify:

- [ ] 1 Organization exists (Test University)
- [ ] 2 Campuses created (Main, North)
- [ ] 3 Departments across campuses
- [ ] 6 Sections linked to departments
- [ ] 15 Users with proper roles and assignments
- [ ] 10 Facilities linked to campus/department
- [ ] 25 Tickets with escalation fields populated
- [ ] All tickets have ticket_no with org prefix (MAIN-, NORTH-)
- [ ] All users have primary_campus and primary_department set
- [ ] Technicians assigned to sections
- [ ] Section heads assigned to sections
- [ ] HODs assigned to departments

---

## Troubleshooting

### Issue: Fixture Load Fails
```bash
# Validate JSON is valid
python -m json.tool tickets/fixtures/tickets_initial_data.json > /dev/null
echo "JSON is valid!"

# Load with full error output
python manage.py loaddata tickets/fixtures/tickets_initial_data.json --verbosity=3
```

### Issue: Foreign Key Errors
```bash
# Make sure migrations are applied
python manage.py migrate

# Check database state
python manage.py dbshell
SELECT COUNT(*) FROM tickets_organization;
SELECT COUNT(*) FROM tickets_campus;
SELECT COUNT(*) FROM tickets_department;
```

### Issue: Can't Login
```bash
# Remember: You must set passwords first!
# (See "Set Test User Passwords" section above)

# Or use Django admin
python manage.py createsuperuser
# Then access http://localhost:8000/admin
```

---

## Next Steps After Verification

1. ✅ Load new fixture with organizational data
2. ✅ Set user passwords for testing
3. ✅ Run test suite to validate
4. ✅ Manual API testing with different roles
5. ✅ Test auto-escalation with dry-run
6. 📋 Review test results and identify any issues
7. 📋 Set up cron job for production auto-escalation (optional)
8. 📋 Configure email notifications (optional)

