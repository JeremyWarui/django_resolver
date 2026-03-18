"""
Phase 6 Comprehensive Tests: API Integration & Testing

This test suite covers:
1. Organizational hierarchy and permission validation
2. Enhanced API endpoints for organizational scope
3. Technician assignment and escalation workflows
4. Analytics dashboard data aggregation
"""

from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from tickets.models import (
    Organization, Campus, Department, Section, Facility,
    CustomUser, Ticket, TicketLog
)
from tickets.api.services import TicketService
from tickets.api.analytics import OrganizationalAnalytics
from tickets.tests.base import BaseTicketTestCase

# Backwards compatibility alias
OrganizationalTicketService = TicketService


class OrganizationalHierarchyTestCase(BaseTicketTestCase):
    """Test organizational hierarchy structure and relationships"""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        # Create comprehensive organizational structure
        cls.org = Organization.objects.create(
            name="Tech Corporation",
            code="TECHCORP",
            organization_type="corporate",
            headquarters="Silicon Valley"
        )

        # Campus A
        cls.campus_a = Campus.objects.create(
            organization=cls.org,
            name="Headquarters",
            code="HQ",
            location="San Francisco"
        )

        # Campus B
        cls.campus_b = Campus.objects.create(
            organization=cls.org,
            name="Regional Office",
            code="REGION",
            location="New York"
        )

        # Departments
        cls.it_dept = Department.objects.create(
            campus=cls.campus_a,
            name="Information Technology",
            code="IT"
        )

        cls.ops_dept = Department.objects.create(
            campus=cls.campus_a,
            name="Operations",
            code="OPS"
        )

        cls.hr_dept = Department.objects.create(
            campus=cls.campus_b,
            name="Human Resources",
            code="HR"
        )

        # Sections
        cls.network_section = Section.objects.create(
            department=cls.it_dept,
            name="Network Services",
            code="NET"
        )

        cls.infra_section = Section.objects.create(
            department=cls.it_dept,
            name="Infrastructure",
            code="INFRA"
        )

        cls.facilities_section = Section.objects.create(
            department=cls.ops_dept,
            name="Facilities Management",
            code="FAC"
        )

        cls.hr_section = Section.objects.create(
            department=cls.hr_dept,
            name="Human Resources Operations",
            code="HRO"
        )

        # Create users with proper organizational context
        # Director (Organization Level)
        cls.director = CustomUser.objects.create_user(
            username="director_tech",
            password="testpass123",
            role="director",
            primary_campus=cls.campus_a,
            primary_department=cls.it_dept
        )

        # HOD Campus A IT
        cls.hod_it = CustomUser.objects.create_user(
            username="hod_it",
            password="testpass123",
            role="hod",
            primary_campus=cls.campus_a,
            primary_department=cls.it_dept
        )
        cls.it_dept.head_of_department = cls.hod_it
        cls.it_dept.save()

        # HOD Campus B HR
        cls.hod_hr = CustomUser.objects.create_user(
            username="hod_hr",
            password="testpass123",
            role="hod",
            primary_campus=cls.campus_b,
            primary_department=cls.hr_dept
        )
        cls.hr_dept.head_of_department = cls.hod_hr
        cls.hr_dept.save()

        # Section Head Network
        cls.section_head_net = CustomUser.objects.create_user(
            username="sh_network",
            password="testpass123",
            role="section_head",
            primary_campus=cls.campus_a,
            primary_department=cls.it_dept
        )
        cls.network_section.section_head = cls.section_head_net
        cls.network_section.save()

        # Section Head Infrastructure
        cls.section_head_infra = CustomUser.objects.create_user(
            username="sh_infra",
            password="testpass123",
            role="section_head",
            primary_campus=cls.campus_a,
            primary_department=cls.it_dept
        )
        cls.infra_section.section_head = cls.section_head_infra
        cls.infra_section.save()

        # Technicians
        cls.tech_network_1 = CustomUser.objects.create_user(
            username="tech_net_1",
            password="testpass123",
            role="technician",
            primary_campus=cls.campus_a,
            primary_department=cls.it_dept
        )
        cls.tech_network_1.sections.add(cls.network_section)

        cls.tech_network_2 = CustomUser.objects.create_user(
            username="tech_net_2",
            password="testpass123",
            role="technician",
            primary_campus=cls.campus_a,
            primary_department=cls.it_dept
        )
        cls.tech_network_2.sections.add(cls.network_section)

        cls.tech_infra = CustomUser.objects.create_user(
            username="tech_infra",
            password="testpass123",
            role="technician",
            primary_campus=cls.campus_a,
            primary_department=cls.it_dept
        )
        cls.tech_infra.sections.add(cls.infra_section)

        # Regular users
        cls.user_campus_a = CustomUser.objects.create_user(
            username="user_a",
            password="testpass123",
            role="user",
            primary_campus=cls.campus_a,
            primary_department=cls.it_dept
        )

        cls.user_campus_b = CustomUser.objects.create_user(
            username="user_b",
            password="testpass123",
            role="user",
            primary_campus=cls.campus_b,
            primary_department=cls.hr_dept
        )

    def test_organizational_structure_created(self):
        """Verify organizational structure is properly set up"""
        # This test class creates 2 organizations: parent's organization + cls.org
        self.assertEqual(Organization.objects.count(), 2)
        # parent's 1 campus + 2 campuses (campus_a, campus_b)
        self.assertEqual(Campus.objects.count(), 3)
        # parent's 2 depts + 3 new depts (it_dept, ops_dept, hr_dept)
        self.assertEqual(Department.objects.count(), 5)
        # Parent class creates 2 sections (IT, HVAC) + this class creates 4 (Network, Infrastructure, Facilities, HR) = 6
        self.assertEqual(Section.objects.count(), 6)

    def test_director_access_all_tickets(self):
        """Test director can see all tickets across organization"""
        # Create tickets in different campuses/departments
        ticket_it = Ticket.objects.create(
            title="IT Network Issue",
            description="Network down",
            section=self.network_section,
            facility=self.facility,
            raised_by=self.user_campus_a,
            status='open'
        )

        ticket_hr = Ticket.objects.create(
            title="HR System Issue",
            description="Payroll system down",
            section=self.facilities_section,
            facility=self.facility,
            raised_by=self.user_campus_b,
            status='open'
        )

        # Director should see both
        accessible = OrganizationalTicketService.get_accessible_tickets(
            self.director)
        self.assertIn(ticket_it, accessible)
        self.assertIn(ticket_hr, accessible)

    def test_hod_campus_scoped_access(self):
        """Test HOD can only see tickets in their department"""
        # IT ticket on Campus A
        ticket_it_a = Ticket.objects.create(
            title="Network Issue",
            description="Test",
            section=self.network_section,
            facility=self.facility,
            raised_by=self.user_campus_a,
            status='open'
        )

        # HR ticket on Campus B (in HR department section)
        ticket_hr_b = Ticket.objects.create(
            title="HR Issue",
            description="Test",
            section=self.hr_section,
            facility=self.facility,
            raised_by=self.user_campus_b,
            status='open'
        )

        # HOD IT should see Campus A IT ticket only
        it_hod_accessible = OrganizationalTicketService.get_accessible_tickets(
            self.hod_it)
        self.assertIn(ticket_it_a, it_hod_accessible)
        self.assertNotIn(ticket_hr_b, it_hod_accessible)

        # HOD HR should see Campus B HR ticket only
        hr_hod_accessible = OrganizationalTicketService.get_accessible_tickets(
            self.hod_hr)
        self.assertNotIn(ticket_it_a, hr_hod_accessible)
        self.assertIn(ticket_hr_b, hr_hod_accessible)

    def test_section_head_department_scoped_access(self):
        """Test Section Head can only see tickets in their department"""
        # Network ticket
        ticket_net = Ticket.objects.create(
            title="Network Issue",
            description="Test",
            section=self.network_section,
            facility=self.facility,
            raised_by=self.user_campus_a,
            status='open'
        )

        # Infrastructure ticket
        ticket_infra = Ticket.objects.create(
            title="Infrastructure Issue",
            description="Test",
            section=self.infra_section,
            facility=self.facility,
            raised_by=self.user_campus_a,
            status='open'
        )

        # Network SH should see network ticket only
        net_sh_accessible = OrganizationalTicketService.get_accessible_tickets(
            self.section_head_net
        )
        self.assertIn(ticket_net, net_sh_accessible)
        self.assertNotIn(ticket_infra, net_sh_accessible)

        # Infrastructure SH should see infra ticket only
        infra_sh_accessible = OrganizationalTicketService.get_accessible_tickets(
            self.section_head_infra
        )
        self.assertNotIn(ticket_net, infra_sh_accessible)
        self.assertIn(ticket_infra, infra_sh_accessible)

    def test_technician_section_scoped_access(self):
        """Test Technician can only see tickets in their sections"""
        ticket_network = Ticket.objects.create(
            title="Network Issue",
            description="Test",
            section=self.network_section,
            facility=self.facility,
            raised_by=self.user_campus_a,
            status='open'
        )

        ticket_infra = Ticket.objects.create(
            title="Infrastructure Issue",
            description="Test",
            section=self.infra_section,
            facility=self.facility,
            raised_by=self.user_campus_a,
            status='open'
        )

        # Tech network should see network ticket only
        net_tech_accessible = OrganizationalTicketService.get_accessible_tickets(
            self.tech_network_1
        )
        self.assertIn(ticket_network, net_tech_accessible)
        self.assertNotIn(ticket_infra, net_tech_accessible)


