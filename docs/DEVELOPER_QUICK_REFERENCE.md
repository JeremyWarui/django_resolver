# Django Resolver - Developer Quick Reference

## 🚀 Quick Start

### Setup
```bash
# Clone and setup
cp .env.example .env
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py loaddata tickets/fixtures/tickets_initial_data.json
```

### Run
```bash
python manage.py runserver
# Access: http://localhost:8000/api/
```

### Test
```bash
python manage.py test tickets
python manage.py test tickets.tests.test_apis.TicketAPITestCase.test_ticket_lifecycle_workflow
```

---

## 📊 File Locations by Task

### Adding a New API Endpoint

1. **Business Logic** → `tickets/api/services/ticket_services.py`
2. **View/Endpoint** → `tickets/api/views/resource_views.py`
3. **URL Route** → `tickets/api/urls.py`
4. **Test** → `tickets/tests/test_apis.py`

**Example**: List user's tickets
```python
# 1. Service (ticket_services.py)
def get_user_tickets(user):
    if user.role == 'technician':
        return Ticket.objects.filter(assigned_to=user)
    return Ticket.objects.filter(raised_by=user)

# 2. View (resource_views.py)
class UserTicketsListView(generics.ListAPIView):
    serializer_class = TicketSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        return get_user_tickets(self.request.user)

# 3. URL (urls.py)
path('my-tickets/', UserTicketsListView.as_view(), name='user-tickets'),

# 4. Test (test_apis.py)
def test_user_tickets(self):
    # Login, GET /my-tickets/, verify results
    pass
```

### Adding a New Model Field

1. **Model** → `tickets/models.py`
2. **Serializer** → `tickets/serializers.py`
3. **Migration** → `python manage.py makemigrations`
4. **Test** → `tickets/tests/test_models.py`

**Example**: Add priority field to Ticket
```python
# 1. Model (models.py)
class Ticket(models.Model):
    PRIORITY_CHOICES = [('low', 'Low'), ('high', 'High')]
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='low')

# 2. Serializer (serializers.py)
class TicketSerializer(serializers.ModelSerializer):
    # priority auto-included from model

# 3. Create migration
python manage.py makemigrations
python manage.py migrate

# 4. Test (test_models.py)
def test_ticket_priority(self):
    ticket = Ticket.objects.create(priority='high')
    assert ticket.priority == 'high'
```

### Adding a New Permission

1. **Permission Class** → `tickets/api/permissions.py`
2. **View Usage** → `tickets/api/views/resource_views.py` (add to permission_classes)
3. **Test** → `tickets/tests/test_apis.py`

**Example**: Only ticket creator can delete
```python
# 1. Permission (permissions.py)
class IsTicketCreator(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.raised_by == request.user

# 2. View (resource_views.py)
class TicketRetrieveUpdate(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsTicketCreator]

# 3. Test (test_apis.py)
def test_ticket_delete_permission(self):
    # Creator can delete: pass
    # Other user can't delete: 403 Forbidden
    pass
```

### Adding a New Analytics Metric

1. **Analytics Logic** → `tickets/api/analytics/analytics.py`
2. **View/Endpoint** → `tickets/api/analytics/views.py`
3. **URL Route** → `tickets/api/urls.py`
4. **Test** → `tickets/tests/test_analytics.py`

**Example**: Get oldest unresolved tickets
```python
# 1. Analytics (analytics/analytics.py)
class TicketAnalytics:
    def get_oldest_unresolved(self):
        tickets = self.tickets.filter(
            status__in=['open', 'assigned', 'in_progress', 'pending']
        ).order_by('created_at')[:10]
        return tickets

# 2. View (analytics/views.py)
class OldestTicketsView(APIView):
    def get(self, request):
        analytics = TicketAnalytics(Ticket.objects)
        tickets = analytics.get_oldest_unresolved()
        return Response(TicketSerializer(tickets, many=True).data)

# 3. URL (urls.py)
path('analytics/oldest/', OldestTicketsView.as_view(), name='oldest-tickets'),

# 4. Test (test_analytics.py)
def test_oldest_tickets(self):
    # Create tickets with known ages
    # Call endpoint
    # Verify correct order
    pass
```

---

## 🔐 Authentication Patterns

### Check Current User Role

```python
# In view
if request.user.role == 'technician':
    queryset = queryset.filter(assigned_to=request.user)

# In serializer
class TicketSerializer(serializers.ModelSerializer):
    def to_representation(self, instance):
        ret = super().to_representation(instance)
        if self.context['request'].user.role != 'admin':
            # Hide sensitive fields
            ret.pop('internal_notes')
        return ret

# In model
class Ticket(models.Model):
    def can_be_edited_by(self, user):
        return user.role in ['admin', 'manager'] or (
            user.role == 'technician' and self.assigned_to == user
        )
```

### Require Specific Role

```python
# Permission class (permissions.py)
class IsTechnician(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role == 'technician'

# In view
class TechnicianOnlyView(APIView):
    permission_classes = [IsAuthenticated, IsTechnician]
```

