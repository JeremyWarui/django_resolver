# Sample Queries for Fixture Data

Comprehensive query examples for exploring and testing Django Resolver ticket management system. All queries use the Django ORM shell.

## Getting Started

Start the Django shell:
```bash
python manage.py shell
```

Import models:
```python
from tickets.models import (
    Campus, Department, CampusDepartment,
    SectionType, Section, TechnicianSection,
    ServiceCategory, ServiceItem,
    Facility, CustomUser,
    Ticket, Comment, Feedback, TicketLog,
)
from django.db.models import Count, Q, Avg, F, Case, When
from django.utils import timezone
from datetime import timedelta
```

---

## Quick Overview Queries

### Count All Records

```python
from tickets.models import (
    Campus, Department, CampusDepartment, Section,
    Facility, CustomUser, Ticket, Comment, Feedback, TicketLog,
)

models = [Campus, Department, CampusDepartment, Section, Facility, CustomUser, Ticket, Comment, Feedback, TicketLog]
for model in models:
    print(f"{model.__name__}: {model.objects.count()}")
```

**Output Example**:
```
Campus: 5
Department: 5
CampusDepartment: 11
Section: 11
Facility: 12
CustomUser: 20+
Ticket: 100+
Comment: 200+
Feedback: 50+
TicketLog: 500+
```

### Show Organizational Hierarchy

```python
# Display structure: Campus → CampusDepartment → Section
for campus in Campus.objects.prefetch_related(
    'campus_departments__department',
    'campus_departments__sections',
).all():
    print(f"\n{campus.name} ({campus.code})")
    for cd in campus.campus_departments.all():
        print(f"  └─ {cd.department.name} (HOD: {cd.head_of_department.username if cd.head_of_department else 'Unassigned'})")
        for section in cd.sections.all():
            print(f"     └─ {section.name}")
```

---

## Organizational Hierarchy Queries

### List All Users by Role and Campus

```python
from tickets.models import CustomUser

roles = ['user', 'technician', 'head_of_section', 'hod', 'manager', 'admin']

for role in roles:
    users = CustomUser.objects.filter(role=role).select_related('primary_campus')
    if users.exists():
        print(f"\n{role.upper()}S ({users.count()}):")
        for user in users:
            campus = user.primary_campus.code if user.primary_campus else "—"
            print(f"  • {user.username} ({user.first_name} {user.last_name}) - Campus: {campus}")
```

### Technicians by Section

```python
# Show which technicians work in which sections (via TechnicianSection)
from tickets.models import TechnicianSection

for ts in TechnicianSection.objects.select_related('technician', 'section__campus_department__campus'):
    campus_code = ts.section.campus_department.campus.code
    print(f"{campus_code}-{ts.section.name}: {ts.technician.username}")
```

### Section Head per Section

```python
from tickets.models import Section

for section in Section.objects.select_related(
    'head_of_section',
    'campus_department__campus',
    'campus_department__department',
):
    cd = section.campus_department
    leader = section.head_of_section.username if section.head_of_section else "Unassigned"
    print(f"{cd.campus.code}-{cd.department.code}: {section.name} (HOS: {leader})")
```

### HOD per CampusDepartment

```python
from tickets.models import CampusDepartment

for cd in CampusDepartment.objects.select_related(
    'campus', 'department', 'head_of_department'
):
    hod = cd.head_of_department.username if cd.head_of_department else "Unassigned"
    print(f"{cd.campus.code}-{cd.department.code} (HOD: {hod})")
    for section in cd.sections.select_related('head_of_section'):
        hos = section.head_of_section.username if section.head_of_section else "Unassigned"
        print(f"  └─ {section.name} (HOS: {hos})")
```

---

## Ticket Queries

### Tickets by Status Distribution

```python
from django.db.models import Count

status_dist = Ticket.objects.values('status').annotate(
    count=Count('id')
).order_by('-count')

print("Ticket Status Distribution:")
for item in status_dist:
    print(f"  {item['status']}: {item['count']}")
```

### Tickets by Priority

```python
priority_dist = Ticket.objects.values('priority').annotate(
    count=Count('id')
).order_by('-count')

for item in priority_dist:
    print(f"{item['priority']}: {item['count']} tickets")
```

### Escalation Status

