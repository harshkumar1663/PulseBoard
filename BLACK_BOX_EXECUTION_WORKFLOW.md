# Black-Box API Testing - Execution Workflow

## Overview

This guide provides step-by-step instructions for executing the complete black-box API testing suite. It assumes you have the PulseBoard backend running locally.

---

## Pre-Test Checklist

- [ ] Backend is running: `docker-compose ps` shows all services up
- [ ] API is responsive: `curl http://localhost:8000/health` returns 200
- [ ] Database migrations applied: `docker-compose exec api alembic current` shows latest version
- [ ] Redis is running: `docker-compose logs redis` shows no errors
- [ ] Worker is running: `docker-compose logs worker` shows "ready to accept tasks"
- [ ] Python 3.8+ installed
- [ ] `requests` library installed: `pip install requests`

---

## Testing Flow

### Phase 1: Infrastructure Verification (5 minutes)

**Goal**: Confirm backend and all services are operational

**Steps**:
```bash
# 1. Check Docker services
docker-compose ps
# Expected: All containers RUNNING

# 2. Health check
curl http://localhost:8000/health
# Expected: {"status": "healthy", "service": "PulseBoard", ...}

# 3. Verify database
docker-compose exec db psql -U postgres -d pulseboard -c "SELECT version();"

# 4. Verify Redis
docker-compose exec redis redis-cli ping
# Expected: PONG

# 5. Verify Flower (monitoring)
curl http://localhost:5555
# Expected: 200 OK
```

**Pass Criteria**: All 5 checks succeed

---

### Phase 2: Authentication Testing (10 minutes)

**Goal**: Verify user registration, login, and token-based authentication work

**Steps**:
```bash
# Run authentication tests
python api_black_box_tests.py --verbose | grep -E "^.*Section 2|^.*PASS|^.*FAIL"

# Expected output:
# Section 2: Authentication
# ✓ 2.1 Register User - PASS
# ✓ 2.3 Login Success - PASS
# ✗ 2.4 Invalid Password - PASS (correctly rejects)
```

**Manual verification** (optional):
```bash
# 1. Register user
TOKEN_RESPONSE=$(curl -s -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "qa_test_'$(date +%s)'@example.com",
    "password": "TestPass123!",
    "full_name": "QA Test User"
  }')

# 2. Extract user info
USER_ID=$(echo $TOKEN_RESPONSE | jq -r '.id')
USER_EMAIL=$(echo $TOKEN_RESPONSE | jq -r '.email')

echo "Created user: ID=$USER_ID, Email=$USER_EMAIL"

# 3. Login
LOGIN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"$USER_EMAIL\", \"password\": \"TestPass123!\"}")

TOKEN=$(echo $LOGIN | jq -r '.access_token')
echo "Received token: ${TOKEN:0:20}..."
```

**Pass Criteria**:
- 2.1 Register User: 201 Created
- 2.3 Login Success: 200 OK with access_token
- 2.4 Invalid Password: 401 Unauthorized
- All auth section tests show PASS

---

### Phase 3: Authorization Testing (5 minutes)

**Goal**: Verify JWT token validation and access control

**Steps**:
```bash
# Run authorization tests
python api_black_box_tests.py --verbose | grep -E "^.*Section 3|^.*PASS|^.*FAIL"

# Expected output:
# Section 3: Authorization
# ✓ 3.1 No Token Access - PASS (correctly rejected)
# ✓ 3.2 Invalid Token - PASS (correctly rejected)
# ✓ 3.3 Malformed Token - PASS (correctly rejected)
# ✓ 3.4 Valid Token Access - PASS
```

**Manual verification** (optional):
```bash
# Test without token (should fail)
curl -i http://localhost:8000/api/v1/events

# Test with invalid token (should fail)
curl -i http://localhost:8000/api/v1/events \
  -H "Authorization: Bearer invalid_token"

# Test with valid token (should succeed)
curl -i http://localhost:8000/api/v1/events \
  -H "Authorization: Bearer $TOKEN"
```

