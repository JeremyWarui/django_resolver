from rest_framework import serializers
from .models import *


class FacilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Facility
        fields = ['id', 'name', 'type', 'status', 'location']


class SectionSerializer(serializers.ModelSerializer):
    technicians = serializers.StringRelatedField(many=True, read_only=True)

    class Meta:
        model = Section
        fields = ['id', 'name', 'description', 'technicians']


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    username = serializers.CharField(read_only=True)
    sections = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Section.objects.all(),
        required=False
    )

    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'first_name',
                  'last_name', 'email', 'password', 'role', 'sections']

    def create(self, validated_data):
        first_name = validated_data.get('first_name')
        last_name = validated_data.get('last_name')
        email = validated_data.get('email', '')
        password = validated_data['password']
        role = validated_data.get('role', 'user')
        sections = validated_data.pop('sections', [])

        base_username = f"{first_name.lower()}.{last_name.lower()}"
        username = base_username
        counter = 1

        # Ensure username is unique
        while CustomUser.objects.filter(username=username).exists():
            username = f"{username}-{counter}"
            counter += 1

        user = CustomUser.objects.create_user(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=password,
            role=role,
        )
        if sections:
            user.sections.set(sections)
        return user


class TinyTicketSerializer(serializers.ModelSerializer):
    """Minimal ticket serializer to avoid circular dependency during nested serialization."""

    class Meta:
        model = Ticket
        fields = ['id', 'ticket_no']


class CommentSerializer(serializers.ModelSerializer):
    """Serializer for ticket comments. Author and ticket are set from context."""

    author = serializers.StringRelatedField(read_only=True)
    ticket = TinyTicketSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ['id', 'ticket', 'text', 'author', 'created_at']


class FeedbackSerializer(serializers.ModelSerializer):
    """Serializer for ticket feedback. Rated_by and ticket are set from context."""

    ticket = TinyTicketSerializer(read_only=True)
    rated_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Feedback
        fields = ['id', 'ticket', 'rated_by',
                  'rating', 'comment', 'created_at']


class TicketSerializer(serializers.ModelSerializer):
    """Main ticket serializer with nested relationships."""

    assigned_to_id = serializers.SlugRelatedField(
        slug_field='id',
        queryset=CustomUser.objects.filter(role='technician'),
        source='assigned_to',
        allow_null=True,
        required=False,
        write_only=True,
        label="Assigned_To ID"
    )

    section_id = serializers.PrimaryKeyRelatedField(
        queryset=Section.objects.all(), source='section', write_only=True, label='Section ID')

    facility_id = serializers.PrimaryKeyRelatedField(
        queryset=Facility.objects.all(), source='facility', write_only=True, label='Facility ID')

    section = serializers.StringRelatedField(read_only=True)
    facility = serializers.StringRelatedField(read_only=True)
    raised_by = serializers.StringRelatedField(read_only=True)
    assigned_to = UserSerializer(read_only=True)
    comments = CommentSerializer(many=True, read_only=True)
    feedback = FeedbackSerializer(read_only=True)

    class Meta:
        model = Ticket
        fields = [
            'id',
            'ticket_no',
            'title',
            'description',
            'status',
            'section_id', 'section',
            'facility_id', 'facility',
            'raised_by',
            'assigned_to_id', 'assigned_to',
            'created_at',
            'updated_at',
            'pending_reason',
            'comments',
            'feedback',
        ]

    def update(self, instance, validated_data):
        """Use default ModelSerializer update then let services call
        model-level change methods to perform and log stateful changes.

        We intentionally don't forward performed_by here; services should
        call `change_status` / `change_assignment` on the model to perform
        atomic state changes and logging.
        """
        return super().update(instance, validated_data)
