# Specification Compliance Implementation Plan

**Branch**: `feature/spec-compliance-fixes`  
**Date**: March 18, 2026  
**Status**: 🔵 In Progress

---

## Overview

This document outlines the implementation of 6 critical compliance fixes required to align the Django Resolver codebase with the official ticket management workflow specification.

### Changes Scope

| Change | Complexity | Estimated Effort | Priority |
|--------|-----------|------------------|----------|
| 1. Priority Field + Auto-Escalation Logic | MEDIUM | 2-3 hours | 🔴 CRITICAL |
| 2. Pending Reasons (Enum) | LOW | 1 hour | 🟠 HIGH |
| 3. Pending Validation Logic | LOW | 1 hour | 🟠 HIGH |
| 4. Ticket Closure Endpoint (Requester) | MEDIUM | 2 hours | 🔴 CRITICAL |
| 5. Director Analytics-Only Separation | MEDIUM | 2-3 hours | 🟠 MEDIUM |
| 6. Comprehensive Test Suite | MEDIUM | 3-4 hours | 🟠 MEDIUM |
| 7. Documentation & Supervisor Role Clarity | LOW | 1 hour | 📋 LOW |

**Total Effort**: ~12-15 hours

---

## Implementation Steps

### Phase 1: Data Model Changes (Models & Migrations)

#### Step 1.1: Add Priority Field to Ticket Model

**File**: `tickets/models.py`

**Changes**:
```python
class Ticket(models.Model):
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='low'
    )
```

**Migration**: 
```bash
python manage.py makemigrations
python manage.py migrate
```

**Files to Modify**:
- [tickets/models.py](tickets/models.py) - Add field definition

---

#### Step 1.2: Add Pending Reasons as Choices

**File**: `tickets/models.py`

**Changes**:
```python
class Ticket(models.Model):
    PENDING_REASON_CHOICES = [
        ('material_shortage', 'Material Shortage'),
        ('awaiting_procurement', 'Awaiting Procurement'),
        ('awaiting_approval', 'Awaiting Approval'),
        ('vendor_dependency', 'Vendor Dependency'),
        ('access_issue', 'Access Issue'),
        ('other', 'Other'),
    ]
    
    pending_reason = models.CharField(
        max_length=30,
        choices=PENDING_REASON_CHOICES,
        blank=True,
        null=True,
    )
    
    pending_comment = models.TextField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Detailed explanation when marking ticket PENDING"
    )
```

**Migration**:
```bash
python manage.py makemigrations
python manage.py migrate
```

**Backward Compatibility**: 
- Existing `pending_reason` text values will need data migration cleanup
- New code enforces enum validation

**Files to Modify**:
- [tickets/models.py](tickets/models.py) - Update field with choices

---

#### Step 1.3: Add Priority Auto-Escalation Logic

**File**: `tickets/models.py` - `Ticket.escalate()` method

**Changes**:
```python
def escalate(self, escalated_by, reason="", is_auto_escalation=False):
    """Escalate ticket and auto-update priority"""
    escalation_paths = {
        0: self._find_section_head(),  # To section head
        1: self._find_hod(),            # To HOD (final level)
    }
    
    if self.escalation_level >= 2:
        raise ValueError("Already at maximum escalation level")
    
    next_escalation_level = self.escalation_level + 1
    escalated_to = escalation_paths.get(self.escalation_level)
    
    if not escalated_to:
        raise ValueError(f"No escalation path for level {self.escalation_level}")
    
    with transaction.atomic():
        # Update escalation
        self.escalation_level = next_escalation_level
        self.escalated_to = escalated_to
        self.escalated_at = timezone.now()
        self.escalation_reason = reason
        
        # Auto-update priority on escalation
        if next_escalation_level == 1:
            self.priority = 'medium'  # Level 1 escalation → MEDIUM
        elif next_escalation_level == 2:
            self.priority = 'high'    # Level 2 escalation → HIGH
        
        if self.status != 'escalated':
            self.status = 'escalated'
        
        self._schedule_next_escalation()
        self.save()
        
        # Log escalation
        TicketLog.objects.create(
            ticket=self,
            action=f"Escalated to {escalated_to.get_role_display()} (Priority: {self.get_priority_display()})",
            performed_by=escalated_by
        )
```