**Pass Criteria**: All authorization tests show PASS (including rejections)

---

### Phase 4: Event Ingestion Testing (10 minutes)

**Goal**: Verify single event submission, validation, and async task triggering

**Steps**:
```bash
# Run event ingestion tests
python api_black_box_tests.py --verbose | grep -E "^.*Section 4|^.*PASS|^.*FAIL"

# Expected output:
# Section 4: Event Ingestion
# ✓ 4.1 Submit Single Event - PASS
# ✓ 4.2 Missing Required Field - PASS (correctly rejected)
# ✓ 4.3 Empty Event Name - PASS (correctly rejected)
```

**Manual verification** (recommended):
```bash
# Submit event and capture response
EVENT=$(curl -s -X POST http://localhost:8000/api/v1/events \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "event_name": "test_page_view",
    "event_type": "engagement",
    "source": "web",
    "payload": {
      "page": "/home",
      "duration": 45
    }
  }')

EVENT_ID=$(echo $EVENT | jq -r '.event_id')
TASK_ID=$(echo $EVENT | jq -r '.task_id')
STATUS=$(echo $EVENT | jq -r '.status')

echo "Event created:"
echo "  Event ID: $EVENT_ID"
echo "  Task ID: $TASK_ID"
echo "  Status: $STATUS"
echo "  Response time: Check it was < 100ms"

# Save for next phase
export EVENT_ID TASK_ID TOKEN USER_EMAIL
```

**Pass Criteria**:
- 4.1: Returns 202 Accepted with event_id and task_id
- 4.2: Returns 422 (missing event_type)
- 4.3: Returns 422 (empty event_name)
- Response time < 100ms

---

### Phase 5: Async Processing & Observable Effects (15 minutes)

**Goal**: Verify async task execution and observable state changes

**Steps**:

**Step 5.1: Check event immediately after submission**
```bash
# Check within 1 second - likely not processed yet
curl -s http://localhost:8000/api/v1/events/$EVENT_ID \
  -H "Authorization: Bearer $TOKEN" | jq '
  {
    id: .id,
    event_name: .event_name,
    processed: .processed,
    processed_at: .processed_at
  }'

# Expected output:
# {
#   "id": <event_id>,
#   "event_name": "test_page_view",
#   "processed": false,
#   "processed_at": null
# }
```

**Step 5.2: Monitor async processing**
```bash
# Open new terminal and watch worker logs
docker-compose logs -f worker | grep -i "process_event\|completed\|error"

# You should see:
# Starting process_event task for event <ID>
# Validating payload...
# Persisting to database...
# Task completed successfully
```

**Step 5.3: Poll for completion**
```bash
#!/bin/bash
# Wait for event to be processed (max 30 seconds)
TOKEN=$1
EVENT_ID=$2

for i in {1..30}; do
  PROCESSED=$(curl -s http://localhost:8000/api/v1/events/$EVENT_ID \
    -H "Authorization: Bearer $TOKEN" | jq -r '.processed')
  
  if [ "$PROCESSED" == "true" ]; then
    echo "✓ Event processed after ${i}s"
    curl -s http://localhost:8000/api/v1/events/$EVENT_ID \
      -H "Authorization: Bearer $TOKEN" | jq '
      {
        id: .id,
        event_name: .event_name,
        processed: .processed,
        processed_at: .processed_at,
        properties: .properties | keys
      }'
    exit 0
  fi
  
  echo "Waiting... ($i/30s)"
  sleep 1
done

echo "✗ Event not processed within 30s"
exit 1
```

Run it:
```bash
# Save script as wait_event.sh
chmod +x wait_event.sh
./wait_event.sh $TOKEN $EVENT_ID
```

**Expected output** (after 3-5 seconds):
```
✓ Event processed after 3s
{
  "id": <event_id>,
  "event_name": "test_page_view",
  "processed": true,
  "processed_at": "2025-12-18T10:35:42.123456",
  "properties": ["original", "normalized_at", "page", "duration"]
}
```