```python
escalation_dist = Ticket.objects.values('escalation_level').annotate(
    count=Count('id')
).order_by('escalation_level')

for item in escalation_dist:
    level = f"Level {item['escalation_level']}" if item['escalation_level'] else "No escalation"
    print(f"{level}: {item['count']} tickets")

# Get escalated tickets with details
escalated = Ticket.objects.filter(escalation_level__gt=0).select_related(
    'section__campus_department__campus', 'section__campus_department__department'
)
print(f"\nEscalated tickets: {escalated.count()}")
for ticket in escalated:
    cd = ticket.section.campus_department
    display = f"{cd.campus.code}-{ticket.section.name}"
    print(f"  {ticket.ticket_no}: Level {ticket.escalation_level} — section: {display}")
```

### Pending Tickets with Reasons

```python
pending = Ticket.objects.filter(status='pending')

print(f"Pending Tickets: {pending.count()}\n")
for ticket in pending:
    print(f"{ticket.ticket_no}: {ticket.title}")
    print(f"  Reason: {ticket.pending_reason}")
    print(f"  Comment: {ticket.pending_comment[:100]}...")
    print()
```

### Tickets Pending Approval

```python
pending_approval = Ticket.objects.filter(status='pending_approval').select_related(
    'service_item', 'raised_by'
)
print(f"Tickets awaiting approval: {pending_approval.count()}")
for ticket in pending_approval:
    print(f"  {ticket.ticket_no}: {ticket.service_item.name if ticket.service_item else '—'} — by {ticket.raised_by.username}")
```

---

## Scope and Access Control Queries

### User Accessible Tickets (Service Layer)

```python
# Example: Get tickets accessible to a specific user
# Always use TicketService.get_accessible_tickets(user) in production code
from tickets.api.services.ticket_service import TicketService

user = CustomUser.objects.filter(role='technician').first()
if user:
    accessible = TicketService.get_accessible_tickets(user)
    print(f"User {user.username} can access {accessible.count()} tickets")
```

### Technician's Current Workload

```python
for ts in TechnicianSection.objects.select_related('technician', 'section').all():
    tech = ts.technician
    assigned = Ticket.objects.filter(
        assigned_to=tech,
        status__in=['assigned', 'in_progress']
    )
    if assigned.exists():
        print(f"\n{tech.username} ({ts.section.name}):")
        for ticket in assigned:
            print(f"  • {ticket.ticket_no}: {ticket.title} ({ticket.status})")
```

### Section Head's Escalated Tickets

```python
# Get tickets escalated to section head level (level=1) in their section
for section in Section.objects.select_related('head_of_section').filter(
    head_of_section__isnull=False
):
    escalated = Ticket.objects.filter(
        section=section,
        escalation_level=1
    )
    if escalated.exists():
        print(f"\n{section.head_of_section.username} ({section.name}) — {escalated.count()} escalated:")
        for ticket in escalated:
            print(f"  • {ticket.ticket_no} - {ticket.priority}")
```

### HOD's CampusDepartment Tickets

```python
# Get open tickets in an HOD's CampusDepartment
for cd in CampusDepartment.objects.select_related(
    'head_of_department', 'campus', 'department'
).filter(head_of_department__isnull=False):
    tickets = Ticket.objects.filter(
        section__campus_department=cd
    ).exclude(status='closed')
    print(f"\n{cd.head_of_department.username} ({cd.campus.code}-{cd.department.code}): {tickets.count()} active tickets")
```

### Manager's Cross-Campus View

```python
# Manager sees their department across ALL campuses
manager = CustomUser.objects.filter(role='manager').first()
if manager and manager.primary_department:
    dept = manager.primary_department
    tickets = Ticket.objects.filter(
        section__campus_department__department=dept
    ).select_related('section__campus_department__campus')
    print(f"Manager {manager.username} — {dept.code} dept, all campuses: {tickets.count()} tickets")
    for campus_code, count in tickets.values_list(
        'section__campus_department__campus__code'
    ).annotate(count=Count('id')):
        print(f"  {campus_code}: {count} tickets")
```

---

## Comment and Collaboration Queries

### Tickets with Comments

```python
top_commented = Ticket.objects.annotate(
    comment_count=Count('comments')
).filter(comment_count__gt=0).order_by('-comment_count')[:10]

for ticket in top_commented:
    print(f"{ticket.ticket_no}: {ticket.comment_count} comments")
```

### Comment Activity Timeline

```python
recent = Comment.objects.select_related(
    'ticket', 'created_by'
).order_by('-created_at')[:20]

for comment in recent:
    print(f"[{comment.created_at.strftime('%Y-%m-%d %H:%M')}] {comment.created_by.username}: {comment.text[:50]}...")
```

