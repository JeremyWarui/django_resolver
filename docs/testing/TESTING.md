# Testing Guide

[← Back to Index](../INDEX.md) | [← Back to README](../../README.md) | [Sample Queries →](SAMPLE_QUERIES.md)

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

**Total Test Coverage**: 166 pytest test functions across 9 test files

> **Note**: Tests use pytest with fixtures for clean, composable testing. All tests are function-based (not class-based). See [Pytest Migration Guide](../PYTEST_MIGRATION_GUIDE.md) for pytest patterns.

#### `test_apis.py` (37 tests) - API Endpoint Tests
Comprehensive REST API endpoint tests using pytest fixtures.

**Usage**: Run specific test:
```bash
pytest tickets/tests/test_apis.py::test_get_tickets -v
```

**Core API Functionality**
- `test_get_tickets(authenticated_client)` - Verify retrieving ticket list
- `test_create_ticket_via_api(authenticated_client, ticket_setup)` - Create ticket through API
- `test_get_ticket_detail(authenticated_client, ticket)` - Retrieve specific ticket
- `test_delete_ticket(authenticated_client)` - Test ticket deletion

**Role-Based Access Control**
- `test_update_ticket_status_technician(technician_factory)` - Technicians can update
- `test_update_ticket_status_admin(admin_user_factory)` - Admins can update
- `test_update_ticket_user_cant(user_factory)` - Users cannot update
- `test_assign_ticket_admin(admin_user_factory)` - Admin assignment

**Filtering & Visibility**
- `test_filter_tickets_by_status(authenticated_client)` - Filter by status
- `test_filter_tickets_by_section(authenticated_client)` - Filter by section

**Comment & Feedback**
- `test_user_can_add_comment(user_factory, ticket)` - Comment creation
- `test_feedback_on_unresolved_ticket(ticket)` - Feedback constraints
- `test_comment_on_closed_ticket(closed_ticket)` - Comments on closed

**Status Transitions**
- `test_ticket_lifecycle_workflow(admin_user_factory)` - Full workflow
- `test_status_transition_validation(ticket)` - Invalid transitions
- `test_cannot_modify_closed_ticket(closed_ticket)` - Closed immutable

**Bulk Operations** (12+ tests)
- `test_bulk_status_update_admin_success(admin_user_factory)` - Batch updates
- `test_bulk_status_update_requires_permission(user_factory)` - Permission check
- `test_bulk_status_update_empty_list(admin_user_factory)` - Edge case handling

#### `test_models.py` (18 tests) - Model Tests
Tests for Django models to ensure proper data validation, methods, and properties. Pytest functions with model fixtures.

**Usage**: Run all model tests:
```bash
pytest tickets/tests/test_models.py -v
```

**Model Creation & Validation**
- `test_user_creation(user_factory)` - CustomUser creation
- `test_technician_creation(technician_factory)` - Technician role
- `test_section_creation(section)` - Section model
- `test_ticket_creation(ticket_factory)` - Ticket creation
- `test_comment_creation(comment_factory)` - Comment model
- `test_feedback_creation(feedback_factory)` - Feedback model

**Auto-Numbering & Fields**
- `test_ticket_auto_numbering(section, facility, user_factory)` - Auto-generated numbers
- `test_ticket_status_choices(ticket)` - Valid status options
- `test_ticket_status_after_assignment(ticket, technician_factory)` - Auto status update

**Relationships**
- `test_section_technician_relationship(section, technician_factory)` - M2M relationships
- `test_feedback_one_per_ticket_constraint(ticket)` - Unique constraint

**Audit Trail**
- `test_ticket_log_creation(ticket)` - Audit trail creation
- `test_ticket_log_on_status_change(ticket)` - Status change logging
- `test_change_assignment_creates_log(ticket, technician_factory)` - Assignment logging
- `test_change_status_sets_resolved_at_and_logs(ticket)` - Resolution tracking

#### `test_serializers.py` (8 tests) - Serializer Tests
Tests for Django REST Framework serializers. Pytest functions with model fixtures.

**Usage**: Run specific serializer test:
```bash
pytest tickets/tests/test_serializers.py::test_ticket_serializer -v
```

- `test_ticket_serializer(ticket_factory)` - TicketSerializer format
- `test_ticket_serializer_create(section, facility, user_factory)` - Ticket creation
- `test_custom_user_serializer(user_factory)` - UserSerializer format
- `test_user_create_serializer()` - User creation serialization
- `test_comment_serializer(comment_factory)` - CommentSerializer
- `test_comment_serializer_create(ticket, user_factory)` - Comment creation
- `test_feedback_serializer_create(ticket, user_factory)` - Feedback creation
- `test_section_serializer_includes_campus_context(section)` - Campus context

