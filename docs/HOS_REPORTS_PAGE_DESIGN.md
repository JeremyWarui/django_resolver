# HOS (Head of Section) Reports Page Design

**Version:** 1.0  
**Based on:** service-desk-implementation-plan.md §5.4 Analytics  
**Status:** Design specification for frontend/backend integration  

---

## Executive Summary

The HOS Reports page provides section-scoped operational dashboards for the Head of Section role. Unlike the Admin (system-wide) view, HOS sees only tickets, technicians, and metrics within their assigned section(s).

**HOS Scope Resolution (R17 active-holder):**  
- Primary: `sections where hos == self` (standing assignment via `Section.hos` FK)
- Cover: active `RoleAssignment(role="hos", is_primary=False)` entries with `valid_from ≤ now < valid_until`

**Four-part layout:**
1. Metric Cards — at-a-glance health (4 cards)
2. Quick-Access Reports — drillable summaries (3 cards)
3. Detail Reports — deep-dive analytics tables
4. HOS-specific widgets — fairness/escalations/at-risk actionables

---

## Part 1: Metric Cards (Section-wide SLA & workload health)

Replace Admin's 4 generic health cards with HOS-specific operational metrics.

| Card # | Title | Field | Endpoint | Notes |
|--------|-------|-------|----------|-------|
| **Card 1** | **Open Backlog** | `open_backlog` | `GET /api/v1/analytics/overview/?days=30` | Count of tickets in `status IN (open, assigned, in_progress, pending)`. Live snapshot (no date filter). |
| **Card 2** | **Section SLA Compliance (Resolution)** | `resolution_sla_pct` | `GET /api/v1/analytics/overview/?days=30` | % of resolved tickets where `resolved_at ≤ resolution_due_at`. Windowed on `resolved_at` in the selected date range. |
| **Card 3** | **Response SLA Compliance** | `response_sla_pct` | `GET /api/v1/analytics/overview/?days=30` | % of created tickets with first response (assigned/status-changed/resolved event) within `response_due_at`. Windowed on `created_at` in the selected date range. |
| **Card 4** | **CSAT (Customer Satisfaction)** | `csat` (+ `delta`) | `GET /api/v1/analytics/overview/?days=30` | Average `TicketFeedback.rating` (1–5 stars) from tickets resolved in the window. Shows trend vs prior equal window. |

### Metric Card Response (Overview endpoint)

```json
{
  "date_range": {
    "from": "2026-05-04",
    "to": "2026-06-03"
  },
  "open_backlog": 12,
  "created": 45,
  "resolved": 38,
  "net_flow": 7,
  "status_distribution": [
    {"status": "in_progress", "count": 6},
    {"status": "assigned", "count": 4},
    {"status": "open", "count": 2},
    {"status": "pending", "count": 0}
  ],
  "live_status_distribution": [
    {"status": "in_progress", "count": 6},
    {"status": "assigned", "count": 4},
    {"status": "open", "count": 2},
    {"status": "pending", "count": 0}
  ],
  "resolution_sla_pct": 91.2,
  "response_sla_pct": 94.7,
  "csat": 4.3,
  "reopen_rate": 2.6,
  "at_risk": 2,
  "breached": 1,
  "escalation_rate": 6.7,
  "delta": {
    "created": 5,
    "resolved": -2,
    "resolution_sla_pct": 2.1,
    "response_sla_pct": 1.5,
    "csat": 0.2,
    "reopen_rate": -0.5
  }
}
```

---

## Part 2: Quick-Access Report Cards (section-scoped drillable summaries)

Three cards that link to detail reports; summary stats with card-tap navigation.