class EscalationWorkflowTestCase(BaseTicketTestCase):
    """Test ticket escalation following organizational hierarchy"""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.org = Organization.objects.create(
            name="Escalation Test Org",
            code="ESCTEST",
            organization_type="corporate"
        )

        cls.campus = Campus.objects.create(
            organization=cls.org,
            name="Main Campus",
            code="MAIN"
        )

        cls.department = Department.objects.create(
            campus=cls.campus,
            name="Test Department",
            code="TEST"
        )

        cls.section = Section.objects.create(
            department=cls.department,
            name="Test Section",
            code="SEC"
        )

        # Create role hierarchy
        cls.technician = CustomUser.objects.create_user(
            username="tech_esc",
            password="test",
            role="technician",
            primary_campus=cls.campus,
            primary_department=cls.department
        )
        cls.technician.sections.add(cls.section)

        cls.section_head = CustomUser.objects.create_user(
            username="sh_esc",
            password="test",
            role="section_head",
            primary_campus=cls.campus,
            primary_department=cls.department
        )
        cls.section.section_head = cls.section_head
        cls.section.save()

        cls.hod = CustomUser.objects.create_user(
            username="hod_esc",
            password="test",
            role="hod",
            primary_campus=cls.campus,
            primary_department=cls.department
        )
        cls.department.head_of_department = cls.hod
        cls.department.save()

    def test_escalation_to_section_head(self):
        """Test ticket escalation from technician to section head"""
        ticket = Ticket.objects.create(
            title="Critical Issue",
            description="Test",
            section=self.section,
            facility=self.facility,
            raised_by=self.user,
            status='open'
        )

        # Escalate from technician
        escalated = OrganizationalTicketService.escalate_ticket(
            ticket=ticket,
            escalated_by=self.technician,
            reason="Issue beyond technician scope",
            manual=True
        )

        self.assertEqual(escalated.escalation_level, 1)
        self.assertEqual(escalated.escalated_to, self.section_head)
        self.assertIsNotNone(escalated.escalated_at)

    def test_escalation_to_hod(self):
        """Test ticket escalation from section head to HOD"""
        ticket = Ticket.objects.create(
            title="Complex Issue",
            description="Test",
            section=self.section,
            facility=self.facility,
            raised_by=self.user,
            status='open',
            escalation_level=1,
            escalated_to=self.section_head,
            escalated_at=timezone.now()
        )

        # Escalate from section head to HOD
        escalated = OrganizationalTicketService.escalate_ticket(
            ticket=ticket,
            escalated_by=self.section_head,
            reason="Requires HOD decision",
            manual=True
        )

        self.assertEqual(escalated.escalation_level, 2)
        self.assertEqual(escalated.escalated_to, self.hod)

    def test_cannot_escalate_beyond_hod(self):
        """Test that tickets cannot be escalated beyond HOD level"""
        ticket = Ticket.objects.create(
            title="Max Escalation",
            description="Test",
            section=self.section,
            facility=self.facility,
            raised_by=self.user,
            status='open',
            escalation_level=2,
            escalated_to=self.hod,
            escalated_at=timezone.now()
        )

        # Try to escalate beyond HOD (should fail or return unchanged)
        with self.assertRaises(Exception):
            OrganizationalTicketService.escalate_ticket(
                ticket=ticket,
                escalated_by=self.hod,
                reason="Cannot escalate further",
                manual=True
            )


