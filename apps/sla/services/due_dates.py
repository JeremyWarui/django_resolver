"""SLA due-date computation — single source for response/resolution targets.

Used at ticket creation and on reopen (QA B2f: reopen restarts the SLA clock
from the reopen time, exactly as if the ticket were newly created).
"""

from datetime import timedelta


def compute_due_dates(priority, start):
    """Return (response_due_at, resolution_due_at) for a priority from `start`."""
    return (
        start + timedelta(minutes=priority.response_minutes),
        start + timedelta(minutes=priority.resolution_minutes),
    )