**Step 5.4: Verify metadata attachment**
```bash
curl -s http://localhost:8000/api/v1/events/$EVENT_ID \
  -H "Authorization: Bearer $TOKEN" | jq '.properties'

# Expected:
# {
#   "original": {
#     "page": "/home",
#     "duration": 45
#   },
#   "normalized_at": "2025-12-18T10:35:42.123456",
#   "page": "/home",
#   "duration": 45.0
# }
```

**Step 5.5: Monitor with Flower**
```bash
# Open browser to http://localhost:5555
# You should see:
# - Task: process_event
# - Status: SUCCESS
# - Runtime: < 2 seconds
# - Worker: worker@...
```

**Pass Criteria**:
- Event created with processed=false
- Event transitions to processed=true within 5 seconds
- processed_at has ISO timestamp
- properties contains original payload + normalized_at
- Worker logs show successful processing

---

### Phase 6: Batch Events Testing (10 minutes)

**Goal**: Verify batch event submission and atomic processing

**Steps**:
```bash
# Run batch tests
python api_black_box_tests.py --verbose | grep -E "^.*Section 5|^.*PASS|^.*FAIL"

# Expected:
# Section 5: Batch Events
# ✓ 5.1 Batch Events - PASS
# ✓ 5.2 Empty Batch - PASS (correctly rejected)
```

**Manual verification**:
```bash
# Submit batch of 3 events
BATCH=$(curl -s -X POST http://localhost:8000/api/v1/events/batch \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "events": [
      {"event_name": "batch_1", "event_type": "test", "payload": {"order": 1}},
      {"event_name": "batch_2", "event_type": "test", "payload": {"order": 2}},
      {"event_name": "batch_3", "event_type": "test", "payload": {"order": 3}}
    ]
  }')

EVENT_IDS=$(echo $BATCH | jq -r '.event_ids[]')
TASK_ID=$(echo $BATCH | jq -r '.task_id')

echo "Batch submitted:"
echo "$BATCH" | jq '
  {
    event_count: .event_count,
    event_ids: .event_ids,
    status: .status
  }'

# Verify all events created
echo ""
echo "Verifying all 3 events created:"
for ID in $EVENT_IDS; do
  curl -s http://localhost:8000/api/v1/events/$ID \
    -H "Authorization: Bearer $TOKEN" | jq '.id, .event_name'
done

# Wait for processing
echo ""
echo "Waiting 5 seconds for processing..."
sleep 5

# Verify all processed
echo "Verifying all 3 events processed:"
for ID in $EVENT_IDS; do
  curl -s http://localhost:8000/api/v1/events/$ID \
    -H "Authorization: Bearer $TOKEN" | jq '{id: .id, processed: .processed, processed_at: .processed_at}'
done
```

**Pass Criteria**:
- Batch returns 202 with 3 event_ids and task_id
- All 3 events retrieve successfully
- All 3 events have processed=true after 5 seconds

---

### Phase 7: Event Retrieval Testing (5 minutes)

**Goal**: Verify event listing, filtering, and retrieval

**Steps**:
```bash
# Run retrieval tests
python api_black_box_tests.py --verbose | grep -E "^.*Section 8|^.*PASS|^.*FAIL"

# Expected:
# Section 8: Event Retrieval
# ✓ 8.1 List Events - PASS
# ✓ 8.3 Get by ID - PASS
# ✓ 8.4 Non-existent Event - PASS (correctly returns 404)
```

