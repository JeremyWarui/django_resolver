# Service Desk — Implementation Plan

> **Source of truth** for the multi-campus facilities service desk. Defines the domain model, the
> invariants the system must enforce, the Django/DRF backend, the ticket lifecycle / SLA /
> escalation engine, the REST + realtime API per role, and a phased build plan.
>
> **How to use with a coding agent.** Execute phases in order; don't start a phase until the
> previous one's acceptance criteria pass. Phase 0 audits the actual repository and records the app
> layout; later phases reconcile the code to this target. The companion `ALIGNMENT.md` maps any
> older planning vocabulary onto the terms used here; `CLAUDE.md` is the frontend contract.

---

## 1. System overview & expected behaviour

The organisation runs **global departments** (e.g. ICT, Finance) across **all campuses**. Each
department is led by a **Manager** (global). At each campus the department is instanced as a
**Campus Department** headed by an **HOD**. Each campus department contains **Sections** —
campus-local instances of a globally-defined **Section Type** — each headed by an **HOS** and
staffed by **Technicians**.

Requests are raised against a global **service catalogue** (Service Category → Service Item). A
ticket is routed to the **section that handles that section type at the requester's campus**.
Tickets carry a **priority** that drives an **SLA clock**; if not resolved in time they **escalate
up a fixed ladder** (Technician → HOS → HOD). The ladder is structural — there is no per-campus
workflow to configure.

### 1.1 The system is configuration-driven

Almost everything the desk does at runtime is **derived from admin-managed reference data**, not
hardcoded. Admins configure the structure; the backend enforces behaviour from it; the frontend
renders from it:

- **Org structure** (campuses, departments, section types, campus departments, sections,
  HOD/HOS/technician placement) → determines **routing** and the **escalation ladder's occupants**.
- **Service catalogue** (categories → items, each tied to a section type) → determines **what can
  be requested** and **where it routes**.
- **Priorities + escalation rules** → determine **SLA timers** and **when/where a ticket escalates**.
- **Facilities + a fixed set of facility types** → the `Facility` registry (real buildings/places
  per campus) drives the location dropdown; the facility type selects which location form to show.

Adding a campus, a service, a priority, or a building is a **data** change, and behaviour adapts
automatically (campus-filtered catalogue, server-set priority, the right location form). §9
specifies this contract. The one deliberate exception is the location *form fields*, which are a
small fixed set in code (§9.4).

### 1.2 Who can raise tickets — universal requester & context switching

**Every authenticated user is a requester.** Raising and tracking your own tickets is a universal
capability, independent of any staff role. This is how a staff member obtains service from *another*
department — e.g. an ICT technician whose office chair is broken raises a request that routes to
**Facilities** at their campus. No second role is needed: routing derives the target department from
the **chosen service item + the requester's campus**, never from the requester's own department.

