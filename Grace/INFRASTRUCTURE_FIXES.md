# Infrastructure Fixes - Critical Production Readiness

This document outlines the critical infrastructure fixes implemented to address production readiness gaps.

## ⚠️ CRITICAL FIXES (Post-Initial Implementation)

### Fix 1: Property Timezone Validation ✅
**Problem**: Using UTC for date validation causes failures for physical hotel operations.
- At 2:00 AM Dubai time (Jan 24), UTC is 10:00 PM (Jan 23)
- Guest booking "today" at front desk would be rejected as "past date"

**Solution**: 
- Added `PROPERTY_TIMEZONE` configuration (default: "Asia/Dubai")
- Date validation now uses property's local timezone via `pytz`
- Validation: `datetime.now(property_tz).date()` instead of UTC

### Fix 2: Multi-Worker Connection Pool Calculation ✅
**Problem**: Connection pool size doesn't account for multiple worker processes.
- Each worker creates its own pool: `(pool_size + max_overflow) * num_workers`
- With 4 workers and pool_size=20, max_overflow=10: 120 connections!
- PostgreSQL default max_connections: 100 → **Connection exhaustion**

**Solution**:
- Reduced default pool_size from 20 to 5, max_overflow from 10 to 2
- Added `NUM_WORKERS` and `POSTGRES_MAX_CONNECTIONS` configuration
- Added warning system that alerts when total connections > 80% of PostgreSQL limit
- Formula: `(DB_POOL_SIZE + DB_MAX_OVERFLOW) * NUM_WORKERS < POSTGRES_MAX_CONNECTIONS`

### Fix 3: HMAC Body Stream Consumption ✅
**Problem**: FastAPI request body stream can only be read once.
- HMAC dependency reads body → stream consumed
- Pydantic tries to read body → empty, causing 422 errors

**Solution**:
- HMAC dependency caches body in `request.state.body`
- Created `HMACVerifiedRoute` custom route class
- Route handler uses cached body if available
- Body can be read multiple times without errors

## 1. Database Connection Pooling ✅

### Problem
The original implementation did not configure connection pooling, which would exhaust PostgreSQL connections under load.

### Solution
- **Configured proper connection pooling** with configurable pool settings:
  - `DB_POOL_SIZE`: Number of connections to maintain (default: 20)
  - `DB_MAX_OVERFLOW`: Maximum overflow connections (default: 10)
  - `DB_POOL_TIMEOUT`: Connection acquisition timeout (default: 30s)
  - `DB_POOL_RECYCLE`: Connection recycling interval (default: 3600s)
  - `DB_POOL_PRE_PING`: Verify connections before use (default: True)

- **Environment-aware pooling**:
  - `QueuePool` for standard containers (connection pooling)
  - `NullPool` for serverless environments (no pooling, new connection per request)

- **Connection pool monitoring**:
  - Added `get_pool_status()` function for monitoring
  - Health check endpoint (`/health`) exposes pool status
  - Startup event verifies pool initialization

### Files Changed
- `app/core/database.py`: Added pool configuration and monitoring
- `app/core/config.py`: Added pool configuration settings
- `app/main.py`: Added health check endpoint

## 2. HMAC Signature Validation ✅

### Problem
Simple API key comparison is vulnerable to replay attacks and doesn't verify request integrity.

### Solution
- **Replaced API key auth with HMAC-SHA256 signature validation**:
  - Signature computed as: `HMAC-SHA256(secret, timestamp + body)`
  - Timestamp included in signature prevents tampering
  - Constant-time comparison prevents timing attacks

- **Replay attack prevention**:
  - Timestamp validation (rejects requests older than 5 minutes)
  - Request body included in signature calculation

- **Implementation**:
  - `app/core/hmac_auth.py`: HMAC verification dependency
  - Reads request body, verifies signature, returns parsed JSON
  - Headers required: `X-Signature`, `X-Timestamp`

### Files Changed
- `app/core/hmac_auth.py`: New HMAC authentication module
- `app/main.py`: Updated webhook endpoint to use HMAC
- `app/core/config.py`: Added `HMAC_SECRET` configuration

## 3. Timezone-Aware Date Validation ✅

### Problem
Date validation used `date.today()` which is timezone-dependent and can cause issues across different server locations.

### Solution
- **UTC-based date validation**:
  - Uses `datetime.now(timezone.utc).date()` for consistent validation
  - Prevents timezone-related validation failures
  - Clear error messages include UTC date for debugging

### Files Changed
- `app/models.py`: Updated `validate_check_in_date` to use UTC

## 4. Integration Tests ✅

### Problem
Tests used mocked database sessions, not testing actual database interactions.

