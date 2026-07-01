# Service Desk — Backend Gap Analysis & Implementation Plan
**Version:** 1.3 (WebSocket corrected — Django Channels replaces Socket.io; full implementation guide added)  
**Status:** Ready for review with backend team  
**Place this file at:** `/docs/BACKEND_PLAN.md` in the codebase root

---

## How to use this document

This document describes what the backend API must support for the Service Desk frontend to work correctly. It is structured as:

1. **Gap analysis** — what the existing API likely has, what is missing
2. **Endpoint specification** — every endpoint the frontend needs
3. **Data model gaps** — database changes required
4. **Auth and scoping requirements** — how the backend must enforce role scope
5. **Real-time requirements** — WebSocket event contracts
6. **Implementation priority order** — what to build first

Share this with the backend team or use it as an AI agent prompt for backend implementation.

---

## 1. Gap analysis

The following areas are most likely missing or incomplete in a typical existing API.
The backend team should audit each and mark: **EXISTS / PARTIAL / MISSING**.

### 1.1 Auth gaps

| Requirement | Status | Notes |
|-------------|--------|-------|
| POST /auth/login → returns JWT + refresh token | ? | Standard — likely exists |
| POST /auth/refresh → rotates refresh token, returns new JWT | ? | Likely exists |
| POST /auth/logout → invalidates refresh token | ? | Likely exists |
| POST /auth/switch-role → issues JWT for a different RoleAssignment | ? | Likely MISSING — new concept |
| JWT payload includes: role, campusId, deptId, sectionId, availableRoles count | ? | Likely PARTIAL — may not include scope fields |
| Multiple RoleAssignments per user | ? | Likely MISSING — most systems assume 1 role per user |

### 1.2 Ticket gaps

| Requirement | Status | Notes |
|-------------|--------|-------|
| POST /tickets — create with location + residential + asset | ? | May exist but missing location/residential fields |
| GET /tickets — list with cursor pagination + role-scoped server-side | ? | Likely has offset pagination, not cursor |
| GET /tickets — filtered by status, priority, assignee, date range | ? | Likely PARTIAL |
| PATCH /tickets/:id/assign | ? | May exist |
| PATCH /tickets/:id/status — with required progress note | ? | May exist but missing note requirement |
| POST /tickets/:id/escalate — with escalation level + reason | ? | Likely MISSING |
| PATCH /tickets/:id/escalation — HOD approve/redirect | ? | Likely MISSING |
| Ticket status: 'assigned' as distinct state (HOS assigns, tech not yet started) | ? | Likely MISSING |
| Ticket status: 'pending' as distinct state (blocked — waiting on parts, access etc.) | ? | Likely MISSING |
| POST /tickets/:id/close — user confirms resolution | ? | Likely MISSING (merged with status change) |
| POST /tickets/:id/reopen — with reason | ? | Likely MISSING |
| POST /tickets/:id/rating — star rating + comment | ? | Likely MISSING |
| GET /tickets/:id/timeline — ordered event log | ? | Likely MISSING |
| Server-side scope enforcement (JWT scope → WHERE clause) | ? | Likely MISSING — critical security requirement |
| Ticket status state machine enforcement | ? | Likely MISSING |
| Automatic ticket routing: serviceItem → section → dept → campus | ? | Likely MISSING |

### 1.3 Service structure gaps

| Requirement | Status | Notes |
|-------------|--------|-------|
| ServiceCategory with context_config JSONB field | ? | Likely MISSING — new concept |
| ServiceItem with optional context_config override | ? | Likely MISSING |
| GET /services/categories?campusId= | ? | May exist without campus scoping |
| GET /services/items/:id/context-config — resolved config (item ?? category) | ? | Likely MISSING |
| CRUD for categories and items (admin) | ? | May exist partially |

### 1.4 Analytics gaps

| Requirement | Status | Notes |
|-------------|--------|-------|
| GET /analytics/tickets/ — filterable ticket drill-down | EXISTS | TicketAnalyticsView |
| GET /analytics/technicians/ — technician performance | EXISTS | TechnicianAnalyticsView |
| GET /analytics/admin-dashboard/ — system-wide overview | EXISTS | AdminDashboardAnalyticsView |
| GET /analytics/section-head/ — HOS-scoped dashboard | EXISTS | SectionHeadDashboardView (legacy) |
| GET /analytics/hod/ — HOD-scoped dashboard | EXISTS | HODDashboardView (legacy) |
| GET /analytics/manager/ — manager-scoped dashboard | EXISTS | ManagerDashboardView (legacy) |
| GET /analytics/organizational/ — full org breakdown | MISSING | Frontend calls this; add OrganisationAnalyticsView delegating to AdminAnalytics.get_organisation_analytics() |
| GET /analytics/user/ — personal ticket stats | EXISTS | UserAnalyticsView |
| GET /analytics/departments/<pk>/ | EXISTS | DepartmentAnalyticsView |
| GET /analytics/campus-departments/<pk>/ | EXISTS | HODAnalyticsView |
| GET /analytics/sections/<pk>/ | EXISTS | HOSAnalyticsView |
| GET /analytics/technicians/me/ — self-service KPIs | EXISTS | TechnicianSelfAnalyticsView |
| GET /analytics/kpis — NOT called by frontend | NOT NEEDED | Frontend classifies analytics through role-scoped endpoints above; no separate /kpis path is called |
| GET /analytics/volume — NOT called by frontend | NOT NEEDED | Volume trend is embedded in /analytics/admin-dashboard/ organisation block |
| GET /analytics/department-breakdown — NOT called by frontend | NOT NEEDED | Covered by DepartmentAnalyticsView at /analytics/departments/<pk>/ |
| GET /analytics/technician-performance — NOT called by frontend | NOT NEEDED | Covered by TechnicianAnalyticsView |
| GET /analytics/sla-status — NOT called by frontend | NOT NEEDED | SLATrackingView.tsx classifies SLA client-side from /tickets/ due_date field |
| POST /reports/export — PDF/CSV | EXISTS | GenerateReportView at GET /reports/generate/ (Excel, not PDF/CSV) |
| Pre-computed analytics cache (5-min refresh job) | EXISTS | Django cache backend (django-redis); get_cached() wraps all analytics with 5-min TTL |

