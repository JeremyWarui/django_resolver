# Django Resolver Documentation Index

Welcome to the comprehensive documentation for Django Resolver - a Django REST API for maintenance ticket management.

## 📚 Quick Navigation

### 🚀 Getting Started

- **[Main README](../README.md)** - Project overview, quick start guide, and installation
- **[Codebase Architecture](CODEBASE_ARCHITECTURE.md)** - Complete codebase structure, file roles, data flows, and directory organization

### 🔌 API Documentation

- **[API Guide](api/GUIDE.md)** - Complete API reference for frontend developers
- **[Analytics API](api/ANALYTICS.md)** - Analytics endpoints and usage

### 📋 Specifications & Compliance

- **[Workflow Specification](specifications/WORKFLOW_SPEC.md)** - Complete ticket workflow specification with organizational scope and ticket placement architecture
- **[Compliance Audit](compliance/AUDIT_STATUS.md)** - Comprehensive compliance audit report (96% compliance status)

### 🏗️ Architecture & Design

- **[Codebase Architecture](CODEBASE_ARCHITECTURE.md)** - Complete codebase structure, file roles, and data flows
- **[Architecture Diagrams](ARCHITECTURE_DIAGRAMS.md)** - Visual flow diagrams and module interactions
- **[API Layers](architecture/LAYERS.md)** - Layered architecture and design patterns

### 🔐 Authentication & Setup

- **[Authentication](AUTHENTICATION.md)** - Authentication system (password-based + future magic links)
- **[Default Credentials](DEFAULT_CREDENTIALS.md)** - Test account information
- **[Organizational Setup](organizational/SETUP.md)** - Setting up organizational hierarchy features

### 🚢 Deployment

- **[Build Configuration](../build.sh)** - Build script for deployment
- **[Render Config](../render.yaml)** - Render deployment configuration

### 🧪 Testing

- **[Testing Guide](testing/TESTING.md)** - Complete testing documentation including test organization, running tests, and using BaseTicketTestCase
- **[Sample Queries](testing/SAMPLE_QUERIES.md)** - 20+ pre-built Django ORM query examples for exploring fixture data
- **[Organizational Testing](organizational/TESTING.md)** - Testing organizational features and hierarchies

### 📋 Reference

- **[Requirements](../requirements.txt)** - Python dependencies
- **[Pytest Config](../pytest.ini)** - Test configuration
- **[License](../LICENSE)** - MIT License

## 📂 Documentation Structure

```
docs/
├── INDEX.md                          # This file - documentation navigation
├── CODEBASE_ARCHITECTURE.md          # Complete architecture overview
├── AUTHENTICATION.md                 # Authentication system
├── ARCHITECTURE_DIAGRAMS.md          # Visual diagrams
├── DEFAULT_CREDENTIALS.md            # Test credentials
├── ORGANIZATIONAL_IMPLEMENTATION_PLAN.md  # Implementation tracking
├── specifications/                   # Workflow specifications & requirements
│   └── WORKFLOW_SPEC.md             # Complete workflow specification
├── compliance/                       # Compliance audits & reports
│   └── AUDIT_STATUS.md              # Consolidated compliance audit (96% status)
├── api/                              # API documentation
│   ├── GUIDE.md                     # Complete API reference
│   └── ANALYTICS.md                 # Analytics endpoints
├── architecture/                     # Architecture and design docs
│   └── LAYERS.md                    # API layered architecture
├── organizational/                   # Organizational features
│   ├── SETUP.md                     # Setup guide
│   └── TESTING.md                   # Testing guide
└── testing/                          # Testing documentation
    ├── TESTING.md                    # Complete testing guide
    └── SAMPLE_QUERIES.md             # Query examples
```

## 🔍 Finding Documentation

### By Task

**Setting Up Development Environment:**
1. [Main README](../README.md) - Installation steps
2. [Codebase Architecture](CODEBASE_ARCHITECTURE.md) - Project structure

**Building Frontend Integration:**
1. [API Guide](api/GUIDE.md) - All endpoints
2. [Analytics API](api/ANALYTICS.md) - Analytics queries

**Understanding Architecture:**
1. [API Layers](architecture/LAYERS.md) - Code organization
2. [Codebase Architecture](CODEBASE_ARCHITECTURE.md) - Complete directory overview
3. [Architecture Diagrams](ARCHITECTURE_DIAGRAMS.md) - Visual references
4. [Workflow Specification](specifications/WORKFLOW_SPEC.md) - Complete specification

**Reviewing Compliance & Spec:**
1. [Workflow Specification](specifications/WORKFLOW_SPEC.md) - Latest specification
2. [Compliance Audit](compliance/AUDIT_STATUS.md) - Audit findings (96% compliance)

**Setting Up Organizational Features:**
1. [Organizational Setup](organizational/SETUP.md) - Implementation guide
2. [Organizational Implementation Plan](ORGANIZATIONAL_IMPLEMENTATION_PLAN.md) - Phase tracking

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
- [Organizational Setup](organizational/SETUP.md) - Feature setup
- [Organizational Testing](organizational/TESTING.md) - Test examples
- [Implementation Plan](ORGANIZATIONAL_IMPLEMENTATION_PLAN.md) - Phase tracking
- [Workflow Specification](specifications/WORKFLOW_SPEC.md) - Complete specification

**Compliance & Audit:**
- [Compliance Audit](compliance/AUDIT_STATUS.md) - Complete compliance findings (96% status)
- [Workflow Specification](specifications/WORKFLOW_SPEC.md) - Specification reference

## 🆘 Common Issues

**API Integration:** See [API Guide](api/GUIDE.md)  
**Testing:** See [Testing Guide](testing/TESTING.md)  
**Database Queries:** See [Sample Queries](testing/SAMPLE_QUERIES.md)  
**Authentication:** See [Authentication](AUTHENTICATION.md)  
**Organizational Features:** See [Organizational Setup](organizational/SETUP.md)

## 📝 Contributing

When adding new documentation:
1. Place in appropriate subdirectory
2. Update this INDEX.md
3. Use clear, descriptive filenames
4. Follow existing formatting patterns

## 📧 Support

For issues or questions, refer to the relevant documentation section above or check the [Main README](../README.md) for contact information.