**CRITICAL 72-Hour Logic**:
```python
@property
def is_critical_overdue(self):
    """Check if ticket is overdue >72 hours without resolution"""
    if self.status in ['resolved', 'closed']:
        return False
    
    hours_since_creation = (timezone.now() - self.created_at).total_seconds() / 3600
    return hours_since_creation > 72 and self.priority != 'critical'

def check_critical_threshold(self):
    """Set priority to CRITICAL if >72 hours without resolution"""
    if self.is_critical_overdue:
        self.priority = 'critical'
        self.save()
        TicketLog.objects.create(
            ticket=self,
            action="Priority set to CRITICAL (>72 hours)",
            performed_by=None
        )
```

**Integration Point**:
- Call `check_critical_threshold()` in management command or scheduled job

**Files to Modify**:
- [tickets/models.py](tickets/models.py) - Update `escalate()` method and add property

---

### Phase 2: API Layer Updates (Serializers, Views, Services)

#### Step 2.1: Update Serializers with Priority & Pending Fields

**File**: `tickets/serializers.py`

**Changes**:
```python
class TicketSerializer(serializers.ModelSerializer):
    pending_reason_display = serializers.SerializerMethodField(read_only=True)
    priority_display = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Ticket
        fields = [
            # ... existing fields ...
            "priority",
            "priority_display",
            "pending_reason",
            "pending_reason_display",
            "pending_comment",
        ]
    
    def get_pending_reason_display(self, obj):
        return obj.get_pending_reason_display() if obj.pending_reason else None
    
    def get_priority_display(self, obj):
        return obj.get_priority_display()
```

**Files to Modify**:
- [tickets/serializers.py](tickets/serializers.py)

---

#### Step 2.2: Add Pending Validation in Service Layer

**File**: `tickets/api/services/services.py`

**Changes**:
```python
@staticmethod
def update_ticket_status(
    ticket: Ticket,
    new_status: str,
    updated_by: CustomUser,
    notes: Optional[str] = None,
    pending_reason: Optional[str] = None,
    pending_comment: Optional[str] = None
) -> Ticket:
    """Update ticket status with validation"""
    
    old_status = ticket.status
    
    # Validate status transition
    is_valid, error_msg = validate_status_transition(old_status, new_status, updated_by.role)
    if not is_valid:
        raise DRFValidationError(error_msg)
    
    # ✅ NEW: Validate PENDING fields are provided
    if new_status == 'pending':
        if not pending_reason:
            raise DRFValidationError(
                "pending_reason is required when marking ticket PENDING"
            )
        if not pending_comment:
            raise DRFValidationError(
                "pending_comment is required when marking ticket PENDING"
            )
        
        # Validate reason is valid choice
        valid_reasons = dict(Ticket.PENDING_REASON_CHOICES).keys()
        if pending_reason not in valid_reasons:
            raise DRFValidationError(
                f"Invalid pending_reason. Must be one of: {', '.join(valid_reasons)}"
            )
        
        # Store pending details before status change
        ticket.pending_reason = pending_reason
        ticket.pending_comment = pending_comment
    
    # Perform status change
    with transaction.atomic():
        ticket.change_status(new_status, performed_by=updated_by)
        
        if notes:
            TicketLog.objects.create(
                ticket=ticket,
                action=f"{old_status} → {new_status}: {notes}",
                performed_by=updated_by
            )
    
    return ticket
```

**Files to Modify**:
- [tickets/api/services/services.py](tickets/api/services/services.py)

---

#### Step 2.3: Add Ticket Closure Endpoint for Requester

**File**: `tickets/api/views/views.py`

