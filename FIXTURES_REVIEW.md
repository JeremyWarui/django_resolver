# Fixtures File Review - Critical Issues Found

## Issues Summary

### 🔴 CRITICAL - Role String Mismatch
**Problem**: Fixture uses deprecated role strings; code expects new strings
- ❌ Fixture: `"role": "director"` → ✅ Code expects: `"role": "manager"`
- ❌ Fixture: `"role": "section_head"` → ✅ Code expects: `"role": "head_of_section"`

**Impact**: Users will have invalid roles; permission checks will fail

**Affected records**: 
- User ID 3 (director_jane)
- Users 6, 7, 8, 9 (section_head_*)

---

### 🔴 CRITICAL - Section Structure Misalignment

**Current fixture structure**:
```
Administration Department (NRB Campus)
├── Plumbing (section id=2)
├── Electrical (section id=3)
├── Carpentry and Masonry (section id=4)
├── General Services (section id=7)
└── Operations (section id=8)
```

**Desired structure** (per requirements):
```
Administration Department (NRB Campus)
└── Maintenance (ONE section for all maintenance work)
    └── Technicians assigned work by ServiceCategory:
        ├── Electrical Services (ServiceCategory)
        ├── Plumbing Services (ServiceCategory)
        ├── Carpentry Services (ServiceCategory)
        ├── Masonry Services (ServiceCategory)
        └── Painting Services (ServiceCategory)
```

**Impact**: 
- Over-fragmenting sections breaks the organizational scope model
- Technician assignment logic assumes fewer, broader sections
- HoS/HoD scope validation expects consolidated sections

**Root cause**: Work types should be in ServiceCategory/ServiceItem (Phase 4), not as separate sections

---

### 🟡 MAJOR - Missing Manager/Director Users

**Problem**: No users with "manager" role
- Should have: 1 Manager for ICT Department (cross-campus)
- Should have: 1 Manager for Administration Department (cross-campus)

**Current managers in fixture**: 0
**Expected managers**: 2+

**Impact**: 
- No way to test cross-campus manager analytics
- Manager dashboard endpoints will have no test data

---

### 🟡 MAJOR - Incomplete Technician-Section Assignment

**Problem**: Technician M2M relationships not fully populated
- Tech records created but sections M2M not set

**Current state**:
```
tech_alex (technician) → NOT assigned to any section
tech_john (technician) → NOT assigned to any section
tech_carol (technician) → NOT assigned to any section
tech_robert (technician) → NOT assigned to any section
```

**Impact**: Tickets assigned to unassigned technicians; scope validation fails

---

### 🟡 MAJOR - Missing User Organization Context

**Problem**: Users missing `primary_campus` and `primary_department` assignments
- Users should have these for scope-aware queries

**Current state**:
```json
{
  "pk": 4,
  "username": "hod_alex",
  "role": "hod",
  "primary_campus": null,
  "primary_department": null
}
```

**Expected**: HoD must have both set

---

### 🟠 MINOR - Missing Token Auth Records

**Issue**: 8 token records exist but not all users have corresponding tokens
- Users 1-14 should all have tokens for login testing
- Missing: Users 17, 18

**Impact**: Can't test auth for all user types

---

### 🟠 MINOR - Inconsistent Campus Distribution

**Current distribution**:
- Campus 1 (NRB): 1 ICT + 1 Admin dept (2 depts)
- Campus 2 (MSA): 1 Admin + 1 Training dept (2 depts)
- Campus 3 (MTG): 1 HR dept (1 dept)
- Campus 4 (EMB): 1 ICT + 1 Admin dept (2 depts)
- Campus 5 (BAR): 1 ICT + 1 Admin dept (2 depts)

**Should be**: More balanced distribution across all 5 campuses (ICT + Administration at minimum)

---

### 📋 Fixture Structure Checklist

