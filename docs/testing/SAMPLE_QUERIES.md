# Sample Queries for Fixture Data

Comprehensive query examples for exploring and testing Django Resolver ticket management system. All queries use the Django ORM shell.

## Getting Started

Start the Django shell:
```bash
python manage.py shell
```

Import models:
```python
from tickets.models import *
from django.db.models import Count, Q, Avg, F, Case, When
from django.utils import timezone
from datetime import timedelta
```

---

## Quick Overview Queries

### Count All Records

```python
from tickets.models import *

# Quick overview
models = [Organization, Campus, Department, Section, Facility, CustomUser, Ticket, Comment, Feedback, TicketLog]
for model in models:
    print(f"{model.__name__}: {model.objects.count()}")
```

**Output Example**:
```
Organization: 1
Campus: 4
Department: 8
Section: 16
Facility: 12
CustomUser: 50+
Ticket: 100+
Comment: 200+
Feedback: 50+
TicketLog: 500+
```

### Show Organizational Hierarchy

```python
# Display organization structure
for org in Organization.objects.all():
    print(f"\n{org.name} ({org.organization_type})")
    for campus in org.campuses.all():
        print(f"  └─ {campus.name} ({campus.code})")
        for dept in campus.departments.all():
            print(f"     └─ {dept.name}")
            for section in dept.sections.all():
                print(f"        └─ {section.name}")
```

---

## Organizational Hierarchy Queries

### List All Users by Role and Campus

```python
from tickets.models import CustomUser

roles = ['user', 'technician', 'head_of_section', 'hod', 'manager', 'admin']

for role in roles:
    users = CustomUser.objects.filter(role=role)
    if users.exists():
        print(f"\n{role.upper()}S ({users.count()}):")
        for user in users:
            campus = user.primary_campus.name if user.primary_campus else "—"
            print(f"  • {user.username} ({user.first_name} {user.last_name}) - Campus: {campus}")
```

### Technicians by Section

```python
# Show which technicians work in which sections
for section in Section.objects.all():
    techs = section.technicians.all()
    if techs.exists():
        tech_list = ", ".join([t.username for t in techs])
        print(f"{section.name}: {tech_list}")
```

### Department Hierarchy with Heads

```python
# Show department structure with managers
for dept in Department.objects.select_related('head_of_department'):
    head = dept.head_of_department.username if dept.head_of_department else "Unassigned"
    print(f"{dept.name} (HOD: {head})")
    for section in dept.sections.select_related('head_of_section'):
        leader = section.head_of_section.username if section.head_of_section else "Unassigned"
        print(f"  └─ {section.name} (Leader: {leader})")
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
# Show ticket count by priority level
priority_dist = Ticket.objects.values('priority').annotate(
    count=Count('id')
).order_by('-count')

for item in priority_dist:
    print(f"{item['priority']}: {item['count']} tickets")
```

### Escalation Status

```python
# Show tickets by escalation level
escalation_dist = Ticket.objects.values('escalation_level').annotate(
    count=Count('id')
).order_by('escalation_level')

for item in escalation_dist:
    level = f"Level {item['escalation_level']}" if item['escalation_level'] else "No escalation"
    print(f"{level}: {item['count']} tickets")

# Get escalated tickets with details
escalated = Ticket.objects.filter(escalation_level__gt=0).select_related('section', 'escalated_by')
print(f"\nEscalated tickets: {escalated.count()}")
for ticket in escalated:
    by_user = ticket.escalated_by.username if ticket.escalated_by else "System"
    print(f"  {ticket.ticket_no}: Level {ticket.escalation_level} - escalated by {by_user}")
```

### Pending Tickets with Reasons

```python
# Get all pending tickets with their reasons and comments
pending = Ticket.objects.filter(status='pending')

print(f"Pending Tickets: {pending.count()}\n")
for ticket in pending:
    print(f"{ticket.ticket_no}: {ticket.title}")
    print(f"  Reason: {ticket.pending_reason}")
    print(f"  Comment: {ticket.pending_comment[:100]}...")
    print()
```

---

## Scope and Access Control Queries

### User Accessible Tickets (Org Scope)

```python
# Example: Get tickets accessible to a specific user
user = CustomUser.objects.filter(role='technician').first()

if user:
    accessible = user.get_accessible_tickets()
    print(f"User {user.username} can access {accessible.count()} tickets")
```

