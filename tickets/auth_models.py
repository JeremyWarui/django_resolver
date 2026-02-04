from django.db import models
from django.utils import timezone
from datetime import timedelta
import secrets


class MagicLink(models.Model):
    """
    Model to store magic link tokens for passwordless authentication.
    """
    user = models.ForeignKey(
        'tickets.CustomUser', on_delete=models.CASCADE, related_name='magic_links')
    token = models.CharField(max_length=64, unique=True)
    email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    @classmethod
    def create_for_user(cls, user, expiry_minutes=15):
        """
        Create a new magic link for user with specified expiry time.
        """
        token = secrets.token_urlsafe(32)
        expires_at = timezone.now() + timedelta(minutes=expiry_minutes)

        # Invalidate any existing unused magic links for this user
        cls.objects.filter(user=user, used=False).update(used=True)

        return cls.objects.create(
            user=user,
            token=token,
            email=user.email,
            expires_at=expires_at
        )

    def is_valid(self):
        """Check if magic link is still valid."""
        return (
            not self.used and
            timezone.now() < self.expires_at
        )

    def mark_as_used(self):
        """Mark magic link as used."""
        self.used = True
        self.used_at = timezone.now()
        self.save()

    def __str__(self):
        return f"Magic Link for {self.user.username} - {'Used' if self.used else 'Valid' if self.is_valid() else 'Expired'}"


class LoginSession(models.Model):
    """
    Model to track user login sessions and preferences.
    """
    user = models.ForeignKey(
        'tickets.CustomUser', on_delete=models.CASCADE, related_name='login_sessions')
    token = models.OneToOneField(
        'authtoken.Token', on_delete=models.CASCADE, related_name='session_info')
    login_method = models.CharField(max_length=20, choices=[
        ('password', 'Password'),
        ('magic_link', 'Magic Link'),
    ])
    remember_me = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    @classmethod
    def create_session(cls, user, token, login_method, remember_me=False, request=None):
        """Create a new login session."""
        # Set expiry based on remember_me and user role
        if remember_me or user.role == 'technician':
            # Long session for technicians or remember_me
            expiry_hours = 24 * 30  # 30 days
        else:
            # Short session for regular users
            expiry_hours = 8  # 8 hours

        expires_at = timezone.now() + timedelta(hours=expiry_hours)

        # Get IP and user agent if request provided
        ip_address = None
        user_agent = ""
        if request:
            ip_address = cls.get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')[
                :500]  # Truncate to prevent overflow

        return cls.objects.create(
            user=user,
            token=token,
            login_method=login_method,
            remember_me=remember_me,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent
        )

    @staticmethod
    def get_client_ip(request):
        """Get client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    def is_valid(self):
        """Check if session is still valid."""
        return timezone.now() < self.expires_at

    def extend_session(self):
        """Extend session expiry on activity."""
        if self.remember_me or self.user.role == 'technician':
            # Extend by 30 days
            self.expires_at = timezone.now() + timedelta(days=30)
        else:
            # Extend by 8 hours
            self.expires_at = timezone.now() + timedelta(hours=8)
        self.save()

    def __str__(self):
        return f"{self.user.username} - {self.login_method} - {'Valid' if self.is_valid() else 'Expired'}"