### Check Token Status

```python
# Verify token exists
from rest_framework.authtoken.models import Token

token = Token.objects.filter(user=request.user).first()
if token:
    # User is authenticated
    pass

# Check session expires at
session = LoginSession.objects.filter(user=request.user).first()
if session and session.expires_at > timezone.now():
    # Session still valid
    pass
```

---

## 🗄️ Database Patterns

### Query Optimization

```python
# ❌ Bad: N+1 queries
tickets = Ticket.objects.all()
for ticket in tickets:
    print(ticket.assigned_to.name)  # Query per iteration!

# ✅ Good: Single query with join
tickets = Ticket.objects.select_related('assigned_to')
for ticket in tickets:
    print(ticket.assigned_to.name)  # No extra queries

# ❌ Bad: Missing index
Ticket.objects.filter(status='open')  # Slow on large tables

# ✅ Good: Index exists (0003 migration)
Ticket.objects.filter(status='open')  # Fast!

# ❌ Bad: Unnecessary prefetch
tickets = Ticket.objects.prefetch_related('comments')  # In list view
return Response(serializer.data)  # Serializer doesn't use comments

# ✅ Good: Skip expensive relations in list
tickets = Ticket.objects.all()  # In list view
skip_comments = True  # Flag to serializer
return Response(serializer.data)
```

### Atomic Operations

```python
# ❌ Bad: Separate operations = inconsistent state
ticket.status = 'in_progress'
ticket.save()
TicketLog.objects.create(ticket=ticket, old_status=...)
# If second operation fails, log missing!

# ✅ Good: Atomic transaction
@transaction.atomic
def change_status(ticket, new_status, user):
    ticket.status = new_status
    ticket.save()
    TicketLog.objects.create(ticket=ticket, old_status=...)
# Both succeed or both fail

# ✅ Better: Use model helper method
ticket.change_status('in_progress', performed_by=user)
# Atomic transaction built-in
```

### Pagination

```python
# All list endpoints auto-paginate
Ticket.objects.all()  # Returns paginated response

# Customize per view
class TicketListCreate(generics.ListCreateAPIView):
    pagination_class = CustomPagination
    # or set in settings.py

# Response format
{
    "count": 523,
    "next": "http://api/.../api/tickets/?page=2",
    "previous": null,
    "total_pages": 53,
    "current_page": 1,
    "results": [...]
}
```

---

## 🎨 Serializer Patterns

### Nested Relationships

```python
# ❌ Bad: Always include nested data
class TicketSerializer(serializers.ModelSerializer):
    comments = CommentSerializer(many=True)  # Always included

# ✅ Good: Skip expensive relations conditionally
class TicketSerializer(serializers.ModelSerializer):
    def get_fields(self):
        fields = super().get_fields()
        if self.context.get('skip_comments'):
            fields.pop('comments', None)
        return fields

# Usage in view
def get_serializer_context(self):
    context = super().get_serializer_context()
    context['skip_comments'] = self.action == 'list'  # Skip in list view
    return context
```

### Custom Fields

```python
# Computed field
class TicketSerializer(serializers.ModelSerializer):
    days_since_creation = serializers.SerializerMethodField()
    
    def get_days_since_creation(self, obj):
        return (timezone.now() - obj.created_at).days

# Read-only field
class TicketSerializer(serializers.ModelSerializer):
    ticket_no = serializers.CharField(read_only=True)
    # Can't be set in POST/PATCH

# Write-only field
class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    # Returned in response as hashed, not plain text
```

### Validation

```python
# Field-level validation
class TicketSerializer(serializers.ModelSerializer):
    def validate_priority(self, value):
        if value not in ['low', 'medium', 'high']:
            raise serializers.ValidationError("Invalid priority")
        return value

# Object-level validation
def validate(self, data):
    if data['assigned_to'] and data['status'] == 'open':
        raise serializers.ValidationError(
            "Can't assign to open ticket"
        )
    return data

# Custom validation in service
def update_ticket(ticket, data, user):
    if not validate_status_transition(
        ticket.status, data['status'], user.role
    ):
        raise ValidationError("Invalid status transition")
    # ... proceed
```

---

## 📝 Testing Patterns

### Test Fixtures

```python
# Base test class (test_apis.py)
class TicketAPITestCase(BaseTicketTestCase):
    def setUp(self):
        super().setUp()
        # Fixtures auto-loaded by BaseTicketTestCase
        # Users: tech_maria, manager_john, admin_alex
        # Tickets: 98 test records
        
    def test_ticket_list(self):
        # Test as technician
        self.client.force_authenticate(user=self.tech_user)
        response = self.client.get('/api/tickets/')
        self.assertEqual(response.status_code, 200)
```

### Authentication in Tests

