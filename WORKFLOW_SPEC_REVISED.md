# Ticket Management System Workflow - REVISED (March 2026)

**This document clarifies and updates the original workflow specification to align with implementation decisions.**

---

## 1. Organisational Structure

The system follows a hierarchical structure:

```
Organisation
└── Campus
    └── Department (e.g. Administration, ICT)
        └── Section (e.g. Electrical, Plumbing, Network Support)
```

### Rules:

* A **Section belongs to a Department**
* A **Department belongs to a Campus**
* A **User belongs to a Campus and Department**
* A User may optionally belong to a Section
* **Technician MUST belong to a section** (one or more via M2M)
* A **Ticket must belong to a Section**

---

## 1.1 Organizational Scope & Ticket Placement (ARCHITECTURAL - NEW)

### Ticket Placement: Primary Key-Based (NOT Name-Based)

**Principle**: Tickets are deterministically placed using **Section ID** (primary key), not section name.

#### Why This Matters:

Multiple sections can share the same name across different campuses:
```
Campus MAIN → Department IT → Section "Networks" (ID=1)
Campus WEST → Department IT → Section "Networks" (ID=5)
```

These are **two different sections** with different IDs. Naming collisions cause **no ambiguity** because:

### Ticket Creation Flow:

1. **User authenticates** with organizational context (Campus + Department)
   - System knows: `User.primary_campus = MAIN`
   - System knows: `User.primary_department = IT`

2. **User selects Section** when creating ticket
   - Frontend shows: `Section ID=1, name="Networks"`
   - System stores: `ticket.section_id = 1` (NOT the name)

3. **Ticket belongs to Section #1**
   - `ticket.section_id = 1` (deterministic FK to specific section)
   - `ticket.section.department.campus_id = 1` (MAIN campus guaranteed by FK chain)

### Consequence:

- **No naming conflicts** - sections identified by ID, not name
- **No scope leakage** - user in MAIN campus cannot accidentally create ticket in WEST campus
- **Organizational hierarchy is namespace** - same section name in different campuses = different records with different IDs
- **Filters always use IDs** - `GET /api/tickets/?section_id=1` is unambiguous

### Rules (ENFORCED):

✅ Tickets created ONLY in sections the user can access (FK validation)  
✅ Only sections within user's campus are shown in selection (business logic filtering)  
✅ Ticket-to-campus mapping is deterministic (derived from section FK chain)  
✅ No manual campus assignment needed (automatically derived)

---

## 2. User Roles (REVISED - Clarification)

### The 6 Roles:

| Role | Original Name | Responsibilities | Org Scope |
|------|--------------|------------------|-----------|
| **user** | Requester | Creates tickets, views own tickets, confirms/rejects resolution, closes own tickets | Section (own tickets only) |
| **technician** | Officer/Technician | Works on assigned tickets, updates progress, marks resolved/pending, can escalate | Section (assigned + own) |
| **section_head** | **Supervisor** | Assigns tickets to technicians, monitors section-level tickets, receives 24h delay alerts, acts on PENDING tickets | Department (via Section management) |
| **hod** | Head of Department | Monitors department performance per campus, receives 48h escalations, resolves bottlenecks | Campus (department-wide) |
| **director** | Director/Admin | **Analytics & Reports ONLY** - no direct ticket management access | Organization (analytics view only) |
| **admin** | System Admin | Full system access, configuration, migrations | System (all access) |

### 🔑 **KEY CLARIFICATION: Supervisor = Section Head**

**Original Spec**: Used term "Supervisor"  
**Implementation**: Use role name `section_head` (more specific than generic "supervisor")  
**Decision**: These are semantically identical:
- Supervisor supervises a **Section** → Section Head is responsible for a **Section**
- Supervisor assigns tickets → Section Head assigns tickets to team members
- Supervisor acts on PENDING → Section Head resolves PENDING issues

> **No separate "Supervisor" role needed.** The `section_head` role IS the supervisor role.

### Director Role - ANALYTICS ONLY (REVISED)

**Original Spec Implied**: Director has "global visibility across all campuses"  
**Clarification**: Director should NOT view tickets directly. Instead:
- Director accesses **dashboard/analytics endpoints only**
- Director sees **metrics, trends, SLA compliance, technician performance**
- Director does NOT browse individual tickets
- Director role: Strategic oversight (not operational)

**Director does NOT see:**
- ❌ Individual ticket details
- ❌ Ticket status listings
- ❌ Assigned technicians (operational detail)