| Card # | Title | Summary Fields | Drill Target | Notes |
|--------|-------|-----------------|--------------|-------|
| **Quick 1** | **Section SLA Compliance** | `resolution_sla_pct` + `response_sla_pct` + `at_risk` + `breached` | `/reports/sla-compliance/` | Linked table: tickets at-risk (within 4h of deadline) + breached (past deadline). Includes `created_at`, `assigned_to`, `priority`, `resolution_due_at`, `status`. |
| **Quick 2** | **Technician Workload & Fairness** | `technician_load[].{username, open_count}` sorted by load | `/reports/technician-performance/` | Bar chart or table: per-technician open ticket count + avg resolution time + recent CSAT. Highlights imbalance (e.g. one tech at 12 open, another at 3). |
| **Quick 3** | **Escalations & Reopens** | `escalation_rate` + `reopen_rate` + `escalated_count` | `/reports/quality-metrics/` | Linked table: tickets escalated at HOS level (current_level=hos) + reopened tickets. Includes `created_at`, `resolved_at`, `reason` (for reopens). |

### Quick-Access Card Aggregates

**Card 1: SLA Compliance Card** — calls `GET /api/v1/analytics/overview/`:
```json
{
  "summary": {
    "resolution_compliance": 91.2,
    "response_compliance": 94.7,
    "at_risk_count": 2,
    "breached_count": 1
  }
}
```

**Card 2: Technician Workload Card** — calls `GET /api/v1/analytics/performance/technicians/`:
```json
{
  "technician_load": [
    {
      "technician_id": 42,
      "username": "tech_alice",
      "first_name": "Alice",
      "last_name": "Kipchoge",
      "open_count": 12
    },
    {
      "technician_id": 55,
      "username": "tech_bob",
      "first_name": "Bob",
      "last_name": "Odhiambo",
      "open_count": 4
    }
  ]
}
```

**Card 3: Escalations & Reopens Card** — calls `GET /api/v1/analytics/quality/`:
```json
{
  "escalation_rate": 6.7,
  "reopen_rate": 2.6,
  "escalated_count": 3,
  "feedback_response_rate": 89.5,
  "delta": {
    "reopen_rate": -0.5
  }
}
```

---

## Part 3: Detail Reports (deep-dive views with tables)

### 3.1 Ticket Analytics (Section-scoped drill)

**Endpoint:** `GET /api/v1/analytics/tickets/?section_id=X&days=30`  
**Access:** HOS (own section) + Admin  
**Scope:** Filtered to `section__hos == user` (active-holder resolved, R17)

**Table columns:**
- Ticket ID / creation date
- Service item / category
- Status (with badge color)
- Assigned technician
- Priority
- Created at / Updated at
- Response due at / Resolution due at
- SLA status (on-track / at-risk / breached)

**Filters:**
- Date range (default: last 30 days, on created_at)
- Status (multi-select: open, assigned, in_progress, pending, resolved, closed)
- Priority (multi-select)
- Assigned technician (multi-select from section pool)

**Sorting:** By status, created_at, updated_at, priority

---

### 3.2 Technician Performance (Section-scoped)

**Endpoint:** `GET /api/v1/analytics/performance/technicians/?days=30`  
**Access:** HOS (section technicians) + HOD + Admin  
**Scope:** Filters to technicians in the HOS's section(s) via `SectionTechnician` join

**Table columns per technician:**
- Name / username
- Total assigned (all-time open)
- Open count (current, live)
- Resolved (in window)
- Escalated count
- Avg resolution time (p50, hours)
- Avg CSAT (stars)
- Escalation rate (% of assigned)

**Aggregate row (section summary):**
- Section total assigned / open / resolved
- Avg response time
- Avg CSAT

**Sorting:** By open_count (workload), resolved, CSAT

**Use case:** "Who is overloaded?" → Reassign from high-load to low-load; "Who is fastest?" → pair slow tech with fast tech for shadowing.

---

### 3.3 Section Performance (within scope only)

**Endpoint:** `GET /api/v1/analytics/performance/sections/?days=30`  
**Access:** HOS (own) + HOD + Admin  
**Scope:** For HOS, shows only their section(s); for HOD, shows all sections in their dept

