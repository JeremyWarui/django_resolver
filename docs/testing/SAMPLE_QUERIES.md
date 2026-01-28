# Sample Queries for Fixture Data

This document provides example queries to explore and test the enhanced fixture data.

## Django Shell Queries

Start the Django shell:
```bash
python manage.py shell
```

### Basic Queries

```python
from tickets.models import *

# Count all records
print(f"Sections: {Section.objects.count()}")
print(f"Facilities: {Facility.objects.count()}")
print(f"Users: {CustomUser.objects.count()}")
print(f"Tickets: {Ticket.objects.count()}")
print(f"Comments: {Comment.objects.count()}")
print(f"Feedback: {Feedback.objects.count()}")
print(f"Logs: {TicketLog.objects.count()}")

# Get all technicians
technicians = CustomUser.objects.filter(role='technician')
for tech in technicians:
    sections = ", ".join([s.name for s in tech.sections.all()])
    print(f"{tech.username}: {sections}")

# Get open tickets
open_tickets = Ticket.objects.filter(status='open')
print(f"Open tickets: {open_tickets.count()}")

# Get pending tickets with reasons
pending = Ticket.objects.filter(status='pending').exclude(pending_reason='')
for ticket in pending:
    print(f"{ticket.ticket_no}: {ticket.pending_reason}")
```

### Tickets by Status

```python
from django.db.models import Count
from tickets.models import Ticket

# Count tickets by status
status_distribution = Ticket.objects.values('status').annotate(
    count=Count('id')
).order_by('-count')

for item in status_distribution:
    print(f"{item['status']}: {item['count']}")
```

### Tickets by Facility

```python
from django.db.models import Count
from tickets.models import Ticket

# Count tickets by facility
facility_distribution = Ticket.objects.values(
    'facility__name', 'facility__type'
).annotate(count=Count('id')).order_by('-count')

for item in facility_distribution:
    print(f"{item['facility__name']} ({item['facility__type']}): {item['count']}")
```

### Tickets by Section

```python
from django.db.models import Count
from tickets.models import Ticket

# Count tickets by section
section_distribution = Ticket.objects.values(
    'section__name'
).annotate(count=Count('id')).order_by('-count')

for item in section_distribution:
    print(f"{item['section__name']}: {item['count']}")
```

### Technician Workload

```python
from django.db.models import Count, Avg
from tickets.models import Ticket, CustomUser

# Technician assignment counts
workload = Ticket.objects.filter(
    assigned_to__role='technician'
).values(
    'assigned_to__username', 'assigned_to__first_name', 'assigned_to__last_name'
).annotate(
    total=Count('id'),
    resolved=Count('id', filter=models.Q(status__in=['resolved', 'closed']))
).order_by('-total')

for item in workload:
    name = f"{item['assigned_to__first_name']} {item['assigned_to__last_name']}"
    print(f"{name} ({item['assigned_to__username']}): {item['total']} tickets, {item['resolved']} resolved")
```

### Technicians by Specialization

```python
from tickets.models import Section

# Get technicians for each section
for section in Section.objects.all():
    techs = section.technicians.all()
    tech_names = ", ".join([t.username for t in techs])
    print(f"{section.name}: {tech_names if tech_names else 'None'}")
```

### Tickets with Feedback

```python
from tickets.models import Ticket

# Get all tickets with feedback
tickets_with_feedback = Ticket.objects.filter(feedback__isnull=False).select_related('feedback')

for ticket in tickets_with_feedback:
    print(f"{ticket.ticket_no}: {ticket.feedback.rating}⭐ - {ticket.feedback.comment[:50]}...")
```

### Average Feedback Rating

```python
from django.db.models import Avg
from tickets.models import Feedback

avg_rating = Feedback.objects.aggregate(Avg('rating'))
print(f"Average rating: {avg_rating['rating__avg']:.2f}⭐")

# By technician
from django.db.models import Count
tech_ratings = Feedback.objects.filter(
    ticket__assigned_to__role='technician'
).values(
    'ticket__assigned_to__username'
).annotate(
    avg_rating=Avg('rating'),
    count=Count('id')
).order_by('-avg_rating')

for item in tech_ratings:
    print(f"{item['ticket__assigned_to__username']}: {item['avg_rating']:.2f}⭐ ({item['count']} ratings)")
```

### Recent Activity

```python
from tickets.models import TicketLog

# Last 10 actions
recent_logs = TicketLog.objects.select_related(
    'ticket', 'performed_by'
).order_by('-timestamp')[:10]

for log in recent_logs:
    user = log.performed_by.username if log.performed_by else 'System'
    print(f"[{log.timestamp}] {user}: {log.action} on {log.ticket.ticket_no}")
```

### Overdue Tickets (older than 24 hours)

```python
from django.utils import timezone
from datetime import timedelta
from tickets.models import Ticket

cutoff = timezone.now() - timedelta(hours=24)
overdue = Ticket.objects.filter(
    status__in=['open', 'assigned'],
    created_at__lt=cutoff
)

print(f"Overdue tickets: {overdue.count()}")
for ticket in overdue:
    age = timezone.now() - ticket.created_at
    print(f"{ticket.ticket_no}: {ticket.title} ({age.days} days old)")
```

### Tickets by User

```python
from tickets.models import Ticket, CustomUser

# Tickets raised by each user
for user in CustomUser.objects.filter(role='user'):
    count = user.raised_tickets.count()
    if count > 0:
        print(f"{user.username}: raised {count} ticket(s)")
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
user = CustomUser.objects.get(username='manager_ben')

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