### 1.5 Real-time gaps

| Requirement | Status | Notes |
|-------------|--------|-------|
| WebSocket server | ? | **Django Channels required** — native Django ASGI WebSocket solution |
| Scoped channels: user:{userId}, section:{id}:{campus}, dept:{id}:{campus}, ticket:{id} (transient), system:{campusId} | ? | Likely MISSING or unscoped |
| Event emission on ticket lifecycle events | ? | Likely MISSING |
| SLA breach event emission (scheduled job) | ? | Likely MISSING |

### 1.6 Admin gaps

| Requirement | Status | Notes |
|-------------|--------|-------|
| CRUD: campuses, departments, sections | ? | May exist |
| CRUD: service categories + context_config editor | ? | Likely MISSING (context_config is new) |
| CRUD: service items with config override | ? | Likely MISSING |
| SLA rule builder per category + priority | ? | Likely PARTIAL |
| Workflow settings (toggles) | ? | Likely MISSING |
| Audit log — all write operations logged with actor + before/after | ? | Likely MISSING |
| RoleAssignment management — assign roles with scope | ? | Likely PARTIAL |

---

## 2. Data model changes required

### 2.1 New: RoleAssignment table

```sql
CREATE TABLE role_assignments (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role          VARCHAR(20) NOT NULL 
                CHECK (role IN ('user','technician','hos','hod','manager','admin')),
  campus_id     UUID REFERENCES campuses(id),     -- NULL for manager, admin
  department_id UUID REFERENCES departments(id),  -- NULL for user, admin
  section_id    UUID REFERENCES sections(id),     -- NULL for hod, manager, admin, user
  is_primary    BOOLEAN NOT NULL DEFAULT false,
  assigned_by   UUID REFERENCES users(id),
  assigned_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  
  -- Constraints per role
  CONSTRAINT chk_user_scope CHECK (
    role != 'user' OR (campus_id IS NOT NULL AND department_id IS NULL AND section_id IS NULL)
  ),
  CONSTRAINT chk_technician_scope CHECK (
    role != 'technician' OR (campus_id IS NOT NULL AND department_id IS NOT NULL AND section_id IS NOT NULL)
  ),
  CONSTRAINT chk_hos_scope CHECK (
    role != 'hos' OR (campus_id IS NOT NULL AND department_id IS NOT NULL AND section_id IS NOT NULL)
  ),
  CONSTRAINT chk_hod_scope CHECK (
    role != 'hod' OR (campus_id IS NOT NULL AND department_id IS NOT NULL AND section_id IS NULL)
  ),
  CONSTRAINT chk_manager_scope CHECK (
    role != 'manager' OR (campus_id IS NULL AND department_id IS NOT NULL AND section_id IS NULL)
  ),
  CONSTRAINT chk_admin_scope CHECK (
    role != 'admin' OR (campus_id IS NULL AND department_id IS NULL AND section_id IS NULL)
  )
);

CREATE UNIQUE INDEX idx_one_primary_per_user 
  ON role_assignments(user_id) WHERE is_primary = true;
```

### 2.2 Modify: tickets table

Add missing columns:

```sql
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS
  -- Status tracking
  status        VARCHAR(20) NOT NULL DEFAULT 'open'
                CHECK (status IN ('open','assigned','in_progress','pending','resolved','escalated','closed')),
  assigned_at   TIMESTAMPTZ,          -- set when status transitions to 'assigned'
  pending_reason TEXT,                -- required when status = 'pending'; cleared on resume
  
  -- Location (nullable — only for spatial services)
  building_id   UUID REFERENCES buildings(id),
  floor         VARCHAR(20),
  room          VARCHAR(50),
  area          VARCHAR(100),
  
  -- Residential (nullable — only when is_residential toggled)
  tenant_name   VARCHAR(200),
  unit_number   VARCHAR(50),
  
  -- Asset (nullable)
  asset_id      UUID REFERENCES assets(id),
  
  -- SLA
  sla_deadline  TIMESTAMPTZ,
  sla_breached  BOOLEAN NOT NULL DEFAULT false,
  
  -- Rating
  rating        SMALLINT CHECK (rating BETWEEN 1 AND 5),
  rating_comment TEXT,
  rated_at      TIMESTAMPTZ,
  
  -- Routing (set automatically on creation)
  campus_id     UUID NOT NULL REFERENCES campuses(id),
  department_id UUID NOT NULL REFERENCES departments(id),
  section_id    UUID NOT NULL REFERENCES sections(id),
  
  -- Status note (required on status change)
  last_status_note TEXT;
```

### 2.3 context_config on service_categories and service_items

> **REVISED — 2026-05-27**  
> The per-field `locationFields` shape (`building/floor/room/area/isResidential` with
> `required|optional|hidden` modes) and `residentialFields` are **removed**.
> Location collection is now entirely user-driven via the `FacilityTypeSelector` in the
> frontend wizard. Admins only toggle whether the Location section appears at all for a
> given service item (`locationEnabled`).

**New `context_config` shape (Django JSONField default):**

```json
{
  "locationEnabled": false,
  "assetLinkable": false,
  "requiresAsset": false
}
```

- `locationEnabled` — when `true`, the wizard step 2 shows the Facility/Location section.
  User picks one of five facility types (Office Block, Building, Facility/Equipment,
  Residential, Grounds) and fills in type-specific fields. The backend stores the result
  in the ticket's `facility_id`, `floor`, `room`, `area`, `tenant_name`, `unit_number`,
  and new `facility_type` field.
- `assetLinkable` — when `true`, show AssetPicker in step 2.
- `requiresAsset` — when `true`, asset selection is required (implies `assetLinkable`).

**Migration — update existing `context_config` columns:**

