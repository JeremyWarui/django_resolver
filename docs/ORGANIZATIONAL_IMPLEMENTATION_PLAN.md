# Django Resolver - Organizational Implementation Plan

## Executive Summary

This document outlines the transformation of Django Resolver from a single-organization ticket management system into a multi-tiered organizational platform supporting corporate and public-sector hierarchies. The enhancement introduces campus-based operations, departmental governance, and role-based escalation workflows while maintaining backwards compatibility.

**Target Organizational Structure:**
```
Organization (Root)
├── Campus/Branch (Geographic/Operational Division)
│   ├── Department (Functional Division)
│   │   ├── Section (Specialized Units)
│   │   │   ├── Technicians (Execution Level)
│   │   │   └── Users (Service Recipients)
│   │   └── Section Head/Maintenance Officer (Section Management)
│   └── Head of Department (Campus/Department Governance & Final Escalation)
└── Director (Strategic Analytics & Organization-wide Oversight - No Direct Ticket Handling)
```

---

## Part 1: Architecture Assessment

### Current Architecture Strengths ✅

**1. Layered Architecture Foundation**
- **Models Layer**: Clean separation of data concerns
- **Services Layer**: Business logic isolation prevents view bloat
- **Views Layer**: Request handling only - perfect for role-based expansion
- **Analytics Layer**: Separate module ready for organizational metrics

**Suitability Score: 9/10** - The existing layered architecture is exceptionally well-suited for organizational scaling.

**2. Role-Based Permission System**
```python
# Current simple roles - easily extensible
ROLE_CHOICES = [
    ("user", "User"),
    ("admin", "Admin"), 
    ("technician", "Technician"),
    ("manager", "Manager"),
]
```

**Assessment**: The permission framework in `tickets/api/permissions.py` uses Django's permission system effectively. The role-based approach can be extended to support organizational hierarchy without breaking existing functionality.

**3. Audit Trail Foundation**
The existing `TicketLog` model and atomic operations (`change_status()`, `change_assignment()`) provide an audit foundation that scales perfectly to organizational requirements.

**4. Service Layer Business Logic**
```python
# Current pattern in ticket_services.py
def validate_status_transition(old_status, new_status, user_role):
    # Business rules isolated here - perfect for org hierarchy rules
```

**Assessment**: Business logic isolation in services makes organizational rule additions clean and testable.

### Current Architecture Gaps 🔄

**1. Single-Organization Assumption**
- All data exists in a flat structure
- No geographic or departmental boundaries
- Global user access patterns

**2. Simple Section Model**
```python
class Section(models.Model):
    name = models.CharField(max_length=100, unique=True)
    # Missing: department, campus relationships
```

**3. Limited Analytics Scope**
Current analytics operate organization-wide. Need campus/department/section-level insights.

---

## Part 2: Organizational Benefits Analysis

### 1. **Real-World Alignment**

**Corporate Context:**
- **Multi-campus universities** with distinct IT, facilities, and administrative needs
- **Retail chains** with store-level operations and regional management
- **Government agencies** with branch offices and departmental hierarchies
- **Healthcare systems** with multiple facilities and specialized departments

**Benefits:**
- Data isolation and privacy between campuses/departments
- Role scoping prevents cross-campus interference
- Realistic escalation paths that mirror organizational charts
- Performance optimization through data partitioning

### 2. **Governance & Accountability**

**Current Problem**: A technician in "IT" section has implicit access to all IT tickets organization-wide.

**Organizational Solution**: 
- IT technician at Campus A only sees Campus A tickets
- Section Head can reassign within their section only
- HOD gets escalated tickets from their campus
- Director sees organization-wide analytics

### 3. **Scalability & Performance**

**Data Partitioning Benefits:**
- Queries filtered by campus/department reduce data set sizes
- Analytics scope to relevant organizational levels
- Permission checks operate on smaller data sets
- Cache strategies can be campus-specific

### 4. **Compliance & Security**

**Multi-campus Benefits:**
- Data residency requirements (campus-specific data storage)
- Role isolation prevents unauthorized access across organizational boundaries
- Audit trails track cross-organizational activities
- Analytics respect organizational privacy boundaries

---

## Part 3: Implementation Roadmap

### Phase 1: Organizational Foundation (Weeks 1-2)

**Priority**: Establish organizational hierarchy models without breaking existing functionality

#### 1.1 Create Organizational Models

**New Models Required:**

```python
# tickets/models.py additions

class Organization(models.Model):
    """Root organizational entity - corporation, university, government agency"""
    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(max_length=10, unique=True)  # e.g., "UNIV", "CORP"
    organization_type = models.CharField(max_length=50, choices=[
        ('corporate', 'Corporate'),
        ('education', 'Educational Institution'),
        ('government', 'Government Agency'),
        ('healthcare', 'Healthcare System'),
        ('other', 'Other')
    ])
    established_date = models.DateField()
    headquarters_location = models.CharField(max_length=200)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.code})"

class Campus(models.Model):
    """Geographic or operational division - campus, branch, site"""
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='campuses')
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=10)  # e.g., "MAIN", "WEST", "HQ"
    location = models.CharField(max_length=200)
    campus_type = models.CharField(max_length=50, choices=[
        ('main', 'Main Campus'),
        ('branch', 'Branch Campus'),
        ('satellite', 'Satellite Office'),
        ('remote', 'Remote Location')
    ])
    established_date = models.DateField()
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['organization', 'name']
        unique_together = [['organization', 'code']]
        verbose_name_plural = "Campuses"
    
    def __str__(self):
        return f"{self.organization.code}-{self.code}: {self.name}"

class Department(models.Model):
    """Functional division within campus - academics, operations, admin"""
    campus = models.ForeignKey(Campus, on_delete=models.CASCADE, related_name='departments')
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=10)  # e.g., "IT", "HR", "OPS"
    department_type = models.CharField(max_length=50, choices=[
        ('academic', 'Academic Department'),
        ('administrative', 'Administrative Department'),
        ('operations', 'Operations Department'),
        ('support', 'Support Services'),
        ('facilities', 'Facilities Management')
    ])
    head_of_department = models.ForeignKey(
        'CustomUser', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='managed_departments'
    )
    budget_code = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['campus', 'name']
        unique_together = [['campus', 'code']]
    
    def __str__(self):
        return f"{self.campus.code}-{self.code}: {self.name}"
```