In the UI this is a **context switch**, not a role change: a staff user toggles between their
**Staff workspace** (their operational role's queues) and **My Requests** (the requester view). Both
are available in one session; the requester context needs no new permissions because the backend
authorises own-ticket create/read for everyone.

A separate mechanism, **role cover** (§3.8), lets a user temporarily hold a *second operational
role* — e.g. a senior technician acting as HOS while the HOS is on leave. That is a time-boxed
`RoleAssignment`, distinct from the requester context above.

### Roles and what each sees

| Role | Scope | Core actions |
|------|-------|--------------|
| **Requester** (any user) | Self, own campus | Create ticket (any department's services served at their campus), view own tickets, public comments, rate resolution |
| **Technician** | Their section(s) | Work assigned queue, change status, comment (public/internal) |
| **HOS** | Their section(s) | Assign/reassign within pool, adjust priority, handle HOS-level escalations, section performance |
| **HOD** | Their campus department | Reassign across sections, handle HOD-level escalations, campus-department performance |
| **Manager** | Their department, all campuses | Department analytics, campus comparison |
| **Admin** | Global config | Manage campuses, departments, section types, sections, catalogue, priorities/SLA, facilities, users/roles |

Every staff role above is **also** a requester via the context switch (§1.2).

---

## 2. Domain model & invariants

### 2.1 Entities

**Organisation**
- `Campus(name, code, location)`
- `Department(name, code, manager → User)`
- `SectionType(name, code, department → Department)` — global definition, owned by a department
- `CampusDepartment(campus → Campus, department → Department, hod → User)`
- `Section(campus_department → CampusDepartment, section_type → SectionType, hos → User, is_active)`
- `SectionTechnician(section → Section, user → User)`

**People**
- `User` + `UserProfile(user 1-1, campus → Campus)`. **`RoleAssignment` (§3.8) is the single source
  of role truth** — a user's active primary assignment *is* their role, and `User.role` is a
  **derived accessor**, not a stored field. Org placement comes from the FKs above
  (manager/hod/hos/`SectionTechnician`). `UserProfile.campus` is the campus used for routing
  (§1.2, R5/R6). Django Groups may mirror the active role for coarse permission gating, but the
  assignment is authoritative.

**Catalogue**
- `ServiceCategory(name, section_type → SectionType, location_details: bool, default_priority → Priority)`
- `ServiceItem(name, service_category → ServiceCategory, default_priority → Priority [nullable override])`

**Priority & SLA**
- `Priority(name, rank, response_minutes, resolution_minutes)`
- `EscalationRule(priority → Priority, to_level ∈ {hos, hod}, threshold_minutes, order)`

**Facilities (location)**
- `FacilityType(name, code)` — a small **fixed** enumeration of facility kinds (§9.4). Seeded:
  `office_block, building, equipment, residential, grounds` (+ `hostel` when added). Each type maps
  to one location form on the frontend. The *set* changes only with a small code change (a new
  form), not at runtime.
- `Facility(campus → Campus, facility_type → FacilityType, name, code [optional])` — the registry of
  real buildings/places per campus; drives the location dropdown.

**Ticketing**
- `Ticket(ticket_no, raised_by → User, requester_campus → Campus, service_item → ServiceItem,
  section → Section, priority → Priority, assigned_to → User [nullable], status, current_level,
  response_due_at, resolution_due_at, paused_at [nullable], accumulated_pause, created_at,
  updated_at, resolved_at, closed_at)`
- `TicketLocation(ticket 1-1, facility_type → FacilityType, facility → Facility [nullable],
  values: JSON)` — present iff `category.location_details`; `facility` set for types whose form has
  a building dropdown (office_block, building); `values` holds the remaining per-type fields
  (validated against the type's known field set — see §9.4)
- `TicketLog(ticket → Ticket, actor → User [nullable=system], event_type, from_value, to_value,
  reason [nullable], level_user → User [nullable snapshot], created_at)` — **append-only / immutable**
- `TicketComment(ticket → Ticket, author → User, body, visibility ∈ {public, internal},
  created_at, updated_at)` — **mutable**
- `TicketFeedback(ticket 1-1, rating: int 1–5, comment, created_at)` — one per ticket, at/after resolution

### 2.2 Relationship summary

```
User ──manages──>            Department          (1 → many)
User ──heads (HOD)──>         CampusDepartment    (1 → many)
User ──heads (HOS)──>         Section             (1 → many)
User ──member of──>           SectionTechnician   (1 → many)
User ──raises (any user)──>   Ticket              (1 → many)   # universal requester (R15)
User ──assigned (tech)──>     Ticket              (1 → many)
Campus ──runs──>              CampusDepartment    (1 → many)
Campus ──home campus of──>    UserProfile         (1 → many)
Department ──instanced at──>  CampusDepartment    (1 → many)
Department ──defines──>       SectionType         (1 → many)
CampusDepartment ──contains─> Section             (1 → many)
SectionType ──typed as──>     Section             (1 → many)
SectionType ──routes to──>    ServiceCategory     (1 → many)
ServiceCategory ──lists──>    ServiceItem         (1 → many)
Priority ──default for──>     ServiceCategory     (1 → many)
Priority ──override──>        ServiceItem         (0/1 → many)
Priority ──rungs──>           EscalationRule      (1 → many)
Priority ──prioritises──>     Ticket              (1 → many)
ServiceItem ──requested in──> Ticket              (1 → many)
Section ──handled by──>       Ticket              (1 → many)
Campus ──has──>               Facility            (1 → many)
FacilityType ──classifies──>  Facility            (1 → many)
FacilityType ──typed as──>    TicketLocation      (1 → many)
Facility ──located at──>      TicketLocation      (0/1 → many)
Ticket ──1-1──>               TicketLocation
Ticket ──logs──>              TicketLog           (1 → many)
Ticket ──comments──>          TicketComment       (1 → many)
Ticket ──1-1──>               TicketFeedback
```

### 2.3 Invariants — the rules the model MUST enforce

- **R1** `CampusDepartment` is unique on `(campus, department)`.
- **R2** A `Section`'s `section_type.department` **must equal** its `campus_department.department` (validator).
- **R3** `Section` is unique on `(campus_department, section_type)`.
- **R4** `ServiceCategory` carries **no** `department` FK; department derives via `section_type.department`.
- **R5** **Catalogue visibility:** a category/item is offered to a requester at campus `C` **only if**
  an active `Section` of that `section_type` exists in `C`'s matching `CampusDepartment`. Enforced in
  the catalogue API and re-validated on create. (This also makes cross-department requests safe — a
  service appears only if it's actually served at the requester's campus.)
- **R6** **Routing:** `Ticket.section` is resolved on creation from `(requester_campus, service_item
  → category → section_type)`. No routing fallback — HOD is the top escalation rung, not a routing target.
- **R7** **Priority ≠ SLA ≠ escalation level.** Every ticket starts at `current_level = technician`.
  Requesters can never set priority — the server derives it from the item's (or category's) default.
- **R8** **Status machine:** transitions restricted to §4. Moving to `pending` requires a reason
  (written to `TicketLog.reason`).
- **R9** **SLA clock pauses** while `status = pending` and resumes on exit; `response_due_at` and
  `resolution_due_at` tracked separately; paused time accumulated in `accumulated_pause`.
- **R10** **Escalation engine** advances `current_level` per `EscalationRule` thresholds, **skips
  vacant rungs**, never escalates `resolved`/`closed`, records the **actual target user** in the log.
- **R11** `TicketLog` is **append-only/immutable** and snapshots the acting/owning user.
  `TicketComment` is mutable/separate. `TicketFeedback` is one-per-ticket, at/after `resolved`.
- **R12** **Transfers:** changing a role-holder re-homes that person's open tickets to the section
  pool; history is preserved because the log snapshots people.
- **R13** **Location** is captured **iff** `category.location_details`. Stored as
  `TicketLocation(facility_type, facility?, values)`. Each facility type has a **known, fixed field
  set** (§9.4); the backend validates `values` against that type's expected keys, and for types with
  a building dropdown the chosen `Facility` must match the requester's campus + type.
- **R14** **The `Facility` registry is admin-managed data** (buildings/places per campus). The **set
  of facility types is fixed in code** (one form per type); adding a type (e.g. `hostel`) is a small
  code change — a new form + enum value — not a runtime config action.
- **R15** **Universal requester:** every authenticated user may raise and view their own tickets
  regardless of operational role; cross-department requests work because routing derives from the
  service item + requester campus (§1.2), not the requester's department.
- **R16** **Configuration-driven:** routing, catalogue visibility, priority/SLA, and escalation all
  derive from admin-managed reference data (§1.1, §9). No deployment-specific behaviour is hardcoded
  in backend logic (location *form fields* are the one fixed-in-code exception, §9.4).
- **R17** **Attributed role cover:** a user may hold a temporary operational role via a
  `RoleAssignment` with `valid_until` + `assigned_by` (§3.8). Every action is attributed to the
  acting user and the role they acted in — **never** via a shared login. Active-holder resolution
  and escalation routing (§4.3) honour active, non-expired assignments.

---

## 3. Backend (Django + DRF)

### 3.1 App layout

The reference layout below separates the independently-configured concerns; the eight folders map
onto the existing model files, so the split is cheap. (A lighter 6- or 3-app grouping is acceptable
if the team prefers — the model boundaries and invariants in §2 are fixed regardless. The layout is
chosen and recorded in Phase 0, before models are written, because the fresh migration reset makes
it free to pick then.)

```
apps/
  accounts/    # User, UserProfile, JWT auth, RoleAssignment (role cover)
  org/         # Campus, Department, SectionType, CampusDepartment, Section, SectionTechnician
  catalog/     # ServiceCategory, ServiceItem
  sla/         # Priority, EscalationRule, escalation engine
  facilities/  # FacilityType (fixed enum), Facility registry, per-type location validators
  tickets/     # Ticket, TicketLocation, TicketLog, TicketComment, TicketFeedback,
               # routing resolver, status service, SLA service
  analytics/   # read-only aggregation endpoints
  realtime/    # Django Channels consumers + event emitters
```

Dependency direction (no cycles): `accounts → org → catalog → sla → facilities → tickets →
analytics`; `realtime` imports `tickets` for event emission only.

### 3.2 Models (sketch — agent finalises types, `Meta`, `__str__`, indexes)

Org, catalogue, and SLA models follow §2.1. Key constraints: `SectionType` unique `(name,
department)`; `CampusDepartment` unique `(campus, department)` (R1); `Section` unique
`(campus_department, section_type)` (R3) with a `clean()` enforcing R2; `ServiceCategory` has **no**
department FK (R4).

```python
# facilities/models.py
class FacilityType(models.Model):
    name = models.CharField(max_length=80, unique=True)   # office_block / building / equipment / residential / grounds (+ hostel)
    code = models.CharField(max_length=20, unique=True)   # stable key used to pick the location form

class Facility(models.Model):
    campus = models.ForeignKey("org.Campus", on_delete=models.CASCADE, related_name="facilities")
    facility_type = models.ForeignKey(FacilityType, on_delete=models.PROTECT, related_name="facilities")
    name = models.CharField(max_length=160)
    code = models.CharField(max_length=40, blank=True)
```

```python
# tickets/models.py
class Ticket(models.Model):
    STATUS = [("open","Open"),("assigned","Assigned"),("in_progress","In progress"),
              ("pending","Pending"),("resolved","Resolved"),("closed","Closed")]   # paused = pending
    LEVEL  = [("technician","Technician"),("hos","HOS"),("hod","HOD")]

    ticket_no = models.CharField(max_length=24, unique=True)            # human id, generated
    raised_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="raised_tickets")
    requester_campus = models.ForeignKey("org.Campus", on_delete=models.PROTECT, related_name="+")  # snapshot
    service_item = models.ForeignKey("catalog.ServiceItem", on_delete=models.PROTECT, related_name="tickets")
    section = models.ForeignKey("org.Section", on_delete=models.PROTECT, related_name="tickets")    # resolved
    priority = models.ForeignKey("sla.Priority", on_delete=models.PROTECT, related_name="+")        # R7
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="assigned_tickets")
    status = models.CharField(max_length=16, choices=STATUS, default="open")
    current_level = models.CharField(max_length=12, choices=LEVEL, default="technician")            # R7
    response_due_at = models.DateTimeField(null=True)
    resolution_due_at = models.DateTimeField(null=True)
    paused_at = models.DateTimeField(null=True)                                                     # R9 (pending)
    accumulated_pause = models.DurationField(default=timedelta())                                   # R9
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)        # ticket-feed ordering key (-updated_at)
    resolved_at = models.DateTimeField(null=True)
    closed_at = models.DateTimeField(null=True)

class TicketLocation(models.Model):                                                                 # R13
    ticket = models.OneToOneField(Ticket, on_delete=models.CASCADE, related_name="location")
    facility_type = models.ForeignKey("facilities.FacilityType", on_delete=models.PROTECT, related_name="+")
    facility = models.ForeignKey("facilities.Facility", null=True, blank=True,
                                 on_delete=models.PROTECT, related_name="+")   # set for building-dropdown types
    values = models.JSONField(default=dict)        # remaining per-type fields; keys validated by the type's known set

# TicketLog / TicketComment / TicketFeedback as in §2.1; TicketLog immutable (R11).
```

### 3.2a Ticket model discipline — intrinsic current state only

`Ticket` stores only what it intrinsically *is right now*. Three kinds of field do **not** belong on it:

- **Derived/computed values** — `sla_breached`, resolution-hours, "is late" flags. Compute from
  timestamps at read time or in analytics; stored derived state drifts from its source.
- **History** — who it escalated to, when, why, prior statuses. That is `TicketLog`'s job; the ticket
  keeps only `current_level` (where it is now).
- **Child data** — location fields, rating/feedback. Those are `TicketLocation` and `TicketFeedback`.

What remains is the lean core (~15 fields): identity (`ticket_no`), routing/priority FKs (`raised_by`,
`requester_campus`, `service_item`, `section`, `priority`, `assigned_to`), current position
(`status`, `current_level`), and the live SLA clock (`response_due_at`, `resolution_due_at`,
`paused_at`, `accumulated_pause`, `created_at`, `updated_at`, `resolved_at`, `closed_at`).

**N+1 discipline (acceptance criterion).** Read serializers MUST `select_related` the FKs
(`section__campus_department`, `priority`, `assigned_to`, `service_item__service_category`) and
`prefetch_related` the children (comments, logs). The list and detail tests MUST assert a bounded
query count (`assertNumQueries`).

### 3.3 Business logic (services — keep out of views)

- **Routing resolver** (`tickets/services/routing.py`): `(requester_campus, service_item)` →
  handling `Section` + its `hos` + `campus_department.hod`. Requester campus comes from
  `request.user.profile.campus`, not the requester's department (R15).
  ```sql
  SELECT s.id AS section_id, s.hos_id, cd.hod_id
  FROM   catalog_serviceitem si
  JOIN   catalog_servicecategory sc ON sc.id = si.service_category_id
  JOIN   org_section s              ON s.section_type_id = sc.section_type_id AND s.is_active
  JOIN   org_campusdepartment cd    ON cd.id = s.campus_department_id
  WHERE  si.id = :service_item_id AND cd.campus_id = :requester_campus_id;
  ```
- **Catalogue filter** (`catalog/services/visibility.py`): only categories/items whose section type
  is active at the requester's campus (R5).
- **Priority resolver:** `item.default_priority or item.service_category.default_priority` (R7).
- **Status service** (`tickets/services/lifecycle.py`): validates §4, requires reason on `pending`,
  maintains `paused_at`/`accumulated_pause`/timestamps, writes `TicketLog`.
- **SLA + escalation engine** (`sla/services/escalation.py`): computes timers at create; the
  scheduled job advances `current_level`, skips vacant rungs, ignores resolved/closed, snapshots the
  owner, honours `accumulated_pause` (R9/R10).
- **Location validator** (`facilities/validators.py`): validates `values` against the chosen facility
  type's known field set, including the building dropdown (the referenced `Facility` must exist and
  match the requester's campus + type → hoisted to `TicketLocation.facility`).
- **Transfer handler** (`org/services/transfer.py`): re-home open tickets on role/membership change (R12).

### 3.4 Serializers (DRF)

`<Model>Serializer`; split read/write where they differ.
- **org/catalog/sla/facilities:** `ServiceCategorySerializer` derives `department` read-only via
  section type (R4); `FacilityTypeSerializer` (name/code); `FacilitySerializer` campus-scoped.
- **tickets:**
  - `TicketCreateSerializer` — accepts `service_item` (+ optional `location`); **ignores client
    priority/section/level**; resolves section + priority server-side (R6/R7); validates `location`
    for the chosen facility type (R13). Fields: `["service_item", "location", "description"]` only.
  - `TicketReadSerializer` — nested item/category/section/priority/assignee, SLA timers, derived
    `is_breaching`; **role-aware** (hides internal comments/fields from requesters).
  - `TicketStatusUpdateSerializer` (transition + reason), `TicketAssignSerializer` (pool-only),
    `TicketPrioritySerializer` (HOS+), `TicketLogSerializer` (RO), `TicketCommentSerializer`
    (visibility-aware), `TicketFeedbackSerializer`.

### 3.5 Permissions

Group-based coarse gating + object checks: technician → `assigned_to == self` or `section in
self.sections`; HOS → `section.hos == self`; HOD → `section.campus_department.hod == self`; Manager
→ department across campuses; Admin → all. **Requester scope is universal** (`raised_by == self`),
available to every user regardless of operational role (R15).

### 3.6 Authentication — JWT (access + refresh), shared with WebSockets

- **JWT** (e.g. SimpleJWT). REST: `Authorization: Bearer <access>`. Short-lived access + rotating
  refresh; `POST /auth/login/`, `POST /auth/refresh/`, `POST /auth/logout/` (blacklist).
- **Claims:** `sub` (user id), `role` (active operational role), scope ids (`campus_id`, and
  `department_id`/`section_id` where applicable) — lets the WS layer and permission checks read scope
  without a DB hit.
- **WebSockets (Channels):** the **same access token** authenticates the WS handshake (query param
  `?token=` or subprotocol); ASGI middleware validates it and sets `scope["user"]`. One credential
  authenticates both REST and WS.
- **Role cover / switch:** the JWT's `role` + scope claims reflect the user's **currently active**
  assignment. A user with more than one active role (their standing role plus a temporary cover, §3.8)
  calls `POST /auth/switch-role/` to re-issue the access token for the chosen role; the client
  reconnects WS so channel subscriptions match. `GET /auth/me/` lists all active assignments so the
  client can render a role/context switcher.

### 3.7 Pagination — by whether the list is re-ordered by activity

The dividing line is whether a list gets re-ordered as tickets are worked. That determines whether
cursor pagination is safe — a cursor bookmarks a position in an ordering, so if the ordering key
changes under it, cursors duplicate or skip rows.

- **Ticket feed → PageNumber, ordered `-updated_at`.** A service desk queue is **activity-first**:
  the ticket just commented on / reassigned / status-changed should surface first, not the
  newest-created-but-quiet one. Activity ordering means the sort key (`updated_at`) moves constantly,
  which rules out cursor — so the ticket feed uses `PageNumberPagination`
  (`{ count, next, previous, results }`). PageNumber re-sorts each request, so a moving key is fine,
  and you keep totals and jump-to-page, which agents and admins use.
- **Append-only feeds → cursor, ordered `-created_at`.** `/tickets/{id}/logs/`,
  `/tickets/{id}/comments/`, `/admin/audit-log/` are append-only: a row's `created_at` never changes,
  so the cursor bookmark is always valid. They can grow long and are read start-to-finish — cursor's
  sweet spot. Envelope: `{ results, meta: { nextCursor, prevCursor, total } }`, ordered `-created_at`
  tie-broken by `id`.
- **Config lists → PageNumber.** Short admin reference lists (`/campuses/`, `/departments/`,
  `/sections/`, `/priorities/`, `/facility-types/`, `/facilities/`, `/users/`) — jump-to-page is more
  useful than a cursor.
- **Frontend impact:** the ticket queue and config tables use page-number controls (and show totals);
  log/comment/audit timelines use next/prev cursors (and may show `meta.total`).

### 3.8 Role assignments & leave cover (`RoleAssignment`)

The attributed alternative to sharing a password. A `RoleAssignment` grants a user an operational
role, optionally time-boxed:

```python
# accounts/models.py
class RoleAssignment(models.Model):
    ROLE = [("technician","Technician"),("hos","HOS"),("hod","HOD"),
            ("manager","Manager"),("admin","Admin")]
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="role_assignments")
    role        = models.CharField(max_length=12, choices=ROLE)
    # scope (nullable by role): technician/hos need section; hod needs campus_department; manager needs department
    section            = models.ForeignKey("org.Section", null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    campus_department  = models.ForeignKey("org.CampusDepartment", null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    department         = models.ForeignKey("org.Department", null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    is_primary  = models.BooleanField(default=False)   # the user's standing role
    valid_from  = models.DateTimeField(null=True, blank=True)   # null = effective now
    valid_until = models.DateTimeField(null=True, blank=True)   # null = standing role; set = cover window
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    assigned_at = models.DateTimeField(auto_now_add=True)

    def is_active(self, now=None):
        now = now or timezone.now()
        return (self.valid_from is None or self.valid_from <= now) and \
               (self.valid_until is None or self.valid_until > now)

    def clean(self):
        # Per-role scope rules live here (one readable, testable place): technician/hos require
        # section; hod requires campus_department; manager requires department; admin requires none.
        ...
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user"], condition=models.Q(is_primary=True),
                                    name="one_primary_role_per_user"),
        ]
```

- **Source of truth.** `RoleAssignment` is authoritative for a user's role; `User.role` derives from
  the active primary assignment. Scope validation lives in `clean()`/serializer, not per-role DB
  `CheckConstraint`s.
- **Active-holder resolution.** "Who is HOS of this section right now" = the active
  `RoleAssignment(role=hos, section=...)` if one exists, else the standing `Section.hos`. Same for HOD
  via `CampusDepartment.hod`.
- **Attribution (R17).** Actions are logged as the acting user + the role they acted in. No shared
  credential ever.
- **Expiry is automatic.** When `valid_until` passes, the assignment stops granting anything on the
  next request — no manual revocation.
- **Authorisation.** Only HOD/admin may create a cover assignment within their scope; `assigned_by`
  records who.

---

## 4. Ticket lifecycle, SLA & escalation

### 4.1 Status machine

```
open ─assign→ assigned ─start→ in_progress ─resolve→ resolved ─close→ closed
                                   │  ▲                                  │
                              hold │  │ resume                           │ reopen
                                   ▼  │                                  ▼
                                pending ──────────────────────────► in_progress
```

Allowed (else → 400): `open→assigned`, `assigned→in_progress`, `in_progress→pending`,
`pending→in_progress`, `in_progress→resolved`, `resolved→closed`, `resolved→in_progress` (reopen),
`closed→in_progress` (reopen). `pending` requires a reason (R8). There is **no approval/redirect
transition and no `escalated` status** — escalation is the `current_level` axis (§4.3).

### 4.2 SLA

On create: `response_due_at = created_at + priority.response_minutes`; `resolution_due_at =
created_at + priority.resolution_minutes`. Entering `pending`: set `paused_at`. Leaving: add the
paused span to `accumulated_pause`, shift both due timestamps by it, clear `paused_at` (R9). Response
vs resolution tracked independently.

### 4.3 Escalation

`current_level` starts at `technician` (R7). The engine reads `EscalationRule` for the ticket's
priority; when the active clock (excluding `accumulated_pause`) passes a rung threshold and the ticket
isn't resolved/closed, it advances `current_level` to that rung's `to_level`, **skipping a vacant
seat** (empty HOS → HOD), and writes an `escalated` `TicketLog` snapshotting the new owner (R10).
Status and `current_level` are **independent axes**.

**Active-holder resolution (R17).** "The HOS"/"the HOD" for escalation and assignment is the active
cover `RoleAssignment` for that scope if one exists (§3.8), else the standing `Section.hos` /
`CampusDepartment.hod`. So when the HOS is on leave and a senior technician holds a cover assignment,
escalations and the log's `level_user` point to the **covering technician**. A seat with neither a
standing holder nor active cover is "vacant" and the engine skips it.

> **Reference implementations provided:** `apps/sla/services/escalation.py` (engine),
> `apps/sla/management/commands/run_escalations.py`, `apps/tickets/services/lifecycle.py` (status +
> pause accounting), `apps/facilities/validators.py` (per-type location validation), with tests —
> they encode paused time, vacant rungs, immutable log snapshots, and per-type location validation.

---

## 5. API surface

REST via DRF routers, base `/api/v1/`. Auth = JWT Bearer (§3.6). Pagination per §3.7 (ticket feed
PageNumber/`-updated_at`; append-only feeds cursor/`-created_at`; config lists PageNumber). All ticket
lists are role-scoped server-side (§3.5).

### 5.1 Auth
`POST /auth/login/` · `POST /auth/refresh/` · `POST /auth/logout/` · `GET /auth/me/` (profile + role
+ scope + active role assignments) · `POST /auth/switch-role/` (re-issue access token for another
active role, §3.8). Admin role-cover CRUD: `POST /users/{id}/role-assignments/`, `PATCH`/`DELETE
/users/{id}/role-assignments/{ra}/` (HOD/admin within scope).

### 5.2 Configuration / admin (admin role)
CRUD: `/campuses/`, `/departments/` (`?campus=` scopes to departments present at that campus — C15),
`/section-types/`, `/campus-departments/`, `/sections/` (`?department=` scopes to that department's
sections — C15), `/sections/{id}/technicians/`, `/priorities/` & `/priorities/{id}/escalation-rules/`,
`/facility-types/` (read-mostly; fixed set), `/facilities/`, `/service-categories/`, `/service-items/`.

### 5.3 Ticketing

| Method | Path | Roles | Purpose |
|--------|------|-------|---------|
| GET | `/catalog/?campus=` | any user | Campus-filtered category→item tree (R5) |
| GET | `/facilities/?campus=&facility_type=` | any user | Buildings for the location dropdown |
| POST | `/tickets/` | any user | Create (server resolves section + priority) — **`service_item` (+location) only** |
| GET | `/tickets/` | scoped | Role-scoped list (PageNumber, ordered `-updated_at`; filters: status, priority, section, campus, `current_level`, breaching) |
| GET | `/tickets/?mine=1` | any user | **My Requests** — tickets I raised (requester context, §1.2) |
| GET | `/tickets/{id}/` | scoped | Detail + merged timeline (visibility-aware) |
| POST | `/tickets/{id}/status/` | technician+ | Transition (+reason for `pending`) |
| POST | `/tickets/{id}/assign/` | hos/hod | Assign/reassign within section pool |
| POST | `/tickets/{id}/priority/` | hos+ | Adjust priority (never requester) |
| GET/POST | `/tickets/{id}/comments/` | scoped | Comments (internal hidden from requester; cursor, `-created_at`) |
| POST | `/tickets/{id}/feedback/` | requester | Rate (once, at/after resolved) |
| GET | `/tickets/{id}/logs/` | staff | Immutable audit (cursor, `-created_at`) |

### 5.4 Analytics (read-only, role-scoped) — Phase 7

All aggregates are computed **server-side**; the client never computes compliance or aggregates.
Every endpoint accepts `date_from` / `date_to` (ISO date) plus a `days` shortcut; default window =
last 30 days, filtered on `created_at`. Every headline number also returns a **delta vs the prior
equal window** so the UI can show trend without a second call.

**Architecture — one aggregation core, role presets over it.** A single service,
`aggregate(scoped_queryset, date_range, group_by) → metrics`, computes everything below. Each role
endpoint is a thin preset that supplies (a) a correctly **scoped queryset** (from the Phase 6 scope
resolver — see below) and (b) a `group_by` dimension. Do **not** re-derive counts per role/module —
that was the old code's cardinal failure (nine modules, one ghost field broke them all, and
dashboard vs analytics numbers silently disagreed). One core means a field rename is a one-line fix
and the technician's two views are just two calls with different scope.

> **Hard dependency (Phase 6 must land first).** Analytics aggregates over an already-correctly-
> scoped queryset and must never re-implement scope. Phase 6's `apply_ticket_scope` must: traverse
> `section__campus_department__…` (there is **no** `Ticket.campus_department`); **fail closed** —
> return `none()` for a non-admin whose scope can't be resolved, never the unfiltered set; use one
> JWT claim casing end-to-end; honour `RoleAssignment.is_active()` so cover assignments scope
> correctly; and read `role` from the active assignment, not a stale login-time claim or a
> `filter(role=…)` on the `@property`.

#### Metric definitions (computed once in the core, in new-model terms)

**Volume & flow** — *open backlog* (count where `status in open/assigned/in_progress/pending`, at
now); *created* / *resolved* (by `created_at` / `resolved_at` in window); **net flow** (created −
resolved, per day for the trend — the leading health indicator: positive = queue growing); *status
distribution*; *priority distribution* (by `priority` name).

**Timeliness (SLA family)** — *response-SLA compliance %* (share of tickets first acted on in window
with first-response ≤ `response_due_at`; first-response = first `TicketLog` event off `open`);
*resolution-SLA compliance %* (share resolved with `resolved_at ≤ resolution_due_at`). The due
timestamps already exclude paused time (R9) — breach checks use the **shifted** due value, never
`created_at + minutes`. *Time-to-first-response* and *time-to-resolution* reported as **p50 and
p90** (not mean); resolution time = `resolved_at − created_at − accumulated_pause`. *At-risk*
(open, `now > resolution_due_at − threshold`, not breached). *Breached* (past `resolution_due_at`).

**Workload & escalation** — *open load per technician* (by `assigned_to`); *escalation rate* (share
with `current_level != technician`); *reassignment rate*. Escalation/breach **attribution** is to
the level the ticket was at when the clock passed the threshold, read from `TicketLog.level_user` —
never the original technician.

**Quality** — *CSAT* (`avg(TicketFeedback.rating)` + feedback response rate = feedback/resolved);
*reopen rate* (share of resolved tickets with a later `reopened` event — catches "fast but wrong").

**Demand shape (strategic)** — volume grouped by *service category/item*, *facility type*, *campus*,
*section_type*. Answers "what is requested, and where" — drives staffing/facilities decisions.

#### Role → scope → what they see

One question per widget, matched to what the role can act on. Scope = the queryset filter.

| Role | Scope filter | Metrics surfaced |
|------|-------------|------------------|
| **Requester** (any user) | `raised_by == self` | own open/resolved counts, per-ticket status, feedback prompt on resolved. No SLA internals, no team metrics. |
| **Technician — individual** | `assigned_to == self` | my open load, resolved (today/week/month), my p50/p90 resolution, my CSAT, my at-risk/breached. (My-Tickets stats + half of analytics.) |
| **Technician — sectional (read-only)** | `section in my sections` | section backlog, net-flow, unassigned count — context only, kept in **separate response keys** so it's never shown as the tech's own performance. (Main-dashboard quick-stats + other half of analytics.) |
| **HOS** | sections where `hos == self` (active-holder resolved, R17) | section SLA compliance, per-technician workload + performance (fairness), escalations at HOS level, reopen rate, unassigned + at-risk actionables. |
| **HOD** | `section__campus_department == mine`, grouped **by section** | section-vs-section comparison, dept SLA compliance + net-flow, escalations at HOD level, technician rollup across sections, demand shape by category. |
| **Manager** | their `Department` across all campuses, grouped **by campus** | campus-vs-campus comparison (compliance, volume, resolution p90), dept-wide trend, demand shape by campus + category. Comparative/trended, no single-ticket actionables. |
| **Admin** | unfiltered | org-wide overview (all of the above unscoped) + config-health signals (sections with no HOS, priorities with no escalation rule, unused facility types). |

#### Endpoints

`/analytics/overview/` (role-scoped summary — the dashboard preset, default window),
`/analytics/sla-compliance/`, `/analytics/resolution-times/` (p50/p90), `/analytics/flow/`
(created/resolved/net + trend), `/analytics/quality/` (CSAT + reopen), `/analytics/demand/` (by
category/facility/campus), and `/analytics/performance/{technicians,sections,campus-departments}/`.
Each respects the caller's scope from the table above. **The four service-desk-health headlines** —
SLA compliance (response + resolution), net flow / backlog, CSAT, reopen rate — anchor every role's
overview; the rest are diagnostic drill-ins.

> **`?user_id=` impersonation** (admin viewing a specific user's dashboard) is **admin-only and
> logged**; for any non-admin caller it is ignored. Decide at build time whether v1 needs it — if
> not, omit it rather than leave a scope-bypass surface.

> **Cheap paths for breakdown-only endpoints (perf, remote DB).** `aggregate()` fires ~20+ queries
> to compute the full headline KPI set. Endpoints that need *only* a group-by breakdown
> (`/analytics/performance/{sections,campus-departments,technicians}/`) must **not** call
> `aggregate()` — they call `breakdown(scoped_qs, date_range, group_by)`, which applies the same
> `created_at` window and runs just the group-by (numbers match the full path exactly). Live
> open-load per technician is `technician_load(scoped_qs)` — one query, no date window;
> `aggregate()` itself reuses it for its headline `technician_load`. Against a remote Postgres
> (Neon) the difference is one round-trip vs dozens; calling the full core on these endpoints
> previously caused request timeouts (500s) under concurrent dashboard loads. `aggregate()` itself
> folds the headline scalars into a single conditional-`Count(filter=Q(...))` pass over the scoped
> queryset (safe — direct `Ticket` columns only, no join fan-out).

### 5.5 Reports (read-only, role-scoped, Excel export) — Phase 9

Role-scoped Excel workbook export. Every report includes a **Summary sheet** that mirrors the analytics
overview (same metrics: open backlog, SLA %, CSAT, resolution p50/p90) so the downloaded file is always
consistent with what the dashboard shows. Rows are sorted/pivot-ready.

**Endpoints:**
```
GET /reports/types/
  Returns: {
    report_types: [
      {id, name, description, filters: [date_range, ...], columns: [...]},
      ...
    ],
    timeframe_options: [
      {value, label},  # "all", "day", "week", "month", "quarter", "year"
    ]
  }
  Auth: authenticated (technician+)

GET /reports/generate/?report_type=X&timeframe=Y&[start_date=]&[end_date=]&[section_id=]&[technician_id=]
  Query params:
    report_type (required): "ticket-lifecycle" | "technician-performance" | "facility-health" |
                           "pending-analysis" | "comprehensive"
    timeframe: "all" (default 30d) | "day" | "week" | "month" | "quarter" | "year"
    start_date, end_date (optional, format YYYY-MM-DD): custom range (overrides timeframe)
    section_id (optional): filter to one section
    technician_id (optional): filter to one technician's assigned tickets
  Returns: Excel workbook (application/vnd.openxmlformats-officedocument.spreadsheetml.sheet)
           Content-Disposition: attachment; filename="[type]_report.xlsx"
  Auth: authenticated; scope enforced server-side via scoped_ticket_qs()
```

**Available report types:**

| ID | Name | Summary + Sheets | Visible to | Notes |
|----|------|------------------|-----------|-------|
| ticket-lifecycle | Ticket Lifecycle Report | Summary (30d) + Ticket Audit Trail | Admin, Manager, HOD, HOS | All tickets + full lifecycle (created, status, assigned, resolved, closed, paused duration) |
| technician-performance | Technician Performance Report | Summary (30d) + Technician Metrics | Admin, Manager, HOD, HOS; Technician sees self only | Per-technician: total assigned, open, resolved, escalated, avg resolution time |
| facility-health | Facility Health Report | Summary (30d) + Facility Breakdown | Admin, Manager, HOD, HOS | Volume grouped by service category × facility type |
| pending-analysis | Pending Tickets Analysis | Summary (30d) + Pending Tickets | Admin, Manager, HOD, HOS | All pending tickets + pause durations + priorities |
| comprehensive | Comprehensive Report | Summary (30d) + all 4 sheets above | Admin, Manager, HOD, HOS | Full workbook — Lifecycle, Technician, Facility, Pending in one download |

**Scope enforcement:**

- **Backend:** `scoped_ticket_qs(user, role)` filters all report data to the caller's scope (same as analytics)
  - Admin sees org-wide
  - Manager sees their department (all campuses)
  - HOD sees their campus department
  - HOS sees their section(s)
  - Technician sees own assigned tickets; if `technician_id` param is passed, it's ignored (tech only sees self)

- **Frontend:** `GenerateReports.tsx` reads role from auth store and shows only relevant types per role
  - Technician: 3 types (lifecycle, "My Performance Report", pending)
  - HOS: 5 types (with "Technician Performance" → "My Team Performance Report")
  - HOD, Manager, Admin: all 5 types
  - Scope badge at top of form says "Your Department — all campuses" (manager) or "Your Section(s)" (HOS), etc.
  - Technician's performance report auto-injects `technician_id=self` in the request

**Summary sheet metrics** (same as analytics overview):
- Open backlog (live count, not windowed)
- Created in window
- Resolved in window
- Net flow (created − resolved)
- Resolution SLA % (met / with due)
- Response SLA % (met / with due)
- At-risk tickets
- Breached tickets
- CSAT (if feedback exists)
- Reopen rate
- Escalation rate
- Resolution p50 and p90 (not means; Python-side percentile to support any DB)

**Time defaults:**
- User selects `timeframe` or custom `start_date` / `end_date`
- If `timeframe=all`, Summary sheet defaults to 30d (matching dashboard preset); data sheets include all
- Date filtering applies to ticket `created_at` (window); for resolved counts, uses `resolved_at` window
- Prior-window (for delta) is auto-derived (same span before the window)

**Excel styling:**
- Sheet 1 is Summary (key-value pairs in two columns, styled header)
- Data sheets have: header row (blue fill, white bold font), alternating row colors, frozen header pane
- Numeric columns centered; string columns left-aligned; percentages formatted as "XX.X%"
- Auto-width per column; text wrapping on description/action columns
- All sheets are pivot-table-ready (no merged cells in data ranges)

### 5.7 Realtime (Channels)
WS authenticated by the JWT access token (§3.6). Channels: `user:{id}` (always — covers My Requests),
plus `section:{id}` / `campus_department:{id}` per active role, and `ticket:{id}` (transient on a
detail page). Emit on: create, assign, status change, escalation (`current_level`), priority change,
new comment, SLA breach.

---

## 6. Frontend reconciliation (summary; detail in CLAUDE.md)

- **Create flow** driven by the campus-filtered catalogue tree (`GET /catalog/`); payload is
  `service_item` (+ optional location) only.
- **Location form is a hardcoded per-type form** (§9.4): on `category.location_details`, the user
  picks a facility type and the wizard shows that type's dedicated form (a switch over the fixed type
  set). Building-dropdown types (office_block, building) load `Facility` rows for the campus; other
  types are plain inputs. No dynamic schema renderer.
- **Server-owned** routing/priority/SLA/escalation; no client-side computation.
- **`pending`** is the paused status (label "Pending"); **no `escalated` status** (use
  `current_level`); **no approve/reject**.
- **JWT Bearer** auth with refresh; WS authenticated by the same token.
- **Pagination per §3.7:** ticket queue PageNumber ordered `-updated_at` (recently-touched first);
  log/comment/audit timelines cursor.
- Merged timeline (logs + comments + feedback), internal comments hidden from requesters.
- One shared role-scoped ticket table; analytics widgets bound to `/analytics/*` (§5.4).
- **Role-scoped reports** (§5.5): Excel export with Summary + data sheets; role-aware type filtering
  in `GenerateReports.tsx`; technician's performance report auto-scopes to self.
- A **context switch** between Staff workspace and My Requests for staff users (§1.2), and an
  operational-role switcher shown only when the user has more than one active role (cover, §3.8).

### 6.1 Shared role-scoped pages (Admin = canonical template)

The Admin Dashboard / Analytics / Reports are the canonical UI; every other role **reuses the same
components, scope-varied** (§1.3) — not bespoke per-role pages. Implemented as three shared
`role`-parametrized views in `features/shared/` (`RoleDashboardView`, `RoleAnalyticsView`,
`RoleReportsPage`); Admin and Manager pages are thin wrappers over them. The role-specific surface is
only StatCards + titles + ticket-table role (+ a few role-gated blocks, e.g. Manager's Campus
Performance). Reusable, self-fetching data components live in `components/shared/data/`
(`DistributionCharts` = generic donut + volume bar; `ServiceHealthCards`; `InsightsPanel`; StatCards
stack) — extend these rather than re-implementing per role. *(Manager is fully migrated; HOD/HOS
report/analytics still use the older unified-envelope `AnalyticsView`; the HOD/HOS migration to the
three shared views — plus section-scoped dashboard charts and recent-tickets — is the remaining
pass.)*

> **Scope-by-role invariant (frontend mirror of §3.5).** Every chart, table, distribution, and KPI on
> dashboards / analytics / reports renders data for the **caller's scope** — campus / departmental /
> sectional / technician — derived **server-side from the JWT**, never from client params. The same
> shared component therefore serves each role: Admin = org-wide, Manager = department across campuses,
> HOD = campus-department (its sections), HOS = section(s)/technicians, Technician = own. Pick the
> role-appropriate endpoint / `group_by`; the backend fails closed (§5.4).

---

## 7. Phased execution plan

Run tests + migrations at the end of each backend phase.

- **Phase 0 — Audit (no changes):** produce `AUDIT.md` (routes/components/API inventory + mapping +
  invariant violations + keep/modify/add/remove). Inspect the backend file structure and **decide the
  app split** (§3.1), recording the chosen layout and rationale. This decision is made here because
  the fresh migration reset makes the layout free to pick now and costly to change later.
- **Phase 1 — Models, auth, fresh migrations:** implement §3.2 models + constraints (R1/R3) +
  validators (R2) + immutable `TicketLog` (R11) + `RoleAssignment` (§3.8) into the chosen layout; set
  up JWT auth (§3.6); reset migrations and build clean (§8); seed facility types (fixed set),
  priorities + escalation rules.
- **Phase 2 — Serializers & config/catalogue APIs:** admin CRUD (§5.2) + catalogue tree with campus
  filter (R5); pagination per §3.7 (ticket feed PageNumber/`-updated_at`; append-only feeds
  cursor/`-created_at`; config lists PageNumber); group permissions.
- **Phase 3 — Create, routing & location:** `TicketCreateSerializer` + routing (R6) + priority
  resolver (R7) + per-type location validation incl. the building dropdown (R13); `ticket_no`
  generation.
- **Phase 4 — Lifecycle, comments, feedback, logs:** status service (reason on `pending`, R8);
  pool-only assign; comments (visibility) + feedback (once, resolved+); every action logs (R11).
- **Phase 5 — SLA engine & escalation job:** timers at create; pause/resume on `pending` (R9);
  escalation worker (R10) with active-holder resolution (R17); transfer handler (R12).
- **Phase 6 — Permissions, role-scoped reads, requester & role cover:** object scoping (§3.5);
  `?mine=1` My Requests for every user (R15); `RoleAssignment` cover CRUD + `switch-role` +
  active-holder resolution honoured in scoping/assignment/escalation (§3.8, R17). **Harden the
  scope resolver (`apply_ticket_scope` + JWT plumbing) — this is a prerequisite for Phase 7 and a
  data-safety fix:** (a) traverse `section__campus_department__…` everywhere (there is no
  `Ticket.campus_department`); (b) **fail closed** — a non-admin whose scope can't be resolved gets
  `none()`, never the unfiltered queryset; (c) one JWT claim casing end-to-end (issuance, refresh
  rotation, reader — the audit found snake/camel mismatch silently dropping scope on refresh);
  (d) honour `RoleAssignment.is_active()` (cover windows); (e) read `role` from the active
  assignment, never `filter(role=…)` on the `@property`; (f) use the real field names (`hos` not
  `head_of_section`, `section_type.name` not `section.name`). *Acceptance includes a negative test
  per scope boundary (HOD A sees zero of campus-dept B; technician individual ⊂ sectional) and a
  test that an unresolved scope returns empty, not everything.*
- **Phase 7 — Analytics endpoints (§5.4):** **rebuild, don't reconcile** — the existing
  `api/analytics/*` modules are on dead fields (`escalation_level`, `Ticket.campus_department`,
  `Section.name/code`, `due_date`, `title`, `pending_reason`, `Ticket.facility`) and two won't even
  import; mine them only as the per-role **metric list**, then write fresh. Build **one
  `aggregate(scoped_qs, date_range, group_by)` core**; role endpoints are presets over it (no
  per-role re-derivation). Implement the metric catalogue and role/scope table in §5.4, paused-aware
  SLA (R9), p50/p90 (not means), `current_level` attribution via `TicketLog.level_user`, and the
  added metrics (net flow, reopen rate, first-response, at-risk, demand shape). Date range on every
  endpoint (default 30 days) + delta vs prior window. *Acceptance: numbers reconcile against raw
  querysets; dashboard preset == analytics for the same scope+window; paused ticket not counted
  breached; date-range filter excludes out-of-window; every scope boundary has a negative test.*
- **Phase 8 — Frontend reconciliation:** dashboards on the shared table; per-type location create
  flow; context switch; JWT wiring; ticket-list pagination (PageNumber/`-updated_at`) + cursor
  timelines; merged timeline; analytics bound to §5.4.
- **Phase 9 — Reports & role-scoped exports (§5.5):** Implement `GenerateReportView` and `ReportTypesView`
  with 5 report types (ticket-lifecycle, technician-performance, facility-health, pending-analysis,
  comprehensive). Each report includes a Summary sheet (metrics matching analytics overview) and
  data sheets (styled, pivot-ready Excel). Backend scope enforced via `scoped_ticket_qs()`; frontend
  role-aware filtering in `GenerateReports.tsx` (technician sees "My Performance", others see role-scoped types).
  Acceptance: all 5 report types generate without error; Summary sheet metrics reconcile with analytics;
  scope boundaries respected (technician only exports self, HOD only exports campus-dept, etc.);
  Excel is properly styled and pivot-compatible.
- **Phase 10 — Cleanup & removal:** delete dead/superseded code (approve/reject, client-side SLA,
  per-campus workflow, duplicate tables, legacy location/escalation fields).
- **Phase 11 — Fresh schema, seed & test:** since data is fixtures, **no legacy backfill** — reset
  migrations, recreate from the aligned models, run seeds (facility types, priorities + rules, demo
  org tree, sample tickets incl. some at `hos`/`hod` level, one `pending`, and one active HOS cover
  assignment). Run the full test suite (R1–R17 + escalation edge cases) and E2E role +
  requester-context + leave-cover walkthroughs. All reports generate and download correctly across all roles.

---

## 8. Cross-cutting notes

- **Fresh start (no legacy migration):** current data is fake/fixture. Reset migrations and rebuild
  from the aligned models — do not write backfill scripts.
  ```bash
  find . -path "*/migrations/*.py" -not -name "__init__.py" -delete
  find . -path "*/migrations/*.pyc" -delete
  # sqlite: rm -f db.sqlite3   |   postgres: dropdb resolver_dev && createdb resolver_dev
  python manage.py makemigrations && python manage.py migrate
  python manage.py seed_full
  ```
  `seed_full` (in `apps/common/management/commands/seed_full.py`) replaces the three separate
  `seed_reference` / `seed_org` / `seed_demo` commands. It is idempotent (get-or-create throughout)
  and seeds: Priorities, EscalationRules, FacilityTypes (5), **Facilities (18 buildings across NRB/MSA/KSM)**,
  Campuses, Departments, Sections, Users, RoleAssignments, Service Catalogue, and 30 demo tickets.
- **Idempotent seeds:** facility types, priorities, escalation rules, facilities — get-or-create by natural key.
- **`pending` semantics:** the paused state means "work paused, SLA frozen, waiting on something."
  Distinct `open`/`assigned` states already cover the early stages, so `pending` is unambiguous. Keep
  it a single paused state for v1; split into "awaiting requester" vs "awaiting parts" only if a real
  need appears.
- **Decision summary:** priority/SLA/escalation are three independent knobs; the org structure *is*
  the workflow; configuration drives behaviour (§1.1, §9), with location form fields the one fixed-in-
  code exception (§9.4); requester is universal (§1.2); role cover is attributed and time-boxed (§3.8);
  JWT carries role+scope and authenticates WS; pagination splits by activity (ticket feed
  PageNumber/`-updated_at`, append-only feeds cursor/`-created_at`); `RoleAssignment` is the role
  source of truth; `Ticket` holds only intrinsic current state (§3.2a).
- **Naming:** the ticket's raiser field is `raised_by`. "Requester" is the role/capability word
  (universal-requester concept, R15), not a model field. `requester_campus` is the campus the request
  is for.

---

## 9. Admin configuration & the config-driven contract

What an admin sets up, and the runtime behaviour each setting drives. The frontend reads the same
configuration and renders from it — so admin changes flow through without code changes.

### 9.1 Organisation → routing & escalation occupants
Admin builds: campuses; departments (+ manager); section types per department; campus departments
(+ HOD); sections (campus instance of a section type, + HOS, R2/R3); technician pools
(`SectionTechnician`). **Drives:** which section a ticket routes to (R6); who occupies each escalation
rung (R10); who can be assigned (the section pool).

### 9.2 Service catalogue → what can be requested & where it goes
Admin builds: service categories (each tied to a **section type**, with `location_details` and a
default priority) → service items (optional priority override). **Drives:** the campus-filtered
catalogue the requester sees (R5); the routing target via the category's section type (R6); the
ticket's server-set priority (R7). No department field on categories (R4).

### 9.3 Priorities & escalation rules → SLA timing & escalation
Admin builds: priorities (`response_minutes`, `resolution_minutes`, `rank`) and per-priority
escalation rungs (`to_level` ∈ {hos, hod}, `threshold_minutes`). **Drives:** SLA due timestamps at
create (§4.2); when/where a ticket escalates (§4.3).

### 9.4 Facility types → the location form (hardcoded per type)
The facility types are a **small fixed set**, so the location form is **hardcoded per type** — one
dedicated form component per type, selected by `facility_type.code`. There is no dynamic schema.
Adding a type later (e.g. `hostel`) means adding one form component and one enum/seed row — a small
reviewed code change, not a runtime config action.

| type `code` | covers | fields (✱ = required) | DB shape |
|-------------|--------|------------------------|----------|
| `office_block` | officer offices | building✱ (dropdown), floor✱, room✱, area | `facility` = building; `values`: floor, room, area |
| `building` | laundries, kitchens, utility blocks | building✱ (dropdown), area✱, room | `facility` = building; `values`: area, room |
| `equipment` | generators, printers, assets | asset_name✱, asset_id, description | `values`: asset_name, asset_id, description |
| `residential` | staff houses | unit_number✱, tenant_name | `values`: unit_number, tenant_name |
| `grounds` | fields, fences, open areas | zone✱, landmark | `values`: zone, landmark |
| `hostel` *(future)* | accommodation | block✱, room✱ *(define when added)* | `facility`? + `values` |

**Where each piece lives:** the *type set and its field shapes* live in **code** (they change rarely,
with a deploy). The *buildings* (`Facility` rows) live in the **database** and are admin-managed —
that's the thing that changes often. Building-dropdown types (`office_block`, `building`) load
`Facility` rows via `GET /facilities/?campus=&facility_type=` and store the chosen one in
`TicketLocation.facility`; everything else goes in `TicketLocation.values`.

**Capture flow (frontend):** category has `location_details` → show the location section → user picks
a facility type → the matching hardcoded form renders → on submit send `{ facility_type_id,
facility_id?, values }`. **Backend** checks `values` carries the expected keys for that type and that
any building `Facility` matches the requester's campus + chosen type (R13).

---

## 10. Role cover & leave (worked example)

The supported answer to "the HOS is on leave — who covers?" is a temporary `RoleAssignment` (§3.8),
not a shared password. It keeps full accountability (R17) and expires on its own.

**Scenario.** Achieng is a senior technician in ICT Support, Nairobi campus. The HOS, Brian, goes on
leave for two weeks; the HOD wants Achieng to run the section meanwhile.

**Setup (HOD action).** `POST /users/{achieng}/role-assignments/` with `{ role: "hos", section: <ICT
Support, NRB>, valid_until: <Brian's return date> }`. `assigned_by` = the HOD. Achieng keeps her
technician assignment; Brian's standing `Section.hos` is untouched.

**During cover.** Achieng logs in with two active roles; the UI shows a switcher (`GET /auth/me/`).
She works tickets as **Technician** and switches to **HOS (covering)** to assign within the pool,
adjust priority, and clear HOS-level escalations. `switch-role` re-issues her token; WS reconnects.
Escalations that would go "to HOS" resolve to **Achieng** (active-holder resolution, §4.3), not
Brian's inbox. Every action is logged as **Achieng** in the **HOS (covering)** role.

**Expiry.** On `valid_until`, the assignment stops granting HOS rights on her next request — no
revocation step, no password to change. Escalations resolve back to Brian automatically.

**Policy note (decide once).** Whether cover *replaces* the standing holder for routing (the default
— active cover wins) or *supplements* them (both notified) is a configuration choice; active-cover-
wins is usually what you want so leave actually offloads the work.

---

## 11. Known implementation corrections (Phase 10 integration)

These rules were discovered during live integration testing with a pure requester account. They
**override any implied behaviour elsewhere in this document** where a conflict exists.

**C1 — No `title` field on Ticket.** The `Ticket` model has no `title` field. The display label
for a ticket is `service_item.name` (fall back to `description`). Never read or render
`ticket.title`.

**C2 — No `/api/v1/users/<id>/` detail endpoint.** `UserViewSet` is not registered; only
`/users/<user_pk>/role-assignments/` exists. The authoritative way to obtain the current user's
full profile is `GET /auth/me/` (`MeView`). The frontend must not call a non-existent user-detail
endpoint; hydrate the auth store from the login-time JWT payload / localStorage profile instead.

**C3 — All main endpoints are under `/api/v1/`.** The `apiClient` base URL must be
`/api/v1` (not `/api`). Auth endpoints (`/auth/login/`, `/auth/refresh/`, `/auth/me/`,
`/auth/switch-role/`) are registered at both `/api/` and `/api/v1/`, so either prefix works for
auth; everything else requires `/api/v1/`.

**C4 — Reference/config endpoints must allow authenticated reads.** `DepartmentViewSet` and
`SectionTypeViewSet` (and any other endpoint the requester UI reads to build the catalogue or
ticket-creation wizard) must use `IsAdminOrReadOnly` — any authenticated user may GET; only admin
may write. Using `IsAdminGroup` on these endpoints breaks the requester flow. The
`SectionTypeViewSet` must also include a `SectionTypeWithCategoriesSerializer` that nests the
related `service_categories` (used by QuickActions and catalogue widgets).

**C5 — Pure requesters (null active role) must see the 'user' workspace.** Every authenticated
user is a requester (R15). Users with no `RoleAssignment` have `role: null` from the JWT.
The sidebar and workspace routing must treat `null` as equivalent to `'user'`; the `/user/*`
route must be accessible to **any authenticated user** regardless of operational role
(`requiredRoles=[]`). Never return `null` from the sidebar for a null role.

**C6 — Login redirect for null-role users must land on `/user`, not `/dashboard`.** The
role-redirect map falls back to `/user` when `role` is null, not to `/dashboard` (which
requires admin). The fallback must be `/user`.

**C7 — Async Channels consumers must never make synchronous ORM calls.** Inside a Django
Channels async consumer, never access ORM properties (including anything that triggers a queryset)
on the user object. Read role/scope data exclusively from `self.scope` (set by the JWT middleware
at WebSocket handshake time). Accessing `user.role` or similar ORM properties in an async consumer
raises `SynchronousOnlyOperation`.

**C8 — `useUserDashboard` must call a real analytics endpoint (not a stub).** The hook must call
`GET /analytics/overview/`, which uses `IsAuthenticated` and automatically scopes results to
`raised_by=user` when the user has no operational role. Map the response: `summary.total` = sum of
all `status_distribution` counts; `summary.open` = `open_backlog`; `summary.pending` =
`status_distribution.find('pending').count`; pass `status_distribution` through directly. Every
role dashboard hook must call a real analytics endpoint. Never leave a dashboard hook returning
`{data: null, loading: false}` — all stat cards will show 0.

**C9 — `flattenJWT` must read `campus_id` from the JWT token payload for null-role users.** The
function `flattenJWT` in `src/lib/api/auth.ts` must not rely solely on `ar?.campusId` for
`primary_campus_id`. When `activeRole` (`ar`) is null (pure requesters with no `RoleAssignment`),
`ar?.campusId` is always null. The JWT access token payload always carries `campus_id` (written by
`build_tokens_for_assignment` from `UserProfile.campus` for every user). The fix: decode the JWT
and use `primary_campus_id: ar?.campusId ?? tokenCampusId ?? null`. Without this, `useCatalog(campusId)`
receives null, disabling the catalogue and leaving the TicketCreationWizard empty.

**C10 — Stale `primary_campus_id: null` in localStorage must be patched on session hydration.**
Fixing `flattenJWT` alone does not help users with existing sessions — their stored profile in
localStorage still has `primary_campus_id: null` from before the fix. `useUserData` must patch
`primary_campus_id` from the stored JWT token claims when the stored value is null, before calling
`setUser()` to hydrate the Zustand store. General rule: when a stored profile field is null but the
corresponding JWT claim has a non-null value, patch it from the token rather than requiring the user
to log out and back in.

**C11 — `_SectionMinSerializer` had no human-readable name (Section column blank).** The serializer
only returned `{id, section_type_id}` — no display name. The frontend `sectionColumn.accessorFn`
read `s?.name`, which was always `undefined`, so the Section column showed blank for every ticket.
Fix: added `section_type_name = CharField(source="section_type.name")` to `_SectionMinSerializer`
in `apps/tickets/serializers.py`. No N+1 — `section__section_type` was already in the queryset's
`select_related`. Frontend updated to read `s?.section_type_name` (with `s?.name` as
backward-compat fallback). Rule: `Ticket.section` is `{id, section_type_id, section_type_name}`.
The Section column must read `section.section_type_name`. Do not add a top-level `name` field to
`_SectionMinSerializer` — the section model has no such field; the display name is always
`section_type.name`.

**C12 — `_overview_slice` omitted `status_distribution` (all stat cards showed 0).** The helper
function that builds every role's `/analytics/overview/` response included `open_backlog`,
`created`, `resolved`, etc. but not `status_distribution`. The frontend `useUserDashboard` summed
`status_distribution` to compute `total`, so `total = 0` for every user and all stat cards showed 0.
Fix: added `"status_distribution": data.get("status_distribution", [])` to `_overview_slice` in
`apps/analytics/views.py`. Rule: `_overview_slice` must always include `status_distribution`; the
frontend uses it to compute the "My Tickets" total and all per-status cards.

**C13 — `useUserDashboard` was fragile to missing `status_distribution`.** The hook computed
`total = dist.reduce(sum)`. If `status_distribution` was absent from the API response, `dist = []`
and `total = 0` permanently, with no indication of why. Fix: added fallback
`total = distTotal > 0 ? distTotal : openBacklog + resolvedCount` in
`src/hooks/dashboard/useUserDashboard.ts`. Rule: dashboard hooks must never produce 0 from a missing
optional field when a reliable fallback exists. Use `open_backlog + resolved` as the fallback for
total ticket count when `status_distribution` is not available.

**C14 — NeonDB cold-start caused `CancelledError` on `/analytics/overview/` (13–19 s first
response).** The direct-env-var database branch in `resolver/settings.py` had no `CONN_MAX_AGE`,
so every request to NeonDB opened a new TCP+TLS+auth connection (~13–19 s). Daphne killed slow
requests and logged `CancelledError`. After the kill the browser re-sent the request and it
eventually succeeded, but React Query sometimes received a network error and left stat cards at
`data=null` indefinitely. Fix: added `CONN_MAX_AGE: 300` and `CONN_HEALTH_CHECKS: True` to the
non-DATABASE_URL branch in `resolver/settings.py`. After the first warm request, subsequent queries
reuse the connection and respond in milliseconds. Rule: both database branches in `settings.py`
must have `CONN_MAX_AGE` set (≥ 60 s for dev, ≥ 300 s for prod). The `DATABASE_URL` branch already
had it via `dj_database_url.config(conn_max_age=600)`. Omitting it on the direct-env-var branch
causes NeonDB cold-start latency that is indistinguishable from application errors.

**C15 — `/departments/?campus=` and `/sections/?department=` accepted their query params but
never applied them.** `DepartmentViewSet` and `SectionViewSet` had no `get_queryset()` override, so
every Campus→Department→Section cascading select in the admin UI (Users page role-assignment form,
Technician form) silently showed every department/section regardless of the selected scope — the
param was accepted, just ignored. Fix: `DepartmentViewSet.get_queryset()` filters by
`campus_departments__campus_id` when `?campus=` is present; `SectionViewSet.get_queryset()` filters
by `campus_department__department_id` when `?department=` is present. Rule: a reference-data
endpoint that documents a scoping query param must apply it in `get_queryset()` — an accepted-but-
ignored param is worse than a missing one, because the URL looks correct while the response isn't.

**C16 — Replacing a user's primary `RoleAssignment` via POST must demote the existing one, not
error.** `UserRoleAssignmentListCreateView` only handled the delete-old-then-create-new path;
posting a new `is_primary=True` assignment directly (the Users admin page's promote/demote flow)
hit the `one_primary_role_per_user` `IntegrityError` instead of replacing it. Fix: when
`is_primary=True`, the view first runs `target.role_assignments.filter(is_primary=True).update(is_primary=False)`
inside `transaction.atomic()`, then creates the new assignment. Rule: replacing a primary role is
demote-then-create, not delete-then-create — the old `RoleAssignment` row must remain (audit trail,
R17 attribution), just no longer primary.