---

## Feedback and Satisfaction Queries

### Average Technician Ratings

```python
tech_ratings = Feedback.objects.filter(
    ticket__assigned_to__role='technician'
).values(
    'ticket__assigned_to__username', 'ticket__assigned_to__first_name'
).annotate(
    avg_rating=Avg('rating'),
    count=Count('id')
).order_by('-avg_rating')

for item in tech_ratings:
    name = item['ticket__assigned_to__first_name'] or item['ticket__assigned_to__username']
    print(f"{name}: {item['avg_rating']:.1f} ({item['count']} ratings)")
```

### Satisfaction Trends by Section (with display_name)

```python
section_ratings = Feedback.objects.select_related(
    'ticket__section__campus_department__campus',
    'ticket__section__campus_department__department',
).values(
    'ticket__section__name',
    'ticket__section__campus_department__campus__code',
).annotate(
    avg_rating=Avg('rating'),
    count=Count('id')
).filter(count__gt=0).order_by('-avg_rating')

for item in section_ratings:
    campus_code = item['ticket__section__campus_department__campus__code']
    section_name = item['ticket__section__name']
    display = f"{campus_code}-{section_name}"
    print(f"{display}: {item['avg_rating']:.1f} ({item['count']} ratings)")
```

---

## Performance and SLA Queries

### Resolution Time Analysis

```python
from django.db.models import ExpressionWrapper, DurationField

resolved = Ticket.objects.filter(
    status__in=['resolved', 'closed'],
    resolved_at__isnull=False
).annotate(
    resolution_time=ExpressionWrapper(
        F('resolved_at') - F('created_at'),
        output_field=DurationField()
    )
).select_related('assigned_to').order_by('-resolution_time')

for ticket in resolved[:10]:
    hours = ticket.resolution_time.total_seconds() / 3600
    print(f"{ticket.ticket_no}: {hours:.1f} hours resolution time")
```

### SLA Compliance (due_date based)

```python
# Overdue tickets: due_date has passed and still open
overdue = Ticket.objects.filter(
    due_date__lt=timezone.now(),
    status__in=['open', 'assigned', 'in_progress', 'pending']
).select_related(
    'section__campus_department__campus',
    'assigned_to',
)

print(f"Overdue tickets: {overdue.count()}")
for ticket in overdue:
    hours_overdue = (timezone.now() - ticket.due_date).total_seconds() / 3600
    print(f"  {ticket.ticket_no}: {hours_overdue:.1f} hours overdue")
```

### Tickets Approaching Escalation Deadline

```python
sla_window = timezone.now() + timedelta(hours=48)
at_risk = Ticket.objects.filter(
    escalation_level=0,
    status__in=['open', 'assigned'],
    next_escalation_due__isnull=False,
    next_escalation_due__lte=sla_window
).order_by('next_escalation_due')

print(f"Tickets approaching escalation: {at_risk.count()}")
for ticket in at_risk:
    hours_left = (ticket.next_escalation_due - timezone.now()).total_seconds() / 3600
    print(f"  {ticket.ticket_no}: {hours_left:.1f} hours until escalation")
```

### Stale Tickets (No Recent Activity)

```python
cutoff = timezone.now() - timedelta(hours=24)
stale = Ticket.objects.filter(
    status__in=['open', 'assigned', 'in_progress'],
    updated_at__lt=cutoff
).order_by('updated_at')

print(f"Stale tickets (no update in 24h): {stale.count()}")
for ticket in stale:
    age = (timezone.now() - ticket.updated_at).days
    print(f"  {ticket.ticket_no}: {age} days since update")
```

---

## Audit and Activity Queries

### Recent Ticket Activity Log

```python
recent_logs = TicketLog.objects.select_related(
    'ticket', 'performed_by'
).order_by('-timestamp')[:20]

for log in recent_logs:
    user = log.performed_by.username if log.performed_by else "System"
    print(f"[{log.timestamp.strftime('%Y-%m-%d %H:%M')}] {log.action}: {log.ticket.ticket_no} - {user}")
```

### Tickets Created Today

```python
today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
today_tickets = Ticket.objects.filter(created_at__gte=today_start)

print(f"Tickets created today: {today_tickets.count()}")
for ticket in today_tickets:
    print(f"  • {ticket.ticket_no}: {ticket.title} (Status: {ticket.status})")
```

---

## Complex Analytical Queries

### Busiest Sections (with campus prefix)

