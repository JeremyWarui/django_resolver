# Redis Caching Implementation Guide

## Overview
This document describes the Redis caching strategy implemented for the Django Resolver API to optimize dashboard performance across Admin, User, and Technician dashboards.

## Architecture

### Cache Strategy
The implementation uses **Django Redis** with intelligent cache key generation and automatic invalidation via Django signals.

### Cache Layers
1. **Analytics Layer** - Dashboard aggregations (5-10 min TTL)
2. **List Layer** - Filtered ticket/user queries (2-15 min TTL)
3. **Lookup Layer** - Sections/facilities (1 hour TTL)

## Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
# Includes: django-redis==5.4.0, redis==5.2.0
```

### 2. Environment Configuration
Add to your `.env` file:
```env
REDIS_URL=redis://127.0.0.1:6379/1
# For production with password:
# REDIS_URL=redis://:password@hostname:6379/1
```

### 3. Redis Server
Start Redis locally:
```bash
# macOS (Homebrew)
brew services start redis

# Ubuntu/Debian
sudo systemctl start redis-server

# Docker
docker run -d -p 6379:6379 redis:alpine
```

Verify Redis is running:
```bash
redis-cli ping
# Should return: PONG
```

## Cache Configuration Details

### Cache Keys Structure
```python
# Analytics caches
analytics:tickets:{hash}        # Ticket analytics with filters
analytics:technician:{id|all}   # Technician performance stats
analytics:admin:dashboard       # Admin system overview

# List caches
list:tickets:{hash}             # Filtered ticket lists
list:users:{hash}               # Filtered user lists

# Lookup caches
lookup:sections:all             # All sections
lookup:facilities:all           # All facilities
```

### TTL (Time To Live) Settings

| Cache Type | TTL | Rationale |
|-----------|-----|-----------|
| **Admin Dashboard** | 5 min | Balance real-time insight with DB load |
| **Ticket Analytics** | 5 min | Frequent updates expected |
| **Technician Analytics** | 10 min | Less volatile, computation-heavy |
| **Ticket Lists** | 2 min | Need fresh data for operations |
| **User Lists** | 15 min | Relatively stable data |
| **Sections/Facilities** | 1 hour | Rarely changes |

## Dashboard-Specific Caching

### Admin Dashboard (`/api/analytics/admin-dashboard/`)
**What's cached:**
- Total tickets count
- Resolution rates
- Overdue tickets list
- Average resolution time
- System-wide metrics

**Cache key:** `analytics:admin:dashboard`
**TTL:** 5 minutes
**Invalidation:** On any ticket create/update/delete

### Technician Dashboard (`/api/analytics/technicians/?technician_id=X`)
**What's cached:**
- Individual technician performance
- Tickets assigned/resolved/pending
- Average ratings
- Resolution times

**Cache key:** `analytics:technician:{id}`
**TTL:** 10 minutes
**Invalidation:** 
- When technician's ticket is updated
- When feedback is added to technician's ticket
- When user's sections change

### Ticket Analytics (`/api/analytics/tickets/`)
**What's cached:**
- Ticket counts by timeframe
- Status distribution
- Trend data
- Facility/section distribution

**Cache key:** `analytics:tickets:{hash}` (based on filters)
**TTL:** 5 minutes
**Invalidation:** On ticket create/update/delete

### Ticket Lists (`/api/tickets/`)
**Common queries cached:**
```python
# Open tickets: /api/tickets/?status=open
# Unassigned: /api/tickets/?assigned_to__isnull=true
# Overdue: /api/tickets/?is_overdue=true
# By technician: /api/tickets/?assigned_to=5
# By section: /api/tickets/?section=2
```

**Cache key:** `list:tickets:{hash}` (includes filters + pagination)
**TTL:** 2 minutes
**Invalidation:** On ticket create/update/delete

## Cache Invalidation

### Automatic Invalidation (via Signals)
The system automatically invalidates caches when data changes:

```python
# Ticket operations
ticket.save()           → Invalidates: ticket lists, analytics
ticket.delete()         → Invalidates: ticket lists, analytics

# User operations  
user.save()            → Invalidates: user lists, technician analytics
user.sections.add()    → Invalidates: user lists, technician analytics

# Feedback
feedback.save()        → Invalidates: technician analytics for assigned tech

# Sections/Facilities
section.save()         → Invalidates: section lookups, ticket caches
facility.save()        → Invalidates: facility lookups, ticket caches
```

### Manual Cache Clearing
```bash
# Clear all caches
python manage.py clear_cache

# Clear specific pattern
python manage.py clear_cache --pattern "analytics:*"
python manage.py clear_cache --pattern "list:tickets:*"
```

### Programmatic Cache Access
```python
from django.core.cache import cache
from tickets.api.cache_utils import CacheKeyBuilder, CacheInvalidator

# Get specific cache
cache_key = CacheKeyBuilder.analytics_admin()
data = cache.get(cache_key)