#### 1.2 Enhanced Section Model

```python
class Section(models.Model):
    """Enhanced section model with departmental hierarchy"""
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='sections')
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10)  # e.g., "NET", "SRV", "APP"
    description = models.TextField(max_length=200, blank=True)
    section_type = models.CharField(max_length=50, choices=[
        ('technical', 'Technical Services'),
        ('facilities', 'Facilities Management'),
        ('administrative', 'Administrative Services'),
        ('support', 'Support Services')
    ])
    section_head = models.ForeignKey(
        'CustomUser', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='managed_sections'
    )
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['department', 'name']
        unique_together = [['department', 'code']]
    
    def __str__(self):
        return f"{self.department.campus.code}-{self.department.code}-{self.code}: {self.name}"
    
    @property
    def full_hierarchy_name(self):
        """Returns: ORG-CAMPUS-DEPT-SECTION"""
        return f"{self.department.campus.organization.code}-{self.department.campus.code}-{self.department.code}-{self.code}"
```

#### 1.3 Migration Strategy

**Migration File Structure:**
```python
# tickets/migrations/0002_organizational_hierarchy.py

class Migration(migrations.Migration):
    dependencies = [
        ('tickets', '0001_initial'),
    ]
    
    operations = [
        # 1. Create new organizational models
        migrations.CreateModel(name='Organization', ...),
        migrations.CreateModel(name='Campus', ...),
        migrations.CreateModel(name='Department', ...),
        
        # 2. Add relationships to existing models
        migrations.AddField(
            model_name='section',
            name='department',
            field=models.ForeignKey(..., null=True),  # Temporarily nullable
        ),
        
        # 3. Data migration function to create default org structure
        migrations.RunPython(create_default_organization),
        
        # 4. Make department field non-nullable
        migrations.AlterField(
            model_name='section',
            name='department',
            field=models.ForeignKey(..., null=False),
        ),
    ]

def create_default_organization(apps, schema_editor):
    """Create default organizational structure for existing data"""
    Organization = apps.get_model('tickets', 'Organization')
    Campus = apps.get_model('tickets', 'Campus')
    Department = apps.get_model('tickets', 'Department')
    Section = apps.get_model('tickets', 'Section')
    
    # Create default organization
    org = Organization.objects.create(
        name="Default Organization",
        code="DEFAULT",
        organization_type="other",
        established_date="2023-01-01",
        headquarters_location="Main Office"
    )
    
    # Create default campus
    campus = Campus.objects.create(
        organization=org,
        name="Default Campus",
        code="MAIN",
        location="Main Campus",
        campus_type="main",
        established_date="2023-01-01"
    )
    
    # Create default department
    department = Department.objects.create(
        campus=campus,
        name="General Operations",
        code="OPS",
        department_type="operations"
    )
    
    # Link existing sections to default department
    for section in Section.objects.all():
        section.department = department
        section.save()
```

### Phase 2: Enhanced User Roles & Permissions (Weeks 3-4)

#### 2.1 Extended Role System

```python
class CustomUser(AbstractUser):
    """Enhanced user model with organizational hierarchy awareness"""
    
    ROLE_CHOICES = [
        ("user", "User"),
        ("technician", "Technician"),
        ("section_head", "Section Head"),  # Previously maintenance_officer
        ("hod", "Head of Department"),
        ("director", "Director"),
        ("admin", "System Administrator"),  # Technical admin role
    ]
    
    role = models.CharField(max_length=15, choices=ROLE_CHOICES, default="user")
    
    # Organizational assignments
    primary_campus = models.ForeignKey(Campus, on_delete=models.CASCADE, related_name='primary_users')
    primary_department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='primary_users')
    
    # Multi-section assignment for technicians
    sections = models.ManyToManyField(Section, related_name="technicians", blank=True)
    
    # Additional user context
    employee_id = models.CharField(max_length=20, unique=True, null=True, blank=True)
    phone_number = models.CharField(max_length=15, blank=True)
    office_location = models.CharField(max_length=100, blank=True)
    
    # Permissions and capabilities
    can_assign_tickets = models.BooleanField(default=False)
    can_escalate_tickets = models.BooleanField(default=False)
    can_view_analytics = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['username']
    
    def __str__(self):
        return f"{self.username} ({self.get_role_display()}) - {self.primary_campus.code}"
    
    @property
    def organizational_scope(self):
        """Returns the scope of organizational access for this user"""
        scopes = {
            'user': 'section',
            'technician': 'section',
            'section_head': 'section',
            'hod': 'department',
            'director': 'organization',
            'admin': 'system'
        }
        return scopes.get(self.role, 'none')
    
    def get_accessible_campuses(self):
        """Returns campuses this user can access based on role"""
        if self.role == 'director':
            return Campus.objects.filter(organization=self.primary_campus.organization)
        elif self.role == 'hod':
            return Campus.objects.filter(id=self.primary_campus.id)
        else:
            return Campus.objects.filter(id=self.primary_campus.id)
    
    def get_accessible_departments(self):
        """Returns departments this user can access"""
        accessible_campuses = self.get_accessible_campuses()
        if self.role == 'director':
            return Department.objects.filter(campus__in=accessible_campuses)
        elif self.role == 'hod':
            return Department.objects.filter(campus=self.primary_campus)
        else:
            return Department.objects.filter(id=self.primary_department.id)
```

#### 2.2 Permission Framework Enhancement

