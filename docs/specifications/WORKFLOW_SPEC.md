# Ticket Management System Workflow - REVISED (May 2026)

[← Back to Index](../INDEX.md) | [Compliance Audit →](../compliance/AUDIT_STATUS.md)

**This document clarifies and updates the original workflow specification to align with implementation decisions.**

---

## 1. Organisational Structure

The system follows a hierarchical structure:

```
Campus  (root entity — no Organization above it)
  └── CampusDepartment  (Campus + Department + HOD)
        └── Section  (CampusDepartment + SectionType + HOS)
              ├── TechnicianSection  (M2M: Technician ↔ Section)
              └── Ticket
```

`Department` is a **global** entity (not owned by any campus). `CampusDepartment` is the join table that binds a Department to a specific Campus and records its Head of Department.

### Rules:

* A **Section belongs to a CampusDepartment** (which links a Campus and a Department)
* A **CampusDepartment belongs to a Campus**
* A **User belongs to a Campus** (`primary_campus`) and may have a `primary_department`
* **Technician MUST be linked to one or more sections** (via `TechnicianSection` M2M)
* A **Ticket must belong to a Section**

---

## 1.1 Organizational Scope & Ticket Placement (ARCHITECTURAL)

### Ticket Placement: Primary Key-Based (NOT Name-Based)

**Principle**: Tickets are deterministically placed using **Section ID** (primary key), not section name.

#### Why This Matters:

Multiple sections can share the same name across different campuses:
```
Campus NRB → CampusDepartment NRB+ICT → Section "ICT Support" (ID=1)
Campus MSA → CampusDepartment MSA+ICT → Section "ICT Support" (ID=5)
```

These are **two different sections** with different IDs. Naming collisions cause **no ambiguity**.

### Ticket Creation Flow (Catalogue-Based):

1. **User authenticates** with organizational context
   - System knows: `User.primary_campus = NRB`

2. **User selects Department and ServiceItem** when creating ticket
   - Request: `{ department_id, service_item_id, title, description }`

3. **System auto-resolves org structure**
   - `user.primary_campus` + `department_id` → finds `CampusDepartment`
   - `service_item → category → section_type` → finds the correct `Section`
   - `ticket.section_id = N` (deterministic FK to specific section)

4. **Response includes resolved context**
   - `{ ticket, campus_department, section, eligible_technicians }`

### Rules (ENFORCED):

✅ Tickets created ONLY in sections the user can access (FK validation)  
✅ Only sections within user's campus are eligible (business logic filtering)  
✅ Ticket-to-campus mapping is deterministic (derived from section FK chain)  
✅ No manual campus assignment needed (automatically derived)

---

## 2. User Roles (REVISED - Clarification)

### The 6 Roles:

| Role | Original Name | Responsibilities | Org Scope |
|------|--------------|------------------|-----------|
| **user** | Requester | Creates tickets, views own tickets, confirms/rejects resolution, closes own tickets | Own tickets only |
| **technician** | Officer/Technician | Works on assigned tickets, updates progress, marks resolved/pending, can escalate | Sections (via TechnicianSection) |
| **head_of_section** | Supervisor | Assigns tickets to technicians, monitors section-level tickets, receives escalation alerts, acts on PENDING tickets | Own section |
| **hod** | Head of Department | Monitors department performance per campus, receives escalations, resolves bottlenecks | Own CampusDepartment |
| **manager** | Manager | **Analytics & Reports ONLY** — no direct ticket list/detail access | Own department across all campuses |
| **admin** | System Admin | Full system access, configuration, migrations | All (system-wide) |

### KEY CLARIFICATION: Supervisor = Section Head

**Original Spec**: Used term "Supervisor"  
**Implementation**: Use role name `head_of_section`  
These are semantically identical — `head_of_section` IS the supervisor role.

### Manager Role — ANALYTICS ONLY

**Original Spec Implied**: Manager (formerly "Director") has "global visibility across all campuses"  
**Clarification**: Manager should NOT view individual tickets directly. Instead:
- Manager accesses **dashboard/analytics endpoints only**
- Manager sees **metrics, trends, SLA compliance, technician performance**
- Manager does NOT browse individual tickets

**Manager does NOT see:**
- Individual ticket details
- Ticket status listings
- Assigned technicians (operational detail)

**Manager sees:**
- Department-wide analytics across all campuses
- SLA compliance reports
- Escalation trends
- Technician productivity metrics