**Manual verification**:
```bash
# List all events for user
curl -s "http://localhost:8000/api/v1/events?limit=10&offset=0" \
  -H "Authorization: Bearer $TOKEN" | jq '
  {
    count: length,
    events: [.[] | {id: .id, event_name: .event_name, processed: .processed}]
  }'

# Get specific event
curl -s http://localhost:8000/api/v1/events/$EVENT_ID \
  -H "Authorization: Bearer $TOKEN" | jq '
  {
    id: .id,
    event_name: .event_name,
    processed: .processed,
    properties: (.properties | keys)
  }'

# Verify 404 on non-existent
curl -i http://localhost:8000/api/v1/events/999999 \
  -H "Authorization: Bearer $TOKEN" | head -1
```

**Pass Criteria**:
- List returns 200 with array of events
- Get by ID returns 200 with event details
- Non-existent returns 404

---

### Phase 8: Error Handling Testing (5 minutes)

**Goal**: Verify proper error responses

**Steps**:
```bash
# Run error handling tests
python api_black_box_tests.py --verbose | grep -E "^.*Section 9|^.*PASS|^.*FAIL"

# Expected:
# Section 9: Error Handling
# ✓ 9.1 Malformed JSON - PASS (rejected with 400)
# ✓ 9.3 Method Not Allowed - PASS (rejected with 405)
```

**Manual verification**:
```bash
# Test malformed JSON
curl -i -X POST http://localhost:8000/api/v1/events \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{invalid json}' | head -5

# Test invalid HTTP method
curl -i -X DELETE http://localhost:8000/api/v1/events \
  -H "Authorization: Bearer $TOKEN" | head -5

# Test missing Content-Type
curl -i -X POST http://localhost:8000/api/v1/events \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"event_name":"test"}' | head -5
```

**Pass Criteria**:
- All error cases return 4xx status codes
- Error responses include descriptive messages

---

### Phase 9: Concurrency Testing (10 minutes)

**Goal**: Verify system handles concurrent requests

**Steps**:
```bash
# Run concurrency tests
python api_black_box_tests.py --verbose | grep -E "^.*Section 10|^.*PASS|^.*FAIL"

# Expected:
# Section 10: Concurrency
# ✓ 10.1 Rapid Submission - PASS (5/5 succeeded)
# ✓ 10.2 Concurrent Requests - PASS (5/5 succeeded)
```

**Manual verification** - Rapid sequential submission:
```bash
echo "Submitting 10 events rapidly..."
for i in {1..10}; do
  curl -s -X POST http://localhost:8000/api/v1/events \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"event_name\": \"rapid_$i\", \"event_type\": \"test\"}" | \
    jq '.event_id' &
done

wait
echo "✓ All 10 submitted"
```

**Manual verification** - Concurrent requests:
```bash
echo "Submitting 10 events concurrently..."
for i in {1..10}; do
  curl -s -X POST http://localhost:8000/api/v1/events \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"event_name\": \"concurrent_$i\", \"event_type\": \"test\"}" | \
    jq '.event_id' &
done

wait
echo "✓ All 10 completed"
```

**Pass Criteria**:
- All rapid requests succeed (10/10)
- All concurrent requests succeed (10/10)
- No duplicate event_ids
- System remains responsive

---

### Phase 10: Statistics Testing (5 minutes)

**Goal**: Verify event statistics endpoint

**Steps**:
```bash
# Run stats tests
python api_black_box_tests.py --verbose | grep -E "^.*Section 11|^.*PASS|^.*FAIL"

# Expected:
# Section 11: Statistics
# ✓ 11.1 Event Statistics - PASS
```

**Manual verification**:
```bash
# Get event statistics
curl -s http://localhost:8000/api/v1/events/status/unprocessed \
  -H "Authorization: Bearer $TOKEN" | jq '
  {
    total_count: .total_count,
    unprocessed_count: .unprocessed_count,
    processed_count: (.total_count - .unprocessed_count)
  }'

# Expected output:
# {
#   "total_count": 20,
#   "unprocessed_count": 0,
#   "processed_count": 20
# }
```

**Pass Criteria**:
- Stats endpoint returns 200 OK
- Counts are accurate (by now all should be processed)

---

## Complete Test Execution (One Command)

Run all tests automatically:

