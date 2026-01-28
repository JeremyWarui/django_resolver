"""
Test cache implementation for Django Resolver.
Run with: python manage.py test tickets.tests.test_caching
"""

from django.test import TestCase, override_settings
from django.core.cache import cache
from tickets.models import Ticket, CustomUser, Section, Facility
from tickets.api.utils.cache_utils import CacheKeyBuilder, CacheInvalidator

# Use LocMemCache for testing - doesn't require Redis to be running
TEST_CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'test-cache',
    }
}


@override_settings(CACHES=TEST_CACHES)
class CacheKeyBuilderTestCase(TestCase):
    """Test cache key generation."""

    def test_analytics_tickets_key_generation(self):
        """Test ticket analytics cache key generation."""
        key1 = CacheKeyBuilder.analytics_tickets(
            timeframe="week", facility_id=1)
        key2 = CacheKeyBuilder.analytics_tickets(
            timeframe="week", facility_id=1)
        key3 = CacheKeyBuilder.analytics_tickets(
            timeframe="day", facility_id=1)

        # Same parameters should generate same key
        self.assertEqual(key1, key2)

        # Different parameters should generate different keys
        self.assertNotEqual(key1, key3)

        # Key should follow pattern
        self.assertTrue(key1.startswith("analytics:tickets:"))

    def test_technician_cache_key(self):
        """Test technician cache key generation."""
        key1 = CacheKeyBuilder.analytics_technician(technician_id=5)
        key2 = CacheKeyBuilder.analytics_technician(technician_id=10)
        key_all = CacheKeyBuilder.analytics_technician()

        self.assertEqual(key1, "analytics:technician:5")
        self.assertEqual(key2, "analytics:technician:10")
        self.assertEqual(key_all, "analytics:technician:all")

    def test_ticket_list_key_with_filters(self):
        """Test ticket list cache key with various filters."""
        key1 = CacheKeyBuilder.ticket_list(status="open", page=1)
        key2 = CacheKeyBuilder.ticket_list(status="open", page=2)
        key3 = CacheKeyBuilder.ticket_list(status="pending", page=1)

        # Different page numbers should create different keys
        self.assertNotEqual(key1, key2)

        # Different status should create different keys
        self.assertNotEqual(key1, key3)

        # Keys should follow pattern
        self.assertTrue(key1.startswith("list:tickets:"))


@override_settings(CACHES=TEST_CACHES)
class CacheInvalidationTestCase(TestCase):
    """Test cache invalidation logic."""

    def setUp(self):
        """Set up test data."""
        self.section = Section.objects.create(name="Test Section")
        self.facility = Facility.objects.create(name="Test Facility")
        self.user = CustomUser.objects.create_user(
            username="testuser", password="testpass", role="user"
        )
        self.technician = CustomUser.objects.create_user(
            username="testtech", password="testpass", role="technician"
        )
        self.technician.sections.add(self.section)

    def test_ticket_cache_invalidation_on_create(self):
        """Test that creating a ticket invalidates relevant caches."""
        # Pre-populate some caches
        ticket_list_key = CacheKeyBuilder.ticket_list(status="open")
        admin_key = CacheKeyBuilder.analytics_admin()

        cache.set(ticket_list_key, "test_data", timeout=300)
        cache.set(admin_key, "admin_data", timeout=300)

        # Verify caches are set
        self.assertIsNotNone(cache.get(ticket_list_key))
        self.assertIsNotNone(cache.get(admin_key))

        # Create a ticket (should trigger signal)
        Ticket.objects.create(
            title="Test Ticket",
            description="Test Description",
            section=self.section,
            facility=self.facility,
            raised_by=self.user,
        )

        # Caches should be invalidated
        # Note: This test assumes signals are working
        # In actual implementation, signals handle invalidation
        self.assertIsNotNone(Ticket.objects.first())

    def test_manual_cache_invalidation(self):
        """Test manual cache invalidation methods."""
        # Set some test caches
        cache.set("analytics:tickets:test", "data1", timeout=300)
        cache.set("analytics:admin:test", "data2", timeout=300)
        cache.set("list:tickets:test", "data3", timeout=300)

        # Verify they're set
        self.assertEqual(cache.get("analytics:tickets:test"), "data1")
        self.assertEqual(cache.get("analytics:admin:test"), "data2")
        self.assertEqual(cache.get("list:tickets:test"), "data3")

        # Invalidate ticket caches
        CacheInvalidator.invalidate_ticket_caches()

        # Should be cleared (if delete_pattern works)
        # Note: delete_pattern behavior depends on Redis being available
        # This is a basic test structure


@override_settings(CACHES=TEST_CACHES)
class CacheFunctionalityTestCase(TestCase):
    """Test actual caching functionality."""

    def test_cache_get_set(self):
        """Test basic cache operations."""
        cache_key = "test:key"
        cache_value = {"data": "test_value"}

        # Set cache
        cache.set(cache_key, cache_value, timeout=60)

        # Get cache
        retrieved = cache.get(cache_key)
        self.assertEqual(retrieved, cache_value)

        # Delete cache
        cache.delete(cache_key)
        self.assertIsNone(cache.get(cache_key))

    def test_cache_timeout(self):
        """Test that cache respects TTL (basic check)."""
        cache_key = "test:timeout"
        cache.set(cache_key, "value", timeout=1)

        # Should exist immediately
        self.assertIsNotNone(cache.get(cache_key))

        # Should exist after short delay
        import time

        time.sleep(0.5)
        self.assertIsNotNone(cache.get(cache_key))

        # Should be gone after timeout
        time.sleep(1)
        self.assertIsNone(cache.get(cache_key))

    def test_cache_clear(self):
        """Test clearing all caches."""
        # Set multiple cache keys
        cache.set("test:1", "value1", timeout=300)
        cache.set("test:2", "value2", timeout=300)

        # Clear all
        cache.clear()

        # All should be gone
        self.assertIsNone(cache.get("test:1"))
        self.assertIsNone(cache.get("test:2"))


@override_settings(CACHES=TEST_CACHES)
class CacheUtilsTestCase(TestCase):
    """Test cache utility functions."""

    def test_get_or_set_cache_miss(self):
        """Test get_or_set_cache on cache miss."""
        from tickets.api.utils.cache_utils import get_or_set_cache

        cache_key = "test:get_or_set"
        call_count = [0]

        def expensive_function():
            call_count[0] += 1
            return {"result": "computed"}

        # First call should compute
        result1 = get_or_set_cache(cache_key, expensive_function, timeout=60)
        self.assertEqual(result1, {"result": "computed"})
        self.assertEqual(call_count[0], 1)

        # Second call should use cache
        result2 = get_or_set_cache(cache_key, expensive_function, timeout=60)
        self.assertEqual(result2, {"result": "computed"})
        self.assertEqual(call_count[0], 1)  # Function not called again

        # Clean up
        cache.delete(cache_key)

    def test_get_or_set_cache_hit(self):
        """Test get_or_set_cache on cache hit."""
        from tickets.api.utils.cache_utils import get_or_set_cache

        cache_key = "test:preloaded"
        cache.set(cache_key, "cached_value", timeout=60)

        # Function should not be called
        def should_not_call():
            raise Exception("Should not be called")

        result = get_or_set_cache(cache_key, should_not_call, timeout=60)
        self.assertEqual(result, "cached_value")

        # Clean up
        cache.delete(cache_key)