**New View Class**:
```python
class TicketCloseView(APIView):
    """Endpoint for requester (user) to close their resolved tickets"""
    
    permission_classes = [IsAuthenticated, IsWithinOrganizationalScope]
    
    def post(self, request, pk):
        """
        POST /api/tickets/{id}/close/
        
        Close a resolved ticket.
        - Requester (user role) can close only their own tickets
        - Admin/manager can close any resolved ticket
        """
        try:
            ticket = get_object_or_404(Ticket, pk=pk)
            
            # Check permission
            if request.user.role == 'user':
                if ticket.raised_by != request.user:
                    raise PermissionDenied(
                        "Only ticket raiser or admin can close this ticket"
                    )
            elif request.user.role not in ['admin', 'manager']:
                raise PermissionDenied(
                    "Only admins, managers, or ticket raiser can close tickets"
                )
            
            # Check ticket status
            if ticket.status != 'resolved':
                raise ValidationError(
                    f"Cannot close ticket in '{ticket.status}' status. "
                    "Ticket must be RESOLVED first."
                )
            
            # Close ticket
            closure_notes = request.data.get('notes', '')
            ticket.change_status('closed', performed_by=request.user)
            
            if closure_notes:
                TicketLog.objects.create(
                    ticket=ticket,
                    action=f"Closed by {request.user.get_role_display()}: {closure_notes}",
                    performed_by=request.user
                )
            
            # Return updated ticket
            serializer = TicketSerializer(ticket)
            return Response(
                {
                    'status': 'closed',
                    'ticket': serializer.data,
                    'message': 'Ticket successfully closed'
                },
                status=status.HTTP_200_OK
            )
        
        except Ticket.DoesNotExist:
            raise NotFound('Ticket not found')
        except (PermissionDenied, ValidationError) as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
```

**URL Route**: Add to `tickets/api/urls.py`
```python
path('tickets/<int:pk>/close/', TicketCloseView.as_view(), name='ticket-close'),
```

**Update Service Layer**:
```python
# tickets/api/services/services.py
@staticmethod
def close_ticket(
    ticket: Ticket,
    closed_by: CustomUser,
    closure_notes: Optional[str] = None
) -> Ticket:
    """
    Close a resolved ticket.
    
    ✅ UPDATED: Allow requester (user who created ticket) to close
    """
    # ✅ Allow requester OR admin
    if closed_by.role == 'user':
        if ticket.raised_by != closed_by:
            raise DRFPermissionDenied(
                "Only ticket raiser can close their own tickets"
            )
    elif closed_by.role not in ['admin', 'manager']:
        raise DRFPermissionDenied(
            "Only admins, managers, or ticket raiser can close tickets"
        )
    
    if ticket.status != 'resolved':
        raise DRFValidationError(
            f"Only resolved tickets can be closed. Ticket is '{ticket.status}'"
        )
    
    with transaction.atomic():
        ticket.change_status('closed', performed_by=closed_by)
        
        if closure_notes:
            TicketLog.objects.create(
                ticket=ticket,
                action=f"Closed - {closure_notes}",
                performed_by=closed_by
            )
    
    return ticket
```

**Files to Modify**:
- [tickets/api/views/views.py](tickets/api/views/views.py) - Add new view class
- [tickets/api/urls.py](tickets/api/urls.py) - Add route
- [tickets/api/services/services.py](tickets/api/services/services.py) - Update close_ticket() method

---

### Phase 3: Role & Permission Updates

#### Step 3.1: Clarify Supervisor Role Documentation

**File**: `tickets/models.py` - CustomUser model docstring

**Changes**: Add clarity that Section Head IS the supervisor
```python
class CustomUser(AbstractUser):
    """
    Enhanced user model with organizational hierarchy awareness.
    
    Roles:
    - user: Requester - creates and closes tickets, provides feedback
    - technician: Works on assigned tickets, updates progress, marks PENDING/RESOLVED
    - section_head: SUPERVISOR - manages technicians, assigns tickets, escalates to HOD
    - hod: Head of Department - final escalation recipient, dept oversight
    - director: Executive view (analytics only, no ticket management)
    - admin: System administrator - full access
    """
```