```python
# tickets/api/permissions.py enhancements

class IsWithinOrganizationalScope(BasePermission):
    """
    Ensures users can only access data within their organizational scope
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
            
        # System admins have access to everything
        if request.user.role == 'admin':
            return True
            
        # All other roles have scoped access
        return True
    
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        # System admin access
        if user.role == 'admin':
            return True
            
        # Object-specific scope checking
        if hasattr(obj, 'section'):
            return self._check_section_access(user, obj.section)
        elif hasattr(obj, 'department'):
            return self._check_department_access(user, obj.department)
        elif hasattr(obj, 'campus'):
            return self._check_campus_access(user, obj.campus)
            
        return False
    
    def _check_section_access(self, user, section):
        """Check if user has access to specific section"""
        if user.role == 'director':
            return section.department.campus.organization == user.primary_campus.organization
        elif user.role == 'hod':
            return section.department.campus == user.primary_campus
        elif user.role == 'section_head':
            return section.department == user.primary_department
        elif user.role in ['technician', 'user']:
            return section.department == user.primary_department
        return False

class CanAssignTickets(BasePermission):
    """Permission for users who can assign tickets to technicians"""
    
    def has_permission(self, request, view):
        return request.user.role in ['section_head', 'hod', 'director', 'admin']

class CanEscalateTickets(BasePermission):
    """Permission for users who can escalate tickets"""
    
    def has_permission(self, request, view):
        return request.user.role in ['section_head', 'hod', 'admin']  # Directors excluded

class CanViewAnalytics(BasePermission):
    """Permission for accessing analytics endpoints"""
    
    def has_permission(self, request, view):
        return (
            request.user.can_view_analytics or 
            request.user.role in ['section_head', 'hod', 'director', 'admin']
        )
```

### Phase 3: Enhanced Ticket Model & Workflows (Weeks 5-6)

#### 3.1 Organizational-Aware Ticket Model

```python
class Ticket(models.Model):
    """Enhanced ticket model with organizational hierarchy and escalation support"""
    
    STATUS_CHOICES = [
        ("open", "Open"),
        ("assigned", "Assigned"),
        ("in_progress", "In Progress"),
        ("pending", "Pending"),
        ("resolved", "Resolved"),
        ("closed", "Closed"),
        ("escalated", "Escalated"),  # New status
    ]
    
    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("normal", "Normal"), 
        ("high", "High"),
        ("urgent", "Urgent"),
        ("critical", "Critical"),
    ]
    
    # Core ticket information
    ticket_no = models.CharField(max_length=15, unique=True, editable=False)  # Extended for org codes
    title = models.CharField(max_length=100)
    description = models.TextField(max_length=500)  # Extended description
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="normal")
    
    # Organizational context
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name='tickets')
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name='tickets')
    
    # User relationships
    raised_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="raised_tickets")
    assigned_to = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, blank=True, null=True,
        related_name="assigned_tickets"
    )
    
    # Status and lifecycle
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True, editable=False)
    closed_at = models.DateTimeField(null=True, blank=True, editable=False)
    
    # Escalation tracking
    escalation_level = models.IntegerField(default=0)  # 0=none, 1=section_head, 2=hod (max level)
    escalated_to = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="escalated_tickets"
    )
    escalated_at = models.DateTimeField(null=True, blank=True)
    escalation_reason = models.TextField(max_length=500, blank=True)
    
    # Additional context
    pending_reason = models.TextField(max_length=500, blank=True, null=True)
    location_details = models.CharField(max_length=200, blank=True)  # Room, building, etc.
    estimated_resolution_hours = models.IntegerField(null=True, blank=True)
    actual_resolution_hours = models.IntegerField(null=True, blank=True, editable=False)
    
    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['status', 'section', '-updated_at'], name='ticket_section_status_idx'),
            models.Index(fields=['assigned_to', 'status'], name='ticket_assignment_idx'),
            models.Index(fields=['escalation_level', '-escalated_at'], name='ticket_escalation_idx'),
            models.Index(fields=['priority', '-created_at'], name='ticket_priority_idx'),
        ]
    
    def save(self, *args, **kwargs):
        """Enhanced save with organizational ticket numbering"""
        if not self.ticket_no:
            # Generate ticket number: ORG-CAP-DEPT-XXXXXX
            org_code = self.section.department.campus.organization.code
            campus_code = self.section.department.campus.code
            dept_code = self.section.department.code
            
            # Get next sequence number for this department
            last_ticket = Ticket.objects.filter(
                section__department=self.section.department
            ).order_by('-id').first()
            
            next_id = 1 if not last_ticket else (last_ticket.id % 999999) + 1
            self.ticket_no = f"{org_code}-{campus_code}-{dept_code}-{next_id:06d}"
        
        # Auto-set closure timestamp
        if self.status == 'closed' and not self.closed_at:
            self.closed_at = timezone.now()
            
        super().save(*args, **kwargs)
    
    def escalate(self, escalated_by, reason=""):
        """Escalate ticket to next organizational level (max: HOD)"""
        from django.db import transaction
        
        escalation_paths = {
            0: self._find_section_head(),      # To section head
            1: self._find_hod(),               # To HOD (final level)
        }
        
        # Check if already at maximum escalation level
        if self.escalation_level >= 2:
            raise ValueError("Ticket is already at maximum escalation level (HOD)")
        
        next_escalation_level = self.escalation_level + 1
        escalated_to = escalation_paths.get(self.escalation_level)
        
        if not escalated_to:
            raise ValueError(f"No escalation path available for level {self.escalation_level}")
        
        with transaction.atomic():
            self.escalation_level = next_escalation_level
            self.escalated_to = escalated_to
            self.escalated_at = timezone.now()
            self.escalation_reason = reason
            if self.status != 'escalated':
                self.status = 'escalated'
            
            self.save()
            
            # Create audit log
            TicketLog.objects.create(
                ticket=self,
                action=f"Ticket escalated to {escalated_to.get_role_display()}: {escalated_to.username}",
                performed_by=escalated_by
            )
    
    def _find_section_head(self):
        """Find section head for escalation"""
        return self.section.section_head
    
    def _find_hod(self):
        """Find HOD for escalation"""
        return self.section.department.head_of_department
    
    def _find_director(self):
        """Directors are not part of escalation chain - method kept for reference only"""
        # Directors only access analytics, not individual tickets
        # This method should not be called in normal escalation flow
        return None
    
    @property
    def is_overdue(self):
        """Check if ticket is overdue based on organizational SLA"""
        if self.status in ['resolved', 'closed']:
            return False
            
        # SLA hours based on priority
        sla_hours = {
            'critical': 4,
            'urgent': 24, 
            'high': 48,
            'normal': 72,
            'low': 120
        }
        
        hours_since_creation = (timezone.now() - self.created_at).total_seconds() / 3600
        return hours_since_creation > sla_hours.get(self.priority, 72)
    
    @property
    def organizational_path(self):
        """Return full organizational path"""
        return (
            f"{self.section.department.campus.organization.name} > "
            f"{self.section.department.campus.name} > "
            f"{self.section.department.name} > "
            f"{self.section.name}"
        )
```

