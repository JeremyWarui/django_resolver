from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.urls import reverse
import logging

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending authentication-related emails."""

    @classmethod
    def send_magic_link(cls, user, magic_link, request=None):
        """
        Send magic link email to user.

        Args:
            user: CustomUser instance
            magic_link: MagicLink instance
            request: HttpRequest instance for building absolute URLs
        """
        try:
            # Build magic link URL
            if request:
                magic_url = request.build_absolute_uri(
                    reverse("magic_link_login", args=[magic_link.token])
                )
            else:
                # Fallback for testing/development
                base_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
                magic_url = f"{base_url}/auth/magic-link/{magic_link.token}"

            # Email context
            context = {
                "user": user,
                "magic_url": magic_url,
                "expiry_minutes": 15,
                "company_name": getattr(settings, "COMPANY_NAME", "Django Resolver"),
            }

            # Render email templates
            html_message = render_to_string("emails/magic_link.html", context)
            plain_message = render_to_string("emails/magic_link.txt", context)

            # Send email
            send_mail(
                subject=f"Your secure login link for {context['company_name']}",
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False,
            )

            logger.info(f"Magic link email sent to {user.email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send magic link email to {user.email}: {str(e)}")
            return False

    @classmethod
    def send_login_notification(cls, user, session_info):
        """
        Send login notification email for security.

        Args:
            user: CustomUser instance
            session_info: LoginSession instance
        """
        try:
            context = {
                "user": user,
                "login_method": session_info.login_method,
                "login_time": session_info.created_at,
                "ip_address": session_info.ip_address,
                "user_agent": session_info.user_agent,
                "company_name": getattr(settings, "COMPANY_NAME", "Django Resolver"),
            }

            # Render email templates
            html_message = render_to_string("emails/login_notification.html", context)
            plain_message = render_to_string("emails/login_notification.txt", context)

            # Send email
            send_mail(
                subject=f"New login to your {context['company_name']} account",
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=True,  # Don't fail login if notification fails
            )

            logger.info(f"Login notification sent to {user.email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send login notification to {user.email}: {str(e)}")
            return False