#### `test_ticket_operations.py` (8 tests) - Ticket Operations Tests
Tests for ticket creation, updating, and assignment workflows. Pytest functions.

**Usage**: Run all ticket operation tests:
```bash
pytest tickets/tests/test_ticket_operations.py -v
```

- `test_create_ticket_direct_orm(ticket_factory)` - Direct creation
- `test_ticket_includes_available_technicians(ticket_factory)` - Serializer fields
- `test_assign_technician_to_ticket(ticket, technician_factory)` - Assignment
- `test_cannot_assign_wrong_section_technician(ticket, technician_factory)` - Constraints
- `test_can_assign_multi_section_technician(ticket, technician_factory)` - Multi-section
- `test_get_available_technicians_for_section(section, technician_factory)` - Query
- `test_unassign_technician_from_ticket(ticket, technician_factory)` - Unassign
- `test_assign_same_technician_multiple_times(ticket, technician_factory)` - Reassign

#### `test_workflow.py` (12 tests) - End-to-End Workflow Tests
Complete workflow tests covering real-world user scenarios. Pytest functions.

**Usage**: Run specific workflow test:
```bash
pytest tickets/tests/test_workflow.py::test_complete_ticket_lifecycle -v
```

- `test_ticket_creation(section, facility, user_factory)` - Creation flow
- `test_admin_can_assign_ticket(admin_user_factory)` - Admin workflow
- `test_technician_can_update_ticket_status(technician_factory)` - Tech workflow
- `test_user_cant_update_ticket_status(user_factory)` - User permissions
- `test_technician_or_admin_add_comment_to_ticket(technician_factory)` - Comments
- `test_user_can_submit_feedback(user_factory, ticket)` - Feedback
- `test_user_cant_submit_feedback_is_not_resolved(user_factory)` - Constraints
- `test_complete_ticket_lifecycle(admin_user_factory)` - Full lifecycle
- `test_admin_workflow_vs_technician_workflow()` - Role differences
- `test_section_based_routing(ticket)` - Routing validation
- `test_admin_cant_assign_to_technician_not_in_section()` - Scope
- Plus additional workflow edge cases

#### `test_analytics.py` (23 tests) - Analytics Tests
Analytics endpoint and data aggregation tests. Pytest functions covering dashboards, metrics, and aggregations.

**Usage**: Run analytics tests with a specific dashboard:
```bash
pytest tickets/tests/test_analytics.py -k director_dashboard -v
```

**Ticket Analytics**
- `test_ticket_analytics_total_count(ticket_factory)` - Count metrics
- `test_ticket_analytics_by_status(ticket_factory)` - Status distribution
- `test_ticket_analytics_trends(ticket_factory)` - Time-based trends
- `test_analytics_ticket_filtering_by_section(ticket_factory)` - Filtering
- `test_analytics_date_range(ticket_factory)` - Date range aggregation

**Technician Analytics**
- `test_technician_analytics_workload(technician_factory)` - Workload metrics
- `test_technician_performance_metrics(technician_factory)` - Performance
- `test_technician_analytics_no_assignments(technician_factory)` - Edge cases
- `test_technician_performance_status_breakdown(technician_factory)` - Status breakdown

**Admin Analytics**
- `test_admin_analytics_access(admin_user_factory)` - Access control
- `test_admin_analytics_system_overview(admin_user_factory)` - System overview

**Role-Based Dashboards**
- `test_director_dashboard(director_factory)` - Director view
- `test_director_dashboard_escalation_trends(director_factory)` - Escalations
- `test_director_dashboard_top_technicians(director_factory)` - Technician ranking
- `test_director_dashboard_facility_metrics(director_factory)` - Facilities
- `test_director_dashboard_section_metrics(director_factory)` - Sections
- `test_hod_dashboard(hod_factory)` - HOD view
- `test_hod_dashboard_department_performance(hod_factory)` - Dept performance
- `test_section_head_dashboard(section_head_factory)` - Section head view

**Edge Cases**
- `test_analytics_empty_dataset()` - Empty data handling
- `test_director_dashboard_facilities_sorted(director_factory)` - Sorting
- `test_director_dashboard_sections_sorted(director_factory)` - Sorting

#### `test_organizational.py` (27 tests) - Organizational Hierarchy & Access Control
Comprehensive tests for organizational hierarchy, role-based access, escalation, and dashboards. Pytest functions.