```sql
-- ServiceCategory: replace locationFields-shape default
ALTER TABLE tickets_servicecategory
  ALTER COLUMN context_config SET DEFAULT
    '{"locationEnabled": false, "assetLinkable": false, "requiresAsset": false}';

-- Back-fill existing rows: map old format → new
-- Any row where locationFields.building != "hidden" → locationEnabled = true
UPDATE tickets_servicecategory
SET context_config = jsonb_build_object(
  'locationEnabled',
  CASE WHEN context_config->'locationFields'->>'building' != 'hidden' THEN true ELSE false END,
  'assetLinkable',  COALESCE((context_config->>'assetLinkable')::boolean, false),
  'requiresAsset',  COALESCE((context_config->>'requiresAsset')::boolean, false)
)
WHERE context_config ? 'locationFields';

-- ServiceItem: same back-fill
UPDATE tickets_serviceitem
SET context_config = jsonb_build_object(
  'locationEnabled',
  CASE WHEN context_config->'locationFields'->>'building' != 'hidden' THEN true ELSE false END,
  'assetLinkable',  COALESCE((context_config->>'assetLinkable')::boolean, false),
  'requiresAsset',  COALESCE((context_config->>'requiresAsset')::boolean, false)
)
WHERE context_config ? 'locationFields';
```

**Django model update (`tickets/models/catalogue.py`):**

```python
CONTEXT_CONFIG_DEFAULT = {
    "locationEnabled": False,
    "assetLinkable": False,
    "requiresAsset": False,
}

class ServiceCategory(models.Model):
    context_config = models.JSONField(default=dict, blank=True)
    # ...

class ServiceItem(models.Model):
    context_config = models.JSONField(null=True, blank=True, default=None)
    # NULL = inherit from category
```

**`resolved_context_config` property (on `ServiceItem`):**

```python
@property
def resolved_context_config(self):
    """Return item-level config, falling back to category default."""
    base = self.category.context_config or CONTEXT_CONFIG_DEFAULT.copy()
    if self.context_config:
        base = {**base, **self.context_config}
    return base
```

### 2.4 New: ticket_events table (timeline)

```sql
CREATE TABLE ticket_events (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticket_id  UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
  event_type VARCHAR(50) NOT NULL,
              -- created, assigned, reassigned, status_changed, comment,
              -- escalated, resolved, closed, reopened, rated
  actor_id   UUID NOT NULL REFERENCES users(id),
  data       JSONB NOT NULL DEFAULT '{}',
              -- varies by event: { from_status, to_status } | { technician_id } | { comment_body } etc.
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_ticket_events_ticket ON ticket_events(ticket_id, created_at);
```

### 2.5 New: sla_rules table

```sql
CREATE TABLE sla_rules (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  service_category_id UUID NOT NULL REFERENCES service_categories(id),
  priority            VARCHAR(10) NOT NULL CHECK (priority IN ('low','medium','high','critical')),
  response_hours      DECIMAL(5,2) NOT NULL,   -- time to first assignment
  resolution_hours    DECIMAL(5,2) NOT NULL,   -- time to resolved status
  created_at          TIMESTAMPTZ DEFAULT now(),
  UNIQUE(service_category_id, priority)
);
```

### 2.6 New: workflow_settings table

```sql
CREATE TABLE workflow_settings (
  key        VARCHAR(100) PRIMARY KEY,
  value      JSONB NOT NULL,
  updated_by UUID REFERENCES users(id),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Seed defaults
INSERT INTO workflow_settings VALUES
  ('auto_assign', 'false', NULL, now()),
  ('sla_warning_minutes', '30', NULL, now()),
  ('require_resolution_note', 'true', NULL, now()),
  ('user_ratings_enabled', 'true', NULL, now()),
  ('escalation_auto_notify', 'true', NULL, now());
```

### 2.7 Facility table — updated types and new `facility_type` on Ticket

> **REVISED — 2026-05-27**
> The `Facility` model's `FACILITY_CHOICES` are updated to match the five user-facing
> facility types. The old choices (`workshop`, `outdoor`, `other`) are retired.
> A new `facility_type` field is added to the `Ticket` model to record which type the
> user selected when raising the ticket.

**Updated `Facility.FACILITY_CHOICES` (Django model):**

```python
FACILITY_CHOICES = [
    ("office_block", "Office Block"),   # Admin offices, departmental blocks
    ("building",     "Building"),       # Dining halls, hostels, kitchens, accommodation
    ("equipment",    "Facility / Equipment"),  # Printers, generators, lab equipment
    ("residential",  "Residential"),    # Staff houses, guest quarters
    ("grounds",      "Grounds"),        # Fields, parking lots, outdoor areas
]
```

**New `facility_type` field on `Ticket`:**

```python
FACILITY_TYPE_CHOICES = [
    ("office_block", "Office Block"),
    ("building",     "Building"),
    ("equipment",    "Facility / Equipment"),
    ("residential",  "Residential"),
    ("grounds",      "Grounds"),
]

class Ticket(models.Model):
    # ...existing fields...
    facility_type = models.CharField(
        max_length=20,
        choices=FACILITY_TYPE_CHOICES,
        blank=True,
    )
```

**Field-to-facility-type mapping (how frontend data maps to ticket fields):**

| Facility type | facility_id | floor | room | area | tenant_name | unit_number |
|---------------|-------------|-------|------|------|-------------|-------------|
| office_block | FK (select) | floor | room | area (opt.) | — | — |
| building | FK (select) | floor | room | area (opt.) | — | — |
| equipment | null | — | asset_id (opt.) | location_desc (opt.) | — | — |
| residential | null | — | — | — | tenant_name (opt.) | unit_number |
| grounds | null | area_zone | — | landmark (opt.) | — | — |

**`GET /api/facilities/` response** — already exists. Filter by `?campus_id=<id>`.
The frontend `FacilityTypeLocationSelector` uses this to populate the building-name
select for `office_block` and `building` types.

**Migration for data back-fill** (existing facilities with old types):

```sql
-- Map old types to new choices
UPDATE tickets_facility SET type = 'office_block'
  WHERE type IN ('workshop') OR (type = 'building' AND name ILIKE '%admin%');

UPDATE tickets_facility SET type = 'equipment'
  WHERE type IN ('equipment', 'ict', 'laundry', 'kitchen', 'other');

UPDATE tickets_facility SET type = 'grounds'
  WHERE type = 'outdoor';
-- 'building' and 'residential' remain unchanged
```

### 2.8 New: analytics_cache table

```sql
CREATE TABLE analytics_cache (
  cache_key   VARCHAR(255) PRIMARY KEY,
              -- e.g. "kpis:section:uuid:2024-01"
  data        JSONB NOT NULL,
  computed_at TIMESTAMPTZ NOT NULL,
  expires_at  TIMESTAMPTZ NOT NULL
);
```

