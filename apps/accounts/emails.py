"""Email helpers for account invites and password resets.

Uses Django's own token/form machinery (django.contrib.auth.tokens,
django.contrib.auth.forms.PasswordResetForm) instead of hand-rolled
crypto or a bespoke token model.

Actual sending happens on a background thread (see _send_async) so a slow or
unreachable mail server can never hang the request: a hung synchronous
send_mail() call inside a Django view previously caused Daphne to forcibly
kill the connection after its shutdown grace period elapsed, leaving the
client with no response at all.
"""

import logging
import threading

from django.conf import settings
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import close_old_connections
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

logger = logging.getLogger(__name__)

INVITE_EXPIRY_DAYS = getattr(settings, "PASSWORD_RESET_TIMEOUT", 259200) // 86400


def _send_async(target, *args, **kwargs):
    """Run `target` inline, or on a daemon thread if EMAIL_SEND_ASYNC is on.
    Either way, exceptions are logged and never propagate to the caller —
    email delivery is best-effort and must never break account creation or a
    password-reset request."""

    def _run():
        try:
            target(*args, **kwargs)
        except Exception:
            logger.exception("Email send failed: %s", target.__name__)
        finally:
            close_old_connections()

    if getattr(settings, "EMAIL_SEND_ASYNC", True):
        threading.Thread(target=_run, daemon=True).start()
    else:
        _run()


def _do_send_invite_email(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    link = f"{settings.FRONTEND_URL}/set-password/{uid}/{token}"
    context = {
        "first_name": user.first_name,
        "username": user.username,
        "link": link,
        "company_name": settings.COMPANY_NAME,
        "expiry_days": INVITE_EXPIRY_DAYS,
    }
    subject = render_to_string("emails/invite_email_subject.txt", context).strip()
    body = render_to_string("emails/invite_email.txt", context)
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email])


def send_invite_email(user):
    """Email a brand-new (inactive, unusable-password) user their username plus
    a one-time link to set their own password and activate the account.
    Fire-and-forget: never blocks or raises into the caller."""
    _send_async(_do_send_invite_email, user)


def _do_send_password_reset_email(email):
    form = PasswordResetForm(data={"email": email})
    if not form.is_valid():
        return
    form.save(
        domain_override="resolver-app",  # unused by our templates; FRONTEND_URL is injected below
        subject_template_name="emails/password_reset_subject.txt",
        email_template_name="emails/password_reset_email.txt",
        from_email=settings.DEFAULT_FROM_EMAIL,
        token_generator=default_token_generator,
        extra_email_context={
            "frontend_url": settings.FRONTEND_URL,
            "company_name": settings.COMPANY_NAME,
        },
    )


def send_password_reset_email(email):
    """Email a password-reset link to an already-active user, if the address
    matches one. Silently no-ops otherwise, so callers can return a generic
    "check your email" response regardless (avoids user enumeration).

    Delegates to Django's own PasswordResetForm, which already looks up
    matching active users with a usable password, builds the uid/token,
    renders the email templates, and sends the mail. Fire-and-forget: never
    blocks or raises into the caller.
    """
    _send_async(_do_send_password_reset_email, email)
