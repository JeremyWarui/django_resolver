# First Time Setup Guide - Django Resolver

[← Back to Index](INDEX.md) | [← Back to README](../README.md)

**This is the complete, step-by-step guide to get Django Resolver running locally.** All setup procedures are consolidated here. For quick overview, see [README](../README.md).

**Time to complete**: 15-20 minutes  
**Prerequisites**: Python 3.10+, PostgreSQL 12+, Git

---

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Clone & Virtual Environment](#clone--virtual-environment)
3. [Database Configuration](#database-configuration)
4. [Install Dependencies](#install-dependencies)
5. [Environment Variables](#environment-variables)
6. [Database Setup](#database-setup)
7. [Load Test Data](#load-test-data)
8. [Set Test User Passwords](#set-test-user-passwords)
9. [Run Development Server](#run-development-server)
10. [Verify Installation](#verify-installation)
11. [Next Steps](#next-steps)
12. [Troubleshooting](#troubleshooting)

---

## System Requirements

### Required
- **Python**: 3.10 or higher
- **PostgreSQL**: 12 or higher
- **Git**: Latest version
- **pip**: Comes with Python

### Optional (for advanced features)
- **Docker/Docker Compose**: For containerized deployment
- **Redis**: For caching (not required for development)

Verify installations:
```bash
python --version      # Should show 3.10+
psql --version        # Should show 12+
git --version         # Should show latest
```

---

## Clone & Virtual Environment

### Step 1: Clone Repository
```bash
git clone https://github.com/yourusername/django_resolver.git
cd django_resolver
```

### Step 2: Create Virtual Environment
```bash
# Create virtual environment
python -m venv .venv

# Activate it
# On macOS/Linux:
source .venv/bin/activate

# On Windows:
.venv\Scripts\activate
```

You should see `(.venv)` in your terminal prompt.

### Step 3: Verify Activation
```bash
which python    # macOS/Linux - should show path in .venv
pip --version   # Should show pip version + .venv path
```

---

## Database Configuration

### Step 1: Create PostgreSQL Database

```bash
# Open PostgreSQL
psql postgres

# Create database and user
CREATE DATABASE django_resolver;
CREATE USER django_user WITH PASSWORD 'secure_password_here';
ALTER ROLE django_user SET client_encoding TO 'utf8';
ALTER ROLE django_user SET default_transaction_isolation TO 'read_committed';
ALTER ROLE django_user SET default_transaction_deferrable TO on;
ALTER ROLE django_user SET default_transaction_is_deferrable TO on;
GRANT ALL PRIVILEGES ON DATABASE django_resolver TO django_user;

# Exit psql
\q
```

### Step 2: Verify Connection

```bash
psql -U django_user -d django_resolver -h localhost
# Should connect successfully
# Type: \q to exit
```

---

## Install Dependencies

```bash
# Ensure you're in the project root
cd django_resolver

# Ensure virtual environment is activated
source .venv/bin/activate  # macOS/Linux

# Install all required packages
pip install -r requirements.txt

# Verify installation
pip list | grep -i django    # Should show Django 6.0.3
```

---

## Environment Variables

### Create .env File

```bash
# In the project root directory
touch .env

# Edit with your editor (nano, vim, VS Code, etc.)
nano .env
```

### Add Configuration

```env
# Database Configuration
DATABASE_URL=postgresql://django_user:secure_password_here@localhost:5432/django_resolver

# Django Settings
SECRET_KEY=your-secret-key-here-make-it-long-and-random
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Email (optional, only if magic links needed)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

# Optional Features
USE_TZ=True
TIME_ZONE=UTC
```

**Security Note**: Never commit `.env` to version control. It's already in `.gitignore`.

---

## Database Setup

### Step 1: Run Migrations

```bash
python manage.py migrate
```

Expected output:
```
Running migrations:
  Applying contenttypes.0001_initial... OK
  Applying auth.0001_initial... OK
  ...
  Applying tickets.0001_initial... OK
```

### Step 2: Verify Migrations

```bash
python manage.py showmigrations tickets
# Should show all migrations as [X] (applied)
```

---

## Load Test Data

### Step 1: Load Fixture (Recommended)

This fixture includes:
- 5 campuses
- 5 global departments, 11 CampusDepartments
- 11 sections with SectionTypes
- 22 ServiceItems across 15 ServiceCategories
- Users with different roles
- Sample tickets, comments and feedback

```bash
python manage.py loaddata tickets/fixtures/tickets_initial_data.json
```

Expected output:
```
Installed N object(s) from ...
```

### Step 2: Verify Data Loaded

```bash
python manage.py shell

from tickets.models import Campus, Department, CampusDepartment, Section, CustomUser, Ticket

print(f"Campuses: {Campus.objects.count()}")
print(f"Departments: {Department.objects.count()}")
print(f"CampusDepartments: {CampusDepartment.objects.count()}")
print(f"Sections: {Section.objects.count()}")
print(f"Users: {CustomUser.objects.count()}")
print(f"Tickets: {Ticket.objects.count()}")

exit()
```

Expected output:
```
Campuses: 5
Departments: 5
CampusDepartments: 11
Sections: 11
Users: 20+
Tickets: 100+
```

---

## Set Test User Passwords

### Option A: Set Selected Users (Recommended)

```bash
python manage.py shell

from tickets.models import CustomUser

# Set passwords for common test users
users = {
    'admin_user': 'adminuser123',
    'jane_user': 'janedoe123',
    'tech_alex': 'alexsmith123',
}

for username, password in users.items():
    try:
        user = CustomUser.objects.get(username=username)
        user.set_password(password)
        user.save()
        print(f'✓ Set password for {username}')
    except CustomUser.DoesNotExist:
        print(f'✗ User {username} not found')

exit()
```

### Option B: Set All Users

```bash
python manage.py shell

from tickets.models import CustomUser

# Get all users and set passwords from DEFAULT_CREDENTIALS
credentials = {
    'admin_user': 'adminuser123',
    'user_sarah': 'adminuser123',
    'manager_ict': 'adminuser123',
    # Add more from docs/DEFAULT_CREDENTIALS.md as needed
}

for username, password in credentials.items():
    try:
        user = CustomUser.objects.get(username=username)
        user.set_password(password)
        user.save()
        print(f'✓ {username}')
    except CustomUser.DoesNotExist:
        pass

print('\nAll passwords set!')
exit()
```

**See [Default Credentials](DEFAULT_CREDENTIALS.md) for complete list of test users and passwords.**

---

## Run Development Server

```bash
python manage.py runserver
```

Expected output:
```
Django version 5.2.7, using settings 'resolver.settings'
Starting development server at http://127.0.0.1:8000/
Quit the server with CONTROL-C.
```

Access in browser:
- **API Root**: http://127.0.0.1:8000/api/
- **Admin Panel**: http://127.0.0.1:8000/admin/
- **API Documentation**: http://127.0.0.1:8000/api/ (if DRF browsable API enabled)

---

## Verify Installation

### Step 1: Create Superuser (Optional)

If you want full admin access:
```bash
python manage.py createsuperuser

Username: admin_test
Email: admin@test.com
Password: (choose secure password)
Password (again): (confirm)
```

### Step 2: Test API Login

Open new terminal (keep server running):
```bash
# Login as test user
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin_user", "password": "adminuser123"}'
```

Expected response:
```json
{
  "token": "abc123def456...",
  "user": {
    "id": 1,
    "username": "admin_user",
    "email": "admin@example.com",
    "role": "admin"
  }
}
```

### Step 3: Run Tests (Optional)

```bash
# Run all tests to verify everything works
pytest tickets/tests/ -v

# Expected: All tests pass (~258 tests)
```

---

## Next Steps

### For Frontend Developers
1. Read [API Integration Guide](API_INTEGRATION_GUIDE.md) - Complete API reference
2. Start with authentication endpoints
3. Build ticket management features

### For Backend Developers
1. Read [Architecture Guide](ARCHITECTURE_GUIDE.md) - How the system works
2. Review [Workflow Specification](specifications/WORKFLOW_SPEC.md) - Business rules
3. Check [Testing Guide](testing/TESTING.md) - Write tests for features

### For DevOps/Deployment
1. Review [Render Config](../render.yaml) - Cloud deployment
2. Read build script: [build.sh](../build.sh)
3. Review production environment variables

### For Everyone
1. Check [Documentation Index](INDEX.md) - Find specific topics
2. Review [Sample Queries](testing/SAMPLE_QUERIES.md) - Common database queries
3. Reference [Default Credentials](DEFAULT_CREDENTIALS.md) - Test user accounts

---

## Troubleshooting

### Common Issues

**❌ Problem**: `psql: error: connection refused`
```
✅ Solution:
1. Ensure PostgreSQL is running: brew services list (macOS) or systemctl status postgresql (Linux)
2. Start PostgreSQL if needed: brew services start postgresql (macOS)
3. Verify port: psql -U postgres -p 5432 -h localhost
```

**❌ Problem**: `ModuleNotFoundError: No module named 'django'`
```
✅ Solution:
1. Ensure virtual environment is activated: source .venv/bin/activate
2. Reinstall requirements: pip install -r requirements.txt
3. Verify: python -c "import django; print(django.VERSION)"
```

**❌ Problem**: `django.core.exceptions.ImproperlyConfigured: SET DEVELOPMENT to a proper value`
```
✅ Solution:
1. Check .env file exists: ls -la .env
2. Ensure DEBUG is set: grep DEBUG .env
3. Reload environment: deactivate && source .venv/bin/activate
```

**❌ Problem**: `Installed 0 object(s)` when loading fixtures
```
✅ Solution:
1. Check fixture path: ls tickets/fixtures/
2. Verify migrations ran: python manage.py showmigrations
3. Check database connection: python manage.py dbshell
4. Try specific fixture: python manage.py loaddata tickets/fixtures/tickets_initial_data.json
```

**❌ Problem**: Tests fail with `OperationalError: relation does not exist`
```
✅ Solution:
1. Clear test database: pytest --create-db
2. Run migrations again: python manage.py migrate
3. Reload fixtures: python manage.py loaddata tickets/fixtures/tickets_initial_data.json
4. Run tests: pytest tickets/tests/
```

### Getting Help

- **API Docs**: [API Integration Guide](API_INTEGRATION_GUIDE.md)
- **Architecture Questions**: [Architecture Guide](ARCHITECTURE_GUIDE.md)
- **Testing**: [Testing Guide](testing/TESTING.md)
- **Workflow**: [Workflow Specification](specifications/WORKFLOW_SPEC.md)
- **Project README**: [README](../README.md)

---

**Last Updated**: March 18, 2026  
**Status**: ✅ Complete & Tested