---

## 3. Endpoint specifications

All endpoints require `Authorization: Bearer <jwt>`.  
Scope is read from the JWT — never from request params for security.

### 3.1 Auth endpoints

```
POST /auth/login
  Body: { email, password }
  Response: { user: AuthUser, accessToken: string }
  Notes: set httpOnly refresh token cookie

POST /auth/refresh
  Body: (refresh token from cookie)
  Response: { accessToken: string }

POST /auth/logout
  Response: 204
  Notes: invalidate refresh token

POST /auth/switch-role
  Body: { roleAssignmentId: string }
  Response: { accessToken: string }
  Notes: verify roleAssignmentId belongs to current user, issue new JWT with that role's scope
```

### 3.2 Ticket endpoints

```
GET /tickets
  Query: status?, priority?, assigneeId?, search?, cursor?, limit=20, dateFrom?, dateTo?
  Response: PaginatedResponse<Ticket> + counts object (see below)
  
  Response shape:
  {
    "data": [ ...tickets ],
    "meta": { "nextCursor": "...", "prevCursor": "...", "total": 12 },
    "counts": {
      "all": 12, "open": 4, "in_progress": 5,
      "escalated": 1, "resolved": 2, "closed": 0
    }
  }
  
  Note: counts always reflect the FULL unfiltered set for the current scope,
  regardless of the status filter applied. This lets FilterPills show all
  counts simultaneously without extra requests.
  
  For SLA tracking endpoint (/analytics/sla-status), counts shape is:
  { "all": 9, "breached": 2, "at_risk": 3, "on_track": 4 }

  Scope: server applies WHERE based on JWT role:
    user       → WHERE raised_by_id = :userId
    technician → WHERE section_id = :sectionId AND campus_id = :campusId
    hos        → WHERE section_id = :sectionId AND campus_id = :campusId
    hod        → WHERE department_id = :deptId AND campus_id = :campusId
    manager    → WHERE department_id = :deptId
    admin      → no filter

POST /tickets/create/
  Body: {
    department_id: int,
    service_item_id: int,
    title: string,
    description?: string,
    -- Location (only when context_config.locationEnabled = true on the service item)
    facility_type?: 'office_block' | 'building' | 'equipment' | 'residential' | 'grounds',
    facility_id?: int | null,    -- FK to Facility (office_block and building only)
    floor?: string,              -- floor/area-zone
    room?: string,               -- room/asset-id
    area?: string,               -- area/location-desc/landmark
    tenant_name?: string,        -- residential only
    unit_number?: string,        -- residential only
    -- Asset (if assetLinkable)
    asset_id?: string,
    -- Form schema answers (dynamic fields per service item)
    form_data?: Record<string, unknown>
  }
  Response: Ticket
  Notes:
    1. Resolve: serviceItem → serviceCategory → section → department → campus
    2. Verify campus matches user's campusId from JWT
    3. Compute sla_deadline from sla_rules for this category + priority
    4. Create ticket_event: type=created
    5. Emit WS event to section:{sectionId}:{campusId} channel
    6. Return created ticket

GET /tickets/:id
  Response: Ticket (full detail)
  Auth: must be raised_by, assigned_to, or in the section/dept/campus scope of their role

PATCH /tickets/:id/status
  Body: { status: TicketStatus, note: string (required), pendingReason?: string, attachmentIds?: string[] }
  Auth: technician (own assigned), hos (section), hod (dept)
  Validation: enforce state machine transitions (see 4.3)
              pendingReason required when status = 'pending'
              status 'assigned' rejected — use /assign endpoint instead
  Notes:
    - Create ticket_event: type=status_changed, data={from, to, note, pendingReason?}
    - If transitioning to resolved: set resolved_at = now()
    - If transitioning to pending: set pending_reason on ticket
    - If transitioning from pending to in_progress: clear pending_reason (set null)
    - Emit WS: ticket:{id}, section:{sectionId}:{campusId}, user:{raisedById}

PATCH /tickets/:id/assign
  Body: { technicianId: string, note?: string }
  Auth: hos, hod
  Validation: technician must be in the same section as the ticket
              ticket must be in status: open or assigned (reassignment)
  Notes:
    - Set status = 'assigned' (not 'in_progress' — technician has not yet started)
    - Set assigned_to_id = technicianId
    - Set assigned_at = now()
    - Create ticket_event: type=assigned (or type=reassigned if previously assigned)
    - Compute/update sla_deadline if not already set
    - Emit WS: ticket:{id}, section:{sectionId}:{campusId}, user:{raisedById}

POST /tickets/:id/escalate
  Body: { level: 'hod' | 'reassign', reason: string, targetSectionId?: string, priorityOverride?: TicketPriority }
  Auth: technician, hos
  Notes:
    - Set status = escalated
    - Create ticket_event: type=escalated
    - If level=hod: emit WS to dept:{deptId}:{campusId}
    - If level=reassign: update section_id, emit WS to new section channel

PATCH /tickets/:id/escalation
  Body: { action: 'approve' | 'reassign', targetSectionId?: string }
  Auth: hod
  Notes: HOD responds to an escalation

POST /tickets/:id/close
  Auth: user (must be raised_by)
  Validation: ticket status must be resolved
  Notes:
    - Set status = closed, closed_at = now()
    - Create ticket_event: type=closed

POST /tickets/:id/reopen
  Body: { reason: string }
  Auth: user (must be raised_by)
  Validation: ticket status must be resolved or closed
  Notes:
    - Set status = open
    - Create ticket_event: type=reopened

POST /tickets/:id/rating
  Body: { rating: 1|2|3|4|5, comment?: string }
  Auth: user (must be raised_by, ticket must be resolved or closed)
  Validation: cannot rate twice
  Notes:
    - Set rating, rating_comment, rated_at
    - Create ticket_event: type=rated

GET /tickets/:id/timeline
  Response: TimelineEvent[]
  Notes: ordered by created_at ASC, includes all ticket_events + comments

GET /tickets/:id/comments
  Response: Comment[]

POST /tickets/:id/comments
  Body: { body: string, attachmentIds?: string[] }
  Auth: any role with access to the ticket
  Notes:
    - Create ticket_event: type=comment
    - Emit WS: ticket:{id}

POST /tickets/:id/attachments
  Body: multipart/form-data with files
  Response: Attachment[]
  Notes: return attachment IDs for use in ticket/comment creation
```