```bash
python api_black_box_tests.py --verbose
```

This will:
1. Register a new test user
2. Login and get access token
3. Run all 42 tests across 10 sections
4. Display detailed pass/fail results
5. Print summary statistics

**Expected output**:
```
======================================================
Test Results Summary
======================================================

✓ Passed: 42/42
✗ Failed: 0/42
✗ Errors: 0/42

Success Rate: 100.0%

✓ All tests passed!
```

---

## Debugging Failed Tests

### If tests fail, follow this workflow:

**Step 1: Check backend health**
```bash
curl http://localhost:8000/health
docker-compose ps
docker-compose logs api | tail -20
```

**Step 2: Check specific service**

If authentication fails:
```bash
docker-compose logs api | grep -i "auth\|token"
```

If event ingestion fails:
```bash
docker-compose logs api | grep -i "event\|ingestion"
docker-compose logs worker | grep -i "process_event\|error"
```

If processing doesn't complete:
```bash
docker-compose logs worker | tail -50
docker-compose logs -f worker | grep -i "process_event"
```

**Step 3: Check database state**
```bash
docker-compose exec db psql -U postgres -d pulseboard << EOF
SELECT count(*) as total_events FROM events;
SELECT count(*) as processed FROM events WHERE processed = true;
SELECT id, event_name, processed, processed_at FROM events ORDER BY created_at DESC LIMIT 5;
EOF
```

**Step 4: Check Redis**
```bash
docker-compose exec redis redis-cli
> INFO stats
> KEYS *
> QUIT
```

**Step 5: Monitor Flower**
```
Open: http://localhost:5555
Look for:
- Task failures
- Worker disconnections
- Long task runtimes
```

---

## Performance Validation

After all tests pass, verify performance baseline:

```bash
# Measure event submission time (should be <100ms)
time curl -X POST http://localhost:8000/api/v1/events \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"event_name":"perf_test","event_type":"test"}' > /dev/null

# Measure event retrieval time (should be <50ms)
time curl http://localhost:8000/api/v1/events \
  -H "Authorization: Bearer $TOKEN" > /dev/null

# Measure batch submission (100 events, should be <200ms)
time curl -X POST http://localhost:8000/api/v1/events/batch \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d @batch_100_events.json > /dev/null
```

---

## CI/CD Integration

To integrate into your CI/CD pipeline:

```yaml
# .github/workflows/api-tests.yml
name: API Black-Box Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Start services
        run: |
          docker-compose up -d
          docker-compose exec api alembic upgrade head
          sleep 5
      
      - name: Run tests
        run: |
          python api_black_box_tests.py --verbose
      
      - name: Collect logs on failure
        if: failure()
        run: |
          docker-compose logs api > api_logs.txt
          docker-compose logs worker > worker_logs.txt
      
      - name: Upload logs
        if: failure()
        uses: actions/upload-artifact@v2
        with:
          name: service-logs
          path: "*.txt"
```

---

## Summary

**Total Time**: ~90 minutes for complete test suite

**Key Validation Points**:
1. ✓ API is accessible and healthy
2. ✓ Authentication/authorization working
3. ✓ Events ingested and async task triggered
4. ✓ Async processing completes with observable effects
5. ✓ Events retrievable and filterable
6. ✓ Error handling proper
7. ✓ Concurrency handled correctly
8. ✓ Statistics accurate

**Success Criteria**: All 42 tests pass with 100% success rate

**Next Steps**:
- Deploy to staging environment
- Run integration tests with frontend
- Performance and load testing
- Production deployment

---

## Files Reference

- `BLACK_BOX_TEST_PLAN.md` - Complete test specification
- `api_black_box_tests.py` - Automated test suite
- `BLACK_BOX_QUICK_REF.md` - Quick reference guide
- `PulseBoard_Black_Box_Tests.postman_collection.json` - Postman collection
- `BLACK_BOX_EXECUTION_WORKFLOW.md` - This file
