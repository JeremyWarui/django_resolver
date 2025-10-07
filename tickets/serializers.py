from django.contrib.auth.models import User
from rest_framework import serializers
from .models import *
from django.contrib.auth import get_user_model

# User = get_user_model()


class FacilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Facility
        fields = ['id', 'name', 'type', 'status', 'location']


class SectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Section
        fields = "__all__"


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    username = serializers.CharField(read_only=True)

    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'first_name',
                  'last_name', 'email', 'password', 'role']

    def create(self, validated_data):
        first_name = validated_data.get('first_name')
        last_name = validated_data.get('last_name')
        email = validated_data.get('email', '')
        password = validated_data['password']
        role = validated_data.get('role', 'user')

        base_username = f"{first_name.lower()}.{last_name.lower()}"
        username = base_username
        counter = 1

        # to ensure the username is unique lets add a digit
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
        return user


class CommentSerializer(serializers.ModelSerializer):
    # Write-only field for author ID
    author_id = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.all(), source='author', write_only=True)
    # write ony field for ticket ID
    ticket_id = serializers.PrimaryKeyRelatedField(
        queryset=Ticket.objects.all(), source='ticket', write_only=True)

    # read-only field for author username
    author = serializers.StringRelatedField(read_only=True)
    ticket = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Comment
        fields = ['id', 'ticket_id', 'ticket', 'text', 'author_id', 'author']


class FeedbackSerializer(serializers.ModelSerializer):
    # Write-only field for rated_by ID
    rated_by_id = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.all(), source='rated_by', write_only=True)
    # write only field for ticket ID
    ticket_id = serializers.PrimaryKeyRelatedField(
        queryset=Ticket.objects.all(), source='ticket', write_only=True)

    ticket = serializers.StringRelatedField(read_only=True)
    rated_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Feedback
        fields = ['id', 'ticket_id', 'ticket',
                  'rated_by_id', 'rated_by', 'rating', 'comment']


class TicketSerializer(serializers.ModelSerializer):
    # write only field for IDS
    raised_by_id = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.all(), source='raised_by', write_only=True)

    assigned_to_id = serializers.SlugRelatedField(
        slug_field='username',
        queryset=CustomUser.objects.all(),
        source='assigned_to',
        allow_null=True,
        required=False)

    section_id = serializers.PrimaryKeyRelatedField(
        queryset=Section.objects.all(), source='section', write_only=True)

    facility_id = serializers.PrimaryKeyRelatedField(
        queryset=Facility.objects.all(), source='facility', write_only=True)

    # read only fields for related names
    section = serializers.StringRelatedField(read_only=True)
    facility = serializers.StringRelatedField(read_only=True)
    raised_by = serializers.StringRelatedField(read_only=True)
    assigned_to = serializers.StringRelatedField(read_only=True)
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
            'raised_by_id', 'raised_by',
            'assigned_to_id', 'assigned_to',
            'created_at',
            'updated_at',
            'comments',
            'feedback',
        ]