#### 3.2 Enhanced Facility Model

```python
class Facility(models.Model):
    """Enhanced facility model with organizational context"""
    
    FACILITY_CHOICES = [
        ("building", "Building"),
        ("ict", "ICT Equipment"),
        ("laundry", "Laundry Equipment"), 
        ("kitchen", "Kitchen Equipment"),
        ("residential", "Residential"),
        ("laboratory", "Laboratory"),
        ("classroom", "Classroom"),
        ("office", "Office Space"),
        ("vehicle", "Vehicle"),
        ("infrastructure", "Infrastructure"),
    ]
    
    name = models.CharField(max_length=100)
    facility_code = models.CharField(max_length=20, unique=True)
    type = models.CharField(max_length=50, choices=FACILITY_CHOICES)
    
    # Organizational location
    campus = models.ForeignKey(Campus, on_delete=models.CASCADE, related_name='facilities')
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='facilities')
    
    # Physical details
    location = models.CharField(max_length=100)  # Building, floor, room
    status = models.CharField(max_length=50, default="active", choices=[
        ('active', 'Active'),
        ('maintenance', 'Under Maintenance'),
        ('inactive', 'Inactive'),
        ('decommissioned', 'Decommissioned')
    ])
    
    # Asset management
    purchase_date = models.DateField(null=True, blank=True)
    warranty_expiry = models.DateField(null=True, blank=True) 
    asset_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    class Meta:
        ordering = ['campus', 'name']
        unique_together = [['campus', 'facility_code']]
        verbose_name_plural = "Facilities"
    
    def __str__(self):
        return f"{self.campus.code}-{self.facility_code}: {self.name}"
```

### Phase 4: Service Layer Enhancements (Weeks 7-8)

#### 4.1 Enhanced Ticket Services