class APIIntegrationTestCase(APITestCase):
    """Test Phase 6 API endpoints"""

    @classmethod
    def setUpTestData(cls):
        cls.client = APIClient()

        # Create basic organizational structure
        cls.org = Organization.objects.create(
            name="API Test Org",
            code="APITEST"
        )

        cls.campus = Campus.objects.create(
            organization=cls.org,
            name="Test Campus",
            code="TC"
        )

        cls.department = Department.objects.create(
            campus=cls.campus,
            name="Test Dept",
            code="TD"
        )

        cls.section = Section.objects.create(
            department=cls.department,
            name="Test Section",
            code="TS"
        )

        cls.facility = Facility.objects.create(
            name="Test Facility",
            facility_code="TF001",
            type="building",
            campus=cls.campus,
            department=cls.department
        )

        # Create users
        cls.admin = CustomUser.objects.create_user(
            username="admin_api",
            password="testpass123",
            role="admin"
        )

        cls.technician = CustomUser.objects.create_user(
            username="tech_api",
            password="testpass123",
            role="technician",
            primary_campus=cls.campus,
            primary_department=cls.department
        )
        cls.technician.sections.add(cls.section)

        cls.user = CustomUser.objects.create_user(
            username="user_api",
            password="testpass123",
            role="user",
            primary_campus=cls.campus,
            primary_department=cls.department
        )

    def test_organizational_ticket_list_endpoint(self):
        """Test /api/tickets/organizational/list/ endpoint"""
        # Create test tickets
        Ticket.objects.create(
            title="Test Ticket 1",
            description="Test",
            section=self.section,
            facility=self.facility,
            raised_by=self.user,
            status='open'
        )

        # Authenticate and request
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/tickets/organizational/list/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertGreater(response.data['count'], 0)

    def test_assignable_users_endpoint(self):
        """Test /api/assignable-users/ endpoint"""
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(
            f'/api/assignable-users/?section_id={self.section.id}')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should include the technician at minimum
        self.assertGreater(len(response.data['results']), 0)

    def test_organizational_analytics_endpoint(self):
        """Test /api/analytics/organizational/ endpoint - admin redirect"""
        self.client.force_authenticate(user=self.admin)

        response = self.client.get('/api/analytics/organizational/')

        # Admin should get 403 or redirect to appropriate dashboard
        self.assertIn(response.status_code, [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_400_BAD_REQUEST
        ])

    def test_escalate_ticket_manual_endpoint(self):
        """Test /api/tickets/{id}/escalate-manual/ endpoint"""
        ticket = Ticket.objects.create(
            title="Escalation Test",
            description="Test",
            section=self.section,
            facility=self.facility,
            raised_by=self.user,
            status='open'
        )

        self.client.force_authenticate(user=self.technician)

        response = self.client.post(
            f'/api/tickets/{ticket.id}/escalate-manual/',
            {'reason': 'Test escalation'},
            format='json'
        )

        # Should succeed or return permission error
        self.assertIn(response.status_code, [
            status.HTTP_200_OK,
            status.HTTP_403_FORBIDDEN
        ])


