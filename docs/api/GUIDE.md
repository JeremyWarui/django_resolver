# Django Resolver API - Frontend Integration Guide

[← Back to Index](../INDEX.md) | [← Back to README](../../README.md) | [Analytics Endpoints →](ANALYTICS.md)

⚠️ **STATUS**: For most frontend integrations, see the new [API Integration Guide](../API_INTEGRATION_GUIDE.md) master guide (covers all endpoints, authentication, examples, with better organization). This document provides additional detailed reference material.

> **Last Updated:** February 2026  
> **Version:** 1.0  
> **Base URL:** `/api/`

A comprehensive guide for frontend developers integrating with the Django Resolver ticket management system.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Core Concepts](#core-concepts)
3. [API Endpoints Reference](#api-endpoints-reference)
4. [Ticket Management](#ticket-management)
   - [Creating Tickets](#creating-tickets)
   - [Updating Tickets](#updating-tickets)
   - [Status Transitions](#status-transitions)
   - [Technician Assignment](#technician-assignment)
5. [Analytics & Reporting](#analytics--reporting)
   - [Timeframe Filtering](#timeframe-filtering)
   - [Status Breakdown](#status-breakdown)
   - [Trend Data](#trend-data)
6. [Frontend Implementation](#frontend-implementation)
   - [React + Vite Setup](#react--vite-setup)
   - [React Components](#react-components)
   - [Common Workflows](#common-workflows)
7. [Error Handling](#error-handling)
8. [Best Practices](#best-practices)

---

## Quick Start

### Base Information
- **API Base URL:** `https://your-domain.com/api/`
- **Authentication:** Optional (most endpoints are public)
- **Response Format:** JSON
- **Pagination:** 20 items per page
- **CORS:** Enabled for configured origins

### Making Your First Request

```javascript
// Get all tickets
const response = await fetch('/api/tickets/');
const data = await response.json();

console.log(`Total tickets: ${data.count}`);
console.log(`First page:`, data.results);
```

---

## Core Concepts

### Ticket Lifecycle
```
open → assigned → in_progress ⟷ pending → resolved → closed
```

### User Roles
- **user**: Can create tickets and add comments
- **technician**: Can be assigned to tickets, update status
- **admin/manager**: Full access including closing tickets

### Key Relationships
- **Ticket** belongs to one **Section** (IT, Plumbing, etc.)
- **Ticket** belongs to one **Facility** (Building, Equipment, etc.)
- **Technician** can belong to multiple **Sections**
- **Ticket** can only be assigned to **Technicians** in its Section

---

## API Endpoints Reference

### Tickets
| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/api/tickets/` | List all tickets | No |
| POST | `/api/tickets/` | Create new ticket | Yes |
| GET | `/api/tickets/{id}/` | Get ticket details | No |
| PATCH | `/api/tickets/{id}/` | Update ticket | Yes |
| DELETE | `/api/tickets/{id}/` | Delete ticket | Yes |

### Technicians & Users
| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/api/technicians/` | List all technicians | No |
| GET | `/api/technicians/?section_id={id}` | Technicians by section | No |
| GET | `/api/users/` | List all users | No |
| GET | `/api/users/?role={role}` | Filter by role | No |

### Reference Data
| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/api/sections/` | List all sections | No |
| GET | `/api/facilities/` | List all facilities | No |

### Analytics
| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/api/analytics/tickets/` | Ticket statistics | No |
| GET | `/api/analytics/technicians/` | Technician performance | No |
| GET | `/api/analytics/admin-dashboard/` | Admin dashboard data | No |

### Query Parameters

**Pagination:**
- `?page=2` - Page number
- `?page_size=20` - Items per page (default: 20)

**Filtering (Tickets):**
- `?status=open` - Filter by status
- `?section=1` - Filter by section ID
- `?assigned_to__isnull=true` - Unassigned tickets
- `?is_overdue=true` - Overdue tickets (>7 days)

**Ordering:**
- `?ordering=-created_at` - Sort by created date (descending)
- `?ordering=status` - Sort by status

---

## Ticket Management

### Creating Tickets

### Creating Tickets

#### Basic Ticket Creation

**Endpoint:** `POST /api/tickets/`

**Request Body:**
```json
{
  "title": "Broken AC in Conference Room",
  "description": "The air conditioning unit is not working properly",
  "section_id": 2,
  "facility_id": 1
}
```

**Response (201 Created):**
```json
{
  "id": 42,
  "ticket_no": "TKT-000042",
  "title": "Broken AC in Conference Room",
  "status": "open",
  "section": "HVAC",
  "facility": "Main Building",
  "raised_by": "john.doe",
  "assigned_to": null,
  "created_at": "2026-02-01T10:30:00Z",
  "updated_at": "2026-02-01T10:30:00Z"
}
```

**Key Notes:**
- `ticket_no` is auto-generated (format: TKT-XXXXXX)
- `status` defaults to "open"
- `raised_by` is set to authenticated user
- Response includes `available_technicians` for immediate assignment

---

### Updating Tickets

#### Assign a Technician

**Endpoint:** `PATCH /api/tickets/{id}/`

**Request:**
```json
{
  "assigned_to_id": 5
}
```

**Response:**
- Status automatically changes from "open" to "assigned"
- Technician must belong to ticket's section

#### Update Status

**Mark as In Progress:**
```json
{
  "status": "in_progress"
}
```

**Mark as Pending (with reason):**
```json
{
  "status": "pending",
  "pending_reason": "Waiting for replacement parts"
}
```

**Mark as Resolved:**
```json
{
  "status": "resolved"
}
```

---

### Status Transitions

#### Valid Transitions
```
open → assigned
assigned → in_progress, pending
in_progress → pending, resolved
pending → in_progress, resolved
resolved → closed (admin/manager only)
closed → (no further transitions)
```

#### Role-Based Permissions
| Role | Can Update Status | Can Close Tickets |
|------|------------------|-------------------|
| user | ❌ | ❌ |
| technician | ✅ | ❌ |
| admin | ✅ | ✅ |
| manager | ✅ | ✅ |

---

### Technician Assignment

#### Method 1: From Ticket Response

When you GET or POST a ticket, the response includes available technicians:

```javascript
const response = await fetch('/api/tickets/42/');
const ticket = await response.json();

// ticket.available_technicians contains technicians for this section
```

#### Method 2: Query by Section

**Endpoint:** `GET /api/technicians/?section_id={section_id}`

**Example:**
```javascript
// User selects section 2 (HVAC)
const response = await fetch('/api/technicians/?section_id=2');
const technicians = await response.json();

// Populate dropdown with technicians
```

**Response:**
```json
[
  {
    "id": 5,
    "username": "jane.tech",
    "first_name": "Jane",
    "last_name": "Tech",
    "role": "technician",
    "sections": [2, 3]
  }
]
```

---

## Analytics & Reporting

### Timeframe Filtering

Get ticket statistics for specific time periods.

**Endpoint:** `GET /api/analytics/tickets/`

#### Query Parameters

| Parameter | Type | Default | Options | Description |
|-----------|------|---------|---------|-------------|
| `timeframe` | string | `day` | `day`, `week`, `month` | Quick time period |
| `days` | integer | `30` | Any number | Custom day range |
| `group_by` | string | `day` | `day`, `week`, `month` | Trend grouping |
| `facility_id` | integer | - | Any ID | Filter by facility |
| `section_id` | integer | - | Any ID | Filter by section |

#### Example Requests

**Today's tickets:**
```javascript
fetch('/api/analytics/tickets/?timeframe=day')
```

**This week:**
```javascript
fetch('/api/analytics/tickets/?timeframe=week')
```

**Last 90 days (grouped by week):**
```javascript
fetch('/api/analytics/tickets/?days=90&group_by=week')
```

**Filter by facility and section:**
```javascript
fetch('/api/analytics/tickets/?timeframe=month&facility_id=1&section_id=2')
```

---

### Status Breakdown

#### Response Structure

```json
{
  "ticket_counts": {
    "period": "Last 7 days",
    "count": 15
  },
  "status_counts": [
    {"status": "open", "count": 6},
    {"status": "assigned", "count": 4},
    {"status": "in_progress", "count": 4},
    {"status": "pending", "count": 3},
    {"status": "resolved", "count": 4},
    {"status": "closed", "count": 4}
  ],
  "facility_distribution": [
    {"facility__name": "Building A", "count": 10},
    {"facility__name": "Building B", "count": 5}
  ],
  "section_distribution": [
    {"section__name": "IT", "count": 8},
    {"section__name": "Plumbing", "count": 7}
  ]
}
```

---

### Trend Data

Trend data is included in analytics responses for charting:

```json
{
  "trend_data": [
    {"date": "2026-01-25", "count": 2},
    {"date": "2026-01-26", "count": 5},
    {"date": "2026-01-27", "count": 3}
  ]
}
```

**Grouping Options:**
- `group_by=day` - Daily data points
- `group_by=week` - Weekly aggregates
- `group_by=month` - Monthly aggregates

---

## Frontend Implementation

### React + Vite Setup

#### Environment Variables

Create a `.env` file in your Vite project root:

```env
VITE_API_BASE_URL=http://localhost:8000/api
# or for production
VITE_API_BASE_URL=https://your-domain.com/api
```

#### API Client Setup

Create a reusable API client (`src/lib/api.js`):

```javascript
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

export const api = {
  async get(endpoint) {
    const response = await fetch(`${API_BASE_URL}${endpoint}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  },

  async post(endpoint, data) {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  },

  async patch(endpoint, data) {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  },

  async delete(endpoint) {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: 'DELETE'
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.ok;
  }
};
```

#### Vite Proxy Configuration (Optional)

For development, configure proxy in `vite.config.js`:

```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
})
```

---

### React Components

#### Ticket Creation Form

```jsx
import { useState, useEffect } from 'react';

function TicketForm() {
  const [sections, setSections] = useState([]);
  const [facilities, setFacilities] = useState([]);
  const [technicians, setTechnicians] = useState([]);
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    section_id: '',
    facility_id: '',
    assigned_to_id: ''
  });

  useEffect(() => {
    // Load reference data
    fetch('/api/sections/')
      .then(r => r.json())
      .then(data => setSections(data.results));
    
    fetch('/api/facilities/')
      .then(r => r.json())
      .then(data => setFacilities(data.results));
  }, []);

  const handleSectionChange = async (sectionId) => {
    setFormData({ ...formData, section_id: sectionId, assigned_to_id: '' });
    
    if (sectionId) {
      const response = await fetch(`/api/technicians/?section_id=${sectionId}`);
      const data = await response.json();
      setTechnicians(data);
    } else {
      setTechnicians([]);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    
    try {
      const response = await fetch('/api/tickets/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: formData.title,
          description: formData.description,
          section_id: formData.section_id,
          facility_id: formData.facility_id,
          ...(formData.assigned_to_id && { assigned_to_id: formData.assigned_to_id })
        })
      });

      if (response.ok) {
        const ticket = await response.json();
        alert(`Ticket ${ticket.ticket_no} created successfully!`);
        // Reset form
        setFormData({
          title: '',
          description: '',
          section_id: '',
          facility_id: '',
          assigned_to_id: ''
        });
        setTechnicians([]);
      } else {
        const errorData = await response.json();
        setError(errorData.error || 'Failed to create ticket');
      }
    } catch (err) {
      setError('Network error. Please try again.');
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      {error && (
        <div className="error-message" style={{ color: 'red', marginBottom: '1rem' }}>
          {error}
        </div>
      )}
      <input
        type="text"
        placeholder="Title"
        value={formData.title}
        onChange={(e) => setFormData({ ...formData, title: e.target.value })}
        required
      />
      
      <textarea
        placeholder="Description"
        value={formData.description}
        onChange={(e) => setFormData({ ...formData, description: e.target.value })}
        required
      />
      
      <select
        value={formData.section_id}
        onChange={(e) => handleSectionChange(e.target.value)}
        required
      >
        <option value="">Select Section</option>
        {sections.map(s => (
          <option key={s.id} value={s.id}>{s.name}</option>
        ))}
      </select>
      
      <select
        value={formData.facility_id}
        onChange={(e) => setFormData({ ...formData, facility_id: e.target.value })}
        required
      >
        <option value="">Select Facility</option>
        {facilities.map(f => (
          <option key={f.id} value={f.id}>{f.name}</option>
        ))}
      </select>
      
      {formData.section_id && (
        <select
          value={formData.assigned_to_id}
          onChange={(e) => setFormData({ ...formData, assigned_to_id: e.target.value })}
        >
          <option value="">Assign Technician (Optional)</option>
          {technicians.map(t => (
            <option key={t.id} value={t.id}>
              {t.first_name} {t.last_name}
            </option>
          ))}
        </select>
      )}
      
      <button type="submit">Create Ticket</button>
    </form>
  );
}
```

#### Analytics Dashboard

```jsx
function TicketAnalytics() {
  const [analytics, setAnalytics] = useState(null);
  const [timeframe, setTimeframe] = useState('week');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchAnalytics = async () => {
      setLoading(true);
      try {
        const response = await fetch(
          `/api/analytics/tickets/?timeframe=${timeframe}&days=30&group_by=day`
        );
        const data = await response.json();
        setAnalytics(data);
      } catch (error) {
        console.error('Analytics error:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchAnalytics();
  }, [timeframe]);

  if (loading) return <div>Loading...</div>;
  if (!analytics) return <div>No data available</div>;

  return (
    <div className="analytics-dashboard">
      <h2>Ticket Analytics</h2>
      
      <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)}>
        <option value="day">Today</option>
        <option value="week">This Week</option>
        <option value="month">This Month</option>
      </select>

      <div className="summary">
        <h3>{analytics.ticket_counts.period}</h3>
        <p>Total: <strong>{analytics.ticket_counts.count}</strong> tickets</p>
      </div>

      <div className="status-breakdown">
        <h3>Status Breakdown</h3>
        {analytics.status_counts.map(status => (
          <div key={status.status} className="status-card">
            <span>{status.status}</span>
            <span>{status.count}</span>
          </div>
        ))}
      </div>

      <div className="distributions">
        <div>
          <h3>By Facility</h3>
          {analytics.facility_distribution.map(item => (
            <div key={item.facility__name}>
              {item.facility__name}: {item.count}
            </div>
          ))}
        </div>

        <div>
          <h3>By Section</h3>
          {analytics.section_distribution.map(item => (
            <div key={item.section__name}>
              {item.section__name}: {item.count}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
```

#### Ticket List Component

```jsx
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

function TicketList() {
  const navigate = useNavigate();
  const [tickets, setTickets] = useState([]);
  const [filters, setFilters] = useState({ status: '' });
  const [loading, setLoading] = useState(false);
  const [pagination, setPagination] = useState({
    currentPage: 1,
    totalPages: 1,
    nextUrl: null,
    prevUrl: null
  });

  useEffect(() => {
    fetchTickets();
  }, []);

  const fetchTickets = async (url = null) => {
    setLoading(true);
    try {
      const endpoint = url || buildUrl();
      const response = await fetch(endpoint);
      const data = await response.json();
      
      setTickets(data.results);
      setPagination({
        currentPage: data.current_page,
        totalPages: data.total_pages,
        nextUrl: data.next,
        prevUrl: data.previous
      });
    } catch (error) {
      console.error('Error fetching tickets:', error);
    } finally {
      setLoading(false);
    }
  };

  const buildUrl = () => {
    const params = new URLSearchParams();
    if (filters.status) params.append('status', filters.status);
    return `/api/tickets/?${params.toString()}`;
  };

  const handleFilterChange = (e) => {
    setFilters({ ...filters, status: e.target.value });
  };

  const applyFilters = () => {
    fetchTickets();
  };

  return (
    <div className="ticket-list">
      <h2>Tickets</h2>
      
      <div className="filters">
        <select value={filters.status} onChange={handleFilterChange}>
          <option value="">All Status</option>
          <option value="open">Open</option>
          <option value="assigned">Assigned</option>
          <option value="in_progress">In Progress</option>
          <option value="resolved">Resolved</option>
        </select>
        
        <button onClick={applyFilters}>Apply Filters</button>
      </div>

      {loading ? (
        <div>Loading...</div>
      ) : (
        <>
          <div className="ticket-grid">
            {tickets.map(ticket => (
              <div key={ticket.id} className="ticket-card">
                <h3>{ticket.ticket_no} - {ticket.title}</h3>
                <p>Status: <span className={`status-${ticket.status}`}>{ticket.status}</span></p>
                <p>Section: {ticket.section}</p>
                <button onClick={() => navigate(`/tickets/${ticket.id}`)}>View Details</button>
              </div>
            ))}
          </div>

          <div className="pagination">
            <button 
              onClick={() => fetchTickets(pagination.prevUrl)}
              disabled={!pagination.prevUrl}
            >
              Previous
            </button>
            <span>Page {pagination.currentPage} of {pagination.totalPages}</span>
            <button 
              onClick={() => fetchTickets(pagination.nextUrl)}
              disabled={!pagination.nextUrl}
            >
              Next
            </button>
          </div>
        </>
      )}
    </div>
  );
}

export default TicketList;
```

---

### Common Workflows

#### Workflow 1: Create and Assign Ticket

```javascript
// Step 1: Create ticket
const createResponse = await fetch('/api/tickets/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    title: 'Fix printer',
    description: 'Printer not working',
    section_id: 1,
    facility_id: 2
  })
});

const ticket = await createResponse.json();

// Step 2: Show available technicians
console.log('Available:', ticket.available_technicians);

// Step 3: Assign selected technician
const assignResponse = await fetch(`/api/tickets/${ticket.id}/`, {
  method: 'PATCH',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ assigned_to_id: 5 })
});
```

#### Workflow 2: Update Ticket Status

```javascript
// Get ticket details
const ticket = await fetch(`/api/tickets/42/`).then(r => r.json());

// Update status based on progress
const updateStatus = async (newStatus, reason = null) => {
  const payload = { status: newStatus };
  if (reason) payload.pending_reason = reason;
  
  await fetch(`/api/tickets/${ticket.id}/`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
};

// Example: Mark as in progress
await updateStatus('in_progress');

// Example: Mark as pending with reason
await updateStatus('pending', 'Waiting for parts');
```

#### Workflow 3: Dynamic Section-Based Technician Loading

```javascript
function TicketAssignment({ ticketId, sectionId }) {
  const [technicians, setTechnicians] = useState([]);

  useEffect(() => {
    if (sectionId) {
      fetch(`/api/technicians/?section_id=${sectionId}`)
        .then(r => r.json())
        .then(data => setTechnicians(data));
    }
  }, [sectionId]);

  const assignTechnician = async (techId) => {
    await fetch(`/api/tickets/${ticketId}/`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ assigned_to_id: techId })
    });
  };

  return (
    <select onChange={(e) => assignTechnician(e.target.value)}>
      <option value="">Select Technician</option>
      {technicians.map(t => (
        <option key={t.id} value={t.id}>
          {t.first_name} {t.last_name}
        </option>
      ))}
    </select>
  );
}
```

---

## Error Handling

### Invalid Technician Assignment

**Request:**
```json
{
  "assigned_to_id": 10
}
```

**Response (400 Bad Request):**
```json
{
  "error": "Technician bob.smith does not belong to section HVAC."
}
```

**Handling:**
```javascript
try {
  const response = await fetch(`/api/tickets/${id}/`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ assigned_to_id: techId })
  });
  
  if (!response.ok) {
    const error = await response.json();
    alert(error.error || 'Assignment failed');
  }
} catch (error) {
  console.error('Network error:', error);
}
```

### Invalid Status Transition

**Request:**
```json
{
  "status": "closed"
}
```

**Response (400 Bad Request):**
```json
{
  "error": "Invalid status transition from 'open' to 'closed'. Valid options: assigned"
}
```

### Modifying Closed Ticket

**Response (400 Bad Request):**
```json
{
  "error": "Cannot modify a closed ticket. Ticket is already finalized."
}
```

### Error Handling Best Practices

```javascript
async function updateTicket(id, data) {
  try {
    const response = await fetch(`/api/tickets/${id}/`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || `HTTP ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Update failed:', error.message);
    // Show user-friendly error message
    alert(`Failed to update ticket: ${error.message}`);
    throw error;
  }
}
```

---

## Best Practices

### 1. Use Available Technicians

✅ **Do:** Use `available_technicians` from ticket response
```javascript
const ticket = await fetch('/api/tickets/42/').then(r => r.json());
const techs = ticket.available_technicians; // Already filtered by section
```

❌ **Don't:** Manually filter all technicians
```javascript
// Inefficient - loads all technicians then filters client-side
const allTechs = await fetch('/api/users/?role=technician').then(r => r.json());
const filtered = allTechs.filter(t => t.sections.includes(sectionId));
```

### 2. Dynamic Loading

✅ **Do:** Load technicians when section changes
```javascript
const handleSectionChange = async (sectionId) => {
  const techs = await fetch(`/api/technicians/?section_id=${sectionId}`)
    .then(r => r.json());
  setTechnicians(techs);
};
```

### 3. Status Validation

✅ **Do:** Check valid transitions before updating
```javascript
const validTransitions = {
  'open': ['assigned'],
  'assigned': ['in_progress', 'pending'],
  'in_progress': ['pending', 'resolved'],
  'pending': ['in_progress', 'resolved'],
  'resolved': ['closed'],
  'closed': []
};

function canTransition(currentStatus, newStatus) {
  return validTransitions[currentStatus]?.includes(newStatus);
}
```

### 4. Pagination Handling

✅ **Do:** Use pagination metadata
```javascript
function Pagination({ data, onPageChange }) {
  return (
    <div>
      <button 
        onClick={() => onPageChange(data.previous)}
        disabled={!data.previous}
      >
        Previous
      </button>
      <span>Page {data.current_page} of {data.total_pages}</span>
      <button 
        onClick={() => onPageChange(data.next)}
        disabled={!data.next}
      >
        Next
      </button>
    </div>
  );
}
```

### 5. Analytics Caching

✅ **Do:** Cache analytics results
```javascript
const [analyticsCache, setAnalyticsCache] = useState({});

const fetchAnalytics = async (timeframe) => {
  // Check cache first
  if (analyticsCache[timeframe]) {
    return analyticsCache[timeframe];
  }
  
  const data = await fetch(`/api/analytics/tickets/?timeframe=${timeframe}`)
    .then(r => r.json());
  
  setAnalyticsCache({ ...analyticsCache, [timeframe]: data });
  return data;
};
```

### 6. Error Boundaries

✅ **Do:** Implement error boundaries in React
```javascript
class TicketErrorBoundary extends React.Component {
  state = { hasError: false };

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return <div>Something went wrong. Please refresh.</div>;
    }
    return this.props.children;
  }
}
```

### 7. Loading States

✅ **Do:** Show loading indicators
```javascript
function TicketList() {
  const [loading, setLoading] = useState(true);
  const [tickets, setTickets] = useState([]);

  useEffect(() => {
    setLoading(true);
    fetch('/api/tickets/')
      .then(r => r.json())
      .then(data => {
        setTickets(data.results);
        setLoading(false);
      });
  }, []);

  if (loading) return <LoadingSpinner />;
  return <TicketGrid tickets={tickets} />;
}
```

### 8. Optimistic Updates

✅ **Do:** Update UI immediately, rollback on error
```javascript
const updateTicketStatus = async (ticketId, newStatus) => {
  const oldTicket = tickets.find(t => t.id === ticketId);
  
  // Update UI immediately
  setTickets(tickets.map(t => 
    t.id === ticketId ? { ...t, status: newStatus } : t
  ));
  
  try {
    await fetch(`/api/tickets/${ticketId}/`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus })
    });
  } catch (error) {
    // Rollback on error
    setTickets(tickets.map(t => 
      t.id === ticketId ? oldTicket : t
    ));
    alert('Update failed');
  }
};
```

---

## Quick Reference

### Timeframe Mapping
```javascript
{
  'day': 1,      // Last 24 hours
  'week': 7,     // Last 7 days
  'month': 30    // Last 30 days
}
```

### Status Flow
```
open → assigned → in_progress ⟷ pending → resolved → closed
```

### Common Filters
```
?status=open                   # Open tickets
?assigned_to__isnull=true      # Unassigned tickets
?is_overdue=true               # Overdue tickets (>7 days)
?section=1                     # By section
?ordering=-created_at          # Newest first
```

### Key Endpoints
```
POST   /api/tickets/                          # Create ticket
PATCH  /api/tickets/{id}/                     # Update ticket
GET    /api/technicians/?section_id={id}     # Get technicians
GET    /api/analytics/tickets/?timeframe=week # Analytics
```

---

**For more detailed backend architecture, see:**
- [API Architecture](./ANALYTICS.md)
- [Project Structure](../PROJECT_STRUCTURE.md)
- [Testing Guide](../testing/TESTING.md)

**Support:** For issues or questions, contact the backend team or file an issue in the project repository.