**Files to Modify**:
- [tickets/models.py](tickets/models.py) - Docstring update

---

#### Step 3.2: Restrict Director to Analytics-Only

**File**: `tickets/api/permissions.py`

**New Permission Class**:
```python
class IsDirectorAnalyticsOnly(permissions.BasePermission):
    """Directors can only access analytics, not raw ticket data"""
    
    def has_permission(self, request, view):
        if request.user.role != 'director':
            return True  # Non-directors proceed to other checks
        
        # Directors can only access analytics endpoints
        analytics_paths = ['/api/analytics/', '/api/reports/']
        return any(request.path.startswith(path) for path in analytics_paths)
    
    def has_object_permission(self, request, view, obj):
        if request.user.role == 'director':
            return False  # Directors cannot view individual tickets
        return True
```

**Update Ticket List View**:
```python
# tickets/api/views/views.py - TicketListCreateView

class TicketListCreateView(ListCreateAPIView):
    permission_classes = [IsWithinOrganizationalScope, IsAuthenticated, IsDirectorAnalyticsOnly]
    
    def get_queryset(self):
        """Filter tickets based on user's organizational scope"""
        user = self.request.user
        
        # ✅ UPDATED: Directors cannot view tickets directly
        if user.role == 'director':
            # Return empty queryset ("use analytics endpoint instead")
            return Ticket.objects.none()
        
        # ... existing logic for all other roles ...
```

**Add Director Analytics Endpoint**:
```python
# tickets/api/views/views.py

class DirectorDashboardView(APIView):
    """Analytics-only dashboard for directors"""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        if request.user.role != 'director':
            raise PermissionDenied("Only directors can access this endpoint")
        
        # Return role-specific analytics
        analytics = OrganizationalAnalytics.director_dashboard(
            organization=request.user.primary_campus.organization if request.user.primary_campus else None
        )
        
        return Response(analytics)
```

**URL Route**: Add to `tickets/api/urls.py`
```python
path('analytics/director-dashboard/', DirectorDashboardView.as_view(), name='director-dashboard'),
```

**Files to Modify**:
- [tickets/api/permissions.py](tickets/api/permissions.py) - Add IsDirectorAnalyticsOnly
- [tickets/api/views/views.py](tickets/api/views/views.py) - Update TicketListCreateView, add DirectorDashboardView
- [tickets/api/urls.py](tickets/api/urls.py) - Add route

---

### Phase 4: Management Commands & Background Tasks

#### Step 4.1: Add Critical Priority Check to Auto-Escalation

**File**: `tickets/management/commands/process_auto_escalations.py`

**Changes**:
```python
def handle(self, *args, **options):
    """Process auto-escalations AND check critical thresholds"""
    
    # ... existing escalation logic ...
    
    # ✅ NEW: Check for critical threshold tickets (>72 hours)
    self.stdout.write(self.style.HTTP_INFO('🔍 Checking critical threshold tickets...'))
    
    critical_candidates = Ticket.objects.filter(
        status__in=['open', 'assigned', 'in_progress', 'pending'],
        priority__in=['low', 'medium', 'high'],
        created_at__lt=timezone.now() - timedelta(hours=72)
    )
    
    critical_count = 0
    for ticket in critical_candidates:
        if ticket.is_critical_overdue:
            ticket.priority = 'critical'
            ticket.save()
            
            TicketLog.objects.create(
                ticket=ticket,
                action="Priority elevated to CRITICAL (>72 hours without resolution)",
                performed_by=None
            )
            critical_count += 1
    
    self.stdout.write(
        self.style.SUCCESS(f'  Escalated to CRITICAL: {critical_count}')
    )
```

**Files to Modify**:
- [tickets/management/commands/process_auto_escalations.py](tickets/management/commands/process_auto_escalations.py)

---

### Phase 5: Comprehensive Test Suite

#### Step 5.1: Priority Escalation Tests

**File**: `tickets/tests/test_priority_escalation.py` (NEW)