### 3.3 Service endpoints

```
GET /services/categories
  Query: campusId (required)
  Response: ServiceCategory[]
  Notes: filter by is_active = true, return with context_config

GET /services/categories/:id/items
  Response: ServiceItem[]
  Notes: filter by is_active = true

GET /services/items/:id/context-config
  Response: ContextConfig
  Notes: return ServiceItem.context_config ?? ServiceCategory.context_config
  This is the resolved config the frontend uses to render the form

Admin CRUD (auth: admin only):
  POST   /admin/services/categories
  PATCH  /admin/services/categories/:id
  DELETE /admin/services/categories/:id
  POST   /admin/services/categories/:id/items
  PATCH  /admin/services/items/:id
  DELETE /admin/services/items/:id
```

### 3.4 Analytics endpoints

All analytics endpoints are scope-filtered by role. No explicit scope params accepted from client.

**Audit note (Phase D):** The original spec assumed a flat set of generic endpoints
(/kpis, /volume, /department-breakdown, /technician-performance, /sla-status). The
frontend was built with role-scoped endpoints instead. The generic endpoints are not
called by any frontend service file. Do not add them — they create dead routes and
duplicate logic already in the role-scoped analytics classes.

**Existing endpoints (all implemented):**
```
GET /analytics/tickets/                    Auth: admin, manager
GET /analytics/technicians/                Auth: admin, manager, hod, technician (self)
GET /analytics/technicians/me/             Auth: technician, admin
GET /analytics/admin-dashboard/            Auth: admin, manager
GET /analytics/section-head/               Auth: head_of_section, admin
GET /analytics/hod/                        Auth: hod, admin
GET /analytics/manager/                    Auth: manager, admin
GET /analytics/user/                       Auth: any authenticated
GET /analytics/departments/<pk>/           Auth: admin, manager, hod
GET /analytics/campus-departments/<pk>/    Auth: admin, manager, hod
GET /analytics/sections/<pk>/             Auth: admin, manager, hod, head_of_section
```

**Missing — add in Phase D:**
```
GET /analytics/organizational/
  Auth: admin, manager
  Response: AdminAnalytics.get_organisation_analytics(days=days)
  Notes: frontend getOrganisationAnalytics() calls this path; delegate entirely to
         the existing AdminAnalytics class — no new query logic needed.
  Cache: 5-min via get_cached() (already handled inside AdminAnalytics)
```

**Reports (existing):**
```
GET  /reports/generate/   Auth: technician+   Returns Excel workbook (openpyxl)
GET  /reports/types/      Auth: technician+   Lists available report types
```

### 3.5 User and role management endpoints

```
GET /users
  Query: role?, campusId?, departmentId?, sectionId?, search?, cursor?, limit=20
  Auth: admin, manager (own dept), hod (own dept+campus)
  Response: PaginatedResponse<UserDetail>

GET /users/:id
  Response: UserDetail

GET /sections/:id/technicians
  Response: TechnicianSummary[]  (includes activeTicketCount and slaComplianceRate)
  Auth: hos, hod

POST /users
  Body: { fullName, email, phone? }
  Auth: admin

POST /users/:id/role-assignments
  Body: { role, campusId?, departmentId?, sectionId?, isPrimary? }
  Auth: admin
  Validation: enforce scope constraints per role (see DB model 2.1)

DELETE /users/:id/role-assignments/:assignmentId
  Auth: admin

PATCH /users/:id/role-assignments/:assignmentId
  Body: { isPrimary?: boolean }
  Auth: admin
```

### 3.6 Admin config endpoints

```
-- Campuses
GET    /admin/campuses
POST   /admin/campuses
PATCH  /admin/campuses/:id
DELETE /admin/campuses/:id

-- Departments
GET    /admin/departments
POST   /admin/departments
PATCH  /admin/departments/:id
DELETE /admin/departments/:id

-- Sections
GET    /admin/sections?departmentId=
POST   /admin/sections
PATCH  /admin/sections/:id
DELETE /admin/sections/:id

-- Buildings/Facilities
GET    /facilities/buildings?campusId=
POST   /admin/buildings
PATCH  /admin/buildings/:id
DELETE /admin/buildings/:id

-- SLA Rules
GET    /admin/sla-rules
POST   /admin/sla-rules
PATCH  /admin/sla-rules/:id
DELETE /admin/sla-rules/:id

-- Workflow settings
GET    /admin/workflows
PATCH  /admin/workflows/:key     Body: { value }

-- Audit log
GET    /admin/audit-logs
  Query: actorId?, action?, from?, to?, cursor?, limit=50
  Response: PaginatedResponse<AuditLogEntry>
```

### 3.7 Notification endpoints

```
GET    /notifications              Response: Notification[]
PATCH  /notifications/:id/read     Response: 204
POST   /notifications/read-all     Response: 204
```

### 3.8 Facilities / assets

```
GET /facilities/buildings?campusId=    Response: Building[]
GET /assets?campusId=&search=          Response: Asset[]
```

---

## 4. Auth and scoping requirements (critical)

This is the most important backend requirement. Every list query must apply a scope filter derived from the JWT — never trust scope params from the client.

### 4.1 Scope middleware

Implement a scope middleware that runs after JWT verification:

```
extractScope(jwt) → ScopeContext {
  userId, role, campusId, deptId, sectionId
}

applyTicketScope(query, scope):
  if scope.role === 'user':        query.where('raised_by_id', scope.userId)
  if scope.role === 'technician':  query.where('section_id', scope.sectionId)
                                        .where('campus_id', scope.campusId)
  if scope.role === 'hos':         query.where('section_id', scope.sectionId)
                                        .where('campus_id', scope.campusId)
  if scope.role === 'hod':         query.where('department_id', scope.deptId)
                                        .where('campus_id', scope.campusId)
  if scope.role === 'manager':     query.where('department_id', scope.deptId)
  if scope.role === 'admin':       (no filter)
```

### 4.2 JWT payload structure

