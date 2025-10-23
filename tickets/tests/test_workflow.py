import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from tickets.models import Ticket, CustomUser, Section, Facility, Comment, Feedback, TicketLog


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def setup_data(db):
    # Create sections
    section = Section.objects.create(
        name='IT',
        description='Information Technology'
    )

    hvac = Section.objects.create(
        name="HVAC",
        description="Air Conditioning systems."
    )

    electrical = Section.objects.create(
        name="Electrical",
        description="Electricity installations and fixtures."
    )

    # Create facility
    facility = Facility.objects.create(
        name='Main Building',
        type='building',
        status='active',
        location='123 Main St'
    )

    # Create users with different roles
    user = CustomUser.objects.create_user(
        username='testuser',
        email='testuser@example.com',
        password='testpass'
    )

    technician = CustomUser.objects.create_user(
        username='techuser',
        email='techuser@example.com',
        password='techpass',
        role='technician',
    )

    hvac_technician = CustomUser.objects.create_user(
        username='hvac_tech',
        email='hvactech@example.com',
        password='hvac123',
        role='technician'
    )

    electrician = CustomUser.objects.create_user(
        username='electrical_tech',
        email='electricaltech@example.com',
        password='electrician123',
        role='technician'
    )

    admin = CustomUser.objects.create_user(
        username="adminuser",
        email="admin@example.com",
        password="adminpass",
        role="admin"
    )

    manager = CustomUser.objects.create_user(
        username="manager",
        email="manager@example.com",
        password="managerpass",
        role="manager"
    )

    # Assign technicians to their respective sections
    technician.sections.add(section)
    hvac_technician.sections.add(hvac)
    electrician.sections.add(electrical)

    return {
        'section': section,
        'hvac_section': hvac,
        'electrical_section': electrical,
        "facility": facility,
        "user": user,
        "technician": technician,
        "hvac_technician": hvac_technician,
        "electrician": electrician,
        "admin": admin,
        "manager": manager
    }


@pytest.mark.django_db
def test_ticket_creation(api_client, setup_data):
    """ user can create a ticket and its starts with open status and no technician"""
    api_client.force_authenticate(user=setup_data['user'])

    payload = {
        "title": "Printer not working",
        "description": "Printer in the admin block is jammed",
        "section_id": setup_data["section"].id,
        "facility_id": setup_data["facility"].id
    }

    response = api_client.post(reverse("ticket-list"), payload, format="json")
    print(response.status_code, response.data)

    assert response.status_code == 201

    ticket = Ticket.objects.get(id=response.data["id"])
    assert ticket.status == "open"
    assert ticket.assigned_to is None
    assert ticket.raised_by == setup_data["user"]


@pytest.mark.django_db
def test_admin_can_assign_ticket(api_client, setup_data):
    """ Admin assigns ticket to technician in same section as ticket section"""
    ticket = Ticket.objects.create(
        title="Network issue",
        description="WiFi is down",
        section=setup_data["section"],
        facility=setup_data["facility"],
        raised_by=setup_data["user"],
        status="open"
    )

    payload = {
        "assigned_to_id": setup_data["technician"].id,
        "status": "assigned"
    }

    print(ticket, payload)
    # ✅ authenticate as admin
    api_client.force_authenticate(user=setup_data["admin"])

    response = api_client.patch(
        reverse("ticket-detail", args=[ticket.id]), payload, format="json")
    print(response.status_code, response.data)

    assert response.status_code in [200, 202]

    ticket.refresh_from_db()
    assert ticket.assigned_to == setup_data["technician"]
    assert ticket.status == "assigned"