```python
# Sections with most open tickets, including campus context
busy_sections = Ticket.objects.filter(
    status__in=['open', 'assigned', 'in_progress']
).select_related(
    'section__campus_department__campus'
).values(
    'section__name',
    'section__campus_department__campus__code',
).annotate(
    count=Count('id')
).order_by('-count')

for item in busy_sections:
    campus_code = item['section__campus_department__campus__code']
    section_name = item['section__name']
    display = f"{campus_code}-{section_name}"
    print(f"{display}: {item['count']} active tickets")
```

### Assignment Patterns (Technician Multi-Section)

```python
# Show which technicians are assigned to multiple sections
multi_section_techs = CustomUser.objects.filter(
    role='technician'
).annotate(
    section_count=Count('technician_sections', distinct=True)
).filter(
    section_count__gt=1
).order_by('-section_count')

for tech in multi_section_techs:
    sections = ", ".join([
        f"{ts.section.campus_department.campus.code}-{ts.section.name}"
        for ts in tech.technician_sections.select_related(
            'section__campus_department__campus'
        ).all()
    ])
    print(f"{tech.username}: {tech.section_count} sections — {sections}")
```

### Technician Performance Report

```python
from django.db.models import Count, Q, Avg

technicians = CustomUser.objects.filter(
    role='technician'
).annotate(
    total_assigned=Count('assigned_tickets'),
    resolved_count=Count('assigned_tickets', filter=Q(assigned_tickets__status__in=['resolved', 'closed'])),
    avg_rating=Avg('assigned_tickets__feedback__rating')
).order_by('-resolved_count')

print("Technician Performance Report")
print("=" * 60)
for tech in technicians:
    sections = ", ".join([
        f"{ts.section.campus_department.campus.code}-{ts.section.name}"
        for ts in tech.technician_sections.select_related(
            'section__campus_department__campus'
        ).all()
    ])
    rating = f"{tech.avg_rating:.2f}" if tech.avg_rating else "N/A"
    print(f"{tech.first_name} {tech.last_name} ({tech.username})")
    print(f"  Sections: {sections or '—'}")
    print(f"  Total assigned: {tech.total_assigned}")
    print(f"  Resolved: {tech.resolved_count}")
    print(f"  Average rating: {rating}")
    print()
```

### Comments on Specific Ticket

```python
from tickets.models import Ticket

ticket = Ticket.objects.prefetch_related('comments__created_by').get(ticket_no='NRB-ICT-00001')
print(f"Ticket: {ticket.title}")
print(f"Comments ({ticket.comments.count()}):")
for comment in ticket.comments.all():
    print(f"  [{comment.created_at}] {comment.created_by.username}: {comment.text}")
```

---

## Tips & Best Practices

1. **Always use `select_related()` for foreign keys** to avoid N+1 queries:
   ```python
   tickets = Ticket.objects.select_related(
       'assigned_to',
       'section__campus_department__campus',
       'section__campus_department__department',
       'facility',
   )
   ```

2. **Use `prefetch_related()` for reverse relationships**:
   ```python
   tickets = Ticket.objects.prefetch_related('comments', 'logs')
   ```

3. **Filter early, aggregate late**:
   ```python
   # Good: Filter first, then aggregate
   Ticket.objects.filter(status='closed').values('section').annotate(Count('id'))
   ```

4. **There is no Organization model** — the hierarchy starts at `Campus`. Queries that previously used `organization__campuses` now start directly from `Campus.objects.all()`.

5. **Technician scope** — use `TechnicianSection` to query which sections a technician belongs to, not `CustomUser.sections`:
   ```python
   # Correct
   TechnicianSection.objects.filter(technician=user).values_list('section_id', flat=True)
   ```

6. **Exit shell and run again to reset loaded data**:
   ```bash
   python manage.py shell  # Fresh Python environment
   ```

---

## API Endpoint Queries

Test these endpoints using curl or your browser:

### Get All Tickets
```bash
curl -H "Authorization: Token YOUR_TOKEN" http://127.0.0.1:8000/api/tickets/
```

### Filter Tickets by Status
```bash
curl -H "Authorization: Token YOUR_TOKEN" "http://127.0.0.1:8000/api/tickets/?status=open"
curl -H "Authorization: Token YOUR_TOKEN" "http://127.0.0.1:8000/api/tickets/?status=pending"
```

### Filter by Section
```bash
curl -H "Authorization: Token YOUR_TOKEN" "http://127.0.0.1:8000/api/tickets/?section_id=1"
```