The JWT must include:
```json
{
  "sub": "user-uuid",
  "email": "user@org.com",
  "role": "technician",
  "campusId": "uuid-or-null",
  "deptId": "uuid-or-null",
  "sectionId": "uuid-or-null",
  "roleAssignmentId": "uuid",
  "iat": 1234567890,
  "exp": 1234571490
}
```

### 4.3 Ticket status state machine (enforce server-side)

```
VALID_TRANSITIONS = {
  open:        ['escalated'],            // open → assigned is triggered by /assign endpoint only
  assigned:    ['in_progress',           // technician starts work
                'open',                  // HOS unassigns (returns to queue)
                'escalated'],
  in_progress: ['pending',               // blocked — waiting on parts, access, approval
                'resolved',              // work complete
                'escalated',             // requires HOD or reroute
                'open'],                 // rarely — technician returns ticket
  pending:     ['in_progress',           // blocker resolved, resuming work
                'escalated'],            // blocker cannot be resolved at section level
  resolved:    ['closed',               // user confirms (via POST /tickets/:id/close)
                'open'],                 // user reopens (via POST /tickets/:id/reopen)
  escalated:   ['in_progress',           // HOD approves and returns to technician
                'resolved'],             // resolved during escalation review
  closed:      []                        // terminal — no transitions out
}

// Special rules:
// open → assigned: ONLY via PATCH /tickets/:id/assign — never via /status endpoint
//   On assign: set status='assigned', set assigned_at=now(), set assigned_to_id
//   This keeps the assign action semantically distinct from a status update

// in_progress → pending: requires pending_reason in request body (what is blocking)
//   pending_reason stored on the ticket and shown in the timeline

// pending → in_progress: clears pending_reason (set to null)

// resolved → closed: triggered by POST /tickets/:id/close (user action), not /status
// resolved → open: triggered by POST /tickets/:id/reopen (user action), not /status

On PATCH /tickets/:id/status:
  if newStatus === 'assigned':
    return 422 { code: 'USE_ASSIGN_ENDPOINT',
                 message: 'Use PATCH /tickets/:id/assign to assign a ticket' }
  if newStatus not in VALID_TRANSITIONS[currentStatus]:
    return 422 { code: 'INVALID_TRANSITION', message: '...' }
  if newStatus === 'pending' AND body.pendingReason is missing:
    return 422 { code: 'VALIDATION_ERROR', details: { pendingReason: ['Required when setting status to pending'] } }
```

### 4.4 Automatic ticket routing on creation

```
On POST /tickets:
  1. serviceItem = find(serviceItemId)
  2. category = serviceItem.serviceCategory
  3. sectionId = category.sectionId
  4. deptId = category.departmentId
  5. campusId = jwt.campusId  (user's campus)
  6. Verify section belongs to dept, dept exists in campus — else 422
  7. Set ticket.section_id, ticket.department_id, ticket.campus_id
  8. Compute SLA deadline: find sla_rule for (categoryId, priority) → add resolution_hours to now()
  9. Create ticket
  10. Emit WS event
```

---

## 5. Real-time (WebSocket) event contracts

### 5.1 Technology: Django Channels

Use Django Channels, not Socket.io. Socket.io is a Node.js protocol — integrating it
with Django requires python-socketio as a separate ASGI process, which loses Django's
native auth and ORM integration. Django Channels is the correct solution for Django + DRF.

Required packages:
  pip install channels channels-redis daphne