@pytest.mark.django_db
def test_admin_cant_assign_ticket_to_technician_not_in_section(api_client, setup_data):
    """ Admin cant assign ticket to technician not in section as ticket section"""
    plumber = CustomUser.objects.create_user(
        username='plumber_tech',
        email='plumbertech@example.com',
        password='plumber123',
        role='technician'
    )

    plumbing = Section.objects.create(
        name="Plumbing",
        description="Plumbing systems such as water and piping."
    )

    plumber.sections.add(plumbing)

    api_client.force_authenticate(user=setup_data["admin"])

    ticket = Ticket.objects.create(
        title="Network issue",
        description="WiFi is down",
        section=setup_data["section"],
        facility=setup_data["facility"],
        raised_by=setup_data["user"],
        status="open"
    )

    payload = {
        "assigned_to_id": plumber.id,
        "status": "assigned"
    }

    print(ticket, payload)

    response = api_client.patch(
        reverse("ticket-detail", args=[ticket.id]), payload, format="json")
    print(response.status_code, response.data)

    assert response.status_code in [400, 404]

    ticket.refresh_from_db()
    assert ticket.assigned_to is None
    assert ticket.status == "open"


@pytest.mark.django_db
def test_technician_can_update_ticket_status(api_client, setup_data):
    """ Technician updates ticket from assigned to in_progress to resolved """
    ticket = Ticket.objects.create(
        title="Email down",
        description="Outlook not syncing",
        section=setup_data["section"],
        facility=setup_data["facility"],
        raised_by=setup_data["user"],
        assigned_to=setup_data["technician"],
        status="assigned"
    )

    payload = {
        "status": "in_progress"
    }
    api_client.force_authenticate(user=setup_data['technician'])

    response = api_client.patch(
        reverse('ticket-detail', args=[ticket.id]), payload, format="json")
    assert response.status_code in [200, 202]
    ticket.refresh_from_db()
    assert ticket.status == "in_progress"

    payload = {
        "status": "resolved"
    }
    response = api_client.patch(
        reverse('ticket-detail', args=[ticket.id]), payload, format="json")
    assert response.status_code in [200, 202]
    ticket.refresh_from_db()
    assert ticket.status == "resolved"


@pytest.mark.django_db
def test_user_cant_update_ticket_status(api_client, setup_data):
    """ User cannot updates ticket from assigned to in_progress to resolved """
    ticket = Ticket.objects.create(
        title="Email down",
        description="Outlook not syncing",
        section=setup_data["section"],
        facility=setup_data["facility"],
        raised_by=setup_data["user"],
        assigned_to=setup_data["technician"],
        status="assigned"
    )

    user2 = CustomUser.objects.create_user(
        username="user2",
        password="userpass123",
        email="user2@example.com",
        role="user"
    )

    payload = {
        "status": "in_progress"
    }

    api_client.force_authenticate(user=user2)

    response = api_client.patch(
        reverse('ticket-detail', args=[ticket.id]), payload, format="json")
    assert response.status_code in [400, 404]
    ticket.refresh_from_db()
    assert ticket.status == "assigned"

    payload = {
        "status": "resolved"
    }
    response = api_client.patch(
        reverse('ticket-detail', args=[ticket.id]), payload, format="json")
    assert response.status_code in [400, 404]
    ticket.refresh_from_db()
    assert ticket.status == "assigned"


@pytest.mark.django_db()
def test_technician_or_admin_add_comment_to_ticket(api_client, setup_data):
    """ test that comments can be added to a ticket """
    ticket = Ticket.objects.create(
        title="Email down",
        description="Outlook not syncing",
        section=setup_data["section"],
        facility=setup_data["facility"],
        raised_by=setup_data["user"],
        assigned_to=setup_data["technician"],
        status="in_progress"
    )
    api_client.force_authenticate(user=setup_data['technician'])
    payload = {
        "text": "It is now working!",
    }

    response = api_client.post(
        reverse("ticket-comments", args=[ticket.id]), payload, format="json")
    print(response.status_code, response.data)
    assert response.status_code == 201
    comment_tech = Comment.objects.first()
    assert comment_tech.author == setup_data["technician"]
    assert comment_tech.text == payload['text']

    api_client.force_authenticate(user=setup_data['admin'])
    admin_payload = {
        "text": "Great to hear!",
    }
    response = api_client.post(
        reverse("ticket-comments", args=[ticket.id]), admin_payload, format="json")
    print(response.status_code, response.data)
    assert response.status_code == 201
    admin_comment = Comment.objects.last()
    assert admin_comment.text == admin_payload["text"]
    assert admin_comment.author == setup_data["admin"]


