# Django Resolver Documentation Index

Welcome to the comprehensive documentation for Django Resolver - a Django REST API for maintenance ticket management.

## � Find Docs by Your Role

**I'm a Frontend Developer** → Build your integration:
- [API Integration Guide](API_INTEGRATION_GUIDE.md) - Complete frontend guide with all endpoints
- [Authentication](AUTHENTICATION.md) - Implement login
- [Analytics API](api/ANALYTICS.md) - Add dashboards

**I'm a Backend Developer** → Build your feature:
- [Architecture Guide](ARCHITECTURE_GUIDE.md) - How the system works (NEW)
- [Codebase Architecture](CODEBASE_ARCHITECTURE.md) - Complete reference
- [Workflow Specification](specifications/WORKFLOW_SPEC.md) - Complete spec
- [Testing Guide](testing/TESTING.md) - Write and run tests

**I'm Setting Up Locally** → Get running:
- [First Time Setup](FIRST_TIME_SETUP.md) - Complete setup guide
- [Default Credentials](DEFAULT_CREDENTIALS.md) - Test user accounts
- [Main README](../README.md) - Quick start

**I'm DevOps/Deploying** → Deploy to production:
- [build.sh](../build.sh) - Build script
- [render.yaml](../render.yaml) - Render deployment config
- [Architecture Guide](ARCHITECTURE_GUIDE.md) - System design

---

## �📚 Quick Navigation

### 🚀 Getting Started

- **[Main README](../README.md)** - Project overview, quick start guide, and installation
- **[Codebase Architecture](CODEBASE_ARCHITECTURE.md)** - Complete codebase structure, file roles, data flows, and directory organization

### 🔌 API Documentation

- **[API Integration Guide](API_INTEGRATION_GUIDE.md)** - Complete API reference for frontend developers (all endpoints, authentication, examples)
- **[Analytics API](api/ANALYTICS.md)** - Analytics endpoints and role-based dashboards

### 📋 Specifications & Compliance

- **[Workflow Specification](specifications/WORKFLOW_SPEC.md)** - Complete ticket workflow specification with organizational scope and ticket placement architecture
- **[Compliance Audit](compliance/AUDIT_STATUS.md)** - Comprehensive compliance audit report (96% compliance status)

### 🏗️ Architecture & Design

- **[Codebase Architecture](CODEBASE_ARCHITECTURE.md)** - Complete codebase structure, file roles, and data flows

- **[API Layers](architecture/LAYERS.md)** - Layered architecture and design patterns

### 🔐 Authentication & Setup

- **[Authentication](AUTHENTICATION.md)** - Authentication system (password-based + future magic links)
- **[Default Credentials](DEFAULT_CREDENTIALS.md)** - Test account information


### 🚢 Deployment

- **[Build Configuration](../build.sh)** - Build script for deployment
- **[Render Config](../render.yaml)** - Render deployment configuration

### 🧪 Testing

- **[Testing Guide](testing/TESTING.md)** - Complete testing documentation including test organization, running tests, pytest fixtures (166 tests)
- **[Sample Queries](testing/SAMPLE_QUERIES.md)** - 40+ pre-built Django ORM query examples for exploring fixture data
- **[Organizational Testing](organizational/TESTING.md)** - Testing organizational features and hierarchies (pytest patterns)

### 📋 Reference

- **[Requirements](../requirements.txt)** - Python dependencies
- **[Pytest Config](../pytest.ini)** - Test configuration
- **[License](../LICENSE)** - MIT License

## 📂 Documentation Structure

```
docs/
├── 📘 Master Guides (Start Here)
│   ├── FIRST_TIME_SETUP.md          # Setup guide for new developers
│   ├── ARCHITECTURE_GUIDE.md        # System architecture overview
│   └── API_INTEGRATION_GUIDE.md     # Complete API reference & integration
│
├── INDEX.md                          # This file - documentation navigation
├── CODEBASE_ARCHITECTURE.md          # Complete technical reference
├── AUTHENTICATION.md                 # Authentication system details
├── DEFAULT_CREDENTIALS.md            # Test user accounts
│
├── specifications/                   # Workflow specs & requirements
│   └── WORKFLOW_SPEC.md             # Complete ticket workflow spec
│
├── compliance/                       # Compliance audits & reports
│   └── AUDIT_STATUS.md              # Consolidated compliance audit (96% pass)
│
├── api/                              # API documentation
│   └── ANALYTICS.md                 # Analytics endpoints & dashboards
│
├── architecture/                     # Architecture details
│   └── LAYERS.md                    # Layered architecture patterns
│
├── organizational/                   # Organizational features
│   └── TESTING.md                   # Organizational testing guide
│
└── testing/                          # Testing documentation
    ├── TESTING.md                    # Complete testing guide (166 tests)
    └── SAMPLE_QUERIES.md             # Django ORM query examples
```

