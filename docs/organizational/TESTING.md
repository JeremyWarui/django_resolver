# Testing the Organizational Implementation

> 📌 **For comprehensive testing guide, see [Testing Guide](../testing/TESTING.md)**  
> This document covers **organizational testing workflows only**. For complete test coverage (166 tests), see the main Testing Guide.

## Quick Start: Load Data & Run Tests

### 1. Update Database
```bash
# Apply migrations (includes organizational models)
python manage.py migrate

# Load updated fixture with organizational data
python manage.py loaddata tickets/fixtures/tickets_initial_data.json
```

### 2. Run All Tests
```bash
# Run complete organizational test suite
pytest tickets/tests/test_organizational.py -v

# Run organizational service tests
pytest tickets/tests/test_organizational.py::test_escalation_workflow -v

# Run all ticket tests
pytest tickets/tests/ -v
```

---

## Manual Testing via API

### Authentication
All endpoints require authentication. Test users from fixture:

```bash
# Admin (can see everything)
username: admin_user
password: adminuser123

# Manager (own department, cross-campus analytics)
username: manager_ict
password: adminuser123

# HOD (campus-level access)
username: hod_alex
password: hod_alex123

# Section Head (department-level access)
username: section_head_maria
password: section_head_maria123

# Technician (section-level access)
username: tech_mike
password: tech_mike123

# User (personal tickets only)
username: user_sarah
password: user_sarah123
```

### Login & Get Token
```bash
curl -X POST http://localhost:8000/api/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"user_sarah","password":"user_sarah123"}'

# Response:
# {
#   "token": "abc123def456...",
#   "user_id": 6,
#   "username": "user_sarah",
#   "role": "user"
# }
```

### Test Different Role Access Levels

#### 1. User Role - Personal Tickets Only
```bash
# List own tickets
curl -H "Authorization: Token YOUR_TOKEN" \
  http://localhost:8000/api/tickets/

# Expected: Only tickets where raised_by = user
# In fixture: user_sarah sees tickets #18, #25 (raised by her)
```

#### 2. Technician Role - Section-Level Access
```bash
# List accessible tickets (within sections assigned to technician)
curl -H "Authorization: Token YOUR_TOKEN" \
  http://localhost:8000/api/tickets/

# Expected: tech_mike sees tickets from Carpentry section only
# In fixture: tech_mike is assigned to Carpentry section
```

#### 3. Section Head Role - Department-Level
```bash
# List all department tickets
curl -H "Authorization: Token YOUR_TOKEN" \
  http://localhost:8000/api/tickets/?department_id=1

# Expected: section_head_maria sees all IT department tickets
# Can assign tickets to technicians in section
# Can escalate tickets to HOD
```

#### 4. HOD Role - Campus-Level
```bash
# List all campus tickets
curl -H "Authorization: Token YOUR_TOKEN" \
  http://localhost:8000/api/tickets/?campus_id=1

# Expected: hod_alex sees all Main Campus tickets
# Can escalate tickets to Director level
# Can view campus analytics dashboard
```

#### 5. Manager Role - Cross-Campus Department Analytics
```bash
# Manager doesn't see individual tickets in list
# Instead, gets analytics view for own department across all campuses
curl -H "Authorization: Token YOUR_TOKEN" \
  http://localhost:8000/api/analytics/manager/

# Expected: Department-level metrics across all org campuses
```

#### 6. Admin Role - Complete Access
```bash
# Admin sees everything
curl -H "Authorization: Token YOUR_TOKEN" \
  http://localhost:8000/api/tickets/

# Expected: All tickets regardless of organizational structure
```

---

## Key Workflows to Test

### Workflow 1: Ticket Creation & Escalation

