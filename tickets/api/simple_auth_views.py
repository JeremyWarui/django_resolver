"""
Simple authentication views with password-based authentication.
- All roles: password authentication with remember-me option
- Magic link functionality commented out for future implementation
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.hashers import check_password
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

# Magic link temporarily disabled - uncomment when email is configured
# from tickets.auth_models import MagicLink, LoginSession
# from tickets.auth_models import LoginSession  # Temporarily disabled
from tickets.serializers import UserSerializer

User = get_user_model()


@api_view(["POST"])
@permission_classes([AllowAny])
def check_auth_method(request):
    """Determine authentication method based on user role.

    Currently all users use password authentication.
    Magic link functionality is commented out for future implementation.
    """
    email = request.data.get("email")

    if not email:
        return Response(
            {"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST
        )

    try:
        user = User.objects.get(email=email)
        # All roles use password authentication for now
        auth_method = "password"

        # Magic link temporarily disabled
        # if user.role in ['technician', 'admin', 'manager']:
        #     auth_method = 'password'
        # else:
        #     auth_method = 'magic_link'

        return Response(
            {"auth_method": auth_method, "user_role": user.role, "user_id": user.id}
        )
    except User.DoesNotExist:
        return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)


@api_view(["POST"])
@permission_classes([AllowAny])
def simple_auth_login(request):
    """Password login for all user roles."""
    username = request.data.get("username")
    password = request.data.get("password")
    remember_me = request.data.get("remember_me", False)

    if not username or not password:
        return Response(
            {"error": "Username and password are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Authenticate user
    user = authenticate(username=username, password=password)

    if not user:
        return Response(
            {"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED
        )

    # All roles can use password login now
    # Magic link functionality is commented out for future implementation
    # if user.role not in ['technician', 'admin', 'manager']:
    #     return Response(
    #         {'error': f'Users with role "{user.role}" should use magic link authentication'},
    #         status=status.HTTP_400_BAD_REQUEST
    #     )

    # Create or get token
    token, created = Token.objects.get_or_create(user=user)

    # Session tracking temporarily disabled - simple token auth only
    # session = LoginSession.create_session(
    #     user=user, token=token, login_method="password", remember_me=remember_me
    # )

    return Response(
        {
            "token": token.key,
            "user_id": user.id,
            "username": user.username,
            "role": user.role,
            "login_method": "password",
            "remember_me": remember_me,
            # "session_id": session.id,  # Disabled for now
        }
    )


# Magic link functionality temporarily disabled
# Uncomment when email service is properly configured
# @api_view(['POST'])
# @permission_classes([AllowAny])
# def request_magic_link(request):
#     """Request magic link for users only."""
#     email = request.data.get('email')
#
#     if not email:
#         return Response(
#             {'error': 'Email is required'},
#             status=status.HTTP_400_BAD_REQUEST
#         )
#
#     try:
#         user = User.objects.get(email=email)
#
#         # Check if user role is allowed for magic link
#         if user.role in ['technician', 'admin', 'manager']:
#             return Response(
#                 {'error': f'Users with role "{user.role}" should use password authentication'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )
#
#         # Create magic link
#         magic_link = MagicLink.create_for_user(user)
#
#         # Send email (simplified for demo)
#         magic_link_url = f"http://localhost:5173/auth/magic-link/{magic_link.token}"
#
#         # For now, just return the URL (in production, send email)
#         return Response({
#             'message': 'Magic link sent to your email',
#             'magic_link_url': magic_link_url  # Remove this in production
#         })
#
#     except User.DoesNotExist:
#         return Response(
#             {'error': 'User not found'},
#             status=status.HTTP_404_NOT_FOUND
#         )


# Magic link login temporarily disabled
# Uncomment when email service is properly configured
# @api_view(['POST'])
# @permission_classes([AllowAny])
# def magic_link_login(request, token):
#     """Login using magic link."""
#     try:
#         magic_link = MagicLink.objects.get(token=token)
#
#         if not magic_link.is_valid():
#             return Response(
#                 {'error': 'Magic link is invalid or expired'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )
#
#         # Mark as used
#         magic_link.used = True
#         magic_link.save()
#
#         user = magic_link.user
#
#         # Create or get token
#         auth_token, created = Token.objects.get_or_create(user=user)
#
#         # Create session tracking
#         session = LoginSession.create_session(
#             user=user,
#             token=auth_token,
#             login_method='magic_link',
#             remember_me=False
#         )
#
#         return Response({
#             'token': auth_token.key,
#             'user_id': user.id,
#             'username': user.username,
#             'role': user.role,
#             'login_method': 'magic_link',
#             'session_id': session.id
#         })
#
#     except MagicLink.DoesNotExist:
#         return Response(
#             {'error': 'Invalid magic link'},
#             status=status.HTTP_404_NOT_FOUND
#         )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def simple_logout(request):
    """Logout and cleanup tokens and sessions."""
    try:
        # Get user's token
        token = request.auth

        # Delete token (session tracking temporarily disabled)
        if token:
            # LoginSession.objects.filter(token=token).delete()  # Disabled for now
            token.delete()

        return Response({"message": "Logged out successfully"})

    except Exception as e:
        return Response(
            {"error": "Logout failed"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def user_profile(request):
    """Get current user profile."""
    serializer = UserSerializer(request.user)
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([AllowAny])
def register_user(request):
    """Register new user with password authentication.

    All users now use password authentication.
    Magic link functionality is commented out for future implementation.
    """
    serializer = UserSerializer(data=request.data)

    if serializer.is_valid():
        user = serializer.save()

        # All users use password authentication now
        auth_method = "password"

        # Magic link temporarily disabled
        # if user.role in ['technician', 'admin', 'manager']:
        #     auth_method = 'password'
        # else:
        #     auth_method = 'magic_link'

        return Response(
            {
                "message": "User registered successfully",
                "user_id": user.id,
                "username": user.username,
                "role": user.role,
                "auth_method": auth_method,
            },
            status=status.HTTP_201_CREATED,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