```python
# Login-based testing
def test_with_login(self):
    response = self.client.post('/api/auth/login/', {
        'username': 'tech_maria',
        'password': 'mariagarcia'
    })
    token = response.data['token']
    
    response = self.client.get('/api/tickets/', HTTP_AUTHORIZATION=f'Token {token}')
    self.assertEqual(response.status_code, 200)

# Force authenticate
def test_with_force_auth(self):
    user = CustomUser.objects.get(username='tech_maria')
    self.client.force_authenticate(user=user)
    
    response = self.client.get('/api/tickets/')
    self.assertEqual(response.status_code, 200)
```

### Common Assertions

```python
# Status codes
self.assertEqual(response.status_code, 200)  # GET/PATCH
self.assertEqual(response.status_code, 201)  # POST
self.assertEqual(response.status_code, 204)  # DELETE
self.assertEqual(response.status_code, 400)  # Validation error
self.assertEqual(response.status_code, 403)  # Permission denied
self.assertEqual(response.status_code, 404)  # Not found

# Data checks
data = response.json()
self.assertEqual(data['id'], ticket.id)
self.assertIn('created_at', data)
self.assertTrue(data['is_overdue'])

# Database checks
self.assertTrue(Ticket.objects.filter(status='resolved').exists())
self.assertEqual(TicketLog.objects.filter(ticket=ticket).count(), 3)
```

---

## 🐛 Common Issues & Solutions

### 403 Forbidden on Analytics Endpoint
**Problem**: User can't access `/api/analytics/admin-dashboard/`
**Solution**: Check permission class - changed to `IsAuthenticated` (allow all users)
```python
# Before: IsAdminOrManager  # Too restrictive
# After: IsAuthenticated   # Allow all, filter data by role
permission_classes = [IsAuthenticated]
```

### LoginSession Constraint Violation
**Problem**: "duplicate key value violates unique constraint" on login
**Solution**: Clear old sessions before reloading fixtures
```bash
python manage.py clear_sessions --force
python manage.py loaddata tickets/fixtures/tickets_initial_data.json
```

### N+1 Query Problem
**Problem**: Ticket list endpoint is slow (list of 100 takes 15 seconds)
**Solution**: Add `select_related()` to get_queryset()
```python
def get_queryset(self):
    return Ticket.objects.select_related(
        'section', 'facility', 'raised_by', 'assigned_to'
    )
```

### Invalid Status Transition
**Problem**: Can't transition ticket from open to resolved
**Solution**: Check `validate_status_transition()` rules - must go through assigned/in_progress
```
open → assigned → in_progress → resolved
# Direct transition not allowed
```

### Token Not Returning on Login
**Problem**: Login succeeds but no token in response
**Solution**: Check Token model exists and migration ran
```bash
python manage.py migrate
# Verify Token records exist in database
python manage.py shell
from rest_framework.authtoken.models import Token
Token.objects.all().count()
```

---

## 📚 Documentation Map

| Task | Document |
|------|----------|
| Understand full architecture | [CODEBASE_ARCHITECTURE.md](CODEBASE_ARCHITECTURE.md) |
| See visual diagrams | [ARCHITECTURE_DIAGRAMS.md](ARCHITECTURE_DIAGRAMS.md) |
| Use API endpoints | [api/GUIDE.md](api/GUIDE.md) |
| Query analytics | [api/ANALYTICS.md](api/ANALYTICS.md) |
| Write tests | [testing/TESTING.md](testing/TESTING.md) |
| Query examples | [testing/SAMPLE_QUERIES.md](testing/SAMPLE_QUERIES.md) |
| Auth details | [AUTHENTICATION.md](AUTHENTICATION.md) |
| Test credentials | [DEFAULT_CREDENTIALS.md](DEFAULT_CREDENTIALS.md) |

---

## 🔗 Key Files

```
Core Models:           tickets/models.py
Serializers:           tickets/serializers.py
API Endpoints:         tickets/api/views/resource_views.py
Business Logic:        tickets/api/services/ticket_services.py
Authentication:        tickets/api/simple_auth_views.py
Analytics:             tickets/api/analytics/
Permissions:           tickets/api/permissions.py
Tests:                 tickets/tests/
Migrations:            tickets/migrations/
Test Data:             tickets/fixtures/tickets_initial_data.json
```

---

## ⚡ Performance Tips

1. **Use `select_related()` for FK fields** in get_queryset()
2. **Use `prefetch_related()` for M2M** only in detail views
3. **Skip expensive serializer fields in list view** with skip_available_technicians flag
4. **Database indexes exist** on status, updated_at, assigned_to (already added)
5. **Pagination default 10 items/page** - don't change unless needed
6. **Atomic transactions** for status/assignment changes to prevent inconsistent state

---

## 🚀 Deployment Checklist

```bash
[ ] Set SECRET_KEY in .env
[ ] Set DEBUG=False in .env
[ ] Set ALLOWED_HOSTS in .env
[ ] Set DATABASE_URL to production DB
[ ] python manage.py migrate
[ ] python manage.py collectstatic
[ ] python manage.py loaddata (if using fixture)
[ ] Test endpoints with curl or frontend
[ ] Monitor logs for errors
```

---

**Last Updated**: January 2025
**Version**: 1.0
**Contact**: Development Team
