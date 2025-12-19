# Black-Box API Testing - Quick Reference

## What This Is

A comprehensive black-box API testing suite that treats the backend as a **closed system** - testing only observable HTTP behavior and external effects. No source code inspection, no internal assumptions.

---

## Prerequisites

### Backend Running
```bash
# Start backend with all services
docker-compose up -d

# Run migrations
docker-compose exec api alembic upgrade head

# Verify health
curl http://localhost:8000/health
```

### Python Testing Dependencies
```bash
pip install requests pytest
```

---

## Running Tests

### Option 1: Automated Test Suite (Recommended)

**Run all tests:**
```bash
python api_black_box_tests.py
```

**Run with verbose output:**
```bash
python api_black_box_tests.py --verbose
```

**Run against remote host:**
```bash
python api_black_box_tests.py --host http://your-api.com:8000
```

### Option 2: Manual curl Commands

All tests are also available as curl commands in `BLACK_BOX_TEST_PLAN.md`.

Quick example:
```bash
# 1. Health check
curl http://localhost:8000/health

# 2. Register user
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "TestPass123!",
    "full_name": "Test User"
  }'

# 3. Login
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "TestPass123!"
  }' | jq -r '.access_token')

# 4. Submit event
curl -X POST http://localhost:8000/api/v1/events \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "event_name": "page_view",
    "event_type": "engagement",
    "payload": {"page": "/home"}
  }'
```

---

## Test Categories

### 1. API Discovery (2 tests)
- Health check endpoint
- OpenAPI schema availability

### 2. Authentication (5 tests)
- User registration
- Duplicate email rejection
- Login success
- Invalid password rejection
- Non-existent user rejection

### 3. Authorization (4 tests)
- Access without token (rejected)
- Invalid token rejection
- Malformed token rejection
- Valid token acceptance

### 4. Event Ingestion (3 tests)
- Single event submission (202 response)
- Missing required field validation
- Empty field validation

### 5. Batch Events (2 tests)
- Batch event submission
- Empty batch rejection

### 6. Async & Observable Effects (3 tests)
- **Event before processing** (processed=false)
- **Event after processing** (processed=true, has timestamp)
- **Metadata attachment** (normalized_at present)

### 7. Event Retrieval (2 tests)
- List user events
- 404 on non-existent event

### 8. Error Handling (2 tests)
- Malformed JSON rejection
- Invalid HTTP method rejection

### 9. Concurrency (2 tests)
- Rapid sequential submissions
- Concurrent requests

### 10. Statistics (1 test)
- Event statistics endpoint

---

## Key Observable Behaviors Being Tested

### Async Task Triggering
**What we're testing**: When an event is submitted, does the response include a task_id and return immediately (202 status)?

```bash
# Submit event - should be <100ms response time
time curl -X POST http://localhost:8000/api/v1/events \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"event_name":"test","event_type":"test"}'

# Response should be 202 Accepted with task_id
# {"event_id": 123, "task_id": "abc-def", "status": "enqueued"}
```

### Processing Observable Effect
**What we're testing**: Does the event eventually get marked as processed?

```bash
# 1. Submit event, get event_id
EVENT_ID=<from submission>

# 2. Check immediately - should be processed=false
curl http://localhost:8000/api/v1/events/$EVENT_ID \
  -H "Authorization: Bearer $TOKEN" | jq '.processed'
# Result: false

# 3. Wait a few seconds
sleep 3

# 4. Check again - should be processed=true
curl http://localhost:8000/api/v1/events/$EVENT_ID \
  -H "Authorization: Bearer $TOKEN" | jq '.processed'
# Result: true

# 5. Should have timestamp and properties
curl http://localhost:8000/api/v1/events/$EVENT_ID \
  -H "Authorization: Bearer $TOKEN" | jq '.processed_at, .properties'
# Result: "2025-12-18T10:30:00", {"original": {...}, "normalized_at": "..."}
```

### Redis-Backed Async Behavior
**What we're testing**: Observable effects only:
- Task ID returned immediately ✓
- Event state transitions from unprocessed to processed ✓
- Processing timestamp and metadata attached ✓
- Response completes before processing ✓

**We do NOT test**:
- Redis internals
- Celery task queue implementation
- Worker logs
- Message broker details

---

## Test Results Interpretation

### SUCCESS: All Green ✓
- All tests passed
- Backend is functioning correctly
- Authentication flows work
- Async event ingestion operational

### FAILURE: Red ✗

