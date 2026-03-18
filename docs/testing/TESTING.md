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

### Test Files Overview

**Total Test Coverage**: 157 test methods across 10 test files

#### `test_apis.py` (41 tests) - API Endpoint Tests
Comprehensive API tests using Django REST Framework's `APITestCase`. Organized into two test classes: `APITests` and `BulkOperationsTestCase`.

**Class: `APITests` - Core API Functionality**
- `test_get_tickets` - Verify retrieving ticket list
- `test_create_ticket_via_api` - Create ticket through API endpoint
- `test_get_ticket_detail` - Retrieve specific ticket with nested data
- `test_delete_ticket` - Test ticket deletion

**Role-Based Access Control**
- `test_update_ticket_status_technician` - Technicians can update status
- `test_update_ticket_status_admin` - Admins can update status
- `test_update_ticket_user_cant` - Regular users cannot update status
- `test_user_cannot_assign_ticket` - Users cannot assign tickets
- `test_assign_ticket_admin` - Admins can assign tickets

**Filtering & Visibility**
- `test_filter_tickets_by_status` - Filter by status field
- `test_filter_tickets_by_section` - Filter by section ID
- `test_user_can_only_view_their_tickets` - Scope enforcement
- `test_technician_can_list_assigned_tickets` - Technician visibility

**Comment & Feedback Management**
- `test_user_can_add_comment` - Comment creation
- `test_feedback_one_per_ticket` - Single feedback constraint
- `test_feedback_on_unresolved_ticket` - Feedback only on resolved
- `test_comment_on_closed_ticket` - Comments blocked on closed
- `test_admin_and_technician_can_view_comments` - Comment visibility

**Ticket Lifecycle & Status Transitions**
- `test_ticket_lifecycle_workflow` - Full open→assigned→resolved→closed flow
- `test_changing_ticket_status` - Status transitions by role
- `test_status_transition_validation` - Invalid transition detection
- `test_valid_status_transitions` - Valid state flows
- `test_resolve_ticket_technician` - Technician resolution

**Closed Ticket Restrictions**
- `test_admin_can_close_resolved_ticket` - Only admins can close resolved
- `test_cannot_close_unresolved_ticket` - Must be resolved first
- `test_cannot_modify_closed_ticket` - Closed is immutable
- `test_assign_resolved_ticket_fails` - Cannot reassign resolved

**Error Handling**
- `test_invalid_data_handling` - Invalid input handling
- `test_anonymous_user_cannot_create_ticket` - Auth required
- `test_unrelated_user_cannot_comment` - Comment permissions

**Class: `BulkOperationsTestCase` (13 tests) - Bulk Status Updates**
- `test_bulk_status_update_admin_success` - Successful bulk updates
- `test_bulk_status_update_technician_success` - Technician bulk updates
- `test_bulk_status_update_requires_authentication` - Auth required
- `test_bulk_status_update_requires_permission` - Permission validation
- `test_bulk_status_update_missing_ticket_ids` - Missing field validation
- `test_bulk_status_update_missing_new_status` - Missing status
- `test_bulk_status_update_invalid_ticket_ids_type` - Type validation
- `test_bulk_status_update_empty_list` - Empty list handling
- `test_bulk_status_update_nonexistent_tickets` - Invalid IDs
- `test_bulk_status_update_partial_failure` - Partial success handling
- `test_bulk_status_update_large_batch` - Large batch processing

#### `test_models.py` (14 tests) - Model Tests
Tests for Django models to ensure proper data validation, methods, and properties. Single `ModelTests` class.

- `test_user_creation` - CustomUser model creation
- `test_user_role_validation` - Role field validation
- `test_technician_creation` - Technician user creation
- `test_section_creation` - Section model creation
- `test_section_technician_relationship` - M2M technician relationships
- `test_ticket_creation` - Ticket model creation
- `test_ticket_auto_numbering` - Auto-generated ticket numbers
- `test_ticket_creation_and_auto_increment_ticket_no` - Incremental numbering
- `test_ticket_status_choices` - Valid status options
- `test_ticket_status_after_assignment` - Status auto-set on assignment
- `test_ticket_log_creation` - Audit trail creation
- `test_change_status_sets_resolved_at_and_logs` - Status change tracking
- `test_change_assignment_creates_log_and_updates_assigned_to` - Assignment tracking
- `test_feedback_one_per_ticket_constraint` - Unique feedback constraint

#### `test_serializers.py` (8 tests) - Serializer Tests
Tests for Django REST Framework serializers. Single `SerializerTests` class extending `BaseTicketTestCase`.

