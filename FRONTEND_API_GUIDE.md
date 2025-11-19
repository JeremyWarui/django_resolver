# Ticket Management API Guide for Frontend

## Creating and Updating Tickets

### 1. Create a New Ticket

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
  "description": "The air conditioning unit is not working properly",
  "status": "open",
  "section_id": 2,
  "section": "HVAC",
  "facility_id": 1,
  "facility": "Main Building",
  "raised_by": "john.doe",
  "assigned_to_id": null,
  "assigned_to": null,
  "available_technicians": [
    {
      "id": 5,
      "username": "jane.tech",
      "first_name": "Jane",
      "last_name": "Tech"
    },
    {
      "id": 8,
      "username": "bob.technician",
      "first_name": "Bob",
      "last_name": "Technician"
    }
  ],
  "created_at": "2025-11-20T10:30:00Z",
  "updated_at": "2025-11-20T10:30:00Z",
  "pending_reason": null,
  "comments": [],
  "feedback": null
}
```

**Notes:**
- `raised_by` is automatically set to the authenticated user
- `status` defaults to "open"
- `ticket_no` is auto-generated
- `available_technicians` shows who can be assigned based on the section

---

### 2. Update a Ticket (Assign Technician)

**Endpoint:** `PATCH /api/tickets/{id}/`

**Request Body (Assign technician):**
```json
{
  "assigned_to_id": 5
}
```

**Response (200 OK):**
```json
{
  "id": 42,
  "ticket_no": "TKT-000042",
  "title": "Broken AC in Conference Room",
  "description": "The air conditioning unit is not working properly",
  "status": "assigned",
  "section_id": 2,
  "section": "HVAC",
  "facility_id": 1,
  "facility": "Main Building",
  "raised_by": "john.doe",
  "assigned_to_id": 5,
  "assigned_to": {
    "id": 5,
    "username": "jane.tech",
    "first_name": "Jane",
    "last_name": "Tech",
    "email": "jane@example.com",
    "role": "technician",
    "sections": [2, 3]
  },
  "available_technicians": [
    {
      "id": 5,
      "username": "jane.tech",
      "first_name": "Jane",
      "last_name": "Tech"
    },
    {
      "id": 8,
      "username": "bob.technician",
      "first_name": "Bob",
      "last_name": "Technician"
    }
  ],
  "created_at": "2025-11-20T10:30:00Z",
  "updated_at": "2025-11-20T10:35:00Z",
  "pending_reason": null,
  "comments": [],
  "feedback": null
}
```

**Notes:**
- Status automatically changes from "open" to "assigned" when technician is assigned
- Only technicians who belong to the ticket's section can be assigned
- Assignment validation is enforced in the backend

---

### 3. Update Ticket Status

**Endpoint:** `PATCH /api/tickets/{id}/`

**Request Body (Mark as in progress):**
```json
{
  "status": "in_progress"
}
```

**Request Body (Mark as pending with reason):**
```json
{
  "status": "pending",
  "pending_reason": "Waiting for replacement parts from supplier"
}
```

**Request Body (Mark as resolved):**
```json
{
  "status": "resolved"
}
```

**Valid Status Transitions:**
```
open → assigned
assigned → in_progress, pending
in_progress → pending, resolved
pending → in_progress, resolved
resolved → closed (admin/manager only)
closed → (no further transitions)
```

---

### 4. Get Available Technicians for a Section

**Method 1: Use the ticket detail response**

When you GET or POST a ticket, the response includes `available_technicians`:

**Endpoint:** `GET /api/tickets/{id}/`

**Response includes:**
```json
{
  "available_technicians": [
    {
      "id": 5,
      "username": "jane.tech",
      "first_name": "Jane",
      "last_name": "Tech"
    }
  ]
}
```

**Method 2: Use the dedicated technicians endpoint**

**Endpoint:** `GET /api/technicians/?section_id={section_id}`

**Example:** `GET /api/technicians/?section_id=2`

**Response (200 OK):**
```json
[
  {
    "id": 5,
    "username": "jane.tech",
    "first_name": "Jane",
    "last_name": "Tech",
    "email": "jane@example.com",
    "role": "technician",
    "sections": [2, 3]
  },
  {
    "id": 8,
    "username": "bob.technician",
    "first_name": "Bob",
    "last_name": "Technician",
    "email": "bob@example.com",
    "role": "technician",
    "sections": [2]
  }
]
```

**Without section filter:** `GET /api/technicians/`
Returns all technicians (useful for admin views)

---

## Frontend Workflow Examples

### Scenario 1: Creating a Ticket with Dropdown for Technicians

```javascript
// 1. User fills out ticket form
const ticketData = {
  title: formData.title,
  description: formData.description,
  section_id: formData.sectionId,
  facility_id: formData.facilityId
};

