# Deploying Django Resolver with Redis on Render

## Render Redis Options

### Option 1: Managed Redis (Recommended - Already Configured)

Your `render.yaml` is now configured with Render's managed Redis service.

**Pricing:**
- **Free tier**: 25 MB, perfect for development/testing
- **Starter**: $10/month - 256 MB
- **Standard**: $50/month - 1 GB
- **Pro**: $200/month - 4 GB

**Features:**
- Automatic backups
- TLS encryption
- Monitoring dashboard
- Auto-scaling
- 99.9% uptime SLA

**Configuration is automatic:**
The `REDIS_URL` environment variable is automatically set by Render and injected into your Django app.

### Option 2: External Redis Provider

If you prefer using an external Redis provider:

#### Upstash (Serverless Redis)
```yaml
# In render.yaml
envVars:
  - key: REDIS_URL
    value: redis://default:your-password@your-endpoint.upstash.io:6379
```

**Pricing:** Pay-per-request, free tier available
**Website:** https://upstash.com

#### Redis Cloud (Redis Labs)
```yaml
envVars:
  - key: REDIS_URL
    value: redis://default:password@redis-12345.redis.cloud:12345
```

**Pricing:** Free tier 30MB
**Website:** https://redis.com/try-free/

#### AWS ElastiCache (Advanced)
```yaml
envVars:
  - key: REDIS_URL
    value: redis://your-cluster.cache.amazonaws.com:6379/0
```

## Deployment Steps

### 1. Using Render's Managed Redis (Recommended)

**Via Render Dashboard:**