```python
class PriorityEscalationTestCase(TestCase):
    """Test priority auto-escalation on ticket events"""
    
    def setUp(self):
        """Create test data: org → campus → dept → section"""
        self.org = Organization.objects.create(name="Test Org", code="TEST")
        self.campus = Campus.objects.create(organization=self.org, name="Main", code="MAIN", location="City")
        self.dept = Department.objects.create(campus=self.campus, name="IT", code="IT")
        self.section = Section.objects.create(department=self.dept, name="Network", code="NET")
        
        self.user = CustomUser.objects.create_user(
            username="user1", password="pass", role='user', 
            primary_campus=self.campus, primary_department=self.dept
        )
        self.section_head = CustomUser.objects.create_user(
            username="head1", password="pass", role='section_head',
            primary_campus=self.campus, primary_department=self.dept
        )
        self.facility = Facility.objects.create(name="Server", campus=self.campus, department=self.dept)
    
    def test_priority_starts_at_low(self):
        """New ticket has priority=LOW"""
        ticket = Ticket.objects.create(
            title="Test", description="Desc",
            section=self.section, facility=self.facility,
            raised_by=self.user
        )
        self.assertEqual(ticket.priority, 'low')
    
    def test_priority_escalates_to_medium_on_level1(self):
        """Priority → MEDIUM when escalated to Section Head (Level 1)"""
        ticket = Ticket.objects.create(
            title="Test", description="Desc",
            section=self.section, facility=self.facility,
            raised_by=self.user, priority='low'
        )
        
        ticket.escalate(escalated_by=self.user, reason="Testing", is_auto_escalation=False)
        ticket.refresh_from_db()
        
        self.assertEqual(ticket.escalation_level, 1)
        self.assertEqual(ticket.priority, 'medium')
    
    def test_priority_escalates_to_high_on_level2(self):
        """Priority → HIGH when escalated to HOD (Level 2)"""
        hod = CustomUser.objects.create_user(
            username="hod1", password="pass", role='hod',
            primary_campus=self.campus, primary_department=self.dept
        )
        self.dept.head_of_department = hod
        self.dept.save()
        
        ticket = Ticket.objects.create(
            title="Test", description="Desc",
            section=self.section, facility=self.facility,
            raised_by=self.user, priority='low'
        )
        
        # First escalation (Level 0 → 1)
        ticket.escalate(escalated_by=self.user, reason="First", is_auto_escalation=False)
        self.assertEqual(ticket.priority, 'medium')
        
        # Second escalation (Level 1 → 2)
        ticket.escalate(escalated_by=self.section_head, reason="Second", is_auto_escalation=False)
        ticket.refresh_from_db()
        
        self.assertEqual(ticket.escalation_level, 2)
        self.assertEqual(ticket.priority, 'high')
    
    def test_priority_becomes_critical_after_72hours(self):
        """Priority → CRITICAL after 72 hours without resolution"""
        ticket = Ticket.objects.create(
            title="Test", description="Desc",
            section=self.section, facility=self.facility,
            raised_by=self.user, priority='low',
            created_at=timezone.now() - timedelta(hours=73)
        )
        
        self.assertTrue(ticket.is_critical_overdue)
        ticket.check_critical_threshold()
        ticket.refresh_from_db()
        
        self.assertEqual(ticket.priority, 'critical')
```

**Files to Create**:
- [tickets/tests/test_priority_escalation.py](tickets/tests/test_priority_escalation.py)

---

#### Step 5.2: Pending Validation Tests

**File**: `tickets/tests/test_pending_validation.py` (NEW)