### Technician's Current Workload

```python
# Show assigned tickets for each technician
for tech in CustomUser.objects.filter(role='technician'):
    assigned = tech.assigned_tickets.filter(status__in=['open', 'assigned', 'in_progress'])
    if assigned.exists():
        print(f"\n{tech.username}:")
        for ticket in assigned:
            print(f"  • {ticket.ticket_no}: {ticket.title} ({ticket.status})")
```

### Section Head's Active Tickets

```python
# Get tickets that need section head attention (escalated)
for section_head in CustomUser.objects.filter(role='head_of_section'):
    section = section_head.managed_sections.all()
    escalated = Ticket.objects.filter(
        section__in=section,
        escalation_level=1
    )
    if escalated.exists():
        print(f"\n{section_head.username} has {escalated.count()} escalated tickets:")
        for ticket in escalated:
            print(f"  • {ticket.ticket_no} - {ticket.priority}")
```

### HOD's Department Tickets

```python
# Get tickets in HOD's department
for hod in CustomUser.objects.filter(role='hod'):
    dept = hod.head_of_for.first()
    if dept:
        tickets = dept.department_tickets.exclude(status='closed')
        print(f"\n{hod.username} ({dept.name}): {tickets.count()} active tickets")
```

---

## Comment and Collaboration Queries

### Tickets with Comments

```python
# Find tickets with the most comments
top_commented = Ticket.objects.annotate(
    comment_count=Count('comments')
).filter(comment_count__gt=0).order_by('-comment_count')[:10]

for ticket in top_commented:
    print(f"{ticket.ticket_no}: {ticket.comment_count} comments")
```

### Comment Activity Timeline

```python
# Get recent comment activity
recent = Comment.objects.select_related(
    'ticket', 'author'
).order_by('-created_at')[:20]

for comment in recent:
    print(f"[{comment.created_at.strftime('%Y-%m-%d %H:%M')}] {comment.author.username}: {comment.text[:50]}...")
```

### Comments by User

```python
# Count comments per user
comment_counts = Comment.objects.values(
    'author__username'
).annotate(count=Count('id')).order_by('-count')

for item in comment_counts:
    print(f"{item['author__username']}: {item['count']} comments")
```

---

## Feedback and Satisfaction Queries

### Tickets with Feedback

```python
# Get resolved tickets that have feedback
with_feedback = Ticket.objects.filter(
    feedback__isnull=False
).select_related('feedback', 'assigned_to')

for ticket in with_feedback:
    tech = ticket.assigned_to.username if ticket.assigned_to else "—"
    rating = "⭐" * ticket.feedback.rating
    print(f"{ticket.ticket_no}: {rating} (Technician: {tech})")
    if ticket.feedback.comment:
        print(f"  Comment: {ticket.feedback.comment[:80]}...")
```

### Average Technician Ratings

```python
# Average feedback rating by technician
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
    rating = "⭐" * int(item['avg_rating'])
    print(f"{name}: {rating} ({item['count']} ratings)")
```

### Satisfaction Trends by Section

```python
# Average feedback rating by section
section_ratings = Feedback.objects.select_related(
    'ticket__section'
).values(
    'ticket__section__name'
).annotate(
    avg_rating=Avg('rating'),
    count=Count('id')
).filter(count__gt=0).order_by('-avg_rating')

for item in section_ratings:
    rating = item['avg_rating']
    print(f"{item['ticket__section__name']}: {rating:.1f}⭐ ({item['count']} ratings)")
```

---

## Performance and SLA Queries

### Resolution Time Analysis

```python
from django.db.models import ExpressionWrapper, DurationField

# Tickets with resolution time calculated
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

### Overdue Tickets (No Recent Activity)

```python
# Tickets without updates for 24+ hours
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

### SLA Compliance

```python
# Check if tickets are approaching SLA deadline
from datetime import timedelta

sla_window = timezone.now() + timedelta(hours=48)
at_risk = Ticket.objects.filter(
    escalation_level=0,
    status__in=['open', 'assigned'],
    next_escalation_due__lte=sla_window
).order_by('next_escalation_due')

print(f"Tickets approaching SLA deadline: {at_risk.count()}")
for ticket in at_risk:
    hours_left = (ticket.next_escalation_due - timezone.now()).total_seconds() / 3600
    print(f"  {ticket.ticket_no}: {hours_left:.1f} hours until escalation")
```

