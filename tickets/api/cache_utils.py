"""
Cache utility functions for Django Resolver API.
Provides consistent caching patterns and invalidation strategies.
"""
from functools import wraps
from django.core.cache import cache
from django.utils.encoding import force_str
import hashlib
import json


class CacheKeyBuilder:
    """Build consistent cache keys across the application."""

    # Cache key prefixes for different data types
    ANALYTICS_TICKETS = "analytics:tickets"
    ANALYTICS_TECHNICIAN = "analytics:technician"
    ANALYTICS_ADMIN = "analytics:admin"
    LIST_TICKETS = "list:tickets"
    LIST_USERS = "list:users"
    LOOKUP_SECTIONS = "lookup:sections"
    LOOKUP_FACILITIES = "lookup:facilities"

    @staticmethod
    def _hash_params(params):
        """Create a hash from parameters for cache key."""
        if not params:
            return "none"
        # Sort keys for consistent hashing
        sorted_params = sorted(params.items())
        param_str = json.dumps(sorted_params, sort_keys=True)
        return hashlib.md5(param_str.encode()).hexdigest()[:12]

    @classmethod
    def analytics_tickets(cls, timeframe=None, facility_id=None, section_id=None,
                          group_by=None, days=None):
        """Build cache key for ticket analytics."""
        params = {
            'timeframe': timeframe,
            'facility_id': facility_id,
            'section_id': section_id,
            'group_by': group_by,
            'days': days
        }
        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}
        param_hash = cls._hash_params(params)
        return f"{cls.ANALYTICS_TICKETS}:{param_hash}"

    @classmethod
    def analytics_technician(cls, technician_id=None):
        """Build cache key for technician analytics."""
        tech_id = technician_id or "all"
        return f"{cls.ANALYTICS_TECHNICIAN}:{tech_id}"

    @classmethod
    def analytics_admin(cls):
        """Build cache key for admin dashboard analytics."""
        return f"{cls.ANALYTICS_ADMIN}:dashboard"

    @classmethod
    def ticket_list(cls, status=None, section=None, assigned_to=None,
                    raised_by=None, is_overdue=None, assigned_to_isnull=None,
                    page=1, page_size=10):
        """Build cache key for ticket list queries."""
        params = {
            'status': status,
            'section': section,
            'assigned_to': assigned_to,
            'raised_by': raised_by,
            'is_overdue': is_overdue,
            'assigned_to_isnull': assigned_to_isnull,
            'page': page,
            'page_size': page_size
        }
        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}
        param_hash = cls._hash_params(params)
        return f"{cls.LIST_TICKETS}:{param_hash}"

    @classmethod
    def user_list(cls, role=None, sections=None, page=1, page_size=10):
        """Build cache key for user list queries."""
        params = {
            'role': role,
            'sections': sections,
            'page': page,
            'page_size': page_size
        }
        params = {k: v for k, v in params.items() if v is not None}
        param_hash = cls._hash_params(params)
        return f"{cls.LIST_USERS}:{param_hash}"

    @classmethod
    def sections_list(cls):
        """Build cache key for sections lookup."""
        return f"{cls.LOOKUP_SECTIONS}:all"

    @classmethod
    def facilities_list(cls):
        """Build cache key for facilities lookup."""
        return f"{cls.LOOKUP_FACILITIES}:all"


class CacheInvalidator:
    """Handle cache invalidation for different operations."""

    @staticmethod
    def invalidate_ticket_caches():
        """Invalidate all ticket-related caches."""
        # Invalidate analytics caches
        cache.delete_pattern(f"{CacheKeyBuilder.ANALYTICS_TICKETS}:*")
        cache.delete_pattern(f"{CacheKeyBuilder.ANALYTICS_ADMIN}:*")
        cache.delete_pattern(f"{CacheKeyBuilder.ANALYTICS_TECHNICIAN}:*")

        # Invalidate ticket list caches
        cache.delete_pattern(f"{CacheKeyBuilder.LIST_TICKETS}:*")

    @staticmethod
    def invalidate_user_caches():
        """Invalidate user-related caches."""
        cache.delete_pattern(f"{CacheKeyBuilder.LIST_USERS}:*")
        cache.delete_pattern(f"{CacheKeyBuilder.ANALYTICS_TECHNICIAN}:*")

    @staticmethod
    def invalidate_section_caches():
        """Invalidate section lookup caches."""
        cache.delete_pattern(f"{CacheKeyBuilder.LOOKUP_SECTIONS}:*")
        # Also invalidate ticket caches as sections affect ticket queries
        CacheInvalidator.invalidate_ticket_caches()

    @staticmethod
    def invalidate_facility_caches():
        """Invalidate facility lookup caches."""
        cache.delete_pattern(f"{CacheKeyBuilder.LOOKUP_FACILITIES}:*")
        # Also invalidate ticket caches as facilities affect ticket queries
        CacheInvalidator.invalidate_ticket_caches()

    @staticmethod
    def invalidate_technician_cache(technician_id):
        """Invalidate cache for specific technician."""
        cache_key = CacheKeyBuilder.analytics_technician(technician_id)
        cache.delete(cache_key)
        # Also invalidate "all technicians" cache
        cache.delete(CacheKeyBuilder.analytics_technician())


def cached_view(timeout=300, key_builder=None):
    """
    Decorator for caching view responses.

    Args:
        timeout: Cache timeout in seconds (default: 5 minutes)
        key_builder: Function that takes request and returns cache key
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(self, request, *args, **kwargs):
            # Build cache key
            if key_builder:
                cache_key = key_builder(request, *args, **kwargs)
            else:
                # Default key based on path and query params
                query_hash = hashlib.md5(
                    force_str(request.GET.urlencode()).encode()
                ).hexdigest()[:12]
                cache_key = f"view:{request.path}:{query_hash}"

            # Try to get from cache
            cached_response = cache.get(cache_key)
            if cached_response is not None:
                return cached_response

            # Generate response
            response = view_func(self, request, *args, **kwargs)

            # Cache the response
            if response.status_code == 200:
                cache.set(cache_key, response, timeout)

            return response
        return wrapper
    return decorator


def get_or_set_cache(cache_key, callback, timeout=300):
    """
    Get data from cache or compute and cache it.

    Args:
        cache_key: The cache key
        callback: Function to call if cache miss
        timeout: Cache timeout in seconds

    Returns:
        The cached or computed data
    """
    data = cache.get(cache_key)
    if data is None:
        data = callback()
        cache.set(cache_key, data, timeout)
    return data
