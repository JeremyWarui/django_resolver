"""
API Utilities Module

This module contains shared utilities for the Django Resolver API:
- cache_utils: Caching patterns and invalidation strategies
- pagination: Custom pagination classes with enhanced metadata
- signals: Django signals for cache invalidation and data synchronization
"""

from .cache_utils import (
    CacheKeyBuilder,
    CacheInvalidator,
    cached_view,
    get_or_set_cache,
)
from .pagination import (
    StandardResultsSetPagination,
    LargeResultsSetPagination,
)

__all__ = [
    "CacheKeyBuilder",
    "CacheInvalidator",
    "cached_view",
    "get_or_set_cache",
    "StandardResultsSetPagination",
    "LargeResultsSetPagination",
]
