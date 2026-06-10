# HOD Reports Page Design Specification

## Executive Summary

Maps AdminDashboard Reports structure to HOD scope (`section__campus_department == mine`, grouped by section). HOD sees comparative analytics across their sections at campus-department level, with escalation and demand visibility enabling strategic workload management and SLA oversight.

---

## 1. Key Metrics Cards (4 cards)

Replaces AdminDashboard's global scope with HOD's campus-department scope. Same visual pattern, department-specific data.

| # | Card Title | Data Field | Source Endpoint | Notes |
|---|------------|-----------|-----------------|-------|
| **1** | **Dept SLA Compliance (Res)** | `resolution_sla_pct` | `/analytics/sla-compliance/` | Share of resolved tickets meeting resolution SLA within the HOD's campus department. Trend delta vs prior window. |
| **2** | **Net Flow (14d)** | `net_flow` + `flow_trend` | `/analytics/flow/` | Created − resolved per day. Positive trend = queue growing; negative = shrinking. 14-day visual trend line. |
| **3** | **Open Backlog** | `open_backlog` | `/analytics/overview/` | Snapshot of tickets in active statuses (open/assigned/in_progress/pending) scoped to HOD's dept, all sections. |
| **4** | **CSAT (Resolved)** | `csat` | `/analytics/quality/` | Average rating on resolved tickets within the campus department. Ratio of feedback received / resolved. |

**Visual treatment:** Same stat card layout as AdminDashboard. Show percentage or count with ↑↓ delta vs prior 30 days.

---

## 2. Quick Access Report Cards (3 cards)

Tactical drill-downs. Each shows a summary stat with link to detailed report view.

| # | Card Title | Primary Metric | Secondary Data | Source Endpoint | Purpose |
|---|------------|----------------|-----------------|-----------------|---------|
| **1** | **Section-vs-Section Comparison** | Section breakdown by open_count + escalation_rate | Per section: total tickets, open count, escalated % | `/analytics/performance/sections/` | HOD sees which sections are most loaded and which have highest escalation rates. Identifies over-loaded sections for rebalancing. |
| **2** | **Escalations at HOD Level** | Count of tickets at `current_level = hod` | Unresolved HOD-level tickets needing action | `/analytics/overview/` (from breakdown) | Immediate actionables. Shows HOD escalations requiring their intervention. Drill to ticket queue filtered by `current_level=hod`. |
| **3** | **Demand Shape (Dept View)** | Top 5 service categories by volume | Category name + count (windowed) | `/analytics/demand/` | Strategic visibility: what services are most requested? Drives staffing and capacity planning decisions. |

---

## 3. Detail Reports (Role-scoped analytics views)

Each row above links to a full-page analytics view with filtering, grouping, and drill-down. HOD scope is enforced server-side.

### 3.1 Ticket Analytics
**Endpoint:** `GET /analytics/performance/sections/`  
**Scope:** `section__campus_department == hod's campus_department`  
**Grouping:** Automatic — by section  
**Visible metrics per section:**
- Total tickets created (windowed)
- Open count (live)
- Resolved count (windowed)
- Resolution SLA compliance % (met / total resolved with due)
- Escalated count (current_level ∈ {hos, hod})
- Escalation rate %
- Reopen rate % (reopened / resolved)

**Filtering options:**
- Date range (default 30 days)
- Status filter (if desired)
- Priority filter