1. **Create Redis Instance**
   - Go to [Render Dashboard](https://dashboard.render.com)
   - Click "New +" → "Redis"
   - Name: `django-resolver-redis`
   - Plan: Select based on needs (Free tier available)
   - Click "Create Redis"

2. **Link to Web Service**
   - Go to your web service
   - Environment → Add environment variable
   - Key: `REDIS_URL`
   - Value: Click "From Service" → Select your Redis instance
   - Save

**Via Infrastructure as Code (render.yaml):**

Your `render.yaml` is already configured! Just push to your repo:

```bash
git add render.yaml
git commit -m "Add Redis service for caching"
git push origin main
```

Render will automatically:
- Create the Redis instance
- Link it to your web service
- Set the `REDIS_URL` environment variable

### 2. Using Blueprint (Automated)

If deploying via Render Blueprint:

```bash
# Push your updated render.yaml
git push origin main

# Render detects changes and:
# 1. Creates Redis service
# 2. Links REDIS_URL to web service
# 3. Rebuilds and redeploys
```

### 3. Verify Deployment

**Check Redis Connection:**

1. Go to Render Dashboard → Your web service → Shell
2. Run:
   ```python
   python manage.py shell
   from django.core.cache import cache
   cache.set('test', 'Render Redis works!')
   print(cache.get('test'))
   ```

**Check Environment Variables:**
```bash
# In Render Shell
echo $REDIS_URL
# Should show: redis://red-xxxxx.render.com:6379
```

**Test Endpoints:**
```bash
# Test cached endpoint
curl https://your-app.onrender.com/api/analytics/admin-dashboard/

# Check response headers (if you add cache headers)
curl -I https://your-app.onrender.com/api/analytics/tickets/
```

## Configuration Details

### Current Settings (Already Configured)

Your `resolver/settings.py` is already set up:

```python
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {'max_connections': 50},
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
            'IGNORE_EXCEPTIONS': True,  # Fail gracefully
        },
    }
}
```

**Key Points:**
- `IGNORE_EXCEPTIONS: True` - App works even if Redis is down
- Connection pooling - Efficient connection management
- Compression - Reduces memory usage

### SSL/TLS for Production

Render's Redis uses TLS by default. If using external Redis with TLS:

```python
# settings.py
CACHES = {
    'default': {
        'LOCATION': os.getenv('REDIS_URL'),
        'OPTIONS': {
            'CONNECTION_POOL_KWARGS': {
                'ssl_cert_reqs': None  # For self-signed certs
            }
        }
    }
}
```

## Monitoring on Render

### Redis Metrics Dashboard

1. Go to Render Dashboard → Your Redis instance
2. View metrics:
   - Memory usage
   - Commands per second
   - Connected clients
   - Hit rate
   - Evicted keys

### Web Service Logs

```bash
# View logs in Render Dashboard
# Look for cache-related messages
[INFO] Cache hit: analytics:admin:dashboard
[INFO] Cache miss: list:tickets:abc123
```

### Custom Monitoring

Add to your Django views:

```python
import logging
logger = logging.getLogger(__name__)

# In cached views
cache_key = CacheKeyBuilder.analytics_admin()
cached_data = cache.get(cache_key)
logger.info(f"Cache {'HIT' if cached_data else 'MISS'}: {cache_key}")
```

## Performance Optimization

### Connection Pooling

Already configured in settings.py:
```python
'CONNECTION_POOL_KWARGS': {'max_connections': 50}
```

### Memory Management

**Check memory usage:**
```python
from django_redis import get_redis_connection
con = get_redis_connection("default")
info = con.info('memory')
print(f"Used memory: {info['used_memory_human']}")
print(f"Max memory: {info.get('maxmemory_human', 'No limit')}")
```

**Set maxmemory policy** (in render.yaml):
```yaml
services:
  - type: redis
    maxmemoryPolicy: allkeys-lru  # Remove least recently used keys
```

### Cache Warming

Add to `build.sh` for production:

```bash
# After migrations
python manage.py shell << EOF
from tickets.api.cache_utils import CacheKeyBuilder
from django.core.cache import cache
# Pre-warm critical caches
# ... warm cache logic ...
EOF
```

## Troubleshooting

### Issue: Cannot connect to Redis

**Check:**
1. Redis service is running (Render Dashboard)
2. `REDIS_URL` is set (Environment tab)
3. IP allowlist includes Render's IPs (if using external Redis)

**Test connection:**
```python
import redis
from django.conf import settings
r = redis.from_url(settings.CACHES['default']['LOCATION'])
r.ping()  # Should return True
```

### Issue: High memory usage

**Solutions:**
1. Reduce cache TTLs
2. Use `allkeys-lru` eviction policy
3. Upgrade Redis plan
4. Compress data before caching

### Issue: Cache not invalidating

**Check:**
1. Signals are registered (`tickets/apps.py`)
2. Redis supports pattern deletion (`delete_pattern`)
3. Use `FLUSHDB` to clear all (destructive):
   ```bash
   redis-cli -u $REDIS_URL FLUSHDB
   ```

### Issue: Slow performance

**Check:**
1. Cache hit rate (should be >80%)
2. Network latency (use same region as Redis)
3. Connection pool size
4. TTL values (too short = frequent DB queries)

## Cost Optimization

### Free Tier Strategy

**Render Free Redis (25 MB):**
- Cache only critical endpoints
- Use shorter TTLs (1-3 min)
- Monitor memory usage
- Implement size limits per cache key

**Example - Optimize for free tier:**
```python
# Reduce TTLs for free tier
if os.getenv('REDIS_PLAN') == 'free':
    CACHE_TTLS = {
        'admin': 180,      # 3 min instead of 5
        'tickets': 120,    # 2 min
        'technician': 300, # 5 min
    }
```

### Paid Tier Benefits

**Starter Plan ($10/month, 256 MB):**
- Production-ready
- Better performance
- More cache space
- 99.9% uptime SLA

**When to upgrade:**
- Cache memory >20 MB consistently
- Cache evictions happening frequently
- High traffic volume (>10k requests/day)

## Production Checklist

- [x] Redis service created on Render
- [x] `REDIS_URL` environment variable set
- [x] `django-redis` installed in requirements.txt
- [x] Cache configuration in settings.py
- [x] Signals registered for cache invalidation
- [ ] Test cache in staging environment
- [ ] Monitor cache hit rates (>80%)
- [ ] Set up alerts for Redis memory/errors
- [ ] Document cache warming strategy (if needed)
- [ ] Configure backup strategy (Render handles this)
- [ ] Review TTLs for production traffic patterns

## Alternative: No Redis (Fallback)

If you want to deploy without Redis initially:

```python
# settings.py - Fallback to local memory cache
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}
```

**Note:** Local memory cache won't work across multiple Render instances (horizontal scaling).

## Support & Resources

- **Render Redis Docs**: https://render.com/docs/redis
- **Django Cache Framework**: https://docs.djangoproject.com/en/4.2/topics/cache/
- **django-redis**: https://github.com/jazzband/django-redis
- **Your Implementation**: `tickets/docs/CACHING_GUIDE.md`

---

**Quick Start:** Just push your updated `render.yaml` to trigger deployment with Redis! 🚀