**For HOS (single section):**
- Shows the section row + **unassigned tickets** + **at-risk/breached** as sub-tables
- Unassigned: tickets in `open` status with no `assigned_to`
- At-risk: tickets within 4h of `resolution_due_at` with status in (open, assigned, in_progress)
- Breached: tickets past `resolution_due_at` with status in (open, assigned, in_progress)

**Table columns (section row):**
- Section type
- Total tickets (all time)
- Open count
- Escalated count
- Resolution SLA % (met / total resolved with due date)
- Avg resolution time (p50)
- Avg CSAT
- Technician count

---

## Part 4: HOS-Specific Widgets (fairness, escalations, actionables)

### 4.1 Per-Technician Workload (Fairness Check)

**Location:** In the Technician Performance detail report (§3.2) or as a live widget on the overview  
**Widget type:** Horizontal bar chart or list

**Chart data:**
- X-axis: technician names
- Y-axis: open ticket count (live snapshot, no date filter)
- Color: green (0–2), yellow (3–5), red (6+) — thresholds configurable

**Data source:** `GET /api/v1/analytics/performance/technicians/` → `technician_load[]`

**Action:** Tap a bar → see that technician's assigned tickets in the Ticket Analytics table (filtered to `assigned_to == that_tech`).

**Purpose:** Spot imbalance at a glance; if one tech has 10 open and another has 2, HOS can reassign to balance.

---

### 4.2 Escalations at HOS Level (Actionable List)

**Location:** Quick-Access Card 3 drill-down, or a dedicated Escalations widget

**Widget type:** Table of HOS-level escalations (read-only list, no reassign from here)

**Data source:** `GET /api/v1/analytics/tickets/?section_id=X` with client-side filter `current_level == "hos"`

**Table columns:**
- Ticket ID / created
- Service item
- Current status
- Assigned technician
- Reason (from `TicketLog` event where `current_level` changed to `"hos"`)
- Days at HOS level
- Actions: View ticket detail, Escalate to HOD, Return to technician

**Queries:** List is read-only; actions invoke `/tickets/{id}/escalation/` (HOD approval flows) or `/tickets/{id}/status/` (return to in_progress).

---

### 4.3 Reopen Rate (Metric + Detail Table)

**Location:** Dashboard Card 4 or Quality Metrics detail report

**Metric:** `reopen_rate` (% of resolved tickets with a later `reopened` event in the window)

**Detail table:** Tickets that were reopened in the date range
- Ticket ID / service item
- Original resolution date
- Reopen date
- Reason (from `TicketLog.event_data`)
- Days between resolve/reopen

**Purpose:** Early-warning signal; high reopen rate (>5%) suggests quality issues or incomplete fixes. Actionable: "talk to the techs about what was missed."

---

### 4.4 Unassigned + At-Risk Actionables (Quick Triage)

**Location:** Section Performance detail report (§3.3) or dedicated Actionables widget

**Widget type:** Split table

**Table A: Unassigned Tickets** (status = open, assigned_to IS NULL)
- Ticket ID / created
- Service item / priority
- Days in backlog
- Raised by

**Table B: At-Risk Tickets** (within 4h of deadline, status in active)
- Ticket ID / created
- Assigned to / priority
- Time to deadline (hours)
- Current status

**Actions:**
- Unassigned: Tap → assign (opens modal with section technicians sorted by workload)
- At-Risk: Tap → escalate or reassign to faster technician

**Purpose:** HOS's daily triage; "assign these 3 today" + "these 2 are about to breach."

---

## Backend Endpoint Mapping