- `test_ticket_serializer` - TicketSerializer data format
- `test_ticket_serializer_create` - Ticket creation via serializer
- `test_custom_user_serializer` - UserSerializer representation
- `test_user_create_serializer` - User creation via serializer
- `test_comment_serializer` - CommentSerializer format
- `test_comment_serializer_create` - Comment creation
- `test_feedback_serializer_create` - Feedback creation
- `test_section_serializer_includes_campus_context` - Campus hierarchy exposure (R1 Enhancement)

#### `test_ticket_operations.py` (9 tests) - Ticket Operations Tests
Tests for ticket creation, updating, and technician assignment workflows. Single `TicketOperationsTestCase` class.

- `test_create_ticket_direct_orm` - Direct ORM ticket creation
- `test_update_ticket_status` - Status field updates
- `test_update_multiple_fields` - Multiple field updates
- `test_assign_technician_to_ticket` - Technician assignment
- `test_get_all_technicians` - List all technicians
- `test_get_technicians_by_section` - Filter technicians by section
- `test_can_assign_multi_section_technician` - Multi-section technician assignment
- `test_cannot_assign_wrong_section_technician` - Section constraint validation
- `test_ticket_includes_available_technicians` - Serializer field inclusion

#### `test_workflow.py` (11 tests) - End-to-End Workflow Tests
Complete workflow tests without predefined fixtures. Tests real-world scenarios.

- `test_ticket_creation` - Basic ticket creation
- `test_admin_can_assign_ticket` - Admin assignment flow
- `test_admin_cant_assign_ticket_to_technician_not_in_section` - Section scope validation
- `test_technician_can_update_ticket_status` - Technician status updates
- `test_user_cant_update_ticket_status` - User permission enforcement
- `test_technician_or_admin_add_comment_to_ticket` - Comment permissions
- `test_user_can_submit_feedback` - Feedback submission
- `test_user_cant_submit_feedback_is_not_resolved` - Feedback constraints
- `test_complete_ticket_lifecycle` - Full workflow from creation to closure
- `test_admin_workflow_vs_technician_workflow` - Role-based workflow differences
- `test_section_based_routing` - Ticket section routing correctness

#### `test_analytics.py` (18 tests) - Analytics Tests
Analytics endpoint and data aggregation tests. Two test classes: `TestAnalyticsConsistency` and `TestAnalyticsEdgeCases`.

**Class: `TestAnalyticsConsistency` - Core Analytics**
- `test_single_ticket_analytics` - Single ticket metrics
- `test_ticket_analytics_api_endpoint` - Ticket analytics endpoint
- `test_ticket_analytics_counts_by_status` - Status distribution
- `test_ticket_analytics_counts_by_timeframe` - Time-based aggregation
- `test_technician_analytics_api_endpoint` - Technician performance endpoint
- `test_technician_analytics_performance` - Technician metrics
- `test_admin_analytics_api_endpoint` - Admin dashboard endpoint
- `test_admin_analytics_system_overview` - System-wide analytics
- `test_admin_analytics_avg_response_time_hours` - Response time calculations
- `test_admin_analytics_get_overdue_tickets` - Overdue identification
- `test_open_tickets_count_consistency` - Open count validation
- `test_resolved_tickets_count_consistency` - Resolved count validation
- `test_tickets_by_age_consistency` - Age-based grouping
- `test_resolution_time_consistency` - Resolution time tracking
- `test_resolution_rate_consistency` - Resolution rate calculation

**Class: `TestAnalyticsEdgeCases` - Edge Cases**
- `test_empty_database_analytics` - Empty data handling
- `test_boundary_conditions` - Boundary value testing
- `test_invalid_technician_analytics` - Invalid input handling

#### `test_organizational.py` (27 tests) - Organizational Hierarchy & Access Control
Comprehensive tests for organizational features. Six test classes.

**Class: `OrganizationalHierarchyTestCase` - Structure Tests**
- `test_organizational_structure_created` - Hierarchy creation verification

**Class: `EscalationWorkflowTestCase` - Escalation Logic**
- `test_escalate_ticket` - Manual escalation
- `test_escalate_ticket_manual_endpoint` - Escalation endpoint
- `test_escalation_to_section_head` - Level 1 escalation
- `test_escalation_to_hod` - Level 2 escalation
- `test_cannot_escalate_beyond_hod` - Max escalation level
- `test_auto_escalation_processing` - Automatic escalation execution
- `test_escalation_trends` - Escalation analytics