```python
# tickets/api/services/ticket_services.py enhancements

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from tickets.models import Ticket, CustomUser, TicketLog

class OrganizationalTicketService:
    """Service for handling organizational ticket operations"""
    
    @staticmethod
    def create_ticket(user, ticket_data):
        """Create ticket with organizational validation"""
        
        # Validate user can create tickets in this section
        section = ticket_data['section']
        if not OrganizationalTicketService._can_user_access_section(user, section):
            raise PermissionDenied("User cannot create tickets in this section")
        
        # Validate facility belongs to section's department
        facility = ticket_data['facility']
        if facility.department != section.department:
            raise ValidationError("Facility must belong to section's department")
        
        # Create ticket with organizational context
        ticket = Ticket.objects.create(
            title=ticket_data['title'],
            description=ticket_data['description'],
            section=section,
            facility=facility,
            raised_by=user,
            priority=ticket_data.get('priority', 'normal'),
            location_details=ticket_data.get('location_details', ''),
            estimated_resolution_hours=ticket_data.get('estimated_resolution_hours')
        )
        
        # Create initial log
        TicketLog.objects.create(
            ticket=ticket,
            action=f"Ticket created in {ticket.organizational_path}",
            performed_by=user
        )
        
        # Auto-notify section head
        OrganizationalTicketService._notify_ticket_creation(ticket)
        
        return ticket
    
    @staticmethod
    def assign_ticket(ticket, assigned_to, assigned_by):
        """Assign ticket with organizational validation"""
        
        # Validate assigner has permission
        if not OrganizationalTicketService._can_assign_tickets(assigned_by):
            raise PermissionDenied("User cannot assign tickets")
        
        # Validate assignee can work in this section
        if not OrganizationalTicketService._can_user_work_in_section(assigned_to, ticket.section):
            raise PermissionDenied("Technician cannot work in this section")
        
        # Validate organizational scope
        if not OrganizationalTicketService._users_in_same_scope(assigned_by, assigned_to):
            raise PermissionDenied("Cannot assign across organizational boundaries")
        
        # Perform assignment
        with transaction.atomic():
            original_assignee = ticket.assigned_to
            ticket.assigned_to = assigned_to
            ticket.status = 'assigned'
            ticket.save()
            
            # Create audit log
            TicketLog.objects.create(
                ticket=ticket,
                action=f"Ticket assigned from {original_assignee or 'unassigned'} to {assigned_to.username}",
                performed_by=assigned_by
            )
        
        return ticket
    
    @staticmethod
    def escalate_ticket(ticket, escalated_by, reason=""):
        """Escalate ticket following organizational hierarchy"""
        
        # Validate escalation permission
        if not OrganizationalTicketService._can_escalate_tickets(escalated_by):
            raise PermissionDenied("User cannot escalate tickets")
        
        # Validate escalation necessity
        if not ticket.is_overdue and escalated_by.role not in ['director', 'admin']:
            raise ValidationError("Only overdue tickets can be escalated")
        
        # Perform escalation
        ticket.escalate(escalated_by, reason)
        
        # Notify escalated recipient
        OrganizationalTicketService._notify_escalation(ticket)
        
        return ticket
    
    @staticmethod
    def close_ticket(ticket, closed_by, resolution_notes=""):
        """Close ticket with organizational validation"""
        
        # Only ticket raiser or admin roles can close
        if (ticket.raised_by != closed_by and 
            closed_by.role not in ['director', 'admin']):
            raise PermissionDenied("Only ticket raiser or admin can close tickets")
        
        # Validate resolution state
        if ticket.status != 'resolved':
            raise ValidationError("Ticket must be resolved before closing")
        
        # Perform closure
        with transaction.atomic():
            ticket.status = 'closed'
            ticket.closed_at = timezone.now()
            
            # Calculate actual resolution time
            if ticket.resolved_at:
                resolution_time = ticket.closed_at - ticket.created_at
                ticket.actual_resolution_hours = int(resolution_time.total_seconds() / 3600)
            
            ticket.save()
            
            # Create audit log
            TicketLog.objects.create(
                ticket=ticket,
                action=f"Ticket closed by {closed_by.username}. Notes: {resolution_notes}",
                performed_by=closed_by
            )
        
        return ticket
    
    @staticmethod
    def get_accessible_tickets(user):
        """Get tickets accessible to user based on organizational role"""
        
        if user.role == 'admin':
            return Ticket.objects.all()
        elif user.role == 'director':
            # Directors only access analytics, not individual tickets
            # Return empty queryset for individual ticket operations
            return Ticket.objects.none()
        elif user.role == 'hod':
            # All tickets in user's campus
            return Ticket.objects.filter(
                section__department__campus=user.primary_campus
            )
        elif user.role == 'section_head':
            # All tickets in user's department
            return Ticket.objects.filter(
                section__department=user.primary_department
            )
        elif user.role == 'technician':
            # Tickets in user's sections + assigned tickets
            return Ticket.objects.filter(
                models.Q(section__in=user.sections.all()) |
                models.Q(assigned_to=user)
            ).distinct()
        elif user.role == 'user':
            # Only own tickets
            return Ticket.objects.filter(raised_by=user)
        
        return Ticket.objects.none()
    
    @staticmethod
    def _can_user_access_section(user, section):
        """Check if user can access tickets in section"""
        if user.role == 'admin':
            return True
        elif user.role == 'director':
            return section.department.campus.organization == user.primary_campus.organization
        elif user.role == 'hod': 
            return section.department.campus == user.primary_campus
        elif user.role in ['section_head', 'technician', 'user']:
            return section.department == user.primary_department
        return False
    
    @staticmethod
    def _can_assign_tickets(user):
        """Check if user can assign tickets"""
        return user.role in ['section_head', 'hod', 'director', 'admin']
    
    @staticmethod
    def _can_escalate_tickets(user):
        """Check if user can escalate tickets"""
        return user.role in ['section_head', 'hod', 'admin']  # Directors removed from escalation
    
    @staticmethod
    def _can_user_work_in_section(user, section):
        """Check if technician can work in section"""
        if user.role != 'technician':
            return False
        return section in user.sections.all()
    
    @staticmethod
    def _users_in_same_scope(user1, user2):
        """Check if users are in same organizational scope"""
        return (
            user1.primary_campus.organization == user2.primary_campus.organization and
            user1.primary_campus == user2.primary_campus
        )
    
    @staticmethod
    def _notify_ticket_creation(ticket):
        """Send notifications for new ticket"""
        # Implementation for notification system
        pass
    
    @staticmethod
    def _notify_escalation(ticket):
        """Send notifications for escalated ticket"""
        # Implementation for notification system
        pass
```

### Phase 5: Analytics & Reporting (Weeks 9-10)

#### 5.1 Organizational Analytics

