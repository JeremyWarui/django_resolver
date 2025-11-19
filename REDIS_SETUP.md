# Redis Caching Setup Checklist

## Prerequisites
- [ ] Python 3.8+ installed
- [ ] Virtual environment activated
- [ ] Redis server (local or remote access)

## Installation Steps

### 1. Install Redis Server

**macOS (Homebrew):**
```bash
brew install redis
brew services start redis
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

**Docker:**
```bash
docker run -d --name redis -p 6379:6379 redis:alpine
```

**Verify Redis is running:**
```bash
redis-cli ping
# Expected output: PONG
```

### 2. Install Python Dependencies

```bash
# Activate virtual environment
source .venv/bin/activate  # macOS/Linux
# or
.venv\Scripts\activate  # Windows

# Install packages
pip install django-redis==5.4.0 redis==5.2.0

# Or install all requirements
pip install -r requirements.txt
```

### 3. Configure Environment

Create or update `.env` file in project root:
```env
# Redis Configuration
REDIS_URL=redis://127.0.0.1:6379/1

# For production with authentication:
# REDIS_URL=redis://:password@hostname:6379/1

# Other existing settings...
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

### 4. Verify Django Configuration

```bash
python manage.py check
# Should show: System check identified no issues (0 silenced).
```

### 5. Test Cache Connection

```bash
python manage.py shell
```

```python
>>> from django.core.cache import cache
>>> cache.set('test', 'Hello Redis!', timeout=60)
True
>>> cache.get('test')
'Hello Redis!'
>>> cache.delete('test')
True
```

### 6. Run Migrations (if needed)

```bash
python manage.py migrate
```

### 7. Load Test Data (Optional)

```bash
python manage.py loaddata tickets/fixtures/tickets_initial_data.json
```

### 8. Start Development Server

```bash
python manage.py runserver
```

### 9. Test Cached Endpoints

**Admin Dashboard:**
```bash
curl http://localhost:8000/api/analytics/admin-dashboard/
```

**Technician Analytics:**
```bash
curl http://localhost:8000/api/analytics/technicians/
```

**Ticket List (with filters):**
```bash
curl http://localhost:8000/api/tickets/?status=open
```

### 10. Verify Caching is Working

**Monitor Redis in real-time:**
```bash
redis-cli MONITOR
# Make API requests and watch cache operations
```

**Check cache keys:**
```bash
redis-cli KEYS "django_resolver:*"
```

**Clear cache:**
```bash
python manage.py clear_cache
```

## Troubleshooting

### Issue: ModuleNotFoundError: No module named 'django_redis'

**Solution:**
```bash
pip install django-redis==5.4.0 redis==5.2.0
```

### Issue: Connection refused to Redis

**Solution:**
```bash
# Check if Redis is running
redis-cli ping

# If not, start Redis
redis-server  # or use brew/systemctl as shown above
```

### Issue: Cache not working (always hitting database)

**Solution:**
```bash
# Check Redis connection in Django
python manage.py shell
>>> from django.core.cache import cache
>>> cache.set('test', 'value')  # Should return True
>>> cache.get('test')  # Should return 'value'

# Check REDIS_URL in .env
# Check Redis logs: redis-cli MONITOR
```

### Issue: Old data showing after updates

**Solution:**
```bash
# Clear all caches
python manage.py clear_cache

# Or clear specific pattern
python manage.py clear_cache --pattern "analytics:*"
```

## Verification Commands

```bash
# 1. Check Redis status
redis-cli ping

# 2. Check Redis info
redis-cli INFO

# 3. List all cache keys
redis-cli KEYS "django_resolver:*"

# 4. Monitor cache operations
redis-cli MONITOR

# 5. Check cache statistics
redis-cli INFO stats

# 6. Test Django cache
python manage.py shell -c "from django.core.cache import cache; print(cache.set('test', 'ok')); print(cache.get('test'))"

# 7. Run cache tests
python manage.py test tickets.tests.test_caching

# 8. Check Django configuration
python manage.py check --deploy
```

## Performance Monitoring

### Before and After Comparison

**Test endpoint performance:**
```bash
# Install Apache Bench (if not installed)
# macOS: brew install httpd
# Ubuntu: sudo apt-get install apache2-utils

# Test admin dashboard (100 requests)
ab -n 100 -c 10 http://localhost:8000/api/analytics/admin-dashboard/

# Clear cache and test again
python manage.py clear_cache
ab -n 100 -c 10 http://localhost:8000/api/analytics/admin-dashboard/

# Compare results: Look at "Time per request" metric
```

### Expected Results

**Without Cache (first run):**
- Time per request: ~250-400ms
- Requests per second: ~50-100

**With Cache (subsequent runs):**
- Time per request: ~5-15ms
- Requests per second: ~1000-2000

## Production Deployment

### Additional Steps for Production

1. **Use Redis Cloud Service**
   ```env
   # AWS ElastiCache
   REDIS_URL=redis://your-cluster.cache.amazonaws.com:6379/0
   
   # Redis Cloud
   REDIS_URL=redis://:password@redis-12345.redis.cloud:12345
   ```

2. **Configure Redis Persistence**
   ```bash
   # In redis.conf
   save 900 1
   save 300 10
   save 60 10000
   ```

3. **Set Memory Limits**
   ```bash
   # In redis.conf
   maxmemory 256mb
   maxmemory-policy allkeys-lru
   ```

4. **Enable Redis AUTH**
   ```bash
   # In redis.conf
   requirepass your-strong-password
   
   # Update .env
   REDIS_URL=redis://:your-strong-password@hostname:6379/1
   ```

5. **Monitor Redis in Production**
   - Set up Redis monitoring (CloudWatch, Datadog, etc.)
   - Configure alerts for memory usage, connection count
   - Track cache hit rates and response times

## Success Criteria

✅ All checks pass:
- [ ] Redis server running and accessible
- [ ] Python packages installed
- [ ] Django configuration valid (`python manage.py check`)
- [ ] Cache connection working (shell test)
- [ ] API endpoints return data
- [ ] Cache keys visible in Redis
- [ ] Cache hit rates > 80% on repeated requests
- [ ] Response times < 20ms for cached requests
- [ ] Tests pass: `python manage.py test tickets.tests.test_caching`

## Next Steps

1. Monitor cache hit rates in development
2. Load test with realistic traffic patterns
3. Adjust TTLs based on actual data volatility
4. Set up Redis monitoring for production
5. Document cache warming strategy if needed
6. Train team on cache management commands

---

**Setup Time:** ~15-30 minutes
**Skills Required:** Basic command line, Python/Django knowledge
**Support:** See `tickets/docs/CACHING_GUIDE.md` for detailed documentation