> **Note**: There is NO "director" role. The `manager` role fulfils the strategic oversight function previously attributed to "director" in older documentation.

---

## 3. Ticket Lifecycle

### States:

```
OPEN → ASSIGNED → IN_PROGRESS → RESOLVED → CLOSED
              ↓                      ↑
              └──→ PENDING ──────────┘

pending_approval → (approve) → open
pending_approval → (reject)  → rejected

ESCALATED: Parallel flag (escalation_level tracks this)
```

### State Definitions:

* **OPEN**: Ticket created, awaiting assignment
* **ASSIGNED**: Assigned to technician
* **IN_PROGRESS**: Work is actively ongoing
* **PENDING**: Work blocked due to external dependency (material, approval, etc.)
* **RESOLVED**: Work completed, awaiting user confirmation
* **CLOSED**: User confirms resolution or admin closes
* **PENDING_APPROVAL**: Ticket requires approval (when `service_item.requires_approval = True`)
* **REJECTED**: Ticket rejected during approval flow

---

## 4. Workflow Process

### Step 1: Ticket Creation

User provides:
* Title
* Description
* Department (ID)
* ServiceItem (ID)

System:
* Resolves `CampusDepartment` from `user.primary_campus` + `department_id`
* Resolves `Section` from `service_item → category → section_type`
* Sets `due_date` from SLA cascade: `service_item.sla_hours` → `section_type.default_sla_hours` → 24h fallback
* Status → OPEN (or PENDING_APPROVAL if `service_item.requires_approval = True`)
* **Priority → LOW** (default)

---

### Step 2: Assignment

Section Head:
* Views OPEN tickets in their Section
* Assigns to Technician (must be in `TechnicianSection` for this section)

System:
* Status → ASSIGNED
* Records `assigned_at` timestamp (escalation clock starts here)

---

### Step 3: Work Execution

Technician:
* Starts work → IN_PROGRESS
* Updates progress as needed

---

### Step 4: Pending (Blocked Work)

Technician may mark ticket as PENDING when work cannot proceed.

#### Requirements (Enforced):

* **MUST select a Pending Reason** from defined list
* **MUST provide a Pending Comment** (detailed explanation)

#### System Actions:

* Status → PENDING
* `pending_reason` = selected reason
* `pending_comment` = detailed comment
* Notify Section Head (via system)
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

### Step 7: User Confirmation

User (Requester):
* Reviews outcome
* **Can close their own ticket** (user closure enabled)

Outcomes:
* Accept → CLOSED (user closes own ticket)
* Reject → IN_PROGRESS (ticket reopened)

User may:
* Provide feedback
* Provide rating (1–5 stars)

---

## 5. Priority Management

### Priority Levels:

```
LOW (default) → MEDIUM (first escalation) → HIGH (second escalation) → CRITICAL (>72h)
```

### Priority Rules:

**Initial Priority**: `LOW` (default when ticket created)

**On First Escalation** (T+48h from `assigned_at`):
* Priority → `MEDIUM`
* Escalation Level → 1 (Section Head notified)

**On Second Escalation** (T+72h, 24h after first):
* Priority → `HIGH`
* Escalation Level → 2 (HOD notified)

**After 72 Hours Without Resolution**:
* Priority → `CRITICAL` (automatic, regardless of escalation level)

### Priority Usage:

* **Filtering**: `GET /api/tickets/?priority=high`
* **Sorting**: Default sort by `-priority, -created_at` (high priority first)
* **SLA thresholds**: Based on priority

---

## 6. Escalation Rules (SLA)

### Timeline (measured from `assigned_at`, NOT `created_at`):

* **Unassigned tickets**: NO auto-escalation — escalation clock does not start until `assigned_at` is set

* **After 48 Hours from assignment**: Escalate to Section Head
  - Escalation Level → 1
  - Priority → MEDIUM
  - Next escalation due: T+24h more

* **After 72 Hours total** (24h after first escalation): Escalate to HOD
  - Escalation Level → 2
  - Priority → HIGH

* **After 72 Hours Total Without Resolution**: Auto-mark as CRITICAL priority

### Important:

* **PENDING does NOT pause SLA timers** — ticket continues to escalate
* Ticket can remain PENDING indefinitely but still escalates
* Escalation and resolution are independent

---

## 7. Facility & Location Model

### Facility

* `name`
* `type`
* `section` (FK)
* `status`
* `location_details` (string)
* Optional asset fields: `purchase_date`, `warranty_expiry`, `asset_value` (visible to `hod` and above)