```python
# tickets/api/analytics/organizational_analytics.py

from django.db.models import Count, Q, Avg, Sum
from django.utils import timezone
from datetime import timedelta
from tickets.models import Ticket, CustomUser, Organization, Campus, Department, Section

class OrganizationalAnalytics:
    """Analytics service for organizational hierarchy"""
    
    @staticmethod
    def director_dashboard(user):
        """Organization-wide analytics for directors"""
        org = user.primary_campus.organization
        
        # Time windows
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # Base queryset for organization
        org_tickets = Ticket.objects.filter(
            section__department__campus__organization=org
        )
        
        # Campus breakdown
        campus_stats = []
        for campus in org.campuses.all():
            campus_tickets = org_tickets.filter(section__department__campus=campus)
            campus_stats.append({
                'campus_name': campus.name,
                'campus_code': campus.code,
                'total_tickets': campus_tickets.count(),
                'open_tickets': campus_tickets.filter(status__in=['open', 'assigned', 'in_progress']).count(),
                'overdue_tickets': sum(1 for t in campus_tickets if t.is_overdue),
                'escalated_tickets': campus_tickets.filter(escalation_level__gt=0).count(),
                'avg_resolution_hours': campus_tickets.filter(
                    actual_resolution_hours__isnull=False
                ).aggregate(avg=Avg('actual_resolution_hours'))['avg'] or 0
            })
        
        # Department performance
        dept_performance = []
        for campus in org.campuses.all():
            for dept in campus.departments.all():
                dept_tickets = org_tickets.filter(section__department=dept)
                if dept_tickets.exists():
                    dept_performance.append({
                        'department': f"{campus.code}-{dept.code}",
                        'total_tickets': dept_tickets.count(),
                        'resolution_rate': dept_tickets.filter(status='closed').count() / dept_tickets.count() * 100,
                        'avg_resolution_hours': dept_tickets.filter(
                            actual_resolution_hours__isnull=False
                        ).aggregate(avg=Avg('actual_resolution_hours'))['avg'] or 0,
                        'escalation_rate': dept_tickets.filter(escalation_level__gt=0).count() / dept_tickets.count() * 100
                    })
        
        # Priority distribution across organization
        priority_stats = org_tickets.values('priority').annotate(
            count=Count('id'),
            avg_resolution_hours=Avg('actual_resolution_hours')
        ).order_by('priority')
        
        return {
            'organization_overview': {
                'total_tickets': org_tickets.count(),
                'active_tickets': org_tickets.filter(status__in=['open', 'assigned', 'in_progress']).count(),
                'resolved_this_week': org_tickets.filter(resolved_at__gte=week_ago).count(),
                'overdue_count': sum(1 for t in org_tickets if t.is_overdue),
                'total_campuses': org.campuses.count(),
                'total_departments': Department.objects.filter(campus__organization=org).count(),
            },
            'campus_breakdown': campus_stats,
            'department_performance': dept_performance,
            'priority_distribution': list(priority_stats),
            'escalation_trends': OrganizationalAnalytics._get_escalation_trends(org_tickets),
            'technician_workload': OrganizationalAnalytics._get_technician_workload(org)
        }
    
    @staticmethod
    def hod_dashboard(user):
        """Campus-level analytics for HODs"""
        campus = user.primary_campus
        
        # Base queryset for campus  
        campus_tickets = Ticket.objects.filter(section__department__campus=campus)
        
        # Department breakdown
        dept_stats = []
        for dept in campus.departments.all():
            dept_tickets = campus_tickets.filter(section__department=dept)
            dept_stats.append({
                'department_name': dept.name,
                'department_code': dept.code,
                'total_tickets': dept_tickets.count(),
                'open_tickets': dept_tickets.filter(status__in=['open', 'assigned', 'in_progress']).count(),
                'section_count': dept.sections.count(),
                'technician_count': CustomUser.objects.filter(
                    role='technician', 
                    sections__department=dept
                ).distinct().count()
            })
        
        # Section performance
        section_performance = []
        for dept in campus.departments.all():
            for section in dept.sections.all():
                section_tickets = campus_tickets.filter(section=section)
                if section_tickets.exists():
                    section_performance.append({
                        'section': f"{dept.code}-{section.code}",
                        'total_tickets': section_tickets.count(),
                        'avg_resolution_hours': section_tickets.filter(
                            actual_resolution_hours__isnull=False
                        ).aggregate(avg=Avg('actual_resolution_hours'))['avg'] or 0,
                        'technician_count': section.technicians.count()
                    })
        
        return {
            'campus_overview': {
                'total_tickets': campus_tickets.count(),
                'departments': campus.departments.count(),
                'total_technicians': CustomUser.objects.filter(
                    role='technician',
                    primary_campus=campus
                ).count(),
                'escalated_to_me': campus_tickets.filter(escalated_to=user).count()
            },
            'department_breakdown': dept_stats,
            'section_performance': section_performance,
            'recent_escalations': campus_tickets.filter(
                escalation_level__gte=1
            ).order_by('-escalated_at')[:10].values(
                'ticket_no', 'title', 'escalation_reason', 'escalated_at'
            )
        }
    
    @staticmethod
    def section_head_dashboard(user):
        """Department-level analytics for section heads"""
        department = user.primary_department
        
        # Base queryset for department
        dept_tickets = Ticket.objects.filter(section__department=department)
        
        # Section breakdown
        section_stats = []
        for section in department.sections.all():
            section_tickets = dept_tickets.filter(section=section)
            section_stats.append({
                'section_name': section.name,
                'section_code': section.code,
                'total_tickets': section_tickets.count(),
                'assigned_tickets': section_tickets.filter(assigned_to__isnull=False).count(),
                'technician_count': section.technicians.count(),
                'avg_resolution_hours': section_tickets.filter(
                    actual_resolution_hours__isnull=False
                ).aggregate(avg=Avg('actual_resolution_hours'))['avg'] or 0
            })
        
        # Technician performance in department
        technicians = CustomUser.objects.filter(
            role='technician',
            sections__department=department
        ).distinct()
        
        tech_performance = []
        for tech in technicians:
            tech_tickets = dept_tickets.filter(assigned_to=tech)
            tech_performance.append({
                'technician_name': tech.get_full_name() or tech.username,
                'assigned_tickets': tech_tickets.filter(status__in=['assigned', 'in_progress']).count(),
                'completed_tickets': tech_tickets.filter(status='closed').count(),
                'avg_resolution_hours': tech_tickets.filter(
                    actual_resolution_hours__isnull=False
                ).aggregate(avg=Avg('actual_resolution_hours'))['avg'] or 0
            })
        
        return {
            'department_overview': {
                'total_tickets': dept_tickets.count(),
                'sections': department.sections.count(),
                'total_technicians': technicians.count(),
                'pending_assignments': dept_tickets.filter(assigned_to__isnull=True).count()
            },
            'section_breakdown': section_stats,
            'technician_performance': tech_performance,
            'assignment_queue': dept_tickets.filter(
                assigned_to__isnull=True
            ).order_by('-priority', 'created_at')[:10].values(
                'ticket_no', 'title', 'priority', 'created_at'
            )
        }
    
    @staticmethod  
    def _get_escalation_trends(tickets):
        """Get escalation trends over time"""
        today = timezone.now().date()
        dates = [today - timedelta(days=i) for i in range(30)]
        
        trends = []
        for date in reversed(dates):
            day_escalations = tickets.filter(
                escalated_at__date=date
            ).count()
            trends.append({
                'date': date.isoformat(),
                'escalations': day_escalations
            })
        
        return trends
    
    @staticmethod
    def _get_technician_workload(organization):
        """Get technician workload across organization"""
        technicians = CustomUser.objects.filter(
            role='technician',
            primary_campus__organization=organization
        )
        
        workload = []
        for tech in technicians:
            active_tickets = tech.assigned_tickets.filter(
                status__in=['assigned', 'in_progress']
            ).count()
            
            workload.append({
                'technician_name': tech.get_full_name() or tech.username,
                'campus': tech.primary_campus.code,
                'department': tech.primary_department.code,
                'active_tickets': active_tickets,
                'sections': list(tech.sections.values_list('code', flat=True))
            })
        
        return workload
```