**Director sees:**
- ✅ Organization-wide analytics
- ✅ Department performance metrics
- ✅ SLA compliance reports
- ✅ Escalation trends
- ✅ Technician productivity metrics

---

## 3. Ticket Lifecycle

### States:

```
OPEN → ASSIGNED → IN_PROGRESS → RESOLVED → CLOSED
              ↓                      ↑
              └──→ PENDING ──────────┘

ESCALATED: Parallel flag (can occur from any active state)
```

### State Definitions:

* **OPEN**: Ticket created, awaiting assignment
* **ASSIGNED**: Assigned to technician
* **IN_PROGRESS**: Work is actively ongoing
* **PENDING**: Work blocked due to external dependency (material, approval, etc.)
* **RESOLVED**: Work completed, awaiting user confirmation
* **CLOSED**: User confirms resolution or admin closes
* **ESCALATED**: Escalation in progress (status + escalation_level = state tracking)

---

## 4. Workflow Process

### Step 1: Ticket Creation

User provides:
* Title
* Description
* Department (user's department)
* Section (responsible section)
* Facility
* Location

System:
* Assigns Campus automatically (derived from Section)
* Status → OPEN
* **Priority → LOW** (default)

---

### Step 2: Assignment

Supervisor (Section Head):
* Views OPEN tickets in their Section
* Assigns to Technician

System:
* Status → ASSIGNED

---

### Step 3: Work Execution

Technician:
* Starts work → IN_PROGRESS
* Updates progress as needed

---

### Step 4: Pending (Blocked Work) - REVISED

Technician may mark ticket as PENDING when work cannot proceed.

#### Requirements (REVISED - Now Enforced):

* **MUST select a Pending Reason** from defined list:
  - Material Shortage
  - Awaiting Procurement
  - Awaiting Approval
  - Vendor Dependency
  - Access Issue
  - Other

* **MUST provide a Pending Comment** (detailed explanation)

#### System Actions:

* Status → PENDING
* `pending_reason` = selected reason
* `pending_comment` = detailed comment
* Notify Supervisor (via system)
* Log activity in TicketLog
* **SLA timer CONTINUES running** (PENDING does NOT pause escalation)

---

### Step 5: Resume Work

Once issue is resolved (materials available, approval granted, etc.):
* Status → IN_PROGRESS

---

### Step 6: Resolution

Technician:
* Marks ticket as RESOLVED

---

### Step 7: User Confirmation - REVISED (Enabled Now)

User (Requester):
* Reviews outcome
* **Can now close their own ticket** ✅ (NEW)

Outcomes:
* Accept → CLOSED (user closes own ticket)
* Reject → IN_PROGRESS (ticket reopened)

User may:
* Provide feedback
* Provide rating (1-5 stars)

---

## 5. Priority Management - NEW FEATURE

### Priority Levels:

```
LOW (default) → MEDIUM (first escalation) → HIGH (second escalation) → CRITICAL (>72h)
```

### Priority Rules:

**Initial Priority**: `LOW` (default when ticket created)

**On First Escalation** (T+48h):
* Priority → `MEDIUM`
* Status → ESCALATED
* Escalation Level → 1 (Section Head)

**On Second Escalation** (T+72h):
* Priority → `HIGH`
* Status → ESCALATED
* Escalation Level → 2 (HOD)

**After 72 Hours Without Resolution**:
* Priority → `CRITICAL` (automatic, regardless of escalation level)
* Notify system administrators
* Mark as urgent

### Priority Usage:

* **Filtering**: `GET /api/tickets/?priority=high`
* **Sorting**: Default sort by `-priority, -created_at` (high priority first)
* **SLA thresholds**: Based on priority (future feature)

---

## 6. Escalation Rules (SLA) - REVISED

### Timeline:

* **After 24 Hours**: Notify Supervisor (section_head) - ⚠️ Advisory
* **After 48 Hours**: Escalate to Section Head
  - Status → ESCALATED
  - Escalation Level → 1
  - Priority → MEDIUM
  - Next escalation due: T+72h
  
* **After 72 Hours (24h after first escalation)**: Escalate to HOD
  - Status → ESCALATED
  - Escalation Level → 2
  - Priority → HIGH
  - Next escalation due: None (max level)

* **After 72 Hours Total**: Auto-mark as CRITICAL priority
  - Regardless of escalation level
  - Alert system admins

### Important:

* **PENDING does NOT pause SLA timers** - ticket continues to escalate
* Ticket can remain PENDING indefinitely but still escalates
* Escalation and resolution are independent

---

## 7. Facility & Location Model

### FacilityType

* name

### Facility

* name
* type
* campus
* department
* status

### Location

* (Stored as `location_details` string field for simplicity)

---

## 8. Ticket Data Requirements (REVISED - Fields Now Complete)

Each ticket must include:

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| title | String(100) | ✅ Yes | Ticket subject |
| description | Text(500) | ✅ Yes | Ticket details |
| campus | FK → Campus | ✅ Yes | Derived from section.department.campus |
| department | FK → Department | ✅ Yes | Derived from section.department |
| section | FK → Section | ✅ Yes | Where ticket belongs |
| facility | FK → Facility | ✅ Yes | Asset/location being worked on |
| location_details | String(200) | ❌ Optional | Room/building specifics |
| created_by | FK → User | ✅ Yes | Ticket creator (raised_by) |
| assigned_to | FK → User | ❌ Optional | Technician assigned |
| supervisor | *Derived* (via section.section_head) | ✅ Derived | Not stored as field |
| status | Choice | ✅ Yes | Current state |
| **priority** | Choice | ✅ Yes | LOW, MEDIUM, HIGH, CRITICAL |
| pending_reason | Choice | ❌ Optional | Only when PENDING |
| **pending_comment** | Text(500) | ❌ Optional | Only when PENDING |
| created_at | DateTime | ✅ Auto | Auto-set |
| updated_at | DateTime | ✅ Auto | Auto-updated |
| resolved_at | DateTime | ❌ Optional | Set when resolved |
| closed_at | DateTime | ❌ Optional | Set when closed |
| escalation_level | Integer (0-2) | ✅ Yes | 0=none, 1=section_head, 2=hod |
| escalated_to | FK → User | ❌ Optional | Who ticket escalated to |
| escalated_at | DateTime | ❌ Optional | When escalation occurred |
| escalation_reason | Text(500) | ❌ Optional | Why escalated |

---

## 9. Visibility Rules (REVISED - Director Changes)

* **Requester (user)** → own tickets only
* **Technician** → assigned tickets + own tickets
* **Section Head** → all section tickets
* **HOD** → all department tickets (per campus)
* **Director** → **analytics dashboard only** (NOT ticket listings)
* **Admin** → full access to all data

---

## 10. Pending Reason Choices - NEW

When ticket status = PENDING, system enforces one of:

```python
PENDING_REASON_CHOICES = [
    ('material_shortage', 'Material Shortage'),
    ('awaiting_procurement', 'Awaiting Procurement'),
    ('awaiting_approval', 'Awaiting Approval'),
    ('vendor_dependency', 'Vendor Dependency'),
    ('access_issue', 'Access Issue'),
    ('other', 'Other'),
]
```

---

## 11. System Requirements

* ✅ Role-based permissions enforced per spec
* ✅ State transitions strictly validated
* ✅ Escalation automated (hourly cron/management command)
* ✅ All actions logged to TicketLog (audit trail)
* ✅ PENDING does NOT pause SLA timers
* ✅ Priority automatically escalates with ticket level
* ✅ Users can close own resolved tickets (NEW)
* ✅ Director role: analytics only, no ticket access (NEW)
* ✅ Pending reason + comment required when marking PENDING (NEW)

---

## Changes from Original Spec

| Change | Reason | Impact |
|--------|--------|--------|
| **Ticket placement via Section ID** (not name) | Deterministic scope enforcement, prevents naming collisions | API always uses section_id parameter |
| **Organizational scope enforcement** | User in campus X → can only create tickets in sections within campus X | Frontend section selector filters by user's campus |
| Supervisor = Section Head (role clarification) | Naming consistency with implementation | No code changes needed (semantic) |
| Add Priority field | SLA tracking and user severity indication | Model migration required |
| Add Pending Comment field | Spec compliance - track reason + comment separately | Model migration required |
| Pending Reason as ENUM | Consistency and data validation | Model migration required |
| Director: Analytics only | Operational vs Strategic separation | API endpoint changes |
| User can close own tickets | Enable core workflow step | Service layer + endpoint changes |
| Auto-increment priority on escalation | Better SLA tracking | Service logic update |
| Auto-mark CRITICAL after 72h | Urgent escalation for long-standing tickets | Scheduler logic update |

---

**This document is the definitive source of truth for the ticket management system.**
**Updated: March 18, 2026**

