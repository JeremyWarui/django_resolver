# Testing Guide

Complete testing documentation for the Django Ticket Resolver System, including test organization, running tests, and using shared fixtures.

---

## Table of Contents

1. [Test Organization](#test-organization)
2. [Running Tests](#running-tests)
3. [Using BaseTicketTestCase](#using-baseticketTestcase)
4. [Test Coverage](#test-coverage)

---

## Test Organization

### Test Files

#### `test_apis.py` - API Endpoint Tests
API tests using Django REST Framework's `APITestCase`. Verifies correct functioning of all API endpoints and their associated business logic.

**Basic API Functionality**
- `test_get_tickets` - Verify retrieving ticket list
- `test_create_ticket` - Ensure tickets can be created with proper data
- `test_get_ticket_detail` - Test retrieving a specific ticket with nested comments & feedback
- `test_delete_ticket` - Test ticket deletion functionality

**Role-Based Permissions**
- `test_update_ticket_status_technician` - Technicians can update ticket status
- `test_update_ticket_status_admin` - Admins can update ticket status
- `test_update_ticket_user_cant` - Regular users cannot update ticket status
- `test_user_cannot_assign_ticket` - Regular users cannot assign tickets
- `test_assign_ticket_admin` - Admins can assign tickets to technicians

**Filtering**
- `test_filter_tickets_by_status` - Filter tickets by different status values
- `test_filter_tickets_by_section` - Filter tickets by section

**Comment and Feedback**
- `test_user_can_add_comment` - Test comment creation functionality
- `test_feedback_one_per_ticket` - Ensure only one feedback per ticket is allowed
- `test_feedback_on_unresolved_ticket` - Feedback only allowed on resolved tickets
- `test_comment_on_closed_ticket` - Comments not allowed on closed tickets

**Workflow**
- `test_ticket_lifecycle_workflow` - Test full ticket lifecycle from open to resolved
- `test_changing_ticket_status` - Test status transitions for different roles
- `test_status_transition_validation` - Test validation of status transitions
- `test_valid_status_transitions` - Test various status transition scenarios
- `test_resolve_ticket_technician` - Technicians can mark tickets as resolved

**Edge Cases**
- `test_assign_resolved_ticket_fails` - Cannot reassign resolved tickets
- `test_invalid_data_handling` - Test handling of invalid input data
- `test_anonymous_user_cannot_create_ticket` - Anonymous users cannot create tickets
- `test_unrelated_user_cannot_comment` - Users not related to ticket cannot comment

**Closed Status**
- `test_admin_can_close_resolved_ticket` - Only admins can close resolved tickets
- `test_cannot_close_unresolved_ticket` - Tickets must be resolved before closing
- `test_cannot_modify_closed_ticket` - Closed tickets cannot be modified
- `test_comment_on_closed_ticket` - Closed tickets cannot receive comments

**Comment Visibility**
- `test_admin_and_technician_can_view_comments` - Verify comment visibility rules for different user roles

#### `test_models.py` - Model Tests
Tests for Django models to ensure proper data validation, methods, and properties.

- `test_user_creation` - Test CustomUser model creation
- `test_section_creation` - Test Section model creation
- `test_technician_creation` - Test technician user creation
- `test_ticket_creation` - Test Ticket model creation
- `test_ticket_is_overdue` - Test ticket overdue status detection
- `test_ticket_set_to_pending_overdue_ticket` - Test status transition for overdue tickets
- `test_ticket_status_after_assignment` - Test status changes during assignment
- `test_ticket_creation_and_auto_increment_ticket_no` - Test automatic ticket number generation
- `test_ticket_count` - Test counting of tickets
- `test_ticket_comments_count` - Test counting comments on a ticket

#### `test_serializers.py` - Serializer Tests
Tests for Django REST Framework serializers to ensure proper data validation and transformation.

- `test_ticket_serializer` - Test TicketSerializer data representation
- `test_comment_serializer` - Test CommentSerializer data representation
- `test_custom_user_serializer` - Test UserSerializer data representation
- `test_user_create_serializer` - Test UserSerializer create method
- `test_ticket_serializer_create` - Test ticket creation through serializer
- `test_comment_serializer_create` - Test comment creation through serializer
- `test_feedback_serializer_create` - Test feedback creation through serializer

#### `test_ticket_operations.py` - Ticket Operations Tests
Tests for ticket creation, updating, and technician assignment workflows.

- Tests ticket POST/PATCH operations
- Tests technician filtering by section
- Validates assignment rules and constraints

#### `test_workflow.py` - End-to-End Workflow Tests
End-to-end workflow tests using pytest fixtures.

- `test_ticket_creation` - Test basic ticket creation workflow
- `test_admin_can_assign_ticket` - Test admin assigning tickets to technicians
- `test_admin_cant_assign_ticket_to_technician_not_in_section` - Test section constraints
- `test_technician_can_update_ticket_status` - Test technician status update workflow
- `test_user_cant_update_ticket_status` - Test user permissions for status updates
- `test_technician_or_admin_add_comment_to_ticket` - Test commenting workflow
- `test_user_can_submit_feedback` - Test feedback submission flow
- `test_user_cant_submit_feedback_is_not_resolved` - Test feedback constraints

#### `test_analytics.py` - Analytics Tests
Tests for analytics endpoints and data aggregation.

- Tests ticket counts and distributions
- Tests technician performance metrics
- Tests system overview analytics

---

## Running Tests

### Pytest (Recommended)

```bash
# Run all tests
pytest tickets/tests/

# Run specific test file
pytest tickets/tests/test_serializers.py

# Run with verbose output
pytest tickets/tests/ -v

# Run with coverage report
pytest tickets/tests/ --cov=tickets --cov-report=html

# Run with coverage in terminal
pytest tickets/tests/ --cov=tickets --cov-report=term-missing

# Run specific test class
pytest tickets/tests/test_apis.py::APITests

# Run specific test method
pytest tickets/tests/test_serializers.py::SerializerTests::test_ticket_serializer

# Run tests matching pattern
pytest tickets/tests/ -k "comment"

# Run with short traceback
pytest tickets/tests/ --tb=short

# Reuse database (faster for repeated runs)
pytest tickets/tests/ --reuse-db
```

### Django Test Runner

```bash
# Run all tests
python manage.py test tickets.tests

# Run specific test file
python manage.py test tickets.tests.test_apis

# Run specific test class
python manage.py test tickets.tests.test_apis.APITests

# Run specific test method
python manage.py test tickets.tests.test_apis.APITests.test_get_tickets
```

---

## Using BaseTicketTestCase

### Overview

The `BaseTicketTestCase` eliminates fixture duplication across test files. Instead of creating users, sections, facilities, and tickets in every test file's `setUp()` method, inherit from the base class.

**Benefits:**
- ✅ Eliminates ~90 lines of duplicated fixture code
- ✅ Faster tests - `setUpTestData()` runs once per test class (not per test method)
- ✅ Consistent fixtures - All tests use the same base data
- ✅ Easy maintenance - Update fixtures in one place

### Quick Start

```python
from tickets.tests.base import BaseTicketTestCase

class MyTests(BaseTicketTestCase):
    def test_something(self):
        # These are available from the base class:
        self.user          # Regular user
        self.admin         # Admin user  
        self.technician    # Technician (assigned to IT section)
        self.section       # IT section
        self.section_hvac  # HVAC section
        self.facility      # Main Building
        self.ticket        # Sample ticket (assigned, IT section)
        
        self.assertEqual(self.user.username, "testuser")
```

### Available Fixtures

| Attribute | Type | Description |
|-----------|------|-------------|
| `self.user` | CustomUser | Regular user (role='user') |
| `self.admin` | CustomUser | Admin user (role='admin', is_staff=True) |
| `self.technician` | CustomUser | Technician (role='technician', assigned to IT section) |
| `self.section` | Section | IT section |
| `self.section_hvac` | Section | HVAC section |
| `self.facility` | Facility | Main Building (type='building', status='active') |
| `self.ticket` | Ticket | Sample ticket (status='assigned', IT section) |

### For API Tests

Use `BaseAPITestCase` for tests that need an authenticated API client:

```python
from tickets.tests.base import BaseAPITestCase

class MyAPITests(BaseAPITestCase):
    def test_api_endpoint(self):
        # self.client is pre-authenticated as self.user
        response = self.client.get('/api/tickets/')
        self.assertEqual(response.status_code, 200)
    
    def test_admin_endpoint(self):
        # Switch to admin user
        self.authenticate_as(self.admin)
        response = self.client.delete(f'/api/tickets/{self.ticket.id}/')
        self.assertEqual(response.status_code, 204)
    
    def test_unauthorized_access(self):
        # Test without authentication
        self.unauthenticate()
        response = self.client.get('/api/tickets/')
        self.assertEqual(response.status_code, 403)
```

### Helper Methods

#### Create Additional Tickets
```python
def test_multiple_tickets(self):
    ticket1 = self.create_ticket(title="Broken AC", status="open")
    ticket2 = self.create_ticket(
        title="Network Issue",
        section=self.section_hvac,
        status="in_progress"
    )
```

#### Create Comments
```python
def test_comments(self):
    comment = self.create_comment(
        ticket=self.ticket,
        text="Need more info",
        author=self.technician
    )
```

#### Create Feedback
```python
def test_feedback(self):
    # First resolve the ticket
    self.ticket.status = "resolved"
    self.ticket.save()
    
    feedback = self.create_feedback(
        ticket=self.ticket,
        rating=5,
        comment="Excellent work!"
    )
```

#### Reset Ticket Sequence
```python
def setUp(self):
    # Call this if you need predictable ticket IDs (e.g., testing ticket number generation)
    self.reset_ticket_sequence()
```

### Migration Example

**Before:**
```python
class MyTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username="testuser",
            email="testuser@example.com",
            password="testpass"
        )
        self.section = Section.objects.create(
            name="IT", 
            description="Information Technology"
        )
        # ... 20 more lines ...
```

**After:**
```python
from tickets.tests.base import BaseTicketTestCase

class MyTests(BaseTicketTestCase):
    # That's it! All fixtures available
    def test_something(self):
        self.assertEqual(self.user.username, "testuser")
```

### When NOT to Use Base Class

If your test needs unique fixture data that conflicts with the base class defaults, you have options:

**1. Override in setUp():**
```python
class MyTests(BaseTicketTestCase):
    def setUp(self):
        # Base class fixtures still available, add your own
        self.custom_ticket = Ticket.objects.create(
            title="Custom",
            section=self.section,
            facility=self.facility,
            raised_by=self.user,
            status="closed"
        )
```

**2. Use helper methods:**
```python
def test_custom_scenario(self):
    custom_ticket = self.create_ticket(status="closed")
```

**3. Don't inherit from base class** (for very unique test scenarios):
```python
from django.test import TestCase

class UniqueTests(TestCase):
    # Create completely custom fixtures
    pass
```

---

## Test Coverage

### Current Coverage

Run with pytest:
```bash
pytest tickets/tests/ --cov=tickets --cov-report=term-missing
```

**Coverage targets:**
- Models: 95%+
- Serializers: 95%+
- Views: 90%+
- Services: 95%+
- Overall: 85%+

### Generating HTML Coverage Report

```bash
# Generate HTML report
pytest tickets/tests/ --cov=tickets --cov-report=html

# Open report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

### Coverage by Module

| Module | Expected Coverage | Notes |
|--------|------------------|-------|
| `models.py` | 95%+ | Core business logic |
| `serializers.py` | 95%+ | Data validation |
| `api/views/` | 90%+ | Request handling |
| `api/services/` | 95%+ | Business logic |
| `api/analytics/` | 85%+ | Data aggregation |
| `api/reports/` | 70%+ | Report generation (complex) |

---

## Best Practices

### 1. Use Descriptive Test Names
```python
# Good
def test_admin_can_close_resolved_ticket(self):
    pass

# Bad
def test_close(self):
    pass
```

### 2. Test One Thing Per Test
```python
# Good
def test_user_can_create_ticket(self):
    # Only test ticket creation
    pass

def test_ticket_has_correct_status_after_creation(self):
    # Only test initial status
    pass

# Bad
def test_ticket_creation_and_status_and_assignment(self):
    # Too many things tested
    pass
```

### 3. Use Base Class for Common Fixtures
```python
# Good
class TicketTests(BaseTicketTestCase):
    def test_ticket_creation(self):
        # Use self.user, self.section, etc.
        pass

# Bad
class TicketTests(TestCase):
    def setUp(self):
        # Duplicate fixture creation
        self.user = CustomUser.objects.create_user(...)
        # ... 30 more lines ...
```

### 4. Clean Up After Tests
```python
def test_external_api_call(self):
    # Mock external services
    with patch('requests.post') as mock_post:
        mock_post.return_value.status_code = 200
        # Test your code
```

### 5. Use Assertions Effectively
```python
# Good
self.assertEqual(response.status_code, 200)
self.assertIn('ticket_no', response.data)
self.assertTrue(ticket.is_overdue)

# Bad
assert response.status_code == 200  # Less informative error messages
```

---

## Debugging Tests

### Run Single Test with Verbose Output
```bash
pytest tickets/tests/test_apis.py::APITests::test_get_tickets -vv
```

### Print Debugging
```python
def test_something(self):
    ticket = self.create_ticket()
    print(f"Ticket ID: {ticket.id}")  # Will show in pytest output with -s
    print(f"Ticket status: {ticket.status}")
    
    # Run with: pytest tickets/tests/ -s
```

### Use pytest's `--pdb` Flag
```bash
# Drop into debugger on failure
pytest tickets/tests/ --pdb

# Drop into debugger at start of test
pytest tickets/tests/test_apis.py::APITests::test_get_tickets --pdb -s
```

### Check Database State
```python
def test_something(self):
    # Create test data
    ticket = self.create_ticket()
    
    # Check what's in the database
    from tickets.models import Ticket
    all_tickets = Ticket.objects.all()
    print(f"Total tickets: {all_tickets.count()}")
    for t in all_tickets:
        print(f"  {t.ticket_no}: {t.status}")
```

---

## Continuous Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.11
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
    
    - name: Run tests
      run: |
        pytest tickets/tests/ --cov=tickets --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v2
```

---

## Additional Resources

- **[SAMPLE_QUERIES.md](SAMPLE_QUERIES.md)** - Django ORM query examples for exploring fixture data
- **[tickets/tests/base.py](../../tickets/tests/base.py)** - Base test class implementation
- **[pytest.ini](../../pytest.ini)** - Pytest configuration
- **Django Testing Docs**: https://docs.djangoproject.com/en/5.2/topics/testing/
- **DRF Testing Docs**: https://www.django-rest-framework.org/api-guide/testing/
- **pytest Docs**: https://docs.pytest.org/
