# Django Resolver - Ticket Management System

A comprehensive Django REST API application for managing maintenance tickets, facilities, and user feedback. This system enables organizations to efficiently track and resolve maintenance issues across different facilities and departments.

## 🚀 Features

### Core Functionality

- **Ticket Management**: Create, track, and resolve maintenance tickets with auto-generated ticket numbers
- **User Management**: Role-based access control (User, Admin, Technician, Manager)
- **Facility Management**: Organize tickets by facilities and sections
- **Comment System**: Real-time communication on tickets
- **Feedback System**: Rate and review completed tickets
- **Audit Logging**: Track all ticket activities for compliance

### API Features

- **RESTful API**: Full CRUD operations for all resources
- **Filtering & Search**: Filter tickets by status, facility, section, etc.
- **Django Admin**: Comprehensive admin interface for data management
- **Auto-generated Ticket Numbers**: Sequential ticket numbering (TKT-000001, TKT-000002, etc.)

### Business Logic

- **Overdue Detection**: Automatically identify tickets older than 24 hours
- **Status Tracking**: Complete ticket lifecycle management
- **User Role Management**: Different permission levels for different user types

## 🛠️ Technology Stack

- **Backend**: Django 4.2.7, Django REST Framework 3.14.0
- **Database**: SQLite (development), PostgreSQL ready
- **Authentication**: Django's built-in authentication system
- **API Documentation**: Built-in Django REST Framework browsable API
- **Admin Interface**: Django Admin with custom configurations

## 📋 Requirements

```txt
Django==4.2.7
djangorestframework==3.14.0
django-filter==23.3
python-decouple==3.8
```

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd django_resolver
```

### 2. Set Up Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Environment Configuration

Create a `.env` file in the project root:

```env
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=sqlite:///db.sqlite3
```

### 5. Database Setup

```bash
python manage.py makemigrations
python manage.py migrate
```

### 6. Create Superuser

```bash
python manage.py createsuperuser
```

### 7. Run Development Server

```bash
python manage.py runserver
```

The application will be available at `http://127.0.0.1:8000/`

## 📚 API Documentation

### Base URL

```
http://127.0.0.1:8000/api/
```

### Available Endpoints

#### Tickets

- `GET /api/tickets/` - List all tickets
- `POST /api/tickets/` - Create new ticket
- `GET /api/tickets/{id}/` - Get ticket details
- `PUT /api/tickets/{id}/` - Update ticket
- `DELETE /api/tickets/{id}/` - Delete ticket

**Filtering Options:**

- `?status=open` - Filter by status
- `?facility=1` - Filter by facility
- `?section=1` - Filter by section
- `?raised_by=1` - Filter by user

#### Users

- `GET /api/users/` - List all users
- `POST /api/users/` - Create new user
- `GET /api/users/{id}/` - Get user details

#### Facilities

- `GET /api/facilities/` - List all facilities
- `POST /api/facilities/` - Create new facility
- `GET /api/facilities/{id}/` - Get facility details

#### Sections

- `GET /api/sections/` - List all sections
- `POST /api/sections/` - Create new section

#### Comments

- `GET /api/comments/` - List all comments
- `POST /api/comments/` - Add comment to ticket

#### Feedback

- `GET /api/feedback/` - List all feedback
- `POST /api/feedback/` - Submit feedback for ticket

### Example API Usage

#### Create a Ticket

```bash
curl -X POST http://127.0.0.1:8000/api/tickets/ \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Broken Air Conditioner",
    "description": "AC unit in room 101 is not cooling",
    "section": 1,
    "facility": 1,
    "raised_by": 1,
    "status": "open"
  }'
```

#### Filter Tickets by Status

```bash
curl "http://127.0.0.1:8000/api/tickets/?status=open"
```

## 🗄️ Database Schema

### Models Overview

#### CustomUser

- Extends Django's AbstractUser
- Roles: User, Admin, Technician, Manager
- Additional fields for role-based access

#### Ticket

- Auto-generated ticket numbers (TKT-XXXXXX)
- Status tracking (Open, Assigned, In Progress, Resolved, Closed)
- Linked to facilities, sections, and users
- Automatic overdue detection

#### Facility

- Types: Building, ICT Equipment, Laundry, Kitchen, Residential
- Status and location tracking

#### Section

- Maintenance departments (IT, Plumbing, Electrical, etc.)
- Linked to facilities

#### Comment

- Thread-based discussions on tickets
- Author tracking and timestamps

#### Feedback Model

- 1-5 star rating system
- One feedback per ticket
- Comments and rating tracking

#### TicketLog

- Audit trail for all ticket actions
- User tracking for accountability

## 🧪 Testing

The project includes comprehensive test coverage:

### Run All Tests

```bash
python manage.py test tickets
```

### Run Specific Tests

```bash
# Model tests
python manage.py test tickets.tests.ModelTests

# API tests
python manage.py test tickets.tests.APITests

# Integration tests
python manage.py test tickets.tests.IntegrationTests
```

### Test Categories

- **Model Tests**: Database operations, business logic, validations
- **Serializer Tests**: Data serialization, user creation, validation
- **API Tests**: CRUD operations, filtering, response codes
- **Integration Tests**: Complete workflows, end-to-end scenarios

## 🔧 Admin Interface

Access the Django admin at `http://127.0.0.1:8000/admin/`

**Features:**

- User management with role assignments
- Ticket management with advanced filtering
- Facility and section organization
- Comment and feedback moderation
- Audit log viewing

## 🏗️ Project Structure

```
django_resolver/
├── manage.py
├── requirements.txt
├── README.md
├── resolver/              # Main project settings
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
└── tickets/               # Main application
    ├── __init__.py
    ├── admin.py          # Admin configurations
    ├── apps.py
    ├── models.py         # Database models
    ├── serializers.py    # API serializers
    ├── views.py          # API views
    ├── urls.py           # URL routing
    ├── tests.py          # Test cases
    └── migrations/       # Database migrations
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8 style guidelines
- Write tests for new features
- Update documentation for API changes
- Use meaningful commit messages

## 📝 API Response Examples

### Ticket List Response

```json
[
  {
    "id": 1,
    "ticket_no": "TKT-000001",
    "title": "Broken Air Conditioner",
    "description": "AC unit in room 101 is not cooling",
    "status": "open",
    "section": "HVAC Department",
    "facility": "Main Building",
    "raised_by": "john.doe",
    "assigned_to": null,
    "created_at": "2025-10-02T10:30:00Z",
    "updated_at": "2025-10-02T10:30:00Z",
    "comments": [],
    "feedback": null
  }
]
```

### User Creation Response

```json
{
  "id": 2,
  "username": "jane.smith",
  "first_name": "Jane",
  "last_name": "Smith",
  "email": "jane.smith@example.com",
  "role": "technician"
}
```

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Django and Django REST Framework communities
- Open source libraries used in this project

---

**Version**: 1.0.0  
**Last Updated**: October 2025  
**Status**: Active Development