asgi.py:
  ProtocolTypeRouter wrapping URLRouter with JWTAuthMiddlewareStack.
  WebSocket URL: ws/  (frontend connects to wss://host/ws/?token=<jwt>)

JWT auth middleware:
  Reads token from query string, validates with SimpleJWT's AccessToken,
  stores user_id, role, campus_id, dept_id, section_id in scope.
  Closes with code 4001 if token missing or invalid.

Consumer (AsyncWebsocketConsumer):
  connect()  — validate scope user_id, accept, await join messages from client
  receive()  — handle join/leave messages, validate channel access before group_add
  send_event() — handler called by channel_layer.group_send, forwards to WebSocket client
  _is_allowed_channel() — validates client only joins channels within their scope

Emitting from DRF views (synchronous context):
  from asgiref.sync import async_to_sync
  from channels.layers import get_channel_layer
  channel_layer = get_channel_layer()
  async_to_sync(channel_layer.group_send)(
      group_name,
      { 'type': 'send_event', 'data': { 'type': event_type, **payload } }
  )

settings.py:
  INSTALLED_APPS += ['channels']
  ASGI_APPLICATION = 'core.asgi.application'
  CHANNEL_LAYERS = {
      'default': {
          'BACKEND': 'channels_redis.core.RedisChannelLayer',
          'CONFIG': { 'hosts': [('redis', 6379)] }
      }
  }

ASGI server (production):
  daphne -b 0.0.0.0 -p 8000 core.asgi:application
  OR uvicorn core.asgi:application --host 0.0.0.0 --port 8000 --workers 4

---

### 5.2 Channel naming and group topology

IMPORTANT: Django Channels group names must use only letters, digits, hyphens,
underscores, and periods. No colons. All group names use underscores.
Frontend wsClient.ts uses the same underscore naming to match.

Groups:
  user_{userId}                  personal channel, one per authenticated user
  ticket_{ticketId}              transient, joined when viewing ticket detail page
  section_{sectionId}_{campusId} operational, HOS and section technicians
  dept_{deptId}_{campusId}       operational, HOD
  system_{campusId}              admin/audit events

Role to group subscription map:

| Role | Persistent groups | Transient (page-level) |
|------|------------------|-----------------------|
| User | user_{userId} | ticket_{id} when on detail page |
| Technician | user_{userId} + section_{sectionId}_{campusId} | ticket_{id} when on detail page |
| HOS | section_{sectionId}_{campusId} | ticket_{id} when on detail page |
| HOD | dept_{deptId}_{campusId} | ticket_{id} when on detail page |
| Manager | none (poll-based 5 min refetch) | none |
| Admin | system_{campusId} | ticket_{id} when on detail page |

Events per group:

  user_{userId}
    ticket_assigned, ticket_status_changed, ticket_resolved, comment_added, sla_warning

  section_{id}_{campus}
    ticket_created, ticket_assigned, ticket_status_changed, sla_warning, sla_breach

  dept_{id}_{campus}
    ticket_escalated, sla_breach, section_summary

  ticket_{id} (transient)
    ticket_status_changed, comment_added, ticket_assigned, sla_warning

  system_{campusId}
    config_changed, user_role_changed, audit_event

---

### 5.3 Event payloads

```json
// ticket_created — emitted to: section_{sectionId}_{campusId}
{
  "event": "ticket_created",
  "ticketId": "uuid",
  "reference": "TKT-00412",
  "title": "Water leakage — Block A",
  "priority": "high",
  "sectionId": "uuid",
  "campusId": "uuid"
}

// ticket_assigned — emitted to: ticket_{id}, section_{sectionId}_{campusId}, user_{raisedById}
{
  "event": "ticket_assigned",
  "ticketId": "uuid",
  "assignedToId": "uuid",
  "assignedToName": "Peter Otieno"
}

// ticket_status_changed — emitted to: ticket_{id}, section_{sectionId}_{campusId}, user_{raisedById}
{
  "event": "ticket_status_changed",
  "ticketId": "uuid",
  "fromStatus": "open",
  "toStatus": "in_progress",
  "note": "On site, investigating"
}

// comment_added — emitted to: ticket:{id}
{
  "event": "comment_added",
  "ticketId": "uuid",
  "commentId": "uuid",
  "authorName": "Peter Otieno",
  "preview": "First 100 chars of comment..."
}

// ticket_escalated — emitted to: dept_{deptId}_{campusId}, ticket_{id}
{
  "event": "ticket_escalated",
  "ticketId": "uuid",
  "reference": "TKT-00412",
  "escalatedBy": "HOS name",
  "reason": "First 100 chars..."
}

// ticket_resolved — emitted to: ticket_{id}, user_{raisedById}
{
  "event": "ticket_resolved",
  "ticketId": "uuid",
  "resolvedBy": "Peter Otieno"
}

// sla_warning — emitted to: section_{sectionId}_{campusId}, ticket_{id}, user_{assignedToId}
// Triggered by scheduled job 30 min before deadline (configurable)
{
  "event": "sla_warning",
  "ticketId": "uuid",
  "reference": "TKT-00412",
  "minutesRemaining": 30
}

// sla_breach — emitted to: section_{sectionId}_{campusId}, dept_{deptId}_{campusId}
// Triggered by scheduled job when deadline passes
{
  "event": "sla_breach",
  "ticketId": "uuid",
  "reference": "TKT-00412",
  "breachedAt": "ISO datetime"
}
```

### 5.4 Scheduled jobs required

```
SLA warning job:     runs every 5 minutes
                     finds tickets where sla_deadline BETWEEN now() AND now() + 30min
                     AND sla_breached = false AND sla_warning_sent = false
                     emits sla_warning event, sets sla_warning_sent = true

SLA breach job:      runs every 5 minutes
                     finds tickets where sla_deadline < now() AND sla_breached = false
                     sets sla_breached = true, emits sla_breach event

Analytics cache job: runs every 5 minutes
                     recomputes KPIs for all active scope combinations
                     stores in analytics_cache with expires_at = now() + 5min
```

---


## 6. API response conventions

Apply consistently across all endpoints.

### 6.1 Success responses

```json
// Single resource
{ "data": { ... } }

// List / paginated
{
  "data": [ ... ],
  "meta": {
    "nextCursor": "string|null",
    "prevCursor": "string|null",
    "total": 248
  }
}

// No content
HTTP 204 (no body)
```

### 6.2 Error responses

```json
HTTP 4xx/5xx
{
  "error": {
    "code": "TICKET_NOT_FOUND",          // machine-readable
    "message": "Ticket not found",       // human-readable
    "details": {                         // optional field-level errors
      "status": ["Invalid transition from resolved to in_progress"]
    }
  }
}
```

### 6.3 Standard error codes

| Code | HTTP | Meaning |
|------|------|---------|
| UNAUTHORIZED | 401 | No/invalid token |
| FORBIDDEN | 403 | Authenticated but no permission |
| NOT_FOUND | 404 | Resource not found |
| INVALID_TRANSITION | 422 | Status state machine violation |
| SCOPE_VIOLATION | 403 | Trying to access out-of-scope resource |
| VALIDATION_ERROR | 422 | Request body validation failed |
| SLA_RULE_MISSING | 422 | No SLA rule for this category+priority |

---

## 7. Implementation priority order

Build in this sequence. Frontend phases are blocked until the corresponding backend phase is done.

### Backend Phase A — Unblocks frontend Phase 2 (foundation)
1. Auth endpoints (login, refresh, logout) — likely exists, verify JWT payload structure
2. POST /auth/switch-role — new, needed for role switcher
3. Update JWT payload to include campusId, deptId, sectionId, roleAssignmentId
4. RoleAssignment DB table + migrations

### Backend Phase B — Unblocks frontend Phase 3-4 (core ticket flow)
5. Add context_config to service_categories and service_items
6. GET /services/categories, GET /services/items/:id/context-config
7. POST /tickets with location + residential + asset + auto-routing
8. GET /tickets with cursor pagination + server-side scope enforcement
9. GET /tickets/:id
10. PATCH /tickets/:id/status with state machine
11. PATCH /tickets/:id/assign
12. POST /tickets/:id/comments, GET /tickets/:id/comments
13. POST /tickets/:id/attachments
14. GET /tickets/:id/timeline (ticket_events table)
15. ticket_events created for all write operations above

### Backend Phase C — Unblocks remaining frontend features
16. POST /tickets/:id/escalate
17. PATCH /tickets/:id/escalation
18. POST /tickets/:id/close
19. POST /tickets/:id/reopen
20. POST /tickets/:id/rating
21. GET /sections/:id/technicians (with workload data)
22. Notification endpoints
23. GET /facilities/buildings

### Backend Phase D — Analytics and real-time
24. WebSocket server with scoped channels (Django Channels + Redis) ✓ DONE
25. WS event emission on all ticket lifecycle events ✓ DONE (emit calls in ticket_actions_views.py)
26. GET /analytics/organizational/ — add OrganisationAnalyticsView to views.py, register URL
    NOTE: /kpis, /volume, /department-breakdown, /technician-performance, /sla-status are
    NOT called by the frontend — do not implement. Role-scoped endpoints already cover all
    analytics the frontend needs. SLA tracking is done client-side in SLATrackingView.tsx.
27. SLA breach scheduled job — management command check_sla, sets sla_breached=True + WS emit
    ⚠️  NOT YET IMPLEMENTED: management command exists but no scheduler configured.
    SLA warnings and breach events will not fire in production without a scheduler.
    TODO: add django-crontab, Celery beat, or a Procfile/systemd timer that runs
    `manage.py check_sla` every 5 minutes and `manage.py process_auto_escalations` every 5 minutes.
28. SLA warning scheduled job — management command check_sla, sets sla_warning_sent=True + WS emit
    (sla_warning_sent field added to Ticket model in migration 0005)
    ⚠️  NOT YET IMPLEMENTED: same scheduler gap as item 27.
29. Analytics cache — EXISTS via get_cached() + django-redis; no separate table needed
30. POST /reports/export — EXISTS as GET /reports/generate/ (different method/path; frontend
    uses GET with query params, not POST body)

### Backend Phase E — Admin config
31. Full CRUD: campuses, departments, sections, buildings
    NOTE: Campus/Department/Section/Facility CRUD already exists at /campuses/, /departments/,
    /sections/, /facilities/. SectionType needs a PATCH endpoint added (SLARulesPage calls
    PATCH /section-types/<pk>/ to update default_sla_hours).
32. Full CRUD: service categories + items with context_config
    NOTE: Already exists at /service-catalogue/service-categories/ and /service-catalogue/service-items/.
33. SLA rules CRUD
    NOTE: The frontend SLARulesPage does NOT call a /sla-rules/ endpoint. It edits SLA times
    via PATCH /section-types/<pk>/ (default_sla_hours) and PATCH /service-catalogue/service-items/<pk>/
    (sla_hours). The SLARule model is used internally during ticket creation only.
    No new SLA rules CRUD endpoint is required.
34. Workflow settings endpoints
    Frontend calls: GET /admin/config/ and PATCH /admin/config/
    Response shape: { auto_escalation_enabled, sla_enforcement_enabled, email_notifications_enabled }
    Requires: WorkflowSettings model + migration + view.
35. User management + role assignment endpoints
    NOTE: User CRUD already exists at /users/, /users/<pk>/. New endpoints needed:
    POST /users/<pk>/role-assignments/
    PATCH /users/<pk>/role-assignments/<ra_pk>/
    DELETE /users/<pk>/role-assignments/<ra_pk>/
36. Audit log — serve TicketLog through GET /admin/audit-log/
    NOTE: Do NOT create a new AuditLog model. See Section 8 for the full design decision.
    TicketLog already captures all ticket lifecycle events. The /admin/audit-log/ endpoint
    maps TicketLog rows to the AuditLogEntry shape expected by the frontend AuditLogPage.

---

## 8. Audit log specification

### Design decision — Phase E

**Do not create a separate `audit_logs` table.** A `TicketLog` model already exists
in the codebase and is used throughout the ticket lifecycle:

```python
class TicketLog(models.Model):
    ticket       = ForeignKey(Ticket, related_name="logs")
    action       = CharField(max_length=255)   # e.g. "Status changed from open to in_progress"
    performed_by = ForeignKey(User, null=True)
    timestamp    = DateTimeField(auto_now_add=True)
```

It is written automatically by `Ticket.change_status()`, `Ticket.change_assignment()`,
and `Ticket.escalate()` — so all significant ticket actions are already logged.

**The `GET /admin/audit-log/` endpoint serves `TicketLog` rows** mapped to the shape
the `AuditLogPage` frontend component expects:

| Frontend field | Source |
|----------------|--------|
| `id`           | `TicketLog.id` |
| `actor`        | `TicketLog.performed_by.username` (or `"system"`) |
| `action`       | first word of `TicketLog.action` lowercased (e.g. `"assigned"`, `"status"`) |
| `target_type`  | `"ticket"` (constant) |
| `target_id`    | `TicketLog.ticket_id` |
| `detail`       | `TicketLog.action` (full text) |
| `created_at`   | `TicketLog.timestamp` |

**Filter query params** (all optional):
- `actor` — substring match on `performed_by__username`
- `date_from` / `date_to` — range on `timestamp`
- `action` — substring match on `action` field
- `target_type` — ignored (always `"ticket"` in this implementation)
- `page` / `page_size` — DRF `PageNumberPagination`, default page size 20

**Why not a general-purpose audit table?**
`TicketLog.ticket` is a required FK so it cannot store non-ticket events (user creation,
campus updates). Adding non-ticket audit logging can be done later by either:
(a) relaxing the FK to nullable and widening `TicketLog` into a general log, or
(b) adding a separate `AuditLog` table only when those events genuinely need to appear
    in the admin UI.

For Phase E the 90% case (ticket lifecycle audit) is covered without any new model or
migration.

---

Original SQL spec (for reference only — **not implemented**):

```sql
-- Kept for reference; replaced by TicketLog-backed endpoint above.
CREATE TABLE audit_logs (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  actor_id    UUID NOT NULL REFERENCES users(id),
  action      VARCHAR(100) NOT NULL,
  resource    VARCHAR(50) NOT NULL,
  resource_id UUID,
  before_data JSONB,
  after_data  JSONB,
  ip_address  INET,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## 9. Change log

| Version | Date | Change |
|---------|------|--------|
| 1.0 | — | Initial plan |
| 1.1 | — | WebSocket corrected — Django Channels replaces Socket.io |
| 1.2 | — | Phase E audit log — TicketLog-backed endpoint; no new table |
| 1.3 | 2026-05-27 | **Location system redesigned.** `context_config.locationFields` per-field shape removed from `ServiceCategory` and `ServiceItem`. Replaced by single `locationEnabled: bool`. Ticket creation now accepts `facility_type` field (`office_block`, `building`, `equipment`, `residential`, `grounds`). `Facility.FACILITY_CHOICES` updated to match these five types; old types `workshop`, `outdoor`, `other` retired. `Ticket` model gains `facility_type` CharField. See §2.3 and §2.7 for full spec and migration SQL. |