---

## Audit and Activity Queries

### Recent Ticket Activity Log

```python
# Last 20 ticket changes
recent_logs = TicketLog.objects.select_related(
    'ticket', 'performed_by'
).order_by('-timestamp')[:20]

for log in recent_logs:
    user = log.performed_by.username if log.performed_by else "System"
    print(f"[{log.timestamp.strftime('%Y-%m-%d %H:%M')}] {log.action}: {log.ticket.ticket_no} - {user}")
```

### Tickets Created Today

```python
# Count tickets created today
today_start = timezone.make_aware(timezone.now().replace(hour=0, minute=0, second=0, microsecond=0))
today_tickets = Ticket.objects.filter(created_at__gte=today_start)

print(f"Tickets created today: {today_tickets.count()}")
for ticket in today_tickets:
    print(f"  • {ticket.ticket_no}: {ticket.title} (Status: {ticket.status})")
```

### Changes by Specific User

```python
# Show all changes made by a specific user
username_to_find = "admin"  # Change to desired username
user = CustomUser.objects.filter(username=username_to_find).first()

if user:
    user_changes = TicketLog.objects.filter(performed_by=user).order_by('-timestamp')
    print(f"Changes made by {username_to_find}: {user_changes.count()}")
    for log in user_changes[:10]:
        print(f"  • {log.action} on {log.ticket.ticket_no}")
```

---

## Complex Analytical Queries

### Tickets by Facility Type

```python
# Count tickets by facility type 
facility_stats = Ticket.objects.values(
    'facility__type'
).annotate(
    count=Count('id'),
    avg_resolution=Avg(
        Case(
            When(resolved_at__isnull=False,
                 then=F('resolved_at') - F('created_at')),
            default=None
        )
    )
).order_by('-count')

for item in facility_stats:
    print(f"{item['facility__type']}: {item['count']} tickets")
```

### Busiest Sections

```python
# Sections with most open tickets
busy_sections = Ticket.objects.filter(
    status__in=['open', 'assigned', 'in_progress']
).values('section__name').annotate(
    count=Count('id')
).order_by('-count')

for item in busy_sections:
    print(f"{item['section__name']}: {item['count']} active tickets")
```

### Assignment Patterns

```python
# Show which technicians are assigned to multiple sections
from django.db.models import Count

multi_section_techs = CustomUser.objects.filter(
    role='technician'
).annotate(
    section_count=Count('sections', distinct=True)
).filter(
    section_count__gt=1
).order_by('-section_count')

for tech in multi_section_techs:
    sections = ", ".join([s.name for s in tech.sections.all()])
    print(f"{tech.username}: {tech.section_count} sections - {sections}")
```

---

## Tips & Best Practices

1. **Always use `select_related()` for foreign keys** to avoid N+1 queries:
   ```python
   tickets = Ticket.objects.select_related('assigned_to', 'section', 'facility')
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

4. **Use raw SQL for complex queries**:
   ```python
   from django.db import connection
   with connection.cursor() as cursor:
       cursor.execute("SELECT ...")
   ```

5. **Exit shell and run again to reset loaded data**:
   ```bash
   python manage.py shell  # Fresh Python environment
   ```
```

### Comments on Specific Ticket

```python
from tickets.models import Ticket

# Get ticket with all comments
ticket = Ticket.objects.prefetch_related('comments').get(ticket_no='TKT-000001')
print(f"Ticket: {ticket.title}")
print(f"Comments ({ticket.comments.count()}):")
for comment in ticket.comments.all():
    print(f"  [{comment.created_at}] {comment.author.username}: {comment.text}")
```

### Complex Query: Technician Performance

```python
from django.db.models import Count, Q, Avg
from tickets.models import CustomUser

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
    sections = ", ".join([s.name for s in tech.sections.all()])
    rating = f"{tech.avg_rating:.2f}⭐" if tech.avg_rating else "N/A"
    print(f"{tech.first_name} {tech.last_name} ({tech.username})")
    print(f"  Specializations: {sections}")
    print(f"  Total assigned: {tech.total_assigned}")
    print(f"  Resolved: {tech.resolved_count}")
    print(f"  Average rating: {rating}")
    print()
```