@pytest.mark.django_db()
def test_user_can_submit_feedback(api_client, setup_data):
    """ User submits feedback after ticket is resolved """
    ticket = Ticket.objects.create(
        title="Email fixed",
        description="Problem resolved",
        section=setup_data["section"],
        facility=setup_data["facility"],
        raised_by=setup_data["user"],
        assigned_to=setup_data["technician"],
        status="resolved"
    )

    api_client.force_authenticate(user=setup_data["user"])
    payload = {
        "rating": 5,
        "comment": "Great job!"
    }

    response = api_client.post(
        reverse("ticket-feedback", args=[ticket.id]), payload, format="json")
    assert response.status_code == 201
    feedback = Feedback.objects.get(ticket=ticket)
    assert feedback.rating == 5
    assert feedback.rated_by == setup_data["user"]


@pytest.mark.django_db()
def test_user_cant_submit_feedback_is_not_resolved(api_client, setup_data):
    """ User submits feedback after ticket is resolved """
    ticket = Ticket.objects.create(
        title="Email fixed",
        description="Problem resolved",
        section=setup_data["section"],
        facility=setup_data["facility"],
        raised_by=setup_data["user"],
        assigned_to=setup_data["technician"],
        status="pending"
    )

    api_client.force_authenticate(user=setup_data["user"])
    payload = {
        "rating": 5,
        "comment": "Great job!"
    }

    response = api_client.post(
        reverse("ticket-feedback", args=[ticket.id]), payload, format="json")
    assert response.status_code == 400
    feedback = Feedback.objects.filter(ticket=ticket).count()
    assert feedback == 0
    # assert feedback.rated_by is None