```bash
# 1. User creates ticket
curl -X POST http://localhost:8000/api/tickets/ \
  -H "Authorization: Token USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Network Down in Building A",
    "description": "Critical network outage",
    "section": 1,
    "facility": 2,
    "priority": "critical"
  }'

# Response shows: escalation_level=0, auto_escalation_enabled=true

# 2. Simulate auto-escalation (48 hours later)
python manage.py process_auto_escalations --dry-run
# Expected output shows which tickets will escalate

# 3. Manual escalation by Section Head
curl -X POST http://localhost:8000/api/tickets/{ticket_id}/escalate/ \
  -H "Authorization: Token SECTION_HEAD_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Unable to resolve within SLA"}'

# Response shows: escalation_level=1, escalated_to=HOD
```

### Workflow 2: Assignment Validation

```bash
# 1. Section Head tries to assign to technician in DIFFERENT section
# Should FAIL with permission error

# 2. Section Head assigns to technician in SAME section
curl -X PATCH http://localhost:8000/api/tickets/{ticket_id}/ \
  -H "Authorization: Token SECTION_HEAD_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"assigned_to": 7}'  # tech_mike in Carpentry

# Should succeed if tech_mike is in the same department

# 3. Confirm technician can see the ticket
curl -H "Authorization: Token TECH_TOKEN" \
  http://localhost:8000/api/tickets/{ticket_id}/

# Expected: Technician sees full ticket details
```

### Workflow 3: Analytics Dashboard Access

```bash
# 1. Section Head views department dashboard
curl -H "Authorization: Token SECTION_HEAD_TOKEN" \
  http://localhost:8000/api/analytics/section-head/

# Expected: Department-level metrics
# - Average resolution time
# - Tickets by priority
# - Technician workload
# - Escalation trends

# 2. HOD views campus dashboard
curl -H "Authorization: Token HOD_TOKEN" \
  http://localhost:8000/api/analytics/hod/

# Expected: Campus-level metrics
# - Department performance
# - Section efficiency
# - Cross-department escalations

# 3. Manager views cross-campus department dashboard
curl -H "Authorization: Token MANAGER_TOKEN" \
  http://localhost:8000/api/analytics/manager/

# Expected: Department metrics across all campuses
# - Per-campus breakdown
# - Top technicians
# - SLA compliance
```

### Workflow 4: Get Assignable Users

```bash
# Get technicians available for assignment in a section
curl -H "Authorization: Token SECTION_HEAD_TOKEN" \
  "http://localhost:8000/api/assignable-users/?section_id=1"

# Response includes only technicians who:
# 1. Have "technician" role
# 2. Are in the same section
# 3. Are active users

# Example response:
# {
#   "count": 2,
#   "results": [
#     {
#       "id": 3,
#       "username": "tech_alex",
#       "first_name": "Alex",
#       "role": "technician"
#     }
#   ]
# }
```

---

## Key Checks to Perform

### ✅ Permissions Checks
- [ ] User can only see own tickets
- [ ] Technician can see section tickets + assigned tickets
- [ ] Section Head can see all department tickets
- [ ] HOD can see all campus tickets
- [ ] Director can see analytics only (not individual tickets)
- [ ] Admin can see everything

### ✅ Escalation Checks
- [ ] Ticket auto_escalation_enabled defaults to True
- [ ] escalation_level starts at 0
- [ ] Manual escalation changes escalation_level to 1 (Section Head)
- [ ] Further escalation changes to 2 (HOD) - max level
- [ ] Cannot escalate beyond HOD (level 2)
- [ ] Auto-escalation respects 48h/24h thresholds

### ✅ Assignment Checks
- [ ] Can only assign to technicians
- [ ] Technician must be in same section
- [ ] Cannot assign across organizational boundaries
- [ ] Cannot assign closed/resolved tickets

### ✅ Audit Trail Checks
- [ ] All escalations logged in TicketLog
- [ ] Status changes recorded
- [ ] Assignment changes recorded
- [ ] Auto-escalations marked as automatic (is_auto_escalation=true)