## API Endpoint Queries

Test these endpoints using curl or your browser:

### Get All Tickets
```bash
curl http://127.0.0.1:8000/api/tickets/
```

### Filter Tickets by Status
```bash
curl "http://127.0.0.1:8000/api/tickets/?status=open"
curl "http://127.0.0.1:8000/api/tickets/?status=pending"
```

### Filter by Facility
```bash
curl "http://127.0.0.1:8000/api/tickets/?facility=1"
```

### Filter by Section
```bash
curl "http://127.0.0.1:8000/api/tickets/?section=1"
```

### Get Specific Ticket with Details
```bash
curl http://127.0.0.1:8000/api/tickets/1/
```

### Get All Users
```bash
curl http://127.0.0.1:8000/api/users/
```

### Filter Users by Role
```bash
curl "http://127.0.0.1:8000/api/users/?role=technician"
```

### Get All Sections
```bash
curl http://127.0.0.1:8000/api/sections/
```

### Get All Facilities
```bash
curl http://127.0.0.1:8000/api/facilities/
```

### Analytics Endpoints

#### Ticket Analytics
```bash
# All ticket analytics
curl http://127.0.0.1:8000/api/analytics/tickets/

# Filter by facility
curl "http://127.0.0.1:8000/api/analytics/tickets/?facility_id=1"

# Filter by section
curl "http://127.0.0.1:8000/api/analytics/tickets/?section_id=1"

# Filter by timeframe
curl "http://127.0.0.1:8000/api/analytics/tickets/?timeframe=week"
```

#### Technician Analytics
```bash
# All technician performance
curl http://127.0.0.1:8000/api/analytics/technicians/

# Specific technician
curl "http://127.0.0.1:8000/api/analytics/technicians/?technician_id=3"
```

#### Admin Dashboard
```bash
curl http://127.0.0.1:8000/api/analytics/admin-dashboard/
```

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

-- Tickets by facility type
SELECT fa.type, COUNT(t.id) as ticket_count
FROM tickets_facility fa
LEFT JOIN tickets_ticket t ON t.facility_id = fa.id
GROUP BY fa.type
ORDER BY ticket_count DESC;

-- Recent ticket activity
SELECT tl.timestamp, u.username, tl.action, t.ticket_no
FROM tickets_ticketlog tl
JOIN tickets_ticket t ON tl.ticket_id = t.id
LEFT JOIN tickets_customuser u ON tl.performed_by_id = u.id
ORDER BY tl.timestamp DESC
LIMIT 20;
```

## Testing Scenarios

### Scenario 1: Assign a Ticket
```python
from tickets.models import Ticket, CustomUser

ticket = Ticket.objects.get(ticket_no='TKT-000002')
tech = CustomUser.objects.get(username='tech_alex')

# Update ticket
ticket.assigned_to = tech
ticket.status = 'assigned'
ticket.save()

print(f"Assigned {ticket.ticket_no} to {tech.username}")
```

### Scenario 2: Add a Comment
```python
from tickets.models import Ticket, Comment, CustomUser

ticket = Ticket.objects.get(ticket_no='TKT-000002')
author = CustomUser.objects.get(username='tech_alex')

comment = Comment.objects.create(
    ticket=ticket,
    author=author,
    text="Investigating the server cooling system now."
)

print(f"Added comment to {ticket.ticket_no}")
```

### Scenario 3: Resolve a Ticket
```python
from tickets.models import Ticket

ticket = Ticket.objects.get(ticket_no='TKT-000002')
ticket.status = 'resolved'
ticket.save()

print(f"Resolved {ticket.ticket_no}")
```

### Scenario 4: Add Feedback
```python
from tickets.models import Ticket, Feedback, CustomUser

ticket = Ticket.objects.get(ticket_no='TKT-000004')
user = CustomUser.objects.get(username='manager_ict')

feedback = Feedback.objects.create(
    ticket=ticket,
    rated_by=user,
    rating=5.0,
    comment="Excellent work! Fixed quickly and professionally."
)

print(f"Added feedback to {ticket.ticket_no}")
```

---

These queries will help you explore and test all aspects of the enhanced fixture data!