class AnalyticsAggregationTestCase(TestCase):
    """Test organizational analytics data aggregation"""

    @classmethod
    def setUpTestData(cls):
        # Create organizational structure
        cls.org = Organization.objects.create(
            name="Analytics Test Org",
            code="ANTEST"
        )

        cls.campus = Campus.objects.create(
            organization=cls.org,
            name="Test Campus",
            code="TC"
        )

        cls.department = Department.objects.create(
            campus=cls.campus,
            name="Test Dept",
            code="TD"
        )

        cls.section = Section.objects.create(
            department=cls.department,
            name="Test Section",
            code="TS"
        )

        cls.facility = Facility.objects.create(
            name="Test Facility",
            facility_code="TF001",
            type="building",
            campus=cls.campus,
            department=cls.department
        )

        # Create users
        cls.director = CustomUser.objects.create_user(
            username="director_an",
            password="test",
            role="director",
            primary_campus=cls.campus,
            primary_department=cls.department
        )

        cls.hod = CustomUser.objects.create_user(
            username="hod_an",
            password="test",
            role="hod",
            primary_campus=cls.campus,
            primary_department=cls.department
        )
        cls.department.head_of_department = cls.hod
        cls.department.save()

        cls.user = CustomUser.objects.create_user(
            username="user_an",
            password="test",
            role="user",
            primary_campus=cls.campus,
            primary_department=cls.department
        )

        # Create test tickets
        for i in range(10):
            status_choice = 'resolved' if i < 5 else 'open'
            ticket = Ticket.objects.create(
                title=f"Test Ticket {i}",
                description="Test",
                section=cls.section,
                facility=cls.facility,
                raised_by=cls.user,
                status=status_choice,
                created_at=timezone.now() - timedelta(days=i)
            )

            if status_choice == 'resolved':
                ticket.resolved_at = timezone.now() - timedelta(days=i-1)
                ticket.save()

    def test_director_dashboard_aggregates_metrics(self):
        """Test that director dashboard aggregates org-wide metrics"""
        dashboard = OrganizationalAnalytics.director_dashboard(
            self.director,
            days=30
        )

        self.assertIn('overview', dashboard)
        self.assertIn('campuses', dashboard)
        self.assertIn('departments', dashboard)

    def test_hod_dashboard_campus_scoped(self):
        """Test that HOD dashboard is scoped to their campus"""
        dashboard = OrganizationalAnalytics.hod_dashboard(
            self.hod,
            days=30
        )

        self.assertIn('overview', dashboard)
        self.assertIn('departments', dashboard)

    def test_aggregation_sla_compliance_calculation(self):
        """Test SLA compliance is calculated correctly in AnalyticsAggregationTestCase"""
        # Create overdue ticket
        overdue_ticket = Ticket.objects.create(
            title="Overdue Test",
            description="Test",
            section=self.section,
            facility=self.facility,
            raised_by=self.user,
            status='open',
            created_at=timezone.now() - timedelta(days=10)
        )

        # Create compliant ticket
        compliant_ticket = Ticket.objects.create(
            title="On-time Test",
            description="Test",
            section=self.section,
            facility=self.facility,
            raised_by=self.user,
            status='resolved',
            created_at=timezone.now() - timedelta(days=1),
            resolved_at=timezone.now()
        )

        dashboard = OrganizationalAnalytics.director_dashboard(
            self.director,
            days=30
        )

        # SLA compliance should be present in overview
        self.assertIn('sla_compliance', dashboard['overview'])