---

## 8. Ticket Data Requirements

Each ticket must include:

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| title | String(100) | Yes | Ticket subject |
| description | Text(500) | Yes | Ticket details |
| section | FK → Section | Yes (derived) | Resolved from service_item + user campus |
| facility | FK → Facility | Yes | Asset/location being worked on |
| service_item | FK → ServiceItem | Yes | Drives section resolution and SLA |
| form_data | JSONField | Optional | Service-specific form data |
| due_date | DateTime | Auto | Set from SLA cascade on creation |
| location_details | String(200) | Optional | Room/building specifics |
| raised_by | FK → CustomUser | Auto | Ticket creator |
| assigned_to | FK → CustomUser | Optional | Technician assigned (must be in TechnicianSection) |
| status | Choice | Yes | Current state |
| priority | Choice | Yes | LOW, MEDIUM, HIGH, CRITICAL |
| pending_reason | Choice | Conditional | Required when status=PENDING |
| pending_comment | Text(500) | Conditional | Required when status=PENDING |
| created_at | DateTime | Auto | Auto-set |
| updated_at | DateTime | Auto | Auto-updated |
| assigned_at | DateTime | Optional | Set when assigned; starts escalation clock |
| resolved_at | DateTime | Optional | Set when resolved |
| closed_at | DateTime | Optional | Set when closed |
| escalation_level | Integer (0-2) | Yes | 0=none, 1=head_of_section, 2=hod |
| escalated_to | FK → CustomUser | Optional | Who ticket escalated to |
| escalated_at | DateTime | Optional | When escalation occurred |
| escalation_reason | Text(500) | Optional | Why escalated |

---

## 9. Visibility Rules

* **Requester (user)** → own tickets only
* **Technician** → tickets in their assigned sections (via TechnicianSection)
* **Section Head** → all section tickets
* **HOD** → all CampusDepartment tickets (own campus + own department)
* **Manager** → **analytics dashboard only** (NOT individual ticket listings)
* **Admin** → full access to all data

---

## 10. Pending Reason Choices

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

* ✅ Role-based permissions enforced per spec (6 roles, no "director")
* ✅ State transitions strictly validated
* ✅ Escalation automated (hourly cron/management command)
* ✅ All actions logged to TicketLog (audit trail)
* ✅ PENDING does NOT pause SLA timers
* ✅ Priority automatically escalates with ticket level
* ✅ Escalation clock starts at `assigned_at` (not `created_at`)
* ✅ Unassigned tickets do NOT auto-escalate
* ✅ Users can close own resolved tickets
* ✅ Manager role: analytics only, no ticket access
* ✅ Pending reason + comment required when marking PENDING
* ✅ `ServiceItem.requires_approval` → ticket starts as `pending_approval`
* ✅ `due_date` set from SLA cascade on ticket creation

---

## Changes from Original Spec

| Change | Reason | Impact |
|--------|--------|--------|
| **Campus is root** (no Organization above it) | Matches actual data model | All FK chains start at Campus |
| **CampusDepartment join table** | Department is global; CampusDepartment links Campus + Department | Queries go through CampusDepartment |
| **TechnicianSection M2M** (not `sections` M2M on CustomUser) | Explicit join model | Technician scope queries via TechnicianSection |
| **Ticket placement via Section ID** (not name) | Deterministic scope enforcement | API always uses section_id parameter |
| **Catalogue-based ticket creation** | Auto-resolves org structure | `POST /api/tickets/create/` with `{ department_id, service_item_id }` |
| Supervisor = Section Head (role clarification) | Naming consistency | No code changes needed (semantic) |
| "Director" renamed to "manager" | Consistent with implementation | All references to "director" removed |
| Add Priority field | SLA tracking and user severity indication | Model field |
| Add Pending Comment field | Spec compliance — track reason + comment separately | Model field |
| Pending Reason as ENUM | Consistency and data validation | Model field |
| Manager: Analytics only | Operational vs Strategic separation | Permission classes |
| User can close own tickets | Enable core workflow step | Service layer + endpoint |
| Auto-increment priority on escalation | Better SLA tracking | Service logic |
| Auto-mark CRITICAL after 72h | Urgent escalation for long-standing tickets | Scheduler logic |
| Escalation clock from `assigned_at` | Unassigned tickets should not escalate | `assigned_at` field + service validation |

---

**This document is the definitive source of truth for the ticket management system.**  
**Updated: May 13, 2026**
