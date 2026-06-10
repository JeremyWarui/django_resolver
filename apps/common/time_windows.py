"""Shared time-window helpers for RoleAssignment cover windows.

A single source of truth for "is this assignment active right now?" so the
identical predicate isn't re-implemented across scope resolution, escalation,
and the model. See SoT §1.3 / R7 (role cover is time-boxed).
"""

from django.db.models import Q


def active_window_q(now):
    """Q matching RoleAssignment rows whose validity window contains `now`.

    `valid_from is null` means "effective now"; `valid_until is null` means
    "standing role". A row is active when it has started and not yet expired.
    """
    return (
        Q(valid_from__isnull=True) | Q(valid_from__lte=now)
    ) & (
        Q(valid_until__isnull=True) | Q(valid_until__gt=now)
    )


def is_window_active(valid_from, valid_until, now):
    """Instance-level equivalent of `active_window_q` for a single assignment."""
    return (
        (valid_from is None or valid_from <= now)
        and (valid_until is None or valid_until > now)
    )