### Phase 6: API Integration & Testing (Weeks 11-12)

#### 6.1 Enhanced API Views

```python
# tickets/api/views/organizational_views.py

from rest_framework.generics import ListAPIView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from tickets.api.permissions import IsWithinOrganizationalScope
from tickets.api.services.ticket_services import OrganizationalTicketService
from tickets.api.analytics.organizational_analytics import OrganizationalAnalytics

class OrganizationalTicketListView(ListAPIView):
    """List tickets within user's organizational scope"""
    
    serializer_class = TicketListSerializer
    permission_classes = [IsAuthenticated, IsWithinOrganizationalScope]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status', 'section', 'assigned_to', 'priority', 'escalation_level']
    ordering_fields = ['created_at', 'updated_at', 'priority']
    ordering = ['-updated_at']
    
    def get_queryset(self):
        """Return tickets accessible to user based on organizational role"""
        return OrganizationalTicketService.get_accessible_tickets(self.request.user)

class AssignableUsersView(ListAPIView):
    """Get technicians that can be assigned tickets within organizational scope"""
    
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, CanAssignTickets]
    
    def get_queryset(self):
        section_id = self.request.query_params.get('section_id')
        if not section_id:
            return CustomUser.objects.none()
        
        try:
            section = Section.objects.get(id=section_id)
        except Section.DoesNotExist:
            return CustomUser.objects.none()
        
        user = self.request.user
        
        # Validate user can assign in this section
        if not OrganizationalTicketService._can_user_access_section(user, section):
            return CustomUser.objects.none()
        
        # Return technicians who can work in this section
        return CustomUser.objects.filter(
            role='technician',
            sections=section,
            is_active=True
        )

class OrganizationalAnalyticsView(APIView):
    """Analytics endpoint that returns data based on user's organizational role"""
    
    permission_classes = [IsAuthenticated, CanViewAnalytics]
    
    def get(self, request):
        user = request.user
        
        if user.role == 'director':
            # Directors get comprehensive organizational analytics
            data = OrganizationalAnalytics.director_dashboard(user)
        elif user.role == 'hod':
            data = OrganizationalAnalytics.hod_dashboard(user)
        elif user.role == 'section_head':
            data = OrganizationalAnalytics.section_head_dashboard(user)
        else:
            return Response({'error': 'Insufficient permissions'}, status=403)
        
        return Response(data)

class EscalateTicketView(APIView):
    """Endpoint for escalating tickets"""
    
    permission_classes = [IsAuthenticated, CanEscalateTickets]
    
    def post(self, request, ticket_id):
        try:
            ticket = Ticket.objects.get(id=ticket_id)
            reason = request.data.get('reason', '')
            
            # Validate user can escalate this ticket
            if not OrganizationalTicketService._can_user_access_section(request.user, ticket.section):
                return Response({'error': 'Cannot escalate tickets outside your scope'}, status=403)
            
            updated_ticket = OrganizationalTicketService.escalate_ticket(ticket, request.user, reason)
            
            return Response({
                'message': 'Ticket escalated successfully',
                'escalated_to': updated_ticket.escalated_to.username,
                'escalation_level': updated_ticket.escalation_level
            })
            
        except Ticket.DoesNotExist:
            return Response({'error': 'Ticket not found'}, status=404)
        except (PermissionDenied, ValidationError) as e:
            return Response({'error': str(e)}, status=400)
```

#### 6.2 Testing Strategy