# Invalidate specific caches
CacheInvalidator.invalidate_ticket_caches()
CacheInvalidator.invalidate_technician_cache(technician_id=5)
```

## Performance Impact

### Expected Improvements
| Endpoint | Before (avg) | After (cached) | Improvement |
|----------|-------------|----------------|-------------|
| Admin Dashboard | 250-400ms | 5-15ms | ~95% |
| Ticket Analytics | 180-300ms | 5-10ms | ~96% |
| Technician Stats | 150-250ms | 5-10ms | ~95% |
| Ticket Lists | 100-200ms | 3-8ms | ~95% |
| Sections/Facilities | 50-80ms | 2-5ms | ~94% |

### Cache Hit Metrics
Monitor cache performance:
```python
# In Django shell
from django.core.cache import cache
from django_redis import get_redis_connection

con = get_redis_connection("default")
info = con.info()
print(f"Cache hits: {info['keyspace_hits']}")
print(f"Cache misses: {info['keyspace_misses']}")
print(f"Hit rate: {info['keyspace_hits'] / (info['keyspace_hits'] + info['keyspace_misses']) * 100:.2f}%")
```

## Monitoring & Debugging

### View Cache Keys
```bash
# Connect to Redis CLI
redis-cli

# List all keys
KEYS django_resolver:*

# View specific key
GET django_resolver:analytics:admin:dashboard

# Check TTL
TTL django_resolver:analytics:admin:dashboard

# Delete key
DEL django_resolver:analytics:admin:dashboard
```

### Common Issues

#### Issue: Cache never hits
**Solution:** Check Redis connection
```bash
redis-cli ping
# Check REDIS_URL in .env
```

#### Issue: Stale data showing
**Solution:** Check cache TTL or manually clear
```bash
python manage.py clear_cache --pattern "analytics:*"
```

#### Issue: Redis memory full
**Solution:** Configure Redis eviction policy
```bash
# In redis.conf
maxmemory 256mb
maxmemory-policy allkeys-lru
```

## Production Considerations

### Redis Configuration
```python
# settings.py - Production settings
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.getenv('REDIS_URL'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 50,  # Adjust based on traffic
                'retry_on_timeout': True,
            },
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
            'IGNORE_EXCEPTIONS': True,  # Fail gracefully if Redis down
        },
    }
}
```

### Deployment Checklist
- [ ] Redis server running and accessible
- [ ] `REDIS_URL` environment variable set
- [ ] Redis persistence configured (RDB/AOF)
- [ ] Redis memory limits set
- [ ] Monitoring enabled (Redis INFO, CloudWatch, etc.)
- [ ] Backup strategy for Redis data (if needed)
- [ ] Connection pooling configured
- [ ] Network security (firewall rules, VPC)

### Cloud Providers

#### AWS ElastiCache
```env
REDIS_URL=redis://your-cluster.cache.amazonaws.com:6379/0
```

#### Redis Cloud
```env
REDIS_URL=redis://:password@redis-12345.redis.cloud:12345
```

#### Heroku Redis
```env
# Automatically set by Heroku addon
# No manual configuration needed
```

#### Digital Ocean Managed Redis
```env
REDIS_URL=redis://default:password@your-cluster-do-user-123456-0.db.ondigitalocean.com:25061
```

## Testing Cache Implementation

### Unit Tests
```python
# tests/test_caching.py
from django.test import TestCase
from django.core.cache import cache
from tickets.models import Ticket

class CacheTestCase(TestCase):
    def test_ticket_cache_invalidation(self):
        """Test that ticket creation invalidates cache"""
        # Pre-populate cache
        cache_key = "test:ticket:list"
        cache.set(cache_key, "old_data", timeout=300)
        
        # Create ticket
        ticket = Ticket.objects.create(...)
        
        # Cache should be cleared
        self.assertIsNone(cache.get(cache_key))
```

### Load Testing
```bash
# Using Apache Bench
ab -n 1000 -c 10 http://localhost:8000/api/analytics/admin-dashboard/

# Compare before/after cache implementation
```

## Best Practices

1. **Always use CacheKeyBuilder** for consistent key generation
2. **Set appropriate TTLs** based on data volatility
3. **Monitor cache hit rates** to validate effectiveness
4. **Use IGNORE_EXCEPTIONS=True** in production for resilience
5. **Document cache dependencies** when adding new features
6. **Test cache invalidation** in development
7. **Consider cache warming** for critical dashboards
8. **Use Redis Cluster** for high availability in production

## Troubleshooting

### Debug Cache Behavior
```python
# Add to view temporarily
import logging
logger = logging.getLogger(__name__)

cache_key = CacheKeyBuilder.analytics_admin()
cached_data = cache.get(cache_key)
logger.info(f"Cache key: {cache_key}, Hit: {cached_data is not None}")
```

### Performance Profiling
```python
import time
start = time.time()
# Your cached query
duration = time.time() - start
print(f"Query took: {duration*1000:.2f}ms")
```

## Future Enhancements

1. **Cache warming**: Pre-populate caches during low-traffic periods
2. **Cache versioning**: Add version numbers to keys for easier invalidation
3. **Distributed caching**: Redis Sentinel/Cluster for HA
4. **Cache analytics**: Dashboard for cache performance metrics
5. **Conditional caching**: Cache only for authenticated users
6. **Fragment caching**: Cache partial responses/templates