## 🔍 Finding Documentation

### 📘 Master Guides (Recommended Entry Points)

**Choose based on your role:**

1. **[First Time Setup](FIRST_TIME_SETUP.md)** - New developers setting up locally
   - Complete 12-section setup guide
   - Covers: clone, venv, database, dependencies, migrations, verification
   - Includes troubleshooting section
   
2. **[Architecture Guide](ARCHITECTURE_GUIDE.md)** - Backend developers learning the system
   - System overview and technology stack
   - 4-layer architecture explanation
   - Ticket lifecycle and state machine
   - Organizational hierarchy
   - Role-based access control
   
3. **[API Integration Guide](API_INTEGRATION_GUIDE.md)** - Frontend developers building integrations
   - Complete authentication guide
   - All endpoint documentation with examples
   - Escalation, analytics, error handling
   - Code examples in JavaScript and Python

### By Task

**Setting Up Development Environment:**
1. [Main README](../README.md) - Installation steps
2. [Codebase Architecture](CODEBASE_ARCHITECTURE.md) - Project structure

**Building Frontend Integration:**
1. [API Integration Guide](API_INTEGRATION_GUIDE.md) - All endpoints with examples
2. [Analytics API](api/ANALYTICS.md) - Analytics queries and dashboards

**Understanding Architecture:**
1. [Architecture Guide](ARCHITECTURE_GUIDE.md) - System design and patterns
2. [Codebase Architecture](CODEBASE_ARCHITECTURE.md) - Complete technical reference
3. [API Layers](architecture/LAYERS.md) - Layered architecture patterns
4. [Workflow Specification](specifications/WORKFLOW_SPEC.md) - Complete workflow specification

**Reviewing Compliance & Spec:**
1. [Workflow Specification](specifications/WORKFLOW_SPEC.md) - Latest specification
2. [Compliance Audit](compliance/AUDIT_STATUS.md) - Audit findings (96% compliance)

**Setting Up Organizational Features:**
1. [First Time Setup](FIRST_TIME_SETUP.md) - Includes organizational hierarchy setup
2. [Organizational Testing](organizational/TESTING.md) - Test organizational features

**Deploying to Production:**
1. [Render Config](../render.yaml) - Cloud deployment configuration

**Writing Tests:**
1. [Testing Guide](testing/TESTING.md) - Complete test documentation including BaseTicketTestCase usage
2. [Sample Queries](testing/SAMPLE_QUERIES.md) - Query examples for exploring data
3. [Organizational Testing](organizational/TESTING.md) - Testing organizational features

### By Component

**Tickets Module:**
- [API Guide](api/GUIDE.md) - Complete ticket management API
- [Testing Guide](testing/TESTING.md) - Test organization and execution

**Analytics:**
- [Analytics API](api/ANALYTICS.md) - Analytics endpoints and usage

**Authentication:**
- [Authentication Guide](AUTHENTICATION.md) - System details and configuration

**Organizational Hierarchy:**
- [First Time Setup](FIRST_TIME_SETUP.md) - Feature setup and configuration
- [Organizational Testing](organizational/TESTING.md) - Test examples
- [Workflow Specification](specifications/WORKFLOW_SPEC.md) - Complete specification with organizational scope

**Compliance & Audit:**
- [Compliance Audit](compliance/AUDIT_STATUS.md) - Complete compliance findings (96% status)
- [Workflow Specification](specifications/WORKFLOW_SPEC.md) - Specification reference

## 🆘 Common Issues

**API Integration:** See [API Integration Guide](API_INTEGRATION_GUIDE.md)  
**Testing:** See [Testing Guide](testing/TESTING.md)  
**Database Queries:** See [Sample Queries](testing/SAMPLE_QUERIES.md)  
**Authentication:** See [Authentication](AUTHENTICATION.md)  
**Organizational Features:** See [First Time Setup](FIRST_TIME_SETUP.md)

## 📝 Contributing

When adding new documentation:
1. Place in appropriate subdirectory
2. Update this INDEX.md
3. Use clear, descriptive filenames
4. Follow existing formatting patterns

## 📧 Support

For issues or questions, refer to the relevant documentation section above or check the [Main README](../README.md) for contact information.
