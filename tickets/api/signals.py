"""
Signal handlers for cache invalidation.
Automatically invalidates relevant caches when models are created, updated, or deleted.
"""
from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver
from tickets.models import Ticket, CustomUser, Section, Facility, Comment, Feedback
from tickets.api.cache_utils import CacheInvalidator


# ============================================
# TICKET SIGNALS
# ============================================

@receiver(post_save, sender=Ticket)
def invalidate_ticket_cache_on_save(sender, instance, created, **kwargs):
    """Invalidate ticket caches when a ticket is created or updated."""
    CacheInvalidator.invalidate_ticket_caches()

    # If ticket is assigned to a technician, invalidate their cache
    if instance.assigned_to:
        CacheInvalidator.invalidate_technician_cache(instance.assigned_to.id)


@receiver(post_delete, sender=Ticket)
def invalidate_ticket_cache_on_delete(sender, instance, **kwargs):
    """Invalidate ticket caches when a ticket is deleted."""
    CacheInvalidator.invalidate_ticket_caches()

    # If ticket was assigned, invalidate technician cache
    if instance.assigned_to:
        CacheInvalidator.invalidate_technician_cache(instance.assigned_to.id)


# ============================================
# USER SIGNALS
# ============================================

@receiver(post_save, sender=CustomUser)
def invalidate_user_cache_on_save(sender, instance, created, **kwargs):
    """Invalidate user caches when a user is created or updated."""
    CacheInvalidator.invalidate_user_caches()

    # If user is a technician, invalidate technician analytics
    if instance.role == 'technician':
        CacheInvalidator.invalidate_technician_cache(instance.id)


@receiver(post_delete, sender=CustomUser)
def invalidate_user_cache_on_delete(sender, instance, **kwargs):
    """Invalidate user caches when a user is deleted."""
    CacheInvalidator.invalidate_user_caches()

    if instance.role == 'technician':
        CacheInvalidator.invalidate_technician_cache(instance.id)


@receiver(m2m_changed, sender=CustomUser.sections.through)
def invalidate_cache_on_user_sections_change(sender, instance, action, **kwargs):
    """Invalidate caches when user's sections change."""
    if action in ['post_add', 'post_remove', 'post_clear']:
        CacheInvalidator.invalidate_user_caches()
        if instance.role == 'technician':
            CacheInvalidator.invalidate_technician_cache(instance.id)


# ============================================
# SECTION & FACILITY SIGNALS
# ============================================

@receiver(post_save, sender=Section)
def invalidate_section_cache_on_save(sender, instance, **kwargs):
    """Invalidate section caches when a section is created or updated."""
    CacheInvalidator.invalidate_section_caches()


@receiver(post_delete, sender=Section)
def invalidate_section_cache_on_delete(sender, instance, **kwargs):
    """Invalidate section caches when a section is deleted."""
    CacheInvalidator.invalidate_section_caches()


@receiver(post_save, sender=Facility)
def invalidate_facility_cache_on_save(sender, instance, **kwargs):
    """Invalidate facility caches when a facility is created or updated."""
    CacheInvalidator.invalidate_facility_caches()


@receiver(post_delete, sender=Facility)
def invalidate_facility_cache_on_delete(sender, instance, **kwargs):
    """Invalidate facility caches when a facility is deleted."""
    CacheInvalidator.invalidate_facility_caches()


# ============================================
# COMMENT & FEEDBACK SIGNALS
# ============================================

@receiver(post_save, sender=Comment)
def invalidate_cache_on_comment_save(sender, instance, **kwargs):
    """Invalidate relevant caches when a comment is added."""
    # Comments might affect ticket detail views, but we primarily
    # care about analytics which aggregate ticket data
    CacheInvalidator.invalidate_ticket_caches()


@receiver(post_save, sender=Feedback)
def invalidate_cache_on_feedback_save(sender, instance, **kwargs):
    """Invalidate relevant caches when feedback is added."""
    # Feedback affects technician ratings and analytics
    CacheInvalidator.invalidate_ticket_caches()

    # Invalidate specific technician's cache if ticket was assigned
    if instance.ticket.assigned_to:
        CacheInvalidator.invalidate_technician_cache(
            instance.ticket.assigned_to.id)


@receiver(post_delete, sender=Feedback)
def invalidate_cache_on_feedback_delete(sender, instance, **kwargs):
    """Invalidate relevant caches when feedback is deleted."""
    CacheInvalidator.invalidate_ticket_caches()

    if instance.ticket.assigned_to:
        CacheInvalidator.invalidate_technician_cache(
            instance.ticket.assigned_to.id)