#### Event Processing Tests Fail (6.3)
```
✗ Event Not Yet Processed After 5s
```
**Likely cause**: Worker not running or not processing events
**Verify**:
```bash
docker-compose ps
# Should show 'worker' service running

docker-compose logs worker
# Check for errors
```

#### Authorization Tests Fail (3.x)
```
✗ 3.2 Invalid Token Rejection - Expected 401, got 200
```
**Likely cause**: Auth middleware not properly validating tokens
**Verify**: Check JWT validation in auth endpoints

#### Event Ingestion Tests Fail (4.x)
```
✗ 4.1 Submit Single Event - Expected 202, got 500
```
**Likely cause**: Database or API error
**Verify**:
```bash
docker-compose logs api
# Check for errors in API logs
```

---

## Performance Baseline

### Expected Response Times

| Operation | Expected Time | Notes |
|-----------|---------------|-------|
| Event submission (POST) | <100ms | Non-blocking, returns 202 immediately |
| Event retrieval (GET) | <50ms | Simple DB lookup |
| Event processing | 1-5s | Async processing after submission |
| Batch submission (100 events) | <200ms | Still non-blocking |

### Performance Test

```bash
# Measure event submission time
time curl -X POST http://localhost:8000/api/v1/events \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"event_name":"perf_test","event_type":"test"}'

# Should complete in <100ms
```

---

## Monitoring During Testing

### Flower Dashboard (Celery Monitoring)
```bash
# Access at http://localhost:5555
# Shows:
# - Executing tasks
# - Task success/failure rates
# - Worker status
# - Task queue depth
```

### API Logs
```bash
docker-compose logs -f api

# Watch for:
# - Request/response timestamps
# - Authentication attempts
# - Any errors
```

### Worker Logs
```bash
docker-compose logs -f worker

# Watch for:
# - Task execution
# - Event validation
# - Database operations
# - Any processing errors
```

### Database Queries
```bash
# Connect to database
docker-compose exec db psql -U postgres -d pulseboard

# Check events table
SELECT id, event_name, processed, processed_at 
FROM events 
ORDER BY created_at DESC 
LIMIT 5;
```

---

## CI/CD Integration

### Run Tests in CI Pipeline

```yaml
# .github/workflows/api-tests.yml
name: API Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
      redis:
        image: redis:7
    
    steps:
      - uses: actions/checkout@v2
      
      - name: Start backend
        run: docker-compose up -d
      
      - name: Run migrations
        run: docker-compose exec api alembic upgrade head
      
      - name: Run tests
        run: python api_black_box_tests.py --host http://localhost:8000
```

---

## Troubleshooting

### Tests Won't Connect
```bash
# Check backend is running
curl http://localhost:8000/health

# If not running
docker-compose up -d
docker-compose logs api
```

### Authentication Tests Fail
```bash
# Verify auth service is working
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"Pass123!","full_name":"Test"}'
```

### Event Processing Tests Fail
```bash
# Verify worker is running
docker-compose ps worker

# Check worker logs
docker-compose logs worker

# Check Redis connection
docker-compose logs redis
```

### Database Errors
```bash
# Check database status
docker-compose exec db psql -U postgres -d pulseboard -c "SELECT count(*) FROM events;"

# Check migrations
docker-compose exec api alembic current
```

---

## What Tests Do NOT Cover

(Intentionally - these are outside black-box scope)

- Internal data structure implementation details
- Worker retry logic internals
- Database transaction details
- Message queue internals
- Caching mechanisms
- Rate limiting specifics
- Analytics processing (intentionally not implemented)

These are implementation details not observable through the API.

---

## Next Steps

1. **Run the test suite**: `python api_black_box_tests.py`
2. **Review results**: Check which tests pass/fail
3. **Fix failures**: Use logs and curl commands to debug
4. **Monitor**: Use Flower dashboard during testing
5. **Integration**: Add to CI/CD pipeline

---

## Files Reference

| File | Purpose |
|------|---------|
| `BLACK_BOX_TEST_PLAN.md` | Complete test specification with all curl commands |
| `api_black_box_tests.py` | Automated test suite (Python) |
| `black_box_quick_ref.md` | This file - quick reference guide |

---

## Support

For debugging:
- Check API logs: `docker-compose logs api`
- Check worker logs: `docker-compose logs worker`
- Check database: `docker-compose exec db psql -U postgres -d pulseboard`
- Monitor tasks: http://localhost:5555 (Flower)

For specific test failures, refer to the test name in the results summary to find the corresponding detailed test in `BLACK_BOX_TEST_PLAN.md`.