| Frontend View | Endpoint(s) Called | Role Scope | Notes |
|---------------|-------------------|-----------|-------|
| **Metric Cards** | `GET /api/v1/analytics/overview/?days={days}` | HOS (their sections) | Uses `OverviewView`, role-filtered by scope resolver. Returns all metrics in one response. |
| **Quick-Access Cards 1–3** | `GET /api/v1/analytics/overview/` + `/api/v1/analytics/quality/` + `/api/v1/analytics/performance/technicians/` | HOS (their sections) | Three separate calls; combine card summaries client-side. |
| **Ticket Analytics table** | `GET /api/v1/analytics/tickets/?section_id=X&days=30&status=&priority=&technician=` | HOS (own section) | Deep-dive drill from Quick-Access Card 1 or standalone page. |
| **Technician Performance table** | `GET /api/v1/analytics/performance/technicians/?days=30` | HOS (section technicians) | Breaks down by `technician_load[].{username, open_count, resolved, escalated, csat}`. |
| **Section Performance table** | `GET /api/v1/analytics/performance/sections/?days=30` | HOS (own section) | For HOS, filters to their section only. Includes sub-tables for unassigned/at-risk. |
| **Escalations list** | `GET /api/v1/analytics/tickets/?current_level=hos` (client filter) + `/api/v1/tickets/?section_id=X` | HOS (own section) | Uses the ticket list endpoint; frontend filters to `current_level == "hos"`. |
| **Reopen rate detail** | `GET /api/v1/analytics/quality/?days=30` (summary) + `/api/v1/tickets/?section_id=X&reopened=true` | HOS (own section) | Metric from `quality/` endpoint; detail table from ticket list with reopened filter. |
| **Unassigned/At-Risk** | `GET /api/v1/analytics/performance/sections/?days=30` (section row) + `/api/v1/tickets/?section_id=X&assigned_to=null&status=open` | HOS (own section) | Section Performance includes unassigned count; drill via ticket list with filters. |

---

## New Endpoints Required (if not already present)

**All role-scoped endpoints below assume the scope resolver (Phase 6) is in place and all endpoints use `scoped_ticket_qs(user, role)` from the same core.**

### Existing — No changes needed:
- `GET /api/v1/analytics/overview/` — Already handles role-scoped aggregation. HOS uses their sections.
- `GET /api/v1/analytics/sla-compliance/` — SLA metrics for HOS's sections.
- `GET /api/v1/analytics/quality/` — CSAT + reopen rate for HOS's sections.
- `GET /api/v1/analytics/performance/technicians/` — Technician breakdown for HOS's section(s).
- `GET /api/v1/analytics/performance/sections/` — Section breakdown (HOS sees only their own).

### Optional — For enhanced filtering:
None required if ticket-list endpoint (`GET /api/v1/tickets/`) supports all necessary filters (status, assigned_to, current_level, reopened, etc.). HOS can drill via the ticket list with query params.

---

## Response Shape (HOS Overview Example)

```json
{
  "date_range": {
    "from": "2026-05-04T00:00:00Z",
    "to": "2026-06-03T23:59:59Z"
  },
  "open_backlog": 12,
  "created": 45,
  "resolved": 38,
  "net_flow": 7,
  "status_distribution": [
    {"status": "in_progress", "count": 6},
    {"status": "assigned", "count": 4},
    {"status": "open", "count": 2},
    {"status": "pending", "count": 0}
  ],
  "live_status_distribution": [
    {"status": "in_progress", "count": 6},
    {"status": "assigned", "count": 4},
    {"status": "open", "count": 2},
    {"status": "pending", "count": 0}
  ],
  "resolution_sla_pct": 91.2,
  "response_sla_pct": 94.7,
  "csat": 4.3,
  "feedback_response_rate": 89.5,
  "reopen_rate": 2.6,
  "at_risk": 2,
  "breached": 1,
  "escalation_rate": 6.7,
  "escalated_count": 3,
  "reassignment_rate": null,
  "technician_load": [
    {
      "technician_id": 42,
      "username": "tech_alice",
      "first_name": "Alice",
      "last_name": "Kipchoge",
      "open_count": 12
    },
    {
      "technician_id": 55,
      "username": "tech_bob",
      "first_name": "Bob",
      "last_name": "Odhiambo",
      "open_count": 4
    }
  ],
  "delta": {
    "created": 5,
    "resolved": -2,
    "resolution_sla_pct": 2.1,
    "response_sla_pct": 1.5,
    "csat": 0.2,
    "reopen_rate": -0.5
  }
}
```