```python
class PendingValidationTestCase(TestCase):
    """Test PENDING status validation and field requirements"""
    
    # ... setup ...
    
    def test_pending_requires_reason(self):
        """Cannot mark PENDING without pending_reason"""
        ticket = Ticket.objects.create(
            title="Test", description="Desc",
            section=self.section, facility=self.facility,
            raised_by=self.user, status='in_progress'
        )
        
        with self.assertRaises(DRFValidationError) as context:
            TicketService.update_ticket_status(
                ticket=ticket,
                new_status='pending',
                updated_by=self.technician,
                pending_reason=None,  # ← Missing
                pending_comment="Waiting for parts"
            )
        
        self.assertIn("pending_reason is required", str(context.exception))
    
    def test_pending_requires_comment(self):
        """Cannot mark PENDING without pending_comment"""
        ticket = Ticket.objects.create(
            title="Test", description="Desc",
            section=self.section, facility=self.facility,
            raised_by=self.user, status='in_progress'
        )
        
        with self.assertRaises(DRFValidationError) as context:
            TicketService.update_ticket_status(
                ticket=ticket,
                new_status='pending',
                updated_by=self.technician,
                pending_reason='material_shortage',
                pending_comment=None  # ← Missing
            )
        
        self.assertIn("pending_comment is required", str(context.exception))
    
    def test_pending_reason_must_be_valid_choice(self):
        """pending_reason must be one of defined choices"""
        ticket = Ticket.objects.create(
            title="Test", description="Desc",
            section=self.section, facility=self.facility,
            raised_by=self.user, status='in_progress'
        )
        
        with self.assertRaises(DRFValidationError) as context:
            TicketService.update_ticket_status(
                ticket=ticket,
                new_status='pending',
                updated_by=self.technician,
                pending_reason='invalid_reason',  # ← Not a valid choice
                pending_comment="Details"
            )
        
        self.assertIn("Invalid pending_reason", str(context.exception))
    
    def test_pending_with_valid_reason_and_comment(self):
        """PENDING succeeds with valid reason and comment"""
        ticket = Ticket.objects.create(
            title="Test", description="Desc",
            section=self.section, facility=self.facility,
            raised_by=self.user, status='in_progress'
        )
        
        updated = TicketService.update_ticket_status(
            ticket=ticket,
            new_status='pending',
            updated_by=self.technician,
            pending_reason='material_shortage',
            pending_comment='Need specialized parts for server'
        )
        
        self.assertEqual(updated.status, 'pending')
        self.assertEqual(updated.pending_reason, 'material_shortage')
        self.assertEqual(updated.pending_comment, 'Need specialized parts for server')
```

**Files to Create**:
- [tickets/tests/test_pending_validation.py](tickets/tests/test_pending_validation.py)

---

#### Step 5.3: Ticket Closure Tests

**File**: `tickets/tests/test_ticket_closure.py` (NEW)

```python
class TicketClosureTestCase(TestCase):
    """Test ticket closure by requester and admin"""
    
    # ... setup ...
    
    def test_requester_can_close_own_resolved_ticket(self):
        """User (requester) can close their own RESOLVED ticket"""
        ticket = Ticket.objects.create(
            title="Test", description="Desc",
            section=self.section, facility=self.facility,
            raised_by=self.user, status='resolved'
        )
        
        # Requester closes own ticket
        closed = TicketService.close_ticket(
            ticket=ticket,
            closed_by=self.user,
            closure_notes="Issue resolved"
        )
        
        self.assertEqual(closed.status, 'closed')
        self.assertIsNotNone(closed.closed_at)
    
    def test_requester_cannot_close_others_ticket(self):
        """User (requester) cannot close other user's ticket"""
        other_user = CustomUser.objects.create_user(
            username="other", password="pass", role='user',
            primary_campus=self.campus, primary_department=self.dept
        )
        ticket = Ticket.objects.create(
            title="Test", description="Desc",
            section=self.section, facility=self.facility,
            raised_by=other_user,  # ← Different user
            status='resolved'
        )
        
        with self.assertRaises(DRFPermissionDenied):
            TicketService.close_ticket(
                ticket=ticket,
                closed_by=self.user,  # ← Different from raised_by
                closure_notes="Issue resolved"
            )
    
    def test_requester_cannot_close_unresolved_ticket(self):
        """User cannot close ticket that is not RESOLVED"""
        ticket = Ticket.objects.create(
            title="Test", description="Desc",
            section=self.section, facility=self.facility,
            raised_by=self.user, status='in_progress'  # ← Not resolved
        )
        
        with self.assertRaises(DRFValidationError):
            TicketService.close_ticket(
                ticket=ticket,
                closed_by=self.user,
                closure_notes="Issue resolved"
            )
    
    def test_admin_can_close_any_resolved_ticket(self):
        """Admin can close any RESOLVED ticket"""
        admin = CustomUser.objects.create_user(
            username="admin", password="pass", role='admin',
            primary_campus=self.campus, primary_department=self.dept
        )
        ticket = Ticket.objects.create(
            title="Test", description="Desc",
            section=self.section, facility=self.facility,
            raised_by=self.user, status='resolved'
        )
        
        closed = TicketService.close_ticket(
            ticket=ticket,
            closed_by=admin,
            closure_notes="Admin closure"
        )
        
        self.assertEqual(closed.status, 'closed')
    
    def test_ticket_close_creates_log(self):
        """Closing ticket creates TicketLog entry"""
        ticket = Ticket.objects.create(
            title="Test", description="Desc",
            section=self.section, facility=self.facility,
            raised_by=self.user, status='resolved'
        )
        
        TicketService.close_ticket(
            ticket=ticket,
            closed_by=self.user,
            closure_notes="Issue resolved"
        )
        
        logs = TicketLog.objects.filter(ticket=ticket, action__icontains='closed')
        self.assertEqual(logs.count(), 1)
        self.assertIn("Issue resolved", logs.first().action)
```