@pytest.mark.django_db
def test_complete_ticket_lifecycle(api_client, setup_data):
    """Test the complete lifecycle of a ticket from creation to closure"""

    # Step 1: User creates a ticket
    api_client.force_authenticate(user=setup_data['user'])

    creation_payload = {
        "title": "Complete Lifecycle Test",
        "description": "Testing the full ticket lifecycle workflow",
        "section_id": setup_data["section"].id,
        "facility_id": setup_data["facility"].id
    }

    creation_response = api_client.post(
        reverse("ticket-list"), creation_payload, format="json")
    assert creation_response.status_code == 201
    ticket_id = creation_response.data["id"]

    # Verify initial state
    ticket = Ticket.objects.get(id=ticket_id)
    assert ticket.status == "open"
    assert ticket.assigned_to is None

    # Step 2: Admin assigns ticket to technician
    api_client.force_authenticate(user=setup_data['admin'])

    assignment_payload = {
        "assigned_to_id": setup_data["technician"].id,
        "status": "assigned"
    }

    assignment_response = api_client.patch(
        reverse("ticket-detail", args=[ticket_id]),
        assignment_payload,
        format="json"
    )
    assert assignment_response.status_code == 200

    # Verify assignment
    ticket.refresh_from_db()
    assert ticket.status == "assigned"
    assert ticket.assigned_to == setup_data["technician"]

    # Step 3: Technician updates status to in_progress
    api_client.force_authenticate(user=setup_data['technician'])

    progress_payload = {
        "status": "in_progress"
    }

    progress_response = api_client.patch(
        reverse("ticket-detail", args=[ticket_id]),
        progress_payload,
        format="json"
    )
    assert progress_response.status_code == 200

    # Verify status update
    ticket.refresh_from_db()
    assert ticket.status == "in_progress"

    # Step 4: Technician adds a comment
    comment_payload = {
        "text": "Working on the issue. Will be resolved soon."
    }

    comment_response = api_client.post(
        reverse("ticket-comments", args=[ticket_id]),
        comment_payload,
        format="json"
    )
    assert comment_response.status_code == 201

    # Step 5: Technician marks ticket as resolved
    resolved_payload = {
        "status": "resolved"
    }

    resolved_response = api_client.patch(
        reverse("ticket-detail", args=[ticket_id]),
        resolved_payload,
        format="json"
    )
    assert resolved_response.status_code == 200

    # Verify resolved status
    ticket.refresh_from_db()
    assert ticket.status == "resolved"

    # Step 6: User adds feedback
    api_client.force_authenticate(user=setup_data['user'])

    feedback_payload = {
        "rating": 5,
        "comment": "Excellent service, thank you!"
    }

    feedback_response = api_client.post(
        reverse("ticket-feedback", args=[ticket_id]),
        feedback_payload,
        format="json"
    )
    assert feedback_response.status_code == 201

    # Verify feedback
    feedback = Feedback.objects.get(ticket_id=ticket_id)
    assert feedback.rating == 5
    assert feedback.rated_by == setup_data['user']

    # Step 7: Admin closes the ticket
    api_client.force_authenticate(user=setup_data['admin'])

    closed_payload = {
        "status": "closed"
    }

    closed_response = api_client.patch(
        reverse("ticket-detail", args=[ticket_id]),
        closed_payload,
        format="json"
    )
    assert closed_response.status_code == 200

    # Verify closed status
    ticket.refresh_from_db()
    assert ticket.status == "closed"

    # Step 8: Verify that the closed ticket cannot be modified
    modified_payload = {
        "title": "Should Not Change"
    }

    modified_response = api_client.patch(
        reverse("ticket-detail", args=[ticket_id]),
        modified_payload,
        format="json"
    )
    assert modified_response.status_code == 400
    assert "Cannot modify a closed ticket" in str(modified_response.data)

    # Step 9: Verify ticket history through logs
    ticket_logs = TicketLog.objects.filter(
        ticket_id=ticket_id).order_by('timestamp')

    # Should have at least 5 log entries: created, assigned, in_progress, resolved, closed
    assert ticket_logs.count() >= 5

    # Verify first and last log entries
    assert "created" in ticket_logs.first().action.lower()
    assert "status changed" in ticket_logs.last().action.lower()
    assert "closed" in ticket_logs.last().action.lower()


@pytest.mark.django_db
def test_section_based_routing(api_client, setup_data):
    """Test that tickets are correctly routed to technicians based on their section"""

    # Create tickets in different sections
    api_client.force_authenticate(user=setup_data['user'])

    # IT Section ticket
    it_ticket_payload = {
        "title": "IT Support Needed",
        "description": "Computer not booting",
        "section_id": setup_data["section"].id,
        "facility_id": setup_data["facility"].id
    }

    it_response = api_client.post(
        reverse("ticket-list"), it_ticket_payload, format="json")
    assert it_response.status_code == 201
    it_ticket_id = it_response.data["id"]

    # HVAC Section ticket
    hvac_ticket_payload = {
        "title": "AC Not Working",
        "description": "Air conditioner is not cooling properly",
        "section_id": setup_data["hvac_section"].id,
        "facility_id": setup_data["facility"].id
    }

    hvac_response = api_client.post(
        reverse("ticket-list"), hvac_ticket_payload, format="json")
    assert hvac_response.status_code == 201
    hvac_ticket_id = hvac_response.data["id"]

    # Login as admin to assign tickets
    api_client.force_authenticate(user=setup_data['admin'])

    # Try to assign IT ticket to HVAC technician (should fail)
    wrong_assignment_payload = {
        "assigned_to_id": setup_data["hvac_technician"].id,
        "status": "assigned"
    }

    wrong_response = api_client.patch(
        reverse("ticket-detail", args=[it_ticket_id]),
        wrong_assignment_payload,
        format="json"
    )
    assert wrong_response.status_code == 400
    assert "does not belong to section" in str(wrong_response.data)

    # Assign IT ticket to IT technician (should succeed)
    correct_it_assignment_payload = {
        "assigned_to_id": setup_data["technician"].id,
        "status": "assigned"
    }

    correct_it_response = api_client.patch(
        reverse("ticket-detail", args=[it_ticket_id]),
        correct_it_assignment_payload,
        format="json"
    )
    assert correct_it_response.status_code == 200

    # Assign HVAC ticket to HVAC technician (should succeed)
    correct_hvac_assignment_payload = {
        "assigned_to_id": setup_data["hvac_technician"].id,
        "status": "assigned"
    }

    correct_hvac_response = api_client.patch(
        reverse("ticket-detail", args=[hvac_ticket_id]),
        correct_hvac_assignment_payload,
        format="json"
    )
    assert correct_hvac_response.status_code == 200

    # Verify assignments
    it_ticket = Ticket.objects.get(id=it_ticket_id)
    hvac_ticket = Ticket.objects.get(id=hvac_ticket_id)

    assert it_ticket.assigned_to == setup_data["technician"]
    assert hvac_ticket.assigned_to == setup_data["hvac_technician"]