**Class: `APIIntegrationTestCase` - API & Scope Tests**
- `test_create_ticket_with_proper_scope` - Scope-compliant creation
- `test_create_ticket_exceeds_scope` - Scope violation detection
- `test_assigned_users_endpoint` - Available technicians filtering
- `test_assign_ticket_with_proper_validation` - Assignment validation
- `test_assign_ticket_invalid_technician` - Invalid technician rejection
- `test_get_accessible_tickets_respects_scope` - Ticket visibility scope
- `test_organizational_ticket_list_endpoint` - Org-scoped list
- `test_director_access_all_tickets` - Director permissions

**Class: `AnalyticsAggregationTestCase` - Role-Specific Dashboards**
- `test_director_dashboard` - Director-level analytics
- `test_director_dashboard_aggregates_metrics` - Metric aggregation
- `test_hod_dashboard` - HOD dashboard layout
- `test_hod_dashboard_campus_scoped` - Campus-scoped data
- `test_section_head_dashboard` - Section head visibility
- `test_hod_campus_scoped_access` - HOD scope enforcement
- `test_technician_section_scoped_access` - Technician scope
- `test_organizational_analytics_endpoint` - Analytics endpoint
- `test_dashboard_sla_compliance_calculation` - SLA metrics
- `test_aggregation_sla_compliance_calculation` - SLA aggregation

#### `test_spec_compliance.py` (11 tests) - Workflow Specification Compliance
Tests for recent specification features: priority field, pending fields, and user closure. Three test classes.

**Class: `PriorityFieldTestCase` - Priority & Auto-Escalation**
- `test_ticket_created_with_low_priority` - Default LOW priority
- `test_priority_escalates_to_medium_on_level_1` - L1 escalation→MEDIUM
- `test_priority_escalates_to_high_on_level_2` - L2 escalation→HIGH
- `test_priority_auto_marks_critical_after_72_hours` - Auto-CRITICAL after SLA

**Class: `PendingFieldsTestCase` - Pending Status with Reason & Comment**
- `test_pending_transition_requires_both_reason_and_comment` - Validation enforcement
- `test_pending_transition_with_both_fields` - Valid pending transition
- `test_pending_reason_is_enum_validated` - Reason field constraints

**Class: `UserTicketClosureTestCase` - User Ticket Closure**
- `test_user_can_close_own_resolved_ticket` - User closure permission
- `test_user_cannot_close_others_resolved_ticket` - Scope enforcement
- `test_user_cannot_close_unresolved_ticket` - Status validation
- `test_admin_can_close_any_resolved_ticket` - Admin closure permission

#### `test_auth_comprehensive.py` (16 tests) - Authentication & Authorization
Comprehensive auth tests. Two test classes: `AuthenticationTestCase` and `AuthorizationIntegrationTestCase`.

**Class: `AuthenticationTestCase` - Auth Methods**
- `test_password_login_staff_roles` - Staff login flow
- `test_password_login_blocked_for_users` - User auth method
- `test_magic_link_login` - Magic link authentication
- `test_magic_link_request_users_only` - Magic link restrictions
- `test_magic_link_blocked_for_staff` - Staff role restrictions
- `test_logout_functionality` - Token invalidation
- `test_auth_method_check` - Auth method validation
- `test_authentication_strategy_consistency` - Consistent patterns
- `test_registration_assigns_correct_auth_method` - Auto-assignment
- `test_session_management` - Session handling
- `test_profile_access` - Profile endpoint access

**Class: `AuthorizationIntegrationTestCase` - Role-Based Access**
- `test_authentication_required_for_all_endpoints` - Auth enforcement
- `test_role_based_endpoint_access` - Role enforcement
- `test_role_based_permissions_tickets` - Ticket permissions
- `test_section_facility_permissions` - Resource permissions
- `test_technician_access_permissions` - Technician scope

---

## Test Coverage Summary

| File | Classes | Tests | Coverage |
|------|---------|-------|----------|
| `test_apis.py` | 2 | 41 | API endpoints, permissions, bulk operations |
| `test_models.py` | 1 | 14 | Model validation, auto-numbering, constraints |
| `test_serializers.py` | 1 | 8 | Data transformation, campus hierarchy |
| `test_ticket_operations.py` | 1 | 9 | CRUD operations, assignment |
| `test_workflow.py` | 1 | 11 | End-to-end workflows, role patterns |
| `test_analytics.py` | 2 | 18 | Analytics endpoints, edge cases |
| `test_organizational.py` | 6 | 27 | Org hierarchy, escalation, dashboards |
| `test_spec_compliance.py` | 3 | 11 | Priority field, pending fields, closure |
| `test_auth_comprehensive.py` | 2 | 16 | Authentication, authorization |
| **TOTAL** | **20** | **157** | **Comprehensive** |

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