**API Endpoint Tests**:
```python
class TicketCloseEndpointTestCase(APITestCase):
    """Test POST /api/tickets/{id}/close/ endpoint"""
    
    # ... setup ...
    
    def test_endpoint_closes_ticket(self):
        """POST /api/tickets/{id}/close/ closes resolved ticket"""
        ticket = Ticket.objects.create(
            title="Test", description="Desc",
            section=self.section, facility=self.facility,
            raised_by=self.user, status='resolved'
        )
        
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            f'/api/tickets/{ticket.id}/close/',
            {'notes': 'Issue fully resolved'},
            format='json'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'closed')
        
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'closed')
    
    def test_endpoint_rejects_non_owner(self):
        """Non-owner requester cannot close ticket"""
        other_user = CustomUser.objects.create_user(
            username="other", password="pass", role='user',
            primary_campus=self.campus, primary_department=self.dept
        )
        ticket = Ticket.objects.create(
            title="Test", description="Desc",
            section=self.section, facility=self.facility,
            raised_by=self.user,  # Different owner
            status='resolved'
        )
        
        self.client.force_authenticate(user=other_user)
        response = self.client.post(
            f'/api/tickets/{ticket.id}/close/',
            {'notes': 'Issue resolved'},
            format='json'
        )
        
        self.assertEqual(response.status_code, 400)
        self.assertIn("Only ticket raiser", response.data['error'])
```

**Files to Create**:
- [tickets/tests/test_ticket_closure.py](tickets/tests/test_ticket_closure.py)

---

#### Step 5.4: Director Analytics-Only Tests

**File**: `tickets/tests/test_director_role.py` (NEW)

```python
class DirectorAnalyticsOnlyTestCase(APITestCase):
    """Test director role is analytics-only, no ticket viewing"""
    
    # ... setup ...
    
    def test_director_cannot_list_tickets(self):
        """Director cannot access ticket list endpoint"""
        director = CustomUser.objects.create_user(
            username="director", password="pass", role='director',
            primary_campus=self.campus
        )
        
        self.client.force_authenticate(user=director)
        response = self.client.get('/api/tickets/', format='json')
        
        # Should return empty or 403
        if response.status_code == 200:
            self.assertEqual(len(response.data['results']), 0)  # Empty queryset
        else:
            self.assertEqual(response.status_code, 403)
    
    def test_director_cannot_view_ticket_detail(self):
        """Director cannot view individual ticket details"""
        director = CustomUser.objects.create_user(
            username="director", password="pass", role='director',
            primary_campus=self.campus
        )
        ticket = Ticket.objects.create(
            title="Test", description="Desc",
            section=self.section, facility=self.facility,
            raised_by=self.user
        )
        
        self.client.force_authenticate(user=director)
        response = self.client.get(f'/api/tickets/{ticket.id}/', format='json')
        
        self.assertEqual(response.status_code, 403)
    
    def test_director_can_access_analytics_endpoint(self):
        """Director can access analytics dashboard"""
        director = CustomUser.objects.create_user(
            username="director", password="pass", role='director',
            primary_campus=self.campus
        )
        
        self.client.force_authenticate(user=director)
        response = self.client.get('/api/analytics/director-dashboard/', format='json')
        
        self.assertEqual(response.status_code, 200)
        # Check response has analytics data (not raw ticket objects)
        self.assertIn('summary', response.data)
```