**Usage**: Run all organizational tests:
```bash
pytest tickets/tests/test_organizational.py -v
```

**Organizational Structure**
- `test_organizational_structure_created(organization, campus, department, section)` - Hierarchy
- `test_director_access_all_tickets(director_factory)` - Director scope
- `test_hod_campus_scoped_access(hod_factory)` - HOD scope
- `test_section_head_department_scoped_access(section_head_factory)` - Head scope
- `test_technician_section_scoped_access(technician_factory)` - Tech scope

**Escalation Workflows**
- `test_escalation_to_section_head(escalation_setup)` - Level 1 escalation
- `test_escalation_to_hod(escalation_setup)` - Level 2 escalation
- `test_cannot_escalate_beyond_hod(escalation_setup)` - Max level check
- `test_escalate_ticket(escalation_setup)` - Manual escalation
- `test_escalate_ticket_manual_endpoint(escalation_setup)` - Endpoint
- `test_auto_escalation_processing(escalation_setup)` - Auto escalation

**API & Scope Validation**
- `test_create_ticket_with_proper_scope(section, facility, user_factory)` - Creation
- `test_create_ticket_exceeds_scope(section, facility, user_factory)` - Scope check
- `test_assign_ticket_with_proper_validation(ticket, section_head_factory)` - Assignment
- `test_assign_ticket_invalid_technician(ticket, user_factory)` - Invalid assignment
- `test_get_accessible_tickets_respects_scope(ticket, user_factory)` - Visibility
- `test_organizational_ticket_list_endpoint(ticket, user_factory)` - List endpoint
- `test_assignable_users_endpoint(user_factory)` - Technicians list
- `test_organizational_analytics_endpoint(director_factory)` - Analytics

**Dashboards & Analytics**
- `test_director_dashboard(director_factory)` - Director dashboard
- `test_director_dashboard_aggregates_metrics(director_factory)` - Metrics
- `test_hod_dashboard(hod_factory)` - HOD dashboard
- `test_hod_dashboard_campus_scoped(hod_factory)` - Campus scope
- `test_section_head_dashboard(section_head_factory)` - Section head view
- `test_dashboard_sla_compliance_calculation(ticket_factory)` - SLA metrics
- `test_escalation_trends(ticket_factory)` - Escalation trends
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
| `test_organizational.py` | - | 27 | Org hierarchy, escalation, dashboards |
| `test_spec_compliance.py` | - | 19 | Priority field, pending fields, compliance |
| `test_auth_comprehensive.py` | - | 14 | Authentication, authorization |
| **TOTAL** | **pytest functions** | **166** | **Comprehensive** |

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

# Run specific test function
pytest tickets/tests/test_apis.py::test_get_tickets

# Run tests matching pattern
pytest tickets/tests/ -k "comment"

# Run with short traceback
pytest tickets/tests/ --tb=short

# Reuse database (faster for repeated runs)
pytest tickets/tests/ --reuse-db
```

## Test Execution Details

### Using pytest Fixtures

Tests use pytest fixtures defined in `tickets/tests/conftest.py`. Common fixtures include:

| Fixture | Returns | Usage |
|---------|---------|-------|
| `user` | CustomUser | Regular user role |
| `admin_user` | CustomUser | Admin user role |
| `technician` | CustomUser | Technician role |
| `authenticated_client` | APIClient | Pre-authenticated test client |
| `organization` | Organization | Test organization |
| `section` | Section | Test section |
| `department` | Department | Test department |
| `facility` | Facility | Test facility |
| `ticket` | Ticket | Sample ticket |

### Using Fixtures in Tests

```python
import pytest

@pytest.mark.django_db
def test_get_tickets(authenticated_client, ticket):
    """Test getting tickets with authenticated client"""
    response = authenticated_client.get('/api/tickets/')
    assert response.status_code == 200
    assert any(t['id'] == ticket.id for t in response.json()['results'])

@pytest.mark.django_db
def test_admin_can_close_ticket(admin_user, ticket):
    """Test admin ticket closure"""
    ticket.status = 'resolved'
    ticket.save()
    
    client = Client()
    client.force_login(admin_user)
    
    # Admin can close resolved ticket
    assert ticket.status == 'resolved'
```

### pytest Fixtures in conftest.py

Check `tickets/tests/conftest.py` for available fixtures and their definitions. Key patterns:

- `@pytest.fixture`: Function-level fixtures
- `@pytest.fixture(scope="session")`: Session-level fixtures (faster setup)
- Use lowercase fixture names for pytest convention
- Fixtures are automatically injected into test functions by name

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