---

## Design Decisions Summary

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| **Scope** | HOS sees sections where `hos == self` (R17 active-holder) | Phase 6 scope resolver + Phase 17 active-holder implementation already in place. |
| **Metric cards** | 4 cards: Backlog, Resolution SLA %, Response SLA %, CSAT | HOS operational priorities: is the queue growing? Are we meeting SLAs? Are tickets being redone? |
| **Quick-Access** | 3 cards with drill links | Mirrors Admin layout (cards + detail); HOS gets section-scoped summaries. |
| **Detail reports** | Ticket Analytics, Technician Performance, Section Performance | Covers: what tickets are open? who is overloaded? what is our collective health? |
| **Workload widget** | In Technician Performance table + optional live bar chart | HOS must spot imbalance to reassign fairly; workload is primary lever. |
| **Escalations** | Read-only list of HOS-level escalations | HOS cannot modify escalations (that's HOD action); this is for tracking. |
| **At-risk/Unassigned** | Sub-tables in Section Performance or Actionables widget | Triage focus: these need assignment or escalation today. |
| **Reopen rate** | Metric card + detail table | Quality indicator; high reopen signals process issues or training gaps. |
| **New endpoints** | None required | All calls use existing `/analytics/*` endpoints with role-scoped filtering. |
| **Date range** | Default 30 days, selectable on page | Matches all other role dashboards. |

---

## Frontend Architecture (TBD — for integration)

**Hooks/components to build:**
1. `useHOSDashboard()` — calls `GET /api/v1/analytics/overview/`, returns { metric1, metric2, delta, technician_load }
2. `<MetricCard/>` — Card 1–4 layout with trend arrow
3. `<QuickAccessCard/>` — Card summary with drill link
4. `<TicketAnalyticsTable/>` — Filterable table (reusable for multiple roles)
5. `<TechnicianPerformanceTable/>` — Workload chart + table
6. `<SectionPerformanceWidget/>` — Section summary + unassigned/at-risk sub-tables
7. `<EscalationsWidget/>` — Read-only escalation list
8. `<WorkloadFairnessChart/>` — Horizontal bar chart of technician open counts

**Layout:**
```
[ Metric Card 1 ] [ Metric Card 2 ]
[ Metric Card 3 ] [ Metric Card 4 ]

[ Quick Access 1 ] [ Quick Access 2 ] [ Quick Access 3 ]

[ Detail Report Tabs ]
  - Ticket Analytics
  - Technician Performance
  - Section Performance
  - Escalations
```

---

## Questions for Stakeholder Review

1. **Workload widget location:** Should it be a live bar chart on the main overview, or only in the Technician Performance detail report?
2. **Escalation actions:** Should HOS be able to return an escalation to in_progress, or only view? (Currently designed as view-only.)
3. **Section multiple:** Does a single HOS manage multiple sections, or always one? (Design assumes multiple possible; scope resolver handles it.)
4. **Reopen threshold:** Is >5% reopen rate the alert threshold, or should HOS configure it?
5. **At-risk threshold:** The design uses 4 hours before deadline. Is this correct, or should it be configurable?

---

## Implementation Checklist

- [ ] Verify scope resolver (Phase 6) returns correct sections for HOS role
- [ ] Verify all `/analytics/*` endpoints respect role-scoped queryset
- [ ] Test HOS sees only their section(s), not other sections
- [ ] Test active-holder resolution (cover assignment shows in scope)
- [ ] Build metric card components + layout
- [ ] Build quick-access card components
- [ ] Build detail report tables (ticket, technician, section)
- [ ] Add workload fairness widget
- [ ] Add escalations list widget
- [ ] Add at-risk/unassigned triage widgets
- [ ] Hook up date range picker
- [ ] Test delta trend indicators
- [ ] Acceptance test: HOS A sees zero from another HOS's section
- [ ] Acceptance test: HOS cover assignment shows active-holder resolved