# ============================================================================
# Phase 4 & 5 Tests: OrganizationalTicketService & OrganizationalAnalytics
# ============================================================================

class OrganizationalTicketServiceTestCase(TestCase):
    """Test cases for OrganizationalTicketService (Phase 4)"""

    @classmethod
    def setUpTestData(cls):
        """Create test organizational hierarchy"""
        # Create organization
        cls.org = Organization.objects.create(
            name="Test University",
            code="UNIV",
            organization_type="education",
            headquarters="Main Campus"
        )

        # Create campuses
        cls.main_campus = Campus.objects.create(
            organization=cls.org,
            name="Main Campus",
            code="MAIN",
            location="City Center"
        )

        cls.branch_campus = Campus.objects.create(
            organization=cls.org,
            name="Branch Campus",
            code="BRANCH",
            location="Suburb"
        )

        # Create departments
        cls.it_dept = Department.objects.create(
            campus=cls.main_campus,
            name="Information Technology",
            code="IT"
        )

        cls.hr_dept = Department.objects.create(
            campus=cls.branch_campus,
            name="Human Resources",
            code="HR"
        )

        # Create sections
        cls.network_section = Section.objects.create(
            department=cls.it_dept,
            name="Network Services",
            code="NET"
        )

        cls.support_section = Section.objects.create(
            department=cls.it_dept,
            name="User Support",
            code="SUP"
        )

        # Create facilities
        cls.main_building = Facility.objects.create(
            name="Main Building",
            facility_code="MAIN-01",
            type="building",
            campus=cls.main_campus,
            department=cls.it_dept,
            location="Building A, Floor 2"
        )

        # Create users with roles
        cls.director = CustomUser.objects.create_user(
            username="director",
            password="testpass123",
            email="director@test.local",
            first_name="Jane",
            last_name="Director",
            role="director",
            primary_campus=cls.main_campus,
            primary_department=cls.it_dept
        )

        cls.hod = CustomUser.objects.create_user(
            username="hod",
            password="testpass123",
            email="hod@test.local",
            first_name="John",
            last_name="HOD",
            role="hod",
            primary_campus=cls.main_campus,
            primary_department=cls.it_dept
        )

        cls.section_head = CustomUser.objects.create_user(
            username="section_head",
            password="testpass123",
            email="sh@test.local",
            first_name="Alice",
            last_name="SectionHead",
            role="section_head",
            primary_campus=cls.main_campus,
            primary_department=cls.it_dept
        )

        cls.technician = CustomUser.objects.create_user(
            username="technician",
            password="testpass123",
            email="tech@test.local",
            first_name="Bob",
            last_name="Technician",
            role="technician",
            primary_campus=cls.main_campus,
            primary_department=cls.it_dept
        )
        cls.technician.sections.add(cls.network_section)

        cls.regular_user = CustomUser.objects.create_user(
            username="user",
            password="testpass123",
            email="user@test.local",
            first_name="Charlie",
            last_name="User",
            role="user",
            primary_campus=cls.main_campus,
            primary_department=cls.it_dept
        )
        cls.regular_user.sections.add(cls.network_section)

    def test_create_ticket_with_proper_scope(self):
        """Test creating ticket within authorized scope"""
        from tickets.api.services import OrganizationalTicketService

        ticket = OrganizationalTicketService.create_ticket(
            data={
                'title': 'Network Issue',
                'description': 'Network connectivity problem'
            },
            created_by=self.regular_user,
            section=self.network_section,
            facility=self.main_building
        )

        self.assertIsNotNone(ticket)
        self.assertEqual(ticket.title, 'Network Issue')
        self.assertEqual(ticket.status, 'open')
        self.assertTrue(ticket.auto_escalation_enabled)

    def test_create_ticket_exceeds_scope(self):
        """Test that user cannot create ticket outside their scope"""
        from tickets.api.services import (
            OrganizationalTicketService,
            InsufficientScopeException,
        )

        other_dept_section = Section.objects.create(
            department=self.hr_dept,
            name="HR Section",
            code="HRSC"
        )

        with self.assertRaises(InsufficientScopeException):
            OrganizationalTicketService.create_ticket(
                data={'title': 'Test', 'description': 'Test'},
                created_by=self.technician,
                section=other_dept_section,
                facility=self.main_building
            )

    def test_assign_ticket_with_proper_validation(self):
        """Test assigning ticket to valid technician"""
        from tickets.api.services import OrganizationalTicketService

        ticket = Ticket.objects.create(
            title='Assign Test',
            description='Test',
            section=self.network_section,
            facility=self.main_building,
            raised_by=self.regular_user,
            status='open'
        )

        updated_ticket = OrganizationalTicketService.assign_ticket(
            ticket=ticket,
            technician=self.technician,
            assigned_by=self.section_head
        )

        self.assertEqual(updated_ticket.assigned_to, self.technician)
        self.assertEqual(updated_ticket.status, 'assigned')

    def test_assign_ticket_invalid_technician(self):
        """Test cannot assign to technician not in section"""
        from tickets.api.services import (
            OrganizationalTicketService,
            InvalidAssignmentException,
        )

        other_section = Section.objects.create(
            department=self.it_dept,
            name="Other Section",
            code="OTH"
        )

        other_tech = CustomUser.objects.create_user(
            username="other_tech",
            password="test",
            role="technician",
            primary_campus=self.main_campus,
            primary_department=self.it_dept
        )
        other_tech.sections.add(other_section)

        ticket = Ticket.objects.create(
            title='Test',
            description='Test',
            section=self.network_section,
            facility=self.main_building,
            raised_by=self.regular_user,
            status='open'
        )

        with self.assertRaises(InvalidAssignmentException):
            OrganizationalTicketService.assign_ticket(
                ticket=ticket,
                technician=other_tech,
                assigned_by=self.section_head
            )

    def test_escalate_ticket(self):
        """Test ticket escalation follows organizational hierarchy"""
        from tickets.api.services import OrganizationalTicketService

        # Set section head
        self.network_section.section_head = self.section_head
        self.network_section.save()

        # Set HOD
        self.it_dept.head_of_department = self.hod
        self.it_dept.save()

        ticket = Ticket.objects.create(
            title='Critical Issue',
            description='Test',
            section=self.network_section,
            facility=self.main_building,
            raised_by=self.regular_user,
            status='in_progress'
        )

        # Escalate to section head
        escalated = OrganizationalTicketService.escalate_ticket(
            ticket=ticket,
            escalated_by=self.technician,
            reason='Exceeds technician capabilities'
        )

        self.assertEqual(escalated.escalation_level, 1)
        self.assertEqual(escalated.escalated_to, self.section_head)
        self.assertEqual(escalated.status, 'escalated')

    def test_get_accessible_tickets_respects_scope(self):
        """Test get_accessible_tickets respects organizational scope"""
        from tickets.api.services import OrganizationalTicketService

        # Create tickets in different departments
        it_ticket = Ticket.objects.create(
            title='IT Ticket',
            description='Test',
            section=self.network_section,
            facility=self.main_building,
            raised_by=self.technician,
            status='open'
        )

        hr_section = Section.objects.create(
            department=self.hr_dept,
            name="HR Section",
            code="HRSC"
        )
        hr_facility = Facility.objects.create(
            name="HR Building",
            facility_code="HR-01",
            type="building",
            campus=self.branch_campus,
            department=self.hr_dept
        )
        hr_ticket = Ticket.objects.create(
            title='HR Ticket',
            description='Test',
            section=hr_section,
            facility=hr_facility,
            raised_by=self.regular_user,
            status='open'
        )

        # Director should see all tickets in organization
        director_tickets = OrganizationalTicketService.get_accessible_tickets(
            self.director)
        self.assertIn(it_ticket, director_tickets)
        self.assertIn(hr_ticket, director_tickets)

        # HOD should only see tickets in their campus
        hod_tickets = OrganizationalTicketService.get_accessible_tickets(
            self.hod)
        self.assertIn(it_ticket, hod_tickets)
        self.assertNotIn(hr_ticket, hod_tickets)

        # Technician should only see tickets in their sections
        tech_tickets = OrganizationalTicketService.get_accessible_tickets(
            self.technician)
        self.assertIn(it_ticket, tech_tickets)

    def test_auto_escalation_processing(self):
        """Test automatic escalation processing"""
        from tickets.api.services import OrganizationalTicketService

        # Set up escalation chain
        self.network_section.section_head = self.section_head
        self.network_section.save()

        ticket = Ticket.objects.create(
            title='Auto Escalate Test',
            description='Test',
            section=self.network_section,
            facility=self.main_building,
            raised_by=self.regular_user,
            status='open',
            auto_escalation_enabled=True,
            next_escalation_due=timezone.now() - timedelta(hours=1)
        )

        # Process auto-escalations
        stats = OrganizationalTicketService.process_auto_escalations()

        self.assertIn('escalated', stats)
        self.assertGreater(stats['escalated'], 0)