**Why this scope:** HOD cannot act on individual technicians or tickets in other departments. Section-level metrics let HOD see cross-section fairness (e.g., Section A has 50% escalation vs Section B's 10%) and make reassignment / capacity decisions.

### 3.2 Technician Performance (Cross-section Rollup)
**Endpoint:** `GET /analytics/performance/technicians/`  
**Scope:** `section__campus_department == hod's campus_department`  
**Grouping:** By technician  
**Visible metrics per technician:**
- Open load (live, active statuses only)
- Resolved count (windowed)
- Escalated count (windowed, attributed to level_user)
- Resolution time p50/p90 (seconds, for quality assessment)
- Reopen rate % (their tickets reopened / their resolved)

**Why cross-section:** HOD manages pool of technicians across sections (implicitly via HOS). Seeing all technicians in the dept allows HOD to spot uneven load distribution (Tech A in Sect 1 has 12 open; Tech C in Sect 2 has 3) and request HOS rebalancing or offer redistribution.

**Example:** HOD sees Jane (Sect 1) has 8 open tickets, all critical/high priority, with a pending escalation. Tom (Sect 2) has 2 open, both low priority. HOD can note the imbalance but must coordinate reallocation via the respective HOS/escalation handlers.

### 3.3 Section Performance (Section-by-section drill-down)
**Endpoint:** `GET /analytics/performance/sections/` (or detail view per section)  
**Scope:** `section == selected section` (HOD scoped to their dept, so HOS can see detail)  
**Drill-in:** From the section card in Quick Access #1, HOD clicks a section name to see that section's full analytics independently.

**Visible metrics per section:**
- Daily net flow (7/14/30 day trend)
- SLA compliance (resolution + response)
- Technician roster with open load
- Escalations (HOS and HOD level separately)
- Demand (service categories most requested at this section)

---

## 4. Backend Endpoints HOD Calls

| # | Endpoint | Method | Purpose | Scope Filter | Group-by | Notes |
|---|----------|--------|---------|-------------|----------|-------|
| **1** | `/analytics/overview/` | GET | Dashboard preset (4 headline cards) | `section__campus_department == hod's cd` | None (aggregate only) | Returns `open_backlog`, `created`, `resolved`, `net_flow`, `resolution_sla_pct`, `response_sla_pct`, `csat`, `reopen_rate`, `at_risk`, `breached`, `escalation_rate`, `delta` |
| **2** | `/analytics/sla-compliance/` | GET | SLA deep-dive | `section__campus_department == hod's cd` | None (aggregate only) | Returns `resolution_sla_pct`, `response_sla_pct`, `at_risk`, `breached` + delta |
| **3** | `/analytics/flow/` | GET | Net flow 14-day trend | `section__campus_department == hod's cd` | None (aggregate only) | Returns `net_flow`, `flow_trend`, `status_distribution`, `priority_distribution` + delta |
| **4** | `/analytics/performance/sections/` | GET | Section-vs-section comparison | `section__campus_department == hod's cd` | Section (automatic) | Returns `breakdown` array with per-section: open_count, escalated_count, resolution_sla_met, reopen_rate, etc. |
| **5** | `/analytics/performance/technicians/` | GET | Technician rollup across sections | `section__campus_department == hod's cd` | Technician (automatic) | Returns `breakdown` array with per-technician: total_assigned, open_count, resolved_count, escalated_count, plus p50/p90 resolution time |
| **6** | `/analytics/demand/` | GET | Service category demand (strategic) | `section__campus_department == hod's cd` | None (aggregate only) | Returns demand breakdown by category + facility type (where applicable) |

**Query params (all endpoints):**
- `date_from` (ISO date, optional) / `date_to` (ISO date, optional) — custom window
- `days` (int, optional) — shortcut (e.g. `?days=7` for last 7 days)
- Default window: last 30 days

**Example calls:**

```bash
# Dashboard preset
GET /api/v1/analytics/overview/?days=30

# Section-vs-section comparison with 14-day window
GET /api/v1/analytics/performance/sections/?date_from=2026-05-20&date_to=2026-06-03

# SLA compliance detail
GET /api/v1/analytics/sla-compliance/?days=30

# Demand shape (top categories for strategic staffing)
GET /api/v1/analytics/demand/?days=30
```

---

## 5. Role-Scoped Design Output

### 5.1 Metric Cards (Summary)

```json
{
  "metric_cards": [
    {
      "title": "Dept SLA Compliance (Res)",
      "data_field": "resolution_sla_pct",
      "source_endpoint": "/analytics/sla-compliance/",
      "display": "percentage with trend delta",
      "scope": "section__campus_department == hod's campus_department",
      "window": "last 30 days (configurable)"
    },
    {
      "title": "Net Flow (14d)",
      "data_field": "net_flow + flow_trend",
      "source_endpoint": "/analytics/flow/",
      "display": "line chart (created - resolved per day)",
      "scope": "section__campus_department == hod's campus_department",
      "window": "last 14 days"
    },
    {
      "title": "Open Backlog",
      "data_field": "open_backlog",
      "source_endpoint": "/analytics/overview/",
      "display": "count (live snapshot, no window filter)",
      "scope": "section__campus_department == hod's campus_department",
      "window": "live (all scoped tickets in active status)"
    },
    {
      "title": "CSAT (Resolved)",
      "data_field": "csat",
      "source_endpoint": "/analytics/quality/",
      "display": "average rating (1-5) with trend delta",
      "scope": "section__campus_department == hod's campus_department",
      "window": "last 30 days"
    }
  ]
}
```

### 5.2 Quick Access Cards (Summary)

```json
{
  "quick_access_cards": [
    {
      "title": "Section-vs-Section Comparison",
      "primary_metric": "Section breakdown by open_count + escalation_rate",
      "source_endpoint": "/analytics/performance/sections/",
      "data_fields": [
        "section_id",
        "section_type_name",
        "open_count",
        "escalated_count",
        "escalation_rate",
        "resolution_sla_met",
        "reopen_rate"
      ],
      "link_to_report": "/reports/sections",
      "scope": "section__campus_department == hod's campus_department, grouped by section",
      "purpose": "Identify over-loaded or under-performing sections"
    },
    {
      "title": "Escalations at HOD Level",
      "primary_metric": "Count of tickets at current_level = hod",
      "source_endpoint": "/analytics/overview/",
      "data_fields": ["escalation_rate", "breakdown[].escalated_count"],
      "link_to_report": "/tickets/?current_level=hod",
      "scope": "section__campus_department == hod's campus_department",
      "purpose": "Immediate action items - HOD-level escalations needing intervention"
    },
    {
      "title": "Demand Shape (Dept View)",
      "primary_metric": "Top 5 service categories by volume",
      "source_endpoint": "/analytics/demand/",
      "data_fields": ["category_name", "count"],
      "link_to_report": "/reports/demand",
      "scope": "section__campus_department == hod's campus_department",
      "purpose": "Strategic visibility for staffing and capacity planning"
    }
  ]
}
```

### 5.3 Detail Reports (Scoping Rules)

```json
{
  "detail_reports": [
    {
      "report_name": "Ticket Analytics",
      "endpoint": "/analytics/performance/sections/",
      "scoped_to_campus_department": true,
      "grouped_by_section": true,
      "visible_metrics": [
        "total_tickets",
        "open_count",
        "resolved_count",
        "resolution_sla_pct",
        "escalated_count",
        "escalation_rate",
        "reopen_rate"
      ]
    },
    {
      "report_name": "Technician Performance",
      "endpoint": "/analytics/performance/technicians/",
      "scoped_to_campus_department": true,
      "cross_section_rollup": true,
      "visible_metrics": [
        "technician_id",
        "username",
        "open_load",
        "resolved_count",
        "escalated_count",
        "resolution_time_p50_seconds",
        "resolution_time_p90_seconds",
        "reopen_rate"
      ],
      "note": "Aggregates technicians across all sections in HOD's campus department"
    },
    {
      "report_name": "Section Performance",
      "endpoint": "/analytics/performance/sections/",
      "scoped_to_campus_department": true,
      "section_by_section_drilldown": true,
      "visible_metrics": [
        "section_id",
        "section_type_name",
        "daily_net_flow_trend",
        "resolution_sla_pct",
        "response_sla_pct",
        "technician_roster_with_load",
        "escalations_hos_level",
        "escalations_hod_level",
        "demand_by_category"
      ]
    }
  ]
}
```

### 5.4 Backend Endpoint Calls (Specification)

```yaml
Endpoint Inventory:
  
  GET /analytics/overview/:
    scope: section__campus_department == hod's campus_department
    group_by: null (returns aggregate across all scoped sections)
    response_keys:
      - open_backlog (live count of active tickets)
      - created (windowed count)
      - resolved (windowed count)
      - net_flow (created - resolved)
      - status_distribution (array by status)
      - live_status_distribution (all scoped tickets by current status)
      - resolution_sla_pct (%)
      - response_sla_pct (%)
      - csat (avg rating)
      - reopen_rate (%)
      - at_risk (live count within 4h of deadline)
      - breached (live count past deadline)
      - escalation_rate (%)
      - delta (object with prior-window comparison for each metric)
    
  GET /analytics/sla-compliance/:
    scope: section__campus_department == hod's campus_department
    group_by: null
    response_keys:
      - resolution_sla_pct (%)
      - response_sla_pct (%)
      - at_risk (count)
      - breached (count)
      - delta (prior-window comparison)
    
  GET /analytics/flow/:
    scope: section__campus_department == hod's campus_department
    group_by: null
    response_keys:
      - open_backlog (live)
      - created (windowed)
      - resolved (windowed)
      - net_flow (windowed)
      - flow_trend (array of {date, created, resolved, net} per day)
      - status_distribution (by status)
      - priority_distribution (by priority)
      - delta (prior-window comparison)
    
  GET /analytics/quality/:
    scope: section__campus_department == hod's campus_department
    group_by: null
    response_keys:
      - csat (avg)
      - feedback_response_rate (%)
      - reopen_rate (%)
      - delta (prior-window comparison)
    
  GET /analytics/demand/:
    scope: section__campus_department == hod's campus_department
    group_by: null
    response_keys:
      - by_category (array of {category_name, count})
      - by_facility_type (array of {facility_type, count})
      (others per aggregate() implementation)
    
  GET /analytics/performance/sections/:
    scope: section__campus_department == hod's campus_department
    group_by: section (automatic)
    response_keys:
      - breakdown (array of per-section metrics):
          - section_id
          - section_type_name
          - campus_name
          - total (created in window)
          - open_count (live)
          - resolved_count (windowed)
          - escalated_count (windowed)
          - escalation_rate (%)
          - reopen_rate (%)
          - resolution_sla_met (count)
          - total_resolved_with_due (for % calculation)
    
  GET /analytics/performance/technicians/:
    scope: section__campus_department == hod's campus_department
    group_by: technician (automatic)
    response_keys:
      - technician_load (array of per-tech open load, live)
      - breakdown (array of per-technician metrics):
          - technician_id
          - username
          - first_name
          - last_name
          - total_assigned (windowed)
          - open_count (live)
          - resolved_count (windowed)
          - escalated_count (windowed)

Query Parameters (all endpoints):
  date_from: ISO date string (optional)
  date_to: ISO date string (optional)
  days: integer (optional, shortcut; default 30)
  Default window: last 30 days if neither date nor days specified
```

---

## 6. Implementation Checklist

### Backend (already implemented, verify scope)
- [ ] `OverviewView` / `SLAComplianceView` / `FlowView` / `QualityView` / `DemandView` 
  - Verify HOD scope: `scoped_qs = scoped_ticket_qs(user, "hod")` yields `section__campus_department == user's campus_department`
  - Verify aggregate() is called with HOD's scoped QS
- [ ] `PerformanceSectionsView`
  - Verify `group_by="section"` is passed to aggregate()
  - Verify breakdown includes escalation_rate, reopen_rate per section
- [ ] `PerformanceTechniciansView`
  - Verify `group_by="technician"` is passed
  - Verify scope is HOD's campus_department (all technicians across sections)
- [ ] `scoped_ticket_qs(user, "hod")` scope resolver
  - Should filter `section__campus_department` where HOD is the active holder (RoleAssignment or standing CampusDepartment.hod)

### Frontend (HOD Reports page)
- [ ] Dashboard layout with 4 metric cards + 3 quick access cards
- [ ] Metric cards call `/analytics/overview/`, `/analytics/sla-compliance/`, `/analytics/flow/`, `/analytics/quality/`
- [ ] Quick access card 1 (Section Comparison) calls `/analytics/performance/sections/`, renders table with clickable section rows
- [ ] Quick access card 2 (Escalations) shows count from overview breakdown, links to ticket queue with `?current_level=hod`
- [ ] Quick access card 3 (Demand) calls `/analytics/demand/`, shows top 5 categories by count
- [ ] Date range picker (default 30 days) affects all calls except live metrics (open_backlog, technician_load, at_risk, breached)
- [ ] Drill-down: clicking a section in card 1 opens `/reports/sections/{section_id}` with that section's isolated metrics
- [ ] Drill-down: clicking technician in Performance view opens tech detail (already exists)

---

## 7. Scope Boundary Examples

**HOD A (ICT, Nairobi):**
- Sees all sections: ICT Support (Nairobi), ICT Labs (Nairobi) ✓
- Sees all technicians in those sections ✓
- Sees escalations attributed to ICT-Nairobi escalation ladder ✓
- **Cannot see:** ICT Support (Kampala), Facilities (Nairobi), any other campus-department ✗

**HOD B (Facilities, Nairobi):**
- Sees: Facilities (Nairobi) sections only ✓
- **Boundary test:** QuerySet for HOD A must return 0 rows from HOD B's campus-department ✓

---

## 8. Notes

- **No per-ticket actionables:** HOD sees comparative/strategic metrics, not individual ticket actions. Ticket reassignment and escalation resolution are handled via the ticket queue or escalation endpoints.
- **SLA is response + resolution:** Both tracked separately; HOD sees both in SLA compliance card.
- **Escalation attribution:** Escalations are attributed to the actual `level_user` from `TicketLog`, not the original assignee (R10 / SoT §4.3).
- **Paused time handled:** `accumulated_pause` is excluded from SLA calculations (R9); the aggregate function uses shifted `resolution_due_at`.