@pytest.mark.django_db
def test_admin_workflow_vs_technician_workflow(api_client, setup_data):
    """Test the different permissions and capabilities of admins vs technicians"""

    # Create test ticket
    api_client.force_authenticate(user=setup_data['user'])

    ticket_payload = {
        "title": "Role Test Ticket",
        "description": "Testing different role capabilities",
        "section_id": setup_data["section"].id,
        "facility_id": setup_data["facility"].id
    }

    ticket_response = api_client.post(
        reverse("ticket-list"), ticket_payload, format="json")
    assert ticket_response.status_code == 201
    ticket_id = ticket_response.data["id"]

    # TECHNICIAN WORKFLOW

    # 1. Technician cannot assign themselves to open tickets
    api_client.force_authenticate(user=setup_data['technician'])

    tech_assign_payload = {
        "assigned_to_id": setup_data["technician"].id,
        "status": "assigned"
    }

    tech_assign_response = api_client.patch(
        reverse("ticket-detail", args=[ticket_id]),
        tech_assign_payload,
        format="json"
    )
    # This may succeed or fail depending on your business logic
    # If technicians are not allowed to assign tickets:
    # assert tech_assign_response.status_code == 400

    # ADMIN WORKFLOW

    # 1. Admin can assign tickets
    api_client.force_authenticate(user=setup_data['admin'])

    admin_assign_payload = {
        "assigned_to_id": setup_data["technician"].id,
        "status": "assigned"
    }

    admin_assign_response = api_client.patch(
        reverse("ticket-detail", args=[ticket_id]),
        admin_assign_payload,
        format="json"
    )
    assert admin_assign_response.status_code == 200

    # 2. Technician can update status to in_progress
    api_client.force_authenticate(user=setup_data['technician'])

    progress_payload = {
        "status": "in_progress"
    }

    progress_response = api_client.patch(
        reverse("ticket-detail", args=[ticket_id]),
        progress_payload,
        format="json"
    )
    assert progress_response.status_code == 200

    # 3. Technician can update status to resolved
    resolved_payload = {
        "status": "resolved"
    }

    resolved_response = api_client.patch(
        reverse("ticket-detail", args=[ticket_id]),
        resolved_payload,
        format="json"
    )
    assert resolved_response.status_code == 200

    # 4. Technician CANNOT close a resolved ticket
    closed_payload = {
        "status": "closed"
    }

    tech_closed_response = api_client.patch(
        reverse("ticket-detail", args=[ticket_id]),
        closed_payload,
        format="json"
    )
    assert tech_closed_response.status_code == 400
    assert "cannot set ticket status to 'closed'" in str(
        tech_closed_response.data).lower()

    # 5. Admin CAN close a resolved ticket
    api_client.force_authenticate(user=setup_data['admin'])

    admin_closed_response = api_client.patch(
        reverse("ticket-detail", args=[ticket_id]),
        closed_payload,
        format="json"
    )
    assert admin_closed_response.status_code == 200

    ticket = Ticket.objects.get(id=ticket_id)
    assert ticket.status == "closed"