**Files to Create**:
- [tickets/tests/test_director_role.py](tickets/tests/test_director_role.py)

---

## Implementation Checklist

### Models & Database
- [ ] Add `priority` field to Ticket model (CharField with choices)
- [ ] Change `pending_reason` to CharField with PENDING_REASON_CHOICES
- [ ] Add `pending_comment` field to Ticket model
- [ ] Create and apply migrations

### Services
- [ ] Update `TicketService.update_ticket_status()` - Add pending validation
- [ ] Update `TicketService.close_ticket()` - Allow requester closure
- [ ] Add pending_reason/comment to create_ticket data dict
- [ ] Update `Ticket.escalate()` - Auto-set priority on escalation
- [ ] Add `Ticket.check_critical_threshold()` method

### Serializers
- [ ] Add priority, pending_reason_display, priority_display to TicketSerializer
- [ ] Add pending_comment field
- [ ] Update TicketListSerializer

### Views & Permissions
- [ ] Add `TicketCloseView` endpoint (POST /api/tickets/{id}/close/)
- [ ] Add `IsDirectorAnalyticsOnly` permission class
- [ ] Update TicketListCreateView to return empty for directors
- [ ] Add DirectorDashboardView (analytics-only)
- [ ] Update URL routes

### Management Commands
- [ ] Update `process_auto_escalations.py` - Check critical threshold

### Tests
- [ ] Create test_priority_escalation.py
- [ ] Create test_pending_validation.py
- [ ] Create test_ticket_closure.py
- [ ] Create test_director_role.py
- [ ] Run full test suite: `python manage.py test tickets`

### Documentation
- [ ] Update models.py docstrings (supervisor = section_head)
- [ ] Update README/ARCHITECTURE docs
- [ ] Update COMPLIANCE_AUDIT_REPORT.md with completed status

---

## Git Workflow

```bash
# Branch created
git checkout -b feature/spec-compliance-fixes

# After each phase, commit
git add .
git commit -m "Phase 1: Add priority and pending fields"
git commit -m "Phase 2: Add ticket closure and validation"
git commit -m "Phase 3: Director analytics-only separation"
git commit -m "Phase 4: Comprehensive test suite"

# Final push
git push origin feature/spec-compliance-fixes

# Create pull request for review
```

---

## Testing Strategy

```bash
# Run all tests
python manage.py test tickets

# Run specific test file
python manage.py test tickets.tests.test_priority_escalation

# Run with coverage
coverage run --source='tickets' manage.py test tickets
coverage report

# Run priority tests only
python manage.py test tickets.tests.test_priority_escalation.PriorityEscalationTestCase
```

---

## Rollback Plan

If issues arise during implementation:

1. **Migrations**: `python manage.py migrate tickets 0xxx_previous`
2. **Code**: `git checkout feature/organizational-hierarchy`
3. **Database**: Restore from backup or reconstruct test data

---

## Success Criteria

✅ All 3 CRITICAL violations fixed
✅ All 6 HIGH priority issues addressed
✅ All tests pass (100% success rate)
✅ No breaking changes to API contracts
✅ Documentation updated
✅ Code reviewed and merged

---

**Next Step**: Begin Phase 1 implementation (Priority Field + Auto-Escalation)