### Solution
- **Real database integration tests**:
  - `tests/conftest.py`: Test database setup with real PostgreSQL
  - `tests/test_integration_rates.py`: Database integration tests for rates endpoint
  - `tests/test_integration_webhook.py`: HMAC signature validation tests
  - Uses `NullPool` for test isolation
  - Automatic table creation/cleanup per test

- **Test fixtures**:
  - `db_session`: Real database session
  - `test_client`: FastAPI test client with database override
  - `sample_rate`: Pre-populated test data

### Files Changed
- `tests/conftest.py`: Test configuration and fixtures
- `tests/test_integration_rates.py`: Rate endpoint integration tests
- `tests/test_integration_webhook.py`: Webhook HMAC tests
- `pytest.ini`: Updated test configuration

## 5. Connection Pool Monitoring ✅

### Problem
No visibility into connection pool status for monitoring and debugging.

### Solution
- **Pool status endpoint**:
  - `/health` endpoint returns pool status
  - Includes pool type, size, checked out connections, overflow
  - Startup event stores initial pool status

- **Monitoring function**:
  - `get_pool_status()` returns detailed pool metrics
  - Supports both QueuePool and NullPool

### Files Changed
- `app/core/database.py`: Added `get_pool_status()` function
- `app/main.py`: Added `/health` endpoint

## Environment Variables

### Required
```bash
HMAC_SECRET=your_hmac_secret_key_here
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/dbname
PROPERTY_TIMEZONE=Asia/Dubai  # IANA timezone name for the hotel location
```

### Critical Configuration
```bash
# Connection Pool Settings (per worker!)
# Total connections = (DB_POOL_SIZE + DB_MAX_OVERFLOW) * NUM_WORKERS
# Example: pool_size=5, max_overflow=2, 4 workers = (5+2)*4 = 28 connections
DB_POOL_SIZE=5  # Reduced from 20 for multi-worker safety
DB_MAX_OVERFLOW=2  # Reduced from 10
NUM_WORKERS=4  # Number of Uvicorn/Gunicorn workers
POSTGRES_MAX_CONNECTIONS=100  # Your PostgreSQL max_connections setting
```

### Optional (with defaults)
```bash
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=3600
DB_POOL_PRE_PING=true
IS_SERVERLESS=false
```

## Testing

### Unit Tests (Mocked)
- `test_rates.py`: Unit tests with mocked database
- `test_webhook.py`: Unit tests with mocked services

### Integration Tests (Real Database)
```bash
# Set up test database
export TEST_DATABASE_URL=postgresql+asyncpg://test:test@localhost:5432/grace_test_db

# Run integration tests
pytest tests/
```

## Deployment Checklist

### Critical Steps
- [ ] Set `PROPERTY_TIMEZONE` to hotel's IANA timezone (e.g., "Asia/Dubai")
- [ ] Set `NUM_WORKERS` to match your Uvicorn/Gunicorn worker count
- [ ] Calculate: `(DB_POOL_SIZE + DB_MAX_OVERFLOW) * NUM_WORKERS < POSTGRES_MAX_CONNECTIONS`
- [ ] Set `POSTGRES_MAX_CONNECTIONS` to your actual PostgreSQL setting
- [ ] Verify startup warnings don't indicate connection exhaustion risk

### Standard Steps
- [ ] Set `HMAC_SECRET` environment variable
- [ ] Configure `DATABASE_URL` with production credentials
- [ ] Set `IS_SERVERLESS=true` if deploying to serverless platform
- [ ] Monitor `/health` endpoint for pool status
- [ ] Set up database connection monitoring/alerts

### Connection Pool Calculation Example
```python
# For 4 workers with PostgreSQL max_connections=100:
# Safe calculation: (5 + 2) * 4 = 28 connections (well under 100)
# Leave room for: admin connections, other apps, maintenance

# If you need more connections per worker:
# Option 1: Reduce NUM_WORKERS
# Option 2: Use PgBouncer for connection pooling
# Option 3: Increase PostgreSQL max_connections (with caution)
```

## Security Notes

1. **HMAC Secret**: Must be kept secure and never exposed
2. **Connection Pooling**: Prevents connection exhaustion attacks
3. **Timestamp Validation**: Prevents replay attacks (5-minute window)
4. **Constant-Time Comparison**: Prevents timing attacks on signature verification

## Performance Considerations

- **Pool Size**: Start with 20, adjust based on load
- **Max Overflow**: Allows burst capacity beyond pool size
- **Pool Recycle**: Prevents stale connections (1 hour default)
- **Pre-Ping**: Verifies connections before use (prevents errors)