### ✅ Organizational Hierarchy Checks
- [ ] Organizations created and displayed correctly
- [ ] Campuses linked to organizations
- [ ] Departments linked to campuses
- [ ] Sections linked to departments
- [ ] Facilities linked to campus/department
- [ ] Users have primary_campus and primary_department

---

## Auto-Escalation Testing

### Dry Run (Recommended First)
```bash
# Identify which tickets would escalate WITHOUT making changes
python manage.py process_auto_escalations --dry-run --verbose

# Output shows:
# - Number of tickets due for escalation
# - Details of each ticket
# - Target escalation user
# - No actual changes made
```

### Verbose Testing
```bash
# Actual execution with detailed logging
python manage.py process_auto_escalations --verbose --limit 5

# Output includes:
# - Tickets processed
# - Escalation details
# - Any failures with reasons
# - Summary statistics
```

### Limit Processing
```bash
# Process only first N tickets (useful for testing large datasets)
python manage.py process_auto_escalations --limit 10

# Processes max 10 tickets, useful for controlled testing
```

### Schedule for Production
```bash
# Add to crontab for hourly execution
# Open crontab editor
crontab -e

# Add this line (runs at top of every hour)
0 * * * * cd /path/to/django_resolver && python manage.py process_auto_escalations >> /var/log/django_escalations.log 2>&1
```

---

## Expected Test Results

### Fixture Data Overview
- **Organizations**: 1 (Test University)
- **Campuses**: 2 (Main, North Branch)
- **Departments**: 3 (IT, Maintenance, Operations)
- **Sections**: 6 (IT, Plumbing, Electrical, HVAC, Carpentry, General)
- **Users**: 7 test accounts with different roles
  - 1 Admin
  - 1 Director
  - 1 HOD
  - 1 Section Head
  - 2 Technicians
  - 1 Regular User
- **Tickets**: 25 tickets with various statuses
- **Facilities**: 10 facilities across campuses/departments

### Test Coverage
- 40+ test methods across organized test cases
- Permission validation tests
- Escalation workflow tests
- API integration tests
- Analytics calculation tests

---

## Troubleshooting

### Issue: Migration Fails
```bash
# Check for conflicts
python manage.py showmigrations tickets

# If needed, reset and remigrate
python manage.py migrate tickets zero
python manage.py migrate tickets
python manage.py loaddata tickets/fixtures/tickets_initial_data.json
```

### Issue: Fixture Load Fails
```bash
# Validate JSON syntax
python -m json.tool tickets/fixtures/tickets_initial_data.json > /dev/null

# Check for missing foreign key references
python manage.py loaddata tickets/fixtures/tickets_initial_data.json --verbosity=2

# If needed, check integrity
python manage.py check
```

### Issue: Tests Fail
```bash
# Run specific test with full traceback
python manage.py test tickets.tests.test_organizational.OrganizationalHierarchyTestCase -v 2

# Run with pdb for debugging
python -m pytest tickets/tests/test_organizational.py::OrganizationalHierarchyTestCase -v --pdb
```

### Issue: Auto-Escalation Not Triggering
```bash
# Check if tickets are due
python manage.py shell
from tickets.models import Ticket
Ticket.objects.filter(next_escalation_due__isnull=False).values('id', 'next_escalation_due')

# Manually trigger for testing (changes ticket times)
ticket = Ticket.objects.first()
ticket.next_escalation_due = timezone.now() - timedelta(hours=1)
ticket.save()

python manage.py process_auto_escalations --verbose
```

---

## Performance Validation

Run after significant changes:

```bash
# Check query performance
python manage.py test tickets.tests.test_organizational -v 2 --keepdb

# Monitor database impact
python manage.py dbshell
SELECT COUNT(*) FROM tickets_ticket;
SELECT COUNT(*) FROM tickets_ticketlog;

# Check index usage
EXPLAIN ANALYZE SELECT * FROM tickets_ticket 
  WHERE status='open' AND escalation_level=0;
```