| Model | Count | Status | Notes |
|-------|-------|--------|-------|
| Organization | 1 | ✅ | Correct |
| Campus | 5 | ✅ | Correct |
| Department | 9 | ⚠️ | Unbalanced distribution |
| Section | 20 | 🔴 | Should be ~5-6 (too many) |
| CustomUser | 16 | 🔴 | Missing managers |
| Facility | 11 | ✅ | Adequate |
| Ticket | 34 | ✅ | Good variety |
| Comment | 7 | ✅ | Adequate |
| Feedback | 5 | ✅ | Adequate |
| TicketLog | 10 | ✅ | Adequate |
| Token | 8 | ⚠️ | Incomplete (missing for some users) |
| DepartmentType | 0 | ⚠️ | Phase 4 (OK to skip for now) |
| SectionType | 0 | ⚠️ | Phase 4 (OK to skip for now) |
| ServiceCategory | 0 | ⚠️ | Phase 4 (OK to skip for now) |
| ServiceItem | 0 | ⚠️ | Phase 4 (OK to skip for now) |

---

## Required Fixes (in order of priority)

### Priority 1: Fix role strings
```json
// OLD
{"pk": 3, "role": "director"}
// NEW
{"pk": 3, "role": "manager"}

// OLD
{"pk": 6, "role": "section_head"}
// NEW
{"pk": 6, "role": "head_of_section"}
```

### Priority 2: Consolidate sections
- Delete separate sections: Plumbing, Electrical, Carpentry, etc.
- Create ONE "Maintenance" section per Administration department
- Reassign all tickets from old sections to Maintenance section
- Create M2M assignments for technicians to Maintenance section

### Priority 3: Add manager users
- Create manager_ict_nrb (manager for ICT dept, no campus/dept assignments)
- Create manager_adm_nrb (manager for Administration dept, no campus/dept assignments)
- Create tokens for these users

### Priority 4: Set user organizational context
- Assign primary_campus and primary_department to all non-admin users
- HoD: set both
- Head of Section: set both
- Technician: set both

### Priority 5: Complete technician-section assignments
- Ensure all technicians have M2M relationship to their section(s)
- Add through-table records in fixture

---

## Recommended Data Structure

```
Organization: Kenya School of Government
├── Campus 1 (NRB)
│   ├── Department 1 (ICT)
│   │   └── Section 1 (ICT Support) - HoS: hos_network_nrb
│   └── Department 2 (Administration)
│       └── Section 2 (Maintenance) - HoS: hos_maint_nrb
│           ├── Tech: tech_alex (Electrical)
│           ├── Tech: tech_john (Plumbing)
│           ├── Tech: tech_carol (Carpentry)
│           └── Tech: tech_robert (General)
│
├── Campus 2 (MSA)
│   ├── Department 3 (ICT)
│   │   └── Section 3 (ICT Support) - HoS: hos_ict_msa
│   └── Department 4 (Administration)
│       └── Section 4 (Maintenance) - HoS: hos_maint_msa
│
├── Campus 3 (MTG) [minimal]
│   ├── Department 5 (ICT)
│   └── Department 6 (Administration)
│
├── Campus 4 (EMB) [minimal]
└── Campus 5 (BAR) [minimal]

Users:
├── admin_user (admin) - system-wide
├── manager_ict (manager) - ICT dept across all campuses
├── manager_adm (manager) - Administration dept across all campuses
├── hod_ict_nrb (hod) - ICT at NRB
├── hod_ict_msa (hod) - ICT at MSA
├── hod_adm_nrb (hod) - Administration at NRB
├── hos_network_nrb (head_of_section) - ICT Support at NRB
├── hos_maint_nrb (head_of_section) - Maintenance at NRB
├── hos_maint_msa (head_of_section) - Maintenance at MSA
├── tech_alex (technician) - Maintenance/Electrical at NRB
├── tech_john (technician) - Maintenance/Plumbing at NRB
├── tech_carol (technician) - Maintenance/Carpentry at NRB
├── tech_robert (technician) - Maintenance/General at NRB
├── tech_msa (technician) - Maintenance at MSA
├── user_sarah (user) - NRB, creates tickets
├── user_msa (user) - MSA, creates tickets
└── user_mtg (user) - MTG, creates tickets
```

---

## Next Steps

1. **Generate corrected fixtures file** with all fixes applied
2. **Verify department-campus relationships** are complete
3. **Add Phase 4 models** (DepartmentType, SectionType, ServiceCategory, ServiceItem) in separate fixture or as future work
4. **Test fixture load**: `python manage.py loaddata tickets_initial_data --ignorenonexistent`
5. **Verify roles**: `python manage.py shell` → check CustomUser role values

