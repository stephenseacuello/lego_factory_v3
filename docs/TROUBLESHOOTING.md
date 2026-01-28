# Troubleshooting Guide

This guide covers common issues and their solutions when running LEGO Factory v3.

## Table of Contents

- [Startup Issues](#startup-issues)
- [Database Issues](#database-issues)
- [Redis Issues](#redis-issues)
- [MQTT Issues](#mqtt-issues)
- [API Issues](#api-issues)
- [Performance Issues](#performance-issues)
- [Security Issues](#security-issues)
- [Test Issues](#test-issues)

---

## Startup Issues

### Application Fails to Start with ConfigurationError

**Symptoms:**
```
ConfigurationError: SECRET_KEY environment variable is required in production.
```

**Cause:** Running in production mode without proper secrets configured.

**Solutions:**

1. **For development/demo:** Enable demo mode
   ```bash
   export DEMO_MODE=true
   python -m flask run
   ```

2. **For production:** Generate proper secrets
   ```bash
   python scripts/generate_secrets.py --output .env
   source .env
   python -m flask run
   ```

3. **Quick fix:** Set individual secrets
   ```bash
   export SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
   export JWT_SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
   ```

### ImportError: No module named 'xxx'

**Symptoms:**
```
ImportError: No module named 'redis'
```

**Solution:** Install missing dependencies
```bash
pip install -r requirements.txt
```

For optional dependencies:
```bash
# Redis support
pip install redis

# MQTT support
pip install paho-mqtt

# OR-Tools for scheduling
pip install ortools

# ML dependencies
pip install torch torchvision
```

### Port Already in Use

**Symptoms:**
```
OSError: [Errno 48] Address already in use
```

**Solutions:**

1. Find and kill the process:
   ```bash
   # macOS/Linux
   lsof -i :5000
   kill -9 <PID>

   # Or use a different port
   export FLASK_PORT=5001
   ```

2. Change port in configuration:
   ```bash
   export FLASK_PORT=8080
   python -m flask run
   ```

---

## Database Issues

### Connection Refused

**Symptoms:**
```
sqlalchemy.exc.OperationalError: could not connect to server: Connection refused
```

**Solutions:**

1. **Check PostgreSQL is running:**
   ```bash
   # macOS
   brew services start postgresql

   # Linux
   sudo systemctl start postgresql

   # Docker
   docker-compose up -d postgres
   ```

2. **Verify connection settings:**
   ```bash
   # Test connection
   psql -h localhost -p 5432 -U postgres -d lego_factory

   # Check environment
   echo $DATABASE_URL
   ```

3. **Create database if missing:**
   ```bash
   createdb lego_factory
   ```

### Migration Issues

**Symptoms:**
```
alembic.util.exc.CommandError: Can't locate revision identified by 'xxx'
```

**Solutions:**

1. **Reset migrations (development only):**
   ```bash
   # Remove alembic version table
   psql -d lego_factory -c "DROP TABLE alembic_version;"

   # Re-run migrations
   alembic upgrade head
   ```

2. **Check migration history:**
   ```bash
   alembic history --verbose
   alembic current
   ```

### TimescaleDB Extension Not Found

**Symptoms:**
```
ERROR: extension "timescaledb" is not available
```

**Solutions:**

1. **Install TimescaleDB:**
   ```bash
   # macOS
   brew install timescaledb

   # Ubuntu
   sudo apt install timescaledb-postgresql-15

   # Enable extension
   psql -d lego_factory -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
   ```

2. **If TimescaleDB not available:** The application will work without it, but historian features will be limited.

---

## Redis Issues

### Connection Refused

**Symptoms:**
```
redis.exceptions.ConnectionError: Error 111 connecting to localhost:6379
```

**Solutions:**

1. **Start Redis:**
   ```bash
   # macOS
   brew services start redis

   # Linux
   sudo systemctl start redis

   # Docker
   docker run -d -p 6379:6379 redis:alpine
   ```

2. **Check Redis configuration:**
   ```bash
   redis-cli ping
   # Should return: PONG
   ```

3. **Verify environment:**
   ```bash
   echo $REDIS_URL
   # Or
   echo $REDIS_HOST $REDIS_PORT
   ```

### Authentication Failed

**Symptoms:**
```
redis.exceptions.AuthenticationError: invalid password
```

**Solution:** Set correct Redis password
```bash
export REDIS_PASSWORD=your_password
# Or in REDIS_URL
export REDIS_URL=redis://:your_password@localhost:6379/0
```

---

## MQTT Issues

### Connection Timeout

**Symptoms:**
```
MQTTHealthCheck: MQTT connection timeout
```

**Solutions:**

1. **Start MQTT broker:**
   ```bash
   # Using Mosquitto
   mosquitto -v

   # Using Docker
   docker run -d -p 1883:1883 eclipse-mosquitto
   ```

2. **Check broker configuration:**
   ```bash
   # Test with mosquitto_pub/sub
   mosquitto_sub -h localhost -t test/#
   mosquitto_pub -h localhost -t test/hello -m "Hello"
   ```

3. **Verify environment:**
   ```bash
   echo $MQTT_HOST $MQTT_PORT
   ```

### Authentication Required

**Symptoms:**
```
Connection refused: not authorized
```

**Solution:** Set MQTT credentials
```bash
export MQTT_USERNAME=your_username
export MQTT_PASSWORD=your_password
```

---

## API Issues

### 401 Unauthorized

**Symptoms:**
```json
{"error": "Missing Authorization Header"}
```

**Solutions:**

1. **Include JWT token:**
   ```bash
   # Get token
   TOKEN=$(curl -X POST http://localhost:5000/api/auth/login \
     -H "Content-Type: application/json" \
     -d '{"username":"admin","password":"admin"}' | jq -r '.access_token')

   # Use token
   curl -H "Authorization: Bearer $TOKEN" http://localhost:5000/api/v1/erp/items
   ```

2. **Check token expiration:** Default is 15 minutes
   ```bash
   # Refresh token
   curl -X POST http://localhost:5000/api/auth/refresh \
     -H "Authorization: Bearer $REFRESH_TOKEN"
   ```

### 404 Not Found

**Symptoms:**
```json
{"error": "Item not found"}
```

**Solutions:**

1. **Verify the resource exists:**
   ```bash
   curl http://localhost:5000/api/v1/erp/items | jq '.[] | .item_id'
   ```

2. **Check API path:** Ensure correct version (`/api/v1/`)

### 500 Internal Server Error

**Symptoms:**
```json
{"error": "Internal server error"}
```

**Solutions:**

1. **Check application logs:**
   ```bash
   # If running with flask
   # Logs appear in terminal

   # If running with gunicorn
   tail -f /var/log/lego-factory/app.log
   ```

2. **Enable debug mode (development only):**
   ```bash
   export FLASK_DEBUG=true
   python -m flask run
   ```

---

## Performance Issues

### Slow API Responses

**Symptoms:** API calls taking > 1 second

**Solutions:**

1. **Check database indexes:**
   ```sql
   -- Find missing indexes
   SELECT relname, seq_scan, idx_scan
   FROM pg_stat_user_tables
   WHERE seq_scan > 0
   ORDER BY seq_scan DESC;
   ```

2. **Enable query logging:**
   ```bash
   export LOG_LEVEL=DEBUG
   ```

3. **Check connection pool:**
   ```bash
   export DB_POOL_SIZE=20
   export DB_MAX_OVERFLOW=40
   ```

### High Memory Usage

**Symptoms:** Application consuming excessive memory

**Solutions:**

1. **Check for memory leaks:**
   ```python
   # Add to code temporarily
   import tracemalloc
   tracemalloc.start()
   # ... run code ...
   snapshot = tracemalloc.take_snapshot()
   top_stats = snapshot.statistics('lineno')[:10]
   ```

2. **Reduce batch sizes:**
   ```bash
   export HISTORIAN_BUFFER_SIZE=500  # Default 1000
   ```

### Scheduling Timeouts

**Symptoms:**
```
SchedulingService: Solver timeout, falling back to heuristic
```

**Solutions:**

1. **Reduce problem size:** Schedule fewer jobs at once

2. **Adjust solver timeout:**
   ```python
   # In code
   solver.parameters.max_time_in_seconds = 60  # Default 30
   ```

3. **Use heuristic mode:** Faster but may not be optimal
   ```python
   result = scheduling_service._schedule_heuristic(jobs, machines, 24)
   ```

---

## Security Issues

### TPM Initialization Failed

**Symptoms:**
```
TPMError: Not connected to TPM
```

**Solutions:**

1. **Use simulation mode (default):**
   ```bash
   export TPM_SIMULATION_MODE=true
   ```

2. **For hardware TPM:**
   ```bash
   # Check TPM device exists
   ls -la /dev/tpm*

   # Install required library
   pip install python-tpm2-pytss

   # Enable hardware mode
   export TPM_SIMULATION_MODE=false
   export TPM_DEVICE_PATH=/dev/tpmrm0
   ```

### JWT Token Invalid

**Symptoms:**
```
jwt.exceptions.InvalidSignatureError: Signature verification failed
```

**Cause:** JWT_SECRET_KEY changed between token creation and validation

**Solutions:**

1. **Invalidate all existing tokens** by changing JWT_SECRET_KEY
2. **Users must re-authenticate** to get new tokens

---

## Test Issues

### Tests Fail with Database Errors

**Symptoms:**
```
sqlalchemy.exc.OperationalError: database "lego_factory_test" does not exist
```

**Solutions:**

1. **Tests use in-memory SQLite by default.** Check `TESTING=true` is set:
   ```bash
   export TESTING=true
   pytest
   ```

2. **Create test database if using PostgreSQL:**
   ```bash
   createdb lego_factory_test
   ```

### Fixtures Not Found

**Symptoms:**
```
fixture 'mock_session' not found
```

**Solution:** Ensure conftest.py is in the test path
```bash
pytest tests/ -v  # Run from project root
```

### Async Test Failures

**Symptoms:**
```
RuntimeError: Event loop is closed
```

**Solution:** Ensure pytest-asyncio is configured
```bash
pip install pytest-asyncio

# In pytest.ini
[pytest]
asyncio_mode = auto
```

---

## Getting Help

If you can't resolve an issue:

1. **Check logs** for detailed error messages
2. **Search existing issues** at https://github.com/anthropics/claude-code/issues
3. **Create a new issue** with:
   - Error message
   - Steps to reproduce
   - Environment details (OS, Python version)
   - Relevant configuration

## Health Check Endpoints

Use these endpoints to diagnose issues:

```bash
# Overall health
curl http://localhost:5000/health

# Detailed health
curl http://localhost:5000/health/ready

# Liveness (is app running?)
curl http://localhost:5000/health/live
```