// 2. Create ticket
const response = await fetch('/api/tickets/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(ticketData)
});

const ticket = await response.json();

// 3. Show available technicians in UI
const availableTechs = ticket.available_technicians;
// Populate dropdown with availableTechs

// 4. Optionally assign immediately (or let user assign later)
if (selectedTechnicianId) {
  await fetch(`/api/tickets/${ticket.id}/`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ assigned_to_id: selectedTechnicianId })
  });
}
```

### Scenario 2: Dynamic Technician Dropdown Based on Section

```javascript
// When user selects a section, fetch available technicians
const handleSectionChange = async (sectionId) => {
  const response = await fetch(`/api/technicians/?section_id=${sectionId}`);
  const technicians = await response.json();
  
  // Update dropdown options
  setAvailableTechnicians(technicians);
};

// Form with real-time technician filtering
<Select onChange={handleSectionChange}>
  <option value="">Select Section</option>
  {sections.map(s => <option value={s.id}>{s.name}</option>)}
</Select>

<Select>
  <option value="">Assign Technician (Optional)</option>
  {availableTechnicians.map(t => (
    <option value={t.id}>{t.first_name} {t.last_name}</option>
  ))}
</Select>
```

### Scenario 3: Updating Ticket from Ticket Detail Page

```javascript
// Get ticket details (includes available technicians)
const ticket = await fetch(`/api/tickets/${ticketId}`).then(r => r.json());

// Show assign button if unassigned
if (!ticket.assigned_to) {
  // Show dropdown with ticket.available_technicians
  const assignTechnician = async (technicianId) => {
    await fetch(`/api/tickets/${ticketId}/`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ assigned_to_id: technicianId })
    });
    
    // Refresh ticket data
    window.location.reload();
  };
}

// Update status
const updateStatus = async (newStatus, pendingReason = null) => {
  const payload = { status: newStatus };
  if (pendingReason) {
    payload.pending_reason = pendingReason;
  }
  
  await fetch(`/api/tickets/${ticketId}/`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
};
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

---

## Complete API Endpoints Summary

### Tickets
- `GET /api/tickets/` - List tickets (with filters)
- `POST /api/tickets/` - Create ticket
- `GET /api/tickets/{id}/` - Get ticket detail
- `PATCH /api/tickets/{id}/` - Update ticket
- `DELETE /api/tickets/{id}/` - Delete ticket

### Technicians
- `GET /api/technicians/` - List all technicians
- `GET /api/technicians/?section_id={id}` - List technicians by section

### Users
- `GET /api/users/` - List all users
- `GET /api/users/?role=technician` - List technicians
- `GET /api/users/?role=technician&sections={id}` - Technicians by section (alternative)

### Sections & Facilities
- `GET /api/sections/` - List sections
- `GET /api/facilities/` - List facilities

---

## React/Vue Component Example

### React Ticket Form Component

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
    // Load sections and facilities on mount
    fetch('/api/sections/').then(r => r.json()).then(data => setSections(data.results));
    fetch('/api/facilities/').then(r => r.json()).then(data => setFacilities(data.results));
  }, []);

  const handleSectionChange = async (sectionId) => {
    setFormData({ ...formData, section_id: sectionId, assigned_to_id: '' });
    
    if (sectionId) {
      // Fetch technicians for selected section
      const response = await fetch(`/api/technicians/?section_id=${sectionId}`);
      const data = await response.json();
      setTechnicians(data);
    } else {
      setTechnicians([]);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    // Create ticket
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
      // Redirect or reset form
    }
  };

  return (
    <form onSubmit={handleSubmit}>
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

---

## Key Points for Frontend Developers

1. **Available Technicians**: The `available_technicians` field in ticket responses shows who can be assigned based on the section.

2. **Dynamic Filtering**: Use `/api/technicians/?section_id={id}` to get technicians filtered by section when building assignment dropdowns.

3. **Automatic Status Updates**: When you assign a technician to an "open" ticket, the status automatically changes to "assigned".

4. **Validation**: The backend enforces that only technicians belonging to the ticket's section can be assigned.

5. **Caching**: List endpoints are cached, so repeated queries are fast (2-15 minute TTL depending on endpoint).

6. **Pagination**: All list endpoints support pagination with `?page=1&page_size=10` parameters.

7. **Filters**: Ticket lists support filters like `?status=open`, `?assigned_to__isnull=true`, `?is_overdue=true`, etc.