```python
# tickets/tests/test_organizational.py

from django.test import TestCase
from tickets.tests.base import BaseTicketTestCase
from tickets.models import Organization, Campus, Department, Section, CustomUser, Ticket

class OrganizationalHierarchyTestCase(BaseTicketTestCase):
    """Test organizational hierarchy and permissions"""
    
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        
        # Create organizational structure
        cls.org = Organization.objects.create(
            name="Test University",
            code="TESTU",
            organization_type="education",
            established_date="2020-01-01",
            headquarters_location="Main Campus"
        )
        
        cls.main_campus = Campus.objects.create(
            organization=cls.org,
            name="Main Campus", 
            code="MAIN",
            location="City Center",
            campus_type="main",
            established_date="2020-01-01"
        )
        
        cls.it_department = Department.objects.create(
            campus=cls.main_campus,
            name="Information Technology",
            code="IT",
            department_type="support"
        )
        
        cls.network_section = Section.objects.create(
            department=cls.it_department,
            name="Network Services",
            code="NET",
            section_type="technical"
        )
        
        # Create users with organizational context
        cls.director = CustomUser.objects.create_user(
            username="director1",
            password="testpass123",
            role="director",
            primary_campus=cls.main_campus,
            primary_department=cls.it_department
        )
        
        cls.hod = CustomUser.objects.create_user(
            username="hod1", 
            password="testpass123",
            role="hod",
            primary_campus=cls.main_campus,
            primary_department=cls.it_department
        )
        
        cls.section_head = CustomUser.objects.create_user(
            username="section_head1",
            password="testpass123",
            role="section_head",
            primary_campus=cls.main_campus,
            primary_department=cls.it_department
        )
    
    def test_organizational_ticket_creation(self):
        """Test ticket creation with organizational context"""
        ticket = Ticket.objects.create(
            title="Network Issue",
            description="Connection problem",
            section=self.network_section,
            facility=self.facility,  # From BaseTicketTestCase
            raised_by=self.user,
            priority="high"
        )
        
        # Verify organizational ticket numbering
        self.assertIn("TESTU-MAIN-IT", ticket.ticket_no)
        self.assertEqual(ticket.organizational_path, 
                        "Test University > Main Campus > Information Technology > Network Services")
    
    def test_escalation_hierarchy(self):
        """Test ticket escalation follows organizational hierarchy"""
        # Set up hierarchy relationships
        self.network_section.section_head = self.section_head
        self.network_section.save()
        
        self.it_department.head_of_department = self.hod
        self.it_department.save()
        
        ticket = Ticket.objects.create(
            title="Critical Network Issue",
            description="Network down",
            section=self.network_section,
            facility=self.facility,
            raised_by=self.user,
            priority="critical"
        )
        
        # Test escalation to section head
        ticket.escalate(self.user, "Network completely down")
        self.assertEqual(ticket.escalated_to, self.section_head)
        self.assertEqual(ticket.escalation_level, 1)
        
        # Test escalation to HOD
        ticket.escalate(self.section_head, "Need additional resources")
        self.assertEqual(ticket.escalated_to, self.hod)
        self.assertEqual(ticket.escalation_level, 2)
    
    def test_role_based_ticket_access(self):
        """Test users can only access tickets within their organizational scope"""
        # Create ticket in network section
        network_ticket = Ticket.objects.create(
            title="Network Issue",
            description="Connection problem",
            section=self.network_section,
            facility=self.facility,
            raised_by=self.user
        )
        
        # Create another campus and department
        branch_campus = Campus.objects.create(
            organization=self.org,
            name="Branch Campus",
            code="BRANCH", 
            location="Suburb",
            campus_type="branch",
            established_date="2021-01-01"
        )
        
        hr_department = Department.objects.create(
            campus=branch_campus,
            name="Human Resources",
            code="HR",
            department_type="administrative"
        )
        
        hr_section = Section.objects.create(
            department=hr_department,
            name="HR Services", 
            code="HRS",
            section_type="administrative"
        )
        
        # Create HR ticket
        hr_ticket = Ticket.objects.create(
            title="HR Issue",
            description="Payroll problem", 
            section=hr_section,
            facility=self.facility,
            raised_by=self.user
        )
        
        # Test director can see all tickets in organization
        director_tickets = OrganizationalTicketService.get_accessible_tickets(self.director)
        self.assertIn(network_ticket, director_tickets)
        self.assertIn(hr_ticket, director_tickets)
        
        # Test HOD can only see tickets in their campus
        hod_tickets = OrganizationalTicketService.get_accessible_tickets(self.hod)  
        self.assertIn(network_ticket, hod_tickets)
        self.assertNotIn(hr_ticket, hod_tickets)
        
        # Test section head can only see tickets in their department
        section_head_tickets = OrganizationalTicketService.get_accessible_tickets(self.section_head)
        self.assertIn(network_ticket, section_head_tickets)
        self.assertNotIn(hr_ticket, section_head_tickets)

class OrganizationalAnalyticsTestCase(BaseTicketTestCase):
    """Test organizational analytics calculations"""
    
    def test_director_dashboard_metrics(self):
        """Test director dashboard returns correct organization-wide metrics"""
        # Create test data across multiple departments
        # ... test implementation
        pass
    
    def test_campus_performance_comparison(self):
        """Test campus performance metrics are calculated correctly"""
        # ... test implementation  
        pass
    
    def test_department_efficiency_metrics(self):
        """Test department efficiency calculations"""
        # ... test implementation
        pass

```

---

## Implementation Timeline

### Weeks 1-2: Foundation
- [ ] Create organizational models (Organization, Campus, Department)
- [ ] Enhance Section model with departmental relationships  
- [ ] Create forward-compatible migrations
- [ ] Update fixtures for testing

### Weeks 3-4: User & Permissions
- [ ] Extend CustomUser with organizational fields
- [ ] Implement new role system (director, hod, section_head)
- [ ] Create organizational permission classes
- [ ] Update existing permission checks

### Weeks 5-6: Ticket Enhancement  
- [ ] Enhance Ticket model with organizational context
- [ ] Implement escalation system
- [ ] Create organizational ticket numbering
- [ ] Add facility enhancements

### Weeks 7-8: Business Logic
- [ ] Update ticket services with organizational validation
- [ ] Implement assignment rules within organizational scope
- [ ] Create escalation workflows
- [ ] Add closure permission controls

### Weeks 9-10: Analytics & Reporting
- [ ] Create organizational analytics service
- [ ] Implement role-specific dashboards
- [ ] Add performance metrics by organizational level
- [ ] Create escalation trend analysis

### Weeks 11-12: Integration & Testing
- [ ] Update API endpoints for organizational scope
- [ ] Create organizational-aware views
- [ ] Implement comprehensive test suite
- [ ] Performance optimization and indexing

---

## Migration Considerations

### Data Migration Strategy
1. **Preserve existing data** - All current tickets remain accessible
2. **Default organizational structure** - Create "Default Organization > Main Campus > General Operations" 
3. **User role upgrades** - Current managers become department heads, admins remain system admins
4. **Backward compatibility** - All existing API endpoints continue functioning

### Performance Optimization
1. **Database indexes** - Add organizational hierarchy indexes
2. **Query optimization** - Filter by organizational scope early
3. **Pagination** - Maintain existing pagination patterns
4. **Caching strategy** - Cache organizational relationships

---

## Success Metrics

### Technical Metrics
- [ ] All existing tests pass after migration
- [ ] API response times remain under 200ms for typical queries  
- [ ] Database query count doesn't increase significantly
- [ ] Zero breaking changes to existing API contracts

### Functional Metrics  
- [ ] Users can only access tickets within their organizational scope
- [ ] Escalation follows correct organizational hierarchy
- [ ] Analytics reflect accurate organizational breakdowns
- [ ] Ticket assignment respects section boundaries

### Organizational Benefits
- [ ] Clear separation of campus operations
- [ ] Role-appropriate access to information
- [ ] Realistic escalation workflows
- [ ] Performance metrics at relevant organizational levels

---

This implementation plan transforms Django Resolver into a realistic organizational platform while maintaining the excellent architecture foundation you've built. The layered approach makes this enhancement manageable and maintainable.