### Get Specific Ticket with Details
```bash
curl -H "Authorization: Token YOUR_TOKEN" http://127.0.0.1:8000/api/tickets/1/
```

### Create Ticket (Catalogue-Based)
```bash
curl -X POST http://127.0.0.1:8000/api/tickets/create/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"department_id": 1, "service_item_id": 5, "title": "Laptop broken", "description": "Screen cracked"}'
```

### Get All Users
```bash
curl -H "Authorization: Token YOUR_TOKEN" http://127.0.0.1:8000/api/users/
```

### Filter Users by Role
```bash
curl -H "Authorization: Token YOUR_TOKEN" "http://127.0.0.1:8000/api/users/?role=technician"
```

### Get All Sections
```bash
curl -H "Authorization: Token YOUR_TOKEN" http://127.0.0.1:8000/api/sections/
```

### Get Campus Departments
```bash
curl -H "Authorization: Token YOUR_TOKEN" http://127.0.0.1:8000/api/campus-departments/
curl -H "Authorization: Token YOUR_TOKEN" "http://127.0.0.1:8000/api/campus-departments/?campus_id=1"
```

### Analytics Endpoints

#### Ticket Analytics
```bash
curl -H "Authorization: Token YOUR_TOKEN" http://127.0.0.1:8000/api/analytics/tickets/
curl -H "Authorization: Token YOUR_TOKEN" "http://127.0.0.1:8000/api/analytics/tickets/?section_id=1&timeframe=week"
```

#### Technician Analytics
```bash
curl -H "Authorization: Token YOUR_TOKEN" http://127.0.0.1:8000/api/analytics/technicians/
curl -H "Authorization: Token YOUR_TOKEN" "http://127.0.0.1:8000/api/analytics/technicians/me/"
```

#### Role-Based Dashboards
```bash
curl -H "Authorization: Token YOUR_TOKEN" http://127.0.0.1:8000/api/analytics/manager/
curl -H "Authorization: Token YOUR_TOKEN" http://127.0.0.1:8000/api/analytics/hod/
curl -H "Authorization: Token YOUR_TOKEN" http://127.0.0.1:8000/api/analytics/section-head/
curl -H "Authorization: Token YOUR_TOKEN" http://127.0.0.1:8000/api/analytics/admin-dashboard/
```

---

## SQL Queries

If you need direct database access:

```sql
-- Count tickets by status
SELECT status, COUNT(*) as count
FROM tickets_ticket
GROUP BY status
ORDER BY count DESC;

-- Technician workload
SELECT u.username, u.first_name, u.last_name, COUNT(t.id) as ticket_count
FROM tickets_customuser u
LEFT JOIN tickets_ticket t ON t.assigned_to_id = u.id
WHERE u.role = 'technician'
GROUP BY u.id, u.username, u.first_name, u.last_name
ORDER BY ticket_count DESC;

-- Average rating by technician
SELECT u.username, AVG(f.rating) as avg_rating, COUNT(f.id) as rating_count
FROM tickets_customuser u
JOIN tickets_ticket t ON t.assigned_to_id = u.id
JOIN tickets_feedback f ON f.ticket_id = t.id
WHERE u.role = 'technician'
GROUP BY u.id, u.username
ORDER BY avg_rating DESC;

-- Sections with campus prefix (display_name pattern)
SELECT
    c.code || '-' || s.name AS display_name,
    COUNT(t.id) AS ticket_count
FROM tickets_section s
JOIN tickets_campusdepartment cd ON s.campus_department_id = cd.id
JOIN tickets_campus c ON cd.campus_id = c.id
LEFT JOIN tickets_ticket t ON t.section_id = s.id
GROUP BY display_name
ORDER BY ticket_count DESC;

-- Overdue tickets (based on due_date)
SELECT ticket_no, title, due_date, status
FROM tickets_ticket
WHERE due_date < NOW()
  AND status NOT IN ('resolved', 'closed', 'rejected')
ORDER BY due_date ASC;

-- Recent ticket activity
SELECT tl.timestamp, u.username, tl.action, t.ticket_no
FROM tickets_ticketlog tl
JOIN tickets_ticket t ON tl.ticket_id = t.id
LEFT JOIN tickets_customuser u ON tl.performed_by_id = u.id
ORDER BY tl.timestamp DESC
LIMIT 20;
```

---

These queries will help you explore and test all aspects of the fixture data.