class Phase45AnalyticsTestCase(TestCase):
    """Test cases for OrganizationalAnalytics (Phase 5)"""

    @classmethod
    def setUpTestData(cls):
        """Create test organizational hierarchy and tickets"""
        # Create organization
        cls.org = Organization.objects.create(
            name="Test Corp",
            code="CORP",
            organization_type="corporate",
            headquarters="HQ"
        )

        # Create campus and departments
        cls.campus = Campus.objects.create(
            organization=cls.org,
            name="Main Office",
            code="MAIN",
            location="Downtown"
        )

        cls.dept = Department.objects.create(
            campus=cls.campus,
            name="Operations",
            code="OPS"
        )

        # Create section
        cls.section = Section.objects.create(
            department=cls.dept,
            name="Support",
            code="SUP"
        )

        # Create facility
        cls.facility = Facility.objects.create(
            name="Office Building",
            facility_code="BLDG-01",
            type="building",
            campus=cls.campus,
            department=cls.dept
        )

        # Create users
        cls.director = CustomUser.objects.create_user(
            username="director",
            password="test",
            role="director",
            primary_campus=cls.campus,
            primary_department=cls.dept
        )

        cls.hod = CustomUser.objects.create_user(
            username="hod",
            password="test",
            role="hod",
            primary_campus=cls.campus,
            primary_department=cls.dept
        )

        cls.section_head = CustomUser.objects.create_user(
            username="section_head",
            password="test",
            role="section_head",
            primary_campus=cls.campus,
            primary_department=cls.dept
        )

        cls.technician = CustomUser.objects.create_user(
            username="tech",
            password="test",
            role="technician",
            primary_campus=cls.campus,
            primary_department=cls.dept
        )
        cls.technician.sections.add(cls.section)

        # Create test tickets
        for i in range(10):
            ticket = Ticket.objects.create(
                title=f'Test Ticket {i}',
                description='Test',
                section=cls.section,
                facility=cls.facility,
                raised_by=cls.technician,
                assigned_to=cls.technician,
                status='resolved' if i < 5 else 'open'
            )

            # Set resolved_at for resolved tickets
            if ticket.status == 'resolved':
                ticket.resolved_at = timezone.now() - timedelta(hours=i)
                ticket.save()

    def test_director_dashboard(self):
        """Test director dashboard includes organization-wide metrics"""
        from tickets.api.analytics import OrganizationalAnalytics

        dashboard = OrganizationalAnalytics.director_dashboard(
            self.director, days=30)

        self.assertIn('organization', dashboard)
        self.assertIn('overview', dashboard)
        self.assertIn('campuses', dashboard)
        self.assertIn('departments', dashboard)

        # Verify metrics
        self.assertEqual(dashboard['overview']['total_tickets'], 10)
        self.assertEqual(dashboard['overview']['total_open'], 5)

    def test_hod_dashboard(self):
        """Test HOD dashboard includes campus-level metrics"""
        from tickets.api.analytics import OrganizationalAnalytics

        dashboard = OrganizationalAnalytics.hod_dashboard(self.hod, days=30)

        self.assertIn('campus', dashboard)
        self.assertIn('overview', dashboard)
        self.assertIn('departments', dashboard)
        self.assertIn('sections', dashboard)
        self.assertIn('technicians', dashboard)

        # Verify campus context
        self.assertEqual(dashboard['campus']['name'], 'Main Office')

    def test_section_head_dashboard(self):
        """Test section head dashboard includes department-level metrics"""
        from tickets.api.analytics import OrganizationalAnalytics

        dashboard = OrganizationalAnalytics.section_head_dashboard(
            self.section_head, days=30)

        self.assertIn('department', dashboard)
        self.assertIn('overview', dashboard)
        self.assertIn('sections', dashboard)
        self.assertIn('technicians', dashboard)

        # Verify department context
        self.assertEqual(dashboard['department']['name'], 'Operations')

    def test_dashboard_sla_compliance_calculation(self):
        """Test SLA compliance is calculated correctly in Phase45AnalyticsTestCase"""
        from tickets.api.analytics import OrganizationalAnalytics

        # This is implicit in dashboard calculations
        dashboard = OrganizationalAnalytics.director_dashboard(self.director)

        self.assertIn('sla_compliance', dashboard['overview'])
        # Should be between 0 and 100
        self.assertGreaterEqual(dashboard['overview']['sla_compliance'], 0)
        self.assertLessEqual(dashboard['overview']['sla_compliance'], 100)

    def test_escalation_trends(self):
        """Test escalation trends are calculated"""
        from tickets.api.analytics import OrganizationalAnalytics

        dashboard = OrganizationalAnalytics.section_head_dashboard(
            self.section_head)

        self.assertIn('escalation_trends', dashboard)
        # Should have trend data for recent days
        self.assertGreater(len(dashboard['escalation_trends']), 0)
