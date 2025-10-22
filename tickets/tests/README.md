# Tests for Django Ticket Resolver System

This directory contains comprehensive test suites for the Django Ticket Resolver System, covering models, serializers, API endpoints, and workflow validations.

## Test Files

### 1. `test_apis.py`

API tests using Django REST Framework's `APITestCase`. These tests verify the correct functioning of all API endpoints and their associated business logic.

#### Basic API Functionality Tests
- `test_get_tickets` - Verify retrieving ticket list
- `test_create_ticket` - Ensure tickets can be created with proper data
- `test_get_ticket_detail` - Test retrieving a specific ticket with nested comments & feedback
- `test_delete_ticket` - Test ticket deletion functionality

#### Role-Based Permission Tests
- `test_update_ticket_status_technician` - Technicians can update ticket status
- `test_update_ticket_status_admin` - Admins can update ticket status
- `test_update_ticket_user_cant` - Regular users cannot update ticket status
- `test_user_cannot_assign_ticket` - Regular users cannot assign tickets
- `test_assign_ticket_admin` - Admins can assign tickets to technicians

#### Filtering Tests
- `test_filter_tickets_by_status` - Filter tickets by different status values
- `test_filter_tickets_by_section` - Filter tickets by section

#### Comment and Feedback Tests
- `test_user_can_add_comment` - Test comment creation functionality
- `test_feedback_one_per_ticket` - Ensure only one feedback per ticket is allowed
- `test_feedback_on_unresolved_ticket` - Feedback only allowed on resolved tickets
- `test_comment_on_closed_ticket` - Comments not allowed on closed tickets

#### Workflow Tests
- `test_ticket_lifecycle_workflow` - Test full ticket lifecycle from open to resolved
- `test_changing_ticket_status` - Test status transitions for different roles
- `test_status_transition_validation` - Test validation of status transitions
- `test_valid_status_transitions` - Test various status transition scenarios
- `test_resolve_ticket_technician` - Technicians can mark tickets as resolved

#### Edge Case Tests
- `test_assign_resolved_ticket_fails` - Cannot reassign resolved tickets
- `test_invalid_data_handling` - Test handling of invalid input data
- `test_anonymous_user_cannot_create_ticket` - Anonymous users cannot create tickets
- `test_unrelated_user_cannot_comment` - Users not related to ticket cannot comment

#### Closed Status Tests
- `test_admin_can_close_resolved_ticket` - Only admins can close resolved tickets
- `test_cannot_modify_closed_ticket` - Closed tickets cannot be modified
- `test_comment_on_closed_ticket` - Closed tickets cannot receive comments

### 2. `test_models.py`

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

### 3. `test_serializers.py`

Tests for Django REST Framework serializers to ensure proper data validation and transformation.

- `test_ticket_serializer` - Test TicketSerializer data representation
- `test_comment_serializer` - Test CommentSerializer data representation
- `test_custom_user_serializer` - Test UserSerializer data representation
- `test_user_create_serializer` - Test UserSerializer create method
- `test_ticket_serializer_create` - Test ticket creation through serializer
- `test_comment_serializer_create` - Test comment creation through serializer
- `test_feedback_serializer_create` - Test feedback creation through serializer

### 4. `test_workflow.py`

End-to-end workflow tests using pytest fixtures.

- `test_ticket_creation` - Test basic ticket creation workflow
- `test_admin_can_assign_ticket` - Test admin assigning tickets to technicians
- `test_admin_cant_assign_ticket_to_technician_not_in_section` - Test section constraints
- `test_technician_can_update_ticket_status` - Test technician status update workflow
- `test_user_cant_update_ticket_status` - Test user permissions for status updates
- `test_technician_or_admin_add_comment_to_ticket` - Test commenting workflow
- `test_user_can_submit_feedback` - Test feedback submission flow
- `test_user_cant_submit_feedback_is_not_resolved` - Test feedback constraints

## Running the Tests

To run all tests:

```bash
python manage.py test tickets.tests
```

To run a specific test file:

```bash
python manage.py test tickets.tests.test_apis
```

To run a specific test class:

```bash
python manage.py test tickets.tests.test_apis.APITests
```

To run a specific test method:

```bash
python manage.py test tickets.tests.test_apis.APITests.test_get_tickets
```