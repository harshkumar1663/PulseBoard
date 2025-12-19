# Black-Box API Testing Plan - PulseBoard Event Ingestion System

**Test Environment**: http://localhost:8000  
**API Docs**: http://localhost:8000/docs  
**Testing Date**: December 18, 2025

---

## Test Scope

Testing the following as a **black-box service**:
- Authentication and authorization flows
- Event ingestion endpoints
- Async task triggering and observable effects
- Error handling and validation
- Batch event processing

**Constraints**:
- No source code inspection
- No internal implementation details assumed
- Only external API behavior verified
- Observable effects only (task IDs, response timing, final state)

---

## Test Environment Setup

### Prerequisites

1. Backend running:
```bash
docker-compose up -d
docker-compose exec api alembic upgrade head
```

2. Verify backend is accessible:
```bash
curl http://localhost:8000/health
# Expected: {"status": "healthy", "service": "PulseBoard", "version": "1.0.0"}
```

3. Set environment variables for tests:
```bash
export API_URL="http://localhost:8000"
export API_DOCS_URL="http://localhost:8000/docs"
```

---

## Section 1: API Discovery & Schema Validation

### Test 1.1: Verify API Documentation Available
**Purpose**: Confirm Swagger/OpenAPI is accessible  
**Method**: GET  
**Endpoint**: `/docs`  
**Headers**: None  
**Body**: None  

```bash
curl -i http://localhost:8000/docs
```

**Expected Response**:
- Status: 200 OK
- Content-Type: text/html
- Body contains: Swagger UI or OpenAPI documentation

**Pass Criteria**: Status 200 and HTML content returned

---

### Test 1.2: Get OpenAPI Schema
**Purpose**: Verify API schema is discoverable  
**Method**: GET  
**Endpoint**: `/openapi.json`  
**Headers**: None  
**Body**: None  

```bash
curl -s http://localhost:8000/openapi.json | jq .
```

**Expected Response**:
- Status: 200 OK
- JSON with paths, components, schemas
- Must contain: `/api/auth/register`, `/api/auth/login`, `/api/v1/events`

**Pass Criteria**: 
- Valid OpenAPI schema returned
- Authentication endpoints present
- Event endpoints present

---

### Test 1.3: Health Check Endpoint
**Purpose**: Verify service is alive  
**Method**: GET  
**Endpoint**: `/health`  
**Headers**: None  
**Body**: None  

```bash
curl -s http://localhost:8000/health | jq .
```

**Expected Response**:
- Status: 200 OK
- JSON:
```json
{
  "status": "healthy",
  "service": "PulseBoard",
  "version": "1.0.0"
}
```

**Pass Criteria**: Status 200, status="healthy", service name present

---

## Section 2: Authentication Flow

### Test 2.1: User Registration
**Purpose**: Create test user for subsequent tests  
**Method**: POST  
**Endpoint**: `/api/auth/register`  
**Headers**: `Content-Type: application/json`  
**Body**:
```json
{
  "email": "testuser@example.com",
  "password": "TestPassword123!",
  "full_name": "Test User"
}
```

```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "testuser@example.com",
    "password": "TestPassword123!",
    "full_name": "Test User"
  }' | jq .
```

**Expected Response**:
- Status: 201 Created
- JSON with user fields:
```json
{
  "id": <integer>,
  "email": "testuser@example.com",
  "full_name": "Test User",
  "is_active": true,
  "created_at": "<ISO timestamp>"
}
```

**Pass Criteria**:
- Status 201
- id is integer > 0
- email matches input
- is_active = true

**Note**: Save the `id` for later tests

---

### Test 2.2: User Registration - Duplicate Email
**Purpose**: Verify duplicate email rejection  
**Method**: POST  
**Endpoint**: `/api/auth/register`  
**Headers**: `Content-Type: application/json`  
**Body**: Same email as Test 2.1

```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "testuser@example.com",
    "password": "DifferentPassword456!",
    "full_name": "Another User"
  }' | jq .
```

**Expected Response**:
- Status: 400 Bad Request
- JSON with error detail

**Pass Criteria**: Status 400 or 409 (conflict)

---

### Test 2.3: User Login - Success
**Purpose**: Obtain valid JWT token  
**Method**: POST  
**Endpoint**: `/api/auth/login`  
**Headers**: `Content-Type: application/json`  
**Body**:
```json
{
  "email": "testuser@example.com",
  "password": "TestPassword123!"
}
```

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "testuser@example.com",
    "password": "TestPassword123!"
  }' | jq .
```

**Expected Response**:
- Status: 200 OK
- JSON:
```json
{
  "access_token": "<JWT string>",
  "refresh_token": "<JWT string>",
  "token_type": "bearer"
}
```

**Pass Criteria**:
- Status 200
- access_token is non-empty string (JWT format: `xxx.yyy.zzz`)
- refresh_token is non-empty string
- token_type = "bearer"

**Note**: Save `access_token` and `refresh_token` for subsequent tests

---

### Test 2.4: User Login - Invalid Credentials
**Purpose**: Verify authentication failure  
**Method**: POST  
**Endpoint**: `/api/auth/login`  
**Headers**: `Content-Type: application/json`  
**Body**:
```json
{
  "email": "testuser@example.com",
  "password": "WrongPassword"
}
```

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "testuser@example.com",
    "password": "WrongPassword"
  }' | jq .
```

**Expected Response**:
- Status: 401 Unauthorized
- JSON with error detail

**Pass Criteria**: Status 401

---

### Test 2.5: User Login - Non-existent Email
**Purpose**: Verify email validation  
**Method**: POST  
**Endpoint**: `/api/auth/login`  
**Headers**: `Content-Type: application/json`  
**Body**:
```json
{
  "email": "nonexistent@example.com",
  "password": "AnyPassword"
}
```

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "nonexistent@example.com",
    "password": "AnyPassword"
  }' | jq .
```

**Expected Response**:
- Status: 401 Unauthorized

**Pass Criteria**: Status 401

---

## Section 3: Authorization Tests

### Test 3.1: Access Protected Endpoint Without Token
**Purpose**: Verify authentication required  
**Method**: GET  
**Endpoint**: `/api/v1/events`  
**Headers**: None  
**Body**: None  

```bash
curl -i http://localhost:8000/api/v1/events
```

**Expected Response**:
- Status: 403 Forbidden or 401 Unauthorized
- JSON with error (or empty body)

**Pass Criteria**: Status 401 or 403 (unauthenticated rejection)

---

### Test 3.2: Access Protected Endpoint With Invalid Token
**Purpose**: Verify token validation  
**Method**: GET  
**Endpoint**: `/api/v1/events`  
**Headers**: `Authorization: Bearer invalid_token_string`  
**Body**: None  

```bash
curl -i http://localhost:8000/api/v1/events \
  -H "Authorization: Bearer invalid_token_string"
```

**Expected Response**:
- Status: 401 Unauthorized

**Pass Criteria**: Status 401

---

### Test 3.3: Access Protected Endpoint With Malformed Token
**Purpose**: Verify token format validation  
**Method**: GET  
**Endpoint**: `/api/v1/events`  
**Headers**: `Authorization: Bearer abc`  
**Body**: None  

```bash
curl -i http://localhost:8000/api/v1/events \
  -H "Authorization: Bearer abc"
```

**Expected Response**:
- Status: 401 Unauthorized

**Pass Criteria**: Status 401

---

### Test 3.4: Access Protected Endpoint With Valid Token
**Purpose**: Verify token acceptance (baseline for authenticated requests)  
**Method**: GET  
**Endpoint**: `/api/v1/events`  
**Headers**: `Authorization: Bearer <valid_access_token>`  
**Body**: None  

```bash
TOKEN="<access_token_from_Test_2.3>"
curl -s http://localhost:8000/api/v1/events \
  -H "Authorization: Bearer $TOKEN" | jq .
```

**Expected Response**:
- Status: 200 OK
- JSON array (possibly empty): `[]`

**Pass Criteria**: Status 200, returns array

---

## Section 4: Event Ingestion - Basic Flow

### Test 4.1: Submit Single Event - Valid Payload
**Purpose**: Test basic event ingestion  
**Method**: POST  
**Endpoint**: `/api/v1/events`  
**Headers**: 
```
Authorization: Bearer <valid_access_token>
Content-Type: application/json
```
**Body**:
```json
{
  "event_name": "page_view",
  "event_type": "engagement",
  "source": "web",
  "session_id": "sess_test_001",
  "payload": {
    "page": "/home",
    "duration": 45,
    "scroll_depth": 75
  }
}
```

```bash
TOKEN="<access_token>"
curl -X POST http://localhost:8000/api/v1/events \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "event_name": "page_view",
    "event_type": "engagement",
    "source": "web",
    "session_id": "sess_test_001",
    "payload": {
      "page": "/home",
      "duration": 45,
      "scroll_depth": 75
    }
  }' | jq .
```

**Expected Response**:
- Status: 202 Accepted
- JSON:
```json
{
  "event_id": <integer>,
  "task_id": "<UUID or string>",
  "status": "enqueued",
  "message": "Event enqueued for processing"
}
```

**Pass Criteria**:
- Status 202 (not 200 or 201, but 202 - async accepted)
- event_id is positive integer
- task_id is non-empty string (UUID format expected)
- status = "enqueued"

**Note**: Save `event_id` and `task_id` for verification tests

---

### Test 4.2: Submit Single Event - Missing Required Field
**Purpose**: Validate required field enforcement  
**Method**: POST  
**Endpoint**: `/api/v1/events`  
**Headers**: `Authorization: Bearer <token>`, `Content-Type: application/json`  
**Body** (missing event_type):
```json
{
  "event_name": "page_view",
  "source": "web"
}
```

```bash
TOKEN="<access_token>"
curl -X POST http://localhost:8000/api/v1/events \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "event_name": "page_view",
    "source": "web"
  }' | jq .
```

**Expected Response**:
- Status: 422 Unprocessable Entity or 400 Bad Request
- JSON with validation error detail

**Pass Criteria**: Status 422 or 400

---

### Test 4.3: Submit Single Event - Empty Event Name
**Purpose**: Validate field constraints  
**Method**: POST  
**Endpoint**: `/api/v1/events`  
**Headers**: `Authorization: Bearer <token>`, `Content-Type: application/json`  
**Body**:
```json
{
  "event_name": "",
  "event_type": "engagement"
}
```

```bash
TOKEN="<access_token>"
curl -X POST http://localhost:8000/api/v1/events \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "event_name": "",
    "event_type": "engagement"
  }' | jq .
```

**Expected Response**:
- Status: 422 Unprocessable Entity

**Pass Criteria**: Status 422

---

### Test 4.4: Submit Single Event - Oversized Payload
**Purpose**: Verify payload size limits  
**Method**: POST  
**Endpoint**: `/api/v1/events`  
**Headers**: `Authorization: Bearer <token>`, `Content-Type: application/json`  
**Body** (payload > 1MB):

```bash
TOKEN="<access_token>"

# Create large payload (1.5MB)
python3 << 'EOF'
import requests
import json

token = "$TOKEN"
large_payload = {"x": "y" * (1024 * 1024 + 512 * 1024)}

response = requests.post(
    "http://localhost:8000/api/v1/events",
    headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    },
    json={
        "event_name": "test",
        "event_type": "test",
        "payload": large_payload
    }
)

print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")
EOF
```

**Expected Response**:
- Status: 400 Bad Request or 422 Unprocessable Entity
- Error message about payload size

**Pass Criteria**: Status >= 400

---

## Section 5: Event Ingestion - Batch Processing

### Test 5.1: Submit Batch Events - Valid
**Purpose**: Test batch ingestion endpoint  
**Method**: POST  
**Endpoint**: `/api/v1/events/batch`  
**Headers**: `Authorization: Bearer <token>`, `Content-Type: application/json`  
**Body**:
```json
{
  "events": [
    {
      "event_name": "page_view",
      "event_type": "engagement",
      "payload": {"page": "/home"}
    },
    {
      "event_name": "button_click",
      "event_type": "interaction",
      "payload": {"button_id": "btn_1"}
    },
    {
      "event_name": "form_submit",
      "event_type": "conversion",
      "payload": {"form_id": "form_1"}
    }
  ]
}
```

```bash
TOKEN="<access_token>"
curl -X POST http://localhost:8000/api/v1/events/batch \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "events": [
      {"event_name": "page_view", "event_type": "engagement", "payload": {"page": "/home"}},
      {"event_name": "button_click", "event_type": "interaction", "payload": {"button_id": "btn_1"}},
      {"event_name": "form_submit", "event_type": "conversion", "payload": {"form_id": "form_1"}}
    ]
  }' | jq .
```

**Expected Response**:
- Status: 202 Accepted
- JSON:
```json
{
  "event_count": 3,
  "event_ids": [<id1>, <id2>, <id3>],
  "task_id": "<UUID>",
  "status": "enqueued",
  "message": "Batch of 3 events enqueued for processing"
}
```

**Pass Criteria**:
- Status 202
- event_count = 3
- event_ids array with 3 integers
- task_id non-empty string

---

### Test 5.2: Submit Batch Events - Empty List
**Purpose**: Verify batch size constraints  
**Method**: POST  
**Endpoint**: `/api/v1/events/batch`  
**Headers**: `Authorization: Bearer <token>`, `Content-Type: application/json`  
**Body**:
```json
{
  "events": []
}
```

```bash
TOKEN="<access_token>"
curl -X POST http://localhost:8000/api/v1/events/batch \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"events": []}' | jq .
```

**Expected Response**:
- Status: 422 Unprocessable Entity

**Pass Criteria**: Status 422

---

### Test 5.3: Submit Batch Events - Too Many (>100)
**Purpose**: Verify batch size limits  
**Method**: POST  
**Endpoint**: `/api/v1/events/batch`  
**Headers**: `Authorization: Bearer <token>`, `Content-Type: application/json`  
**Body**: 101 events

```bash
TOKEN="<access_token>"

python3 << 'EOF'
import requests

token = "$TOKEN"
events = [
    {"event_name": f"event_{i}", "event_type": "test"}
    for i in range(101)
]

response = requests.post(
    "http://localhost:8000/api/v1/events/batch",
    headers={"Authorization": f"Bearer {token}"},
    json={"events": events}
)

print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")
EOF
```

**Expected Response**:
- Status: 422 Unprocessable Entity

**Pass Criteria**: Status 422

---

## Section 6: Async Task Triggering & Observable Effects

### Test 6.1: Verify Task Queuing (Immediate Response)
**Purpose**: Verify async task is enqueued immediately  
**Method**: POST  
**Endpoint**: `/api/v1/events`  
**Measure**: Response time  

```bash
TOKEN="<access_token>"

time curl -X POST http://localhost:8000/api/v1/events \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "event_name": "test",
    "event_type": "engagement",
    "payload": {"test": "data"}
  }' | jq .
```

**Expected Response**:
- Status: 202 Accepted
- Response time: < 100ms (non-blocking, no wait for processing)

**Pass Criteria**:
- Status 202
- Response time significantly faster than typical processing time (should be < 100ms)

---

### Test 6.2: Query Event Status - Before Processing
**Purpose**: Verify event created but not yet processed  
**Method**: GET  
**Endpoint**: `/api/v1/events/{event_id}`  
**Headers**: `Authorization: Bearer <token>`  

```bash
TOKEN="<access_token>"
EVENT_ID="<event_id_from_Test_4.1>"

curl -s http://localhost:8000/api/v1/events/$EVENT_ID \
  -H "Authorization: Bearer $TOKEN" | jq .
```

**Expected Response (immediately after submission)**:
- Status: 200 OK
- JSON with:
```json
{
  "id": <event_id>,
  "event_name": "...",
  "processed": false,
  "processed_at": null,
  "properties": null
}
```

**Pass Criteria**: processed = false, processed_at = null

---

### Test 6.3: Query Event Status - After Processing (Observable Effect)
**Purpose**: Verify async processing completed  
**Method**: GET  
**Endpoint**: `/api/v1/events/{event_id}`  
**Headers**: `Authorization: Bearer <token>`  
**Delay**: Wait 2-3 seconds after submission  

```bash
TOKEN="<access_token>"
EVENT_ID="<event_id_from_Test_4.1>"

# Wait for async processing
sleep 2

curl -s http://localhost:8000/api/v1/events/$EVENT_ID \
  -H "Authorization: Bearer $TOKEN" | jq .
```

**Expected Response (after processing)**:
- Status: 200 OK
- JSON with:
```json
{
  "id": <event_id>,
  "event_name": "page_view",
  "processed": true,
  "processed_at": "2025-12-18T...",
  "properties": {
    "original": {...},
    "normalized_at": "2025-12-18T..."
  }
}
```

**Pass Criteria**:
- processed = true (changed from false)
- processed_at is non-null ISO timestamp
- properties contains data (was null before)

**Note**: This is the primary observable effect of async processing

---

### Test 6.4: Polling Event for Completion
**Purpose**: Verify processing completes within timeout  
**Method**: GET  
**Endpoint**: `/api/v1/events/{event_id}`  
**Behavior**: Poll until processed=true or timeout  

```bash
#!/bin/bash
TOKEN="<access_token>"
EVENT_ID="<event_id>"
MAX_WAIT=30
INTERVAL=1
ELAPSED=0

while [ $ELAPSED -lt $MAX_WAIT ]; do
  RESPONSE=$(curl -s http://localhost:8000/api/v1/events/$EVENT_ID \
    -H "Authorization: Bearer $TOKEN")
  
  PROCESSED=$(echo $RESPONSE | jq -r '.processed')
  
  if [ "$PROCESSED" == "true" ]; then
    echo "✓ Event processed after ${ELAPSED}s"
    echo "$RESPONSE" | jq .
    exit 0
  fi
  
  echo "Waiting... ($ELAPSED/${MAX_WAIT}s)"
  sleep $INTERVAL
  ELAPSED=$((ELAPSED + INTERVAL))
done

echo "✗ Event not processed within ${MAX_WAIT}s"
exit 1
```

**Expected Behavior**:
- Event becomes processed within 5-10 seconds
- processed flag transitions from false → true
- processed_at gets a timestamp

**Pass Criteria**: Event marked processed within 30 seconds

---

### Test 6.5: Metadata Attachment Verification
**Purpose**: Verify user and timestamp metadata attached  
**Method**: GET  
**Endpoint**: `/api/v1/events/{event_id}`  
**After processing** (see Test 6.3)  

```bash
TOKEN="<access_token>"
EVENT_ID="<event_id>"

curl -s http://localhost:8000/api/v1/events/$EVENT_ID \
  -H "Authorization: Bearer $TOKEN" | jq '.properties'
```

**Expected Response**:
```json
{
  "original": {
    "page": "/home",
    "duration": 45
  },
  "normalized_at": "2025-12-18T10:30:00.123456",
  "page": "/home",
  "duration": 45.0
}
```

**Pass Criteria**:
- properties is non-null
- contains "normalized_at" (timestamp)
- contains "original" (preserves raw payload)
- extracted fields are present and type-converted

---

## Section 7: Batch Event Processing - Observable Effects

### Test 7.1: Submit Batch and Verify All Events Created
**Purpose**: Verify batch creates all events  
**Method**: POST then GET  

```bash
TOKEN="<access_token>"

# Submit batch
BATCH=$(curl -s -X POST http://localhost:8000/api/v1/events/batch \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "events": [
      {"event_name": "event_1", "event_type": "type_1"},
      {"event_name": "event_2", "event_type": "type_2"},
      {"event_name": "event_3", "event_type": "type_3"}
    ]
  }')

EVENT_IDS=$(echo $BATCH | jq -r '.event_ids[]')

echo "Event IDs: $EVENT_IDS"

# Verify each created
for ID in $EVENT_IDS; do
  curl -s http://localhost:8000/api/v1/events/$ID \
    -H "Authorization: Bearer $TOKEN" | jq "{id: .id, event_name: .event_name}"
done
```

**Expected Response**:
- All event_ids are accessible
- Each returns 200 OK with correct event_name

**Pass Criteria**: All 3 events retrievable

---

### Test 7.2: Verify Batch Events Process Atomically
**Purpose**: Verify batch processing completes for all events  
**Method**: POST, wait, GET all  

```bash
TOKEN="<access_token>"

# Submit batch
BATCH=$(curl -s -X POST http://localhost:8000/api/v1/events/batch \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "events": [
      {"event_name": "batch_1", "event_type": "test"},
      {"event_name": "batch_2", "event_type": "test"},
      {"event_name": "batch_3", "event_type": "test"}
    ]
  }')

EVENT_IDS=$(echo $BATCH | jq -r '.event_ids[]')

# Wait for processing
sleep 3

# Check all processed
for ID in $EVENT_IDS; do
  PROCESSED=$(curl -s http://localhost:8000/api/v1/events/$ID \
    -H "Authorization: Bearer $TOKEN" | jq -r '.processed')
  
  echo "Event $ID processed: $PROCESSED"
  
  if [ "$PROCESSED" != "true" ]; then
    echo "✗ Event $ID not processed"
    exit 1
  fi
done

echo "✓ All batch events processed"
```

**Expected Behavior**:
- All events eventually have processed=true
- All have processed_at timestamps

**Pass Criteria**: 100% of batch events processed

---

## Section 8: Event Retrieval & Listing

### Test 8.1: List User Events
**Purpose**: Verify event listing endpoint  
**Method**: GET  
**Endpoint**: `/api/v1/events`  
**Headers**: `Authorization: Bearer <token>`  
**Params**: `limit=10&offset=0`  

```bash
TOKEN="<access_token>"

curl -s "http://localhost:8000/api/v1/events?limit=10&offset=0" \
  -H "Authorization: Bearer $TOKEN" | jq .
```

**Expected Response**:
- Status: 200 OK
- JSON array of events:
```json
[
  {
    "id": <int>,
    "event_name": "<string>",
    "event_type": "<string>",
    "processed": <bool>,
    "processed_at": "<ISO timestamp or null>",
    ...
  },
  ...
]
```

**Pass Criteria**:
- Status 200
- Returns array
- Contains events submitted earlier

---

### Test 8.2: List Events - Pagination
**Purpose**: Verify pagination works  
**Method**: GET  
**Endpoint**: `/api/v1/events`  
**Params**: `limit=5&offset=0`, then `limit=5&offset=5`  

```bash
TOKEN="<access_token>"

echo "Page 1:"
curl -s "http://localhost:8000/api/v1/events?limit=5&offset=0" \
  -H "Authorization: Bearer $TOKEN" | jq 'length'

echo "Page 2:"
curl -s "http://localhost:8000/api/v1/events?limit=5&offset=5" \
  -H "Authorization: Bearer $TOKEN" | jq 'length'
```

**Expected Behavior**:
- Page 1 returns up to 5 events
- Page 2 returns next set
- Different events in each page

**Pass Criteria**: Pagination works correctly

---

### Test 8.3: Get Single Event by ID
**Purpose**: Verify get by ID endpoint  
**Method**: GET  
**Endpoint**: `/api/v1/events/{event_id}`  
**Headers**: `Authorization: Bearer <token>`  

```bash
TOKEN="<access_token>"
EVENT_ID="<valid_event_id>"

curl -s http://localhost:8000/api/v1/events/$EVENT_ID \
  -H "Authorization: Bearer $TOKEN" | jq .
```

**Expected Response**:
- Status: 200 OK
- JSON with complete event object

**Pass Criteria**: Status 200, event_id matches

---

### Test 8.4: Get Event - Non-existent ID
**Purpose**: Verify 404 handling  
**Method**: GET  
**Endpoint**: `/api/v1/events/999999`  
**Headers**: `Authorization: Bearer <token>`  

```bash
TOKEN="<access_token>"

curl -s http://localhost:8000/api/v1/events/999999 \
  -H "Authorization: Bearer $TOKEN" | jq .
```

**Expected Response**:
- Status: 404 Not Found

**Pass Criteria**: Status 404

---

### Test 8.5: Access Another User's Event
**Purpose**: Verify authorization enforcement  
**Method**: GET  
**Endpoint**: `/api/v1/events/{event_id_of_other_user}`  
**Headers**: `Authorization: Bearer <token_of_different_user>`  

```bash
# Create second user and get token
TOKEN_USER2="<token_for_different_user>"
EVENT_ID_USER1="<event_id_created_by_user1>"

curl -i http://localhost:8000/api/v1/events/$EVENT_ID_USER1 \
  -H "Authorization: Bearer $TOKEN_USER2"
```

**Expected Response**:
- Status: 403 Forbidden or 404 Not Found
- Should not return event details

**Pass Criteria**: Status 403 or 404 (user isolation enforced)

---

## Section 9: Error Handling

### Test 9.1: Malformed JSON
**Purpose**: Verify JSON parsing errors handled  
**Method**: POST  
**Endpoint**: `/api/v1/events`  
**Headers**: `Content-Type: application/json`  
**Body**: Invalid JSON  

```bash
TOKEN="<access_token>"

curl -i -X POST http://localhost:8000/api/v1/events \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{invalid json}'
```

**Expected Response**:
- Status: 400 Bad Request or 422 Unprocessable Entity

**Pass Criteria**: Status >= 400

---

### Test 9.2: Unsupported Content-Type
**Purpose**: Verify content-type validation  
**Method**: POST  
**Endpoint**: `/api/v1/events`  
**Headers**: `Content-Type: text/plain`  
**Body**: JSON string  

```bash
TOKEN="<access_token>"

curl -i -X POST http://localhost:8000/api/v1/events \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: text/plain" \
  -d '{"event_name": "test", "event_type": "test"}'
```

**Expected Response**:
- Status: 415 Unsupported Media Type or 422 Unprocessable Entity

**Pass Criteria**: Status >= 400

---

### Test 9.3: Method Not Allowed
**Purpose**: Verify HTTP method validation  
**Method**: PUT (invalid for event submission)  
**Endpoint**: `/api/v1/events`  

```bash
TOKEN="<access_token>"

curl -i -X PUT http://localhost:8000/api/v1/events \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Expected Response**:
- Status: 405 Method Not Allowed or 404 Not Found

**Pass Criteria**: Status 405 or 404

---

## Section 10: Concurrency & Rate Behavior

### Test 10.1: Rapid Sequential Event Submission
**Purpose**: Verify handling of rapid submissions  
**Method**: POST multiple events in quick succession  

```bash
TOKEN="<access_token>"

for i in {1..10}; do
  curl -s -X POST http://localhost:8000/api/v1/events \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{
      \"event_name\": \"rapid_$i\",
      \"event_type\": \"test\"
    }" | jq '.event_id'
done
```

**Expected Behavior**:
- All 10 requests succeed with 202 status
- Each gets unique event_id
- All are queued for processing

**Pass Criteria**: 10/10 succeeds with unique IDs

---

### Test 10.2: Concurrent Requests
**Purpose**: Test concurrent handling  
**Method**: Parallel POST requests  

```bash
TOKEN="<access_token>"

parallel -j 5 << 'EOF'
curl -s -X POST http://localhost:8000/api/v1/events \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"event_name": "concurrent", "event_type": "test"}'
EOF
```

Or using Python:

```bash
python3 << 'EOF'
import requests
import concurrent.futures

TOKEN = "<access_token>"

def submit_event(i):
    return requests.post(
        "http://localhost:8000/api/v1/events",
        headers={"Authorization": f"Bearer {TOKEN}"},
        json={
            "event_name": f"concurrent_{i}",
            "event_type": "test"
        }
    )

with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
    futures = [submit_event(i) for i in range(10)]
    results = [f.result() for f in concurrent.futures.as_completed(futures)]

success_count = sum(1 for r in results if r.status_code == 202)
print(f"✓ {success_count}/10 succeeded")
EOF
```

**Expected Behavior**:
- All requests succeed
- No race conditions
- All events created independently

**Pass Criteria**: 100% success rate

---

## Section 11: Event Statistics

### Test 11.1: Get Event Statistics
**Purpose**: Verify stats endpoint  
**Method**: GET  
**Endpoint**: `/api/v1/events/status/unprocessed`  
**Headers**: `Authorization: Bearer <token>`  

```bash
TOKEN="<access_token>"

curl -s http://localhost:8000/api/v1/events/status/unprocessed \
  -H "Authorization: Bearer $TOKEN" | jq .
```

**Expected Response**:
- Status: 200 OK
- JSON:
```json
{
  "unprocessed_count": <int>,
  "total_count": <int>,
  "user_id": <int>
}
```

**Pass Criteria**:
- Status 200
- unprocessed_count >= 0
- total_count >= unprocessed_count

---

### Test 11.2: Statistics After Events Processed
**Purpose**: Verify stats update after processing  
**Method**: GET after processing completes  

```bash
TOKEN="<access_token>"

# Submit event
EVENT=$(curl -s -X POST http://localhost:8000/api/v1/events \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"event_name": "test", "event_type": "test"}')

echo "Stats before processing:"
curl -s http://localhost:8000/api/v1/events/status/unprocessed \
  -H "Authorization: Bearer $TOKEN" | jq '.unprocessed_count'

# Wait for processing
sleep 3

echo "Stats after processing:"
curl -s http://localhost:8000/api/v1/events/status/unprocessed \
  -H "Authorization: Bearer $TOKEN" | jq '.unprocessed_count'
```

**Expected Behavior**:
- unprocessed_count increases after submission
- unprocessed_count decreases after processing

**Pass Criteria**: Stats reflect current state

---

## Test Execution Summary

### Quick Test Script (All Critical Path Tests)

```bash
#!/bin/bash

API="http://localhost:8000"
PASS=0
FAIL=0

test_endpoint() {
  local name=$1
  local method=$2
  local endpoint=$3
  local headers=$4
  local body=$5
  local expect_status=$6
  
  echo -n "Testing: $name... "
  
  if [ -z "$body" ]; then
    response=$(curl -s -w "\n%{http_code}" -X $method "$API$endpoint" $headers)
  else
    response=$(curl -s -w "\n%{http_code}" -X $method "$API$endpoint" $headers -d "$body")
  fi
  
  status=$(echo "$response" | tail -n 1)
  
  if [ "$status" == "$expect_status" ]; then
    echo "✓ PASS (Status: $status)"
    ((PASS++))
  else
    echo "✗ FAIL (Expected: $expect_status, Got: $status)"
    ((FAIL++))
  fi
}

# Test 1: Health
test_endpoint "Health Check" "GET" "/health" "" "" "200"

# Test 2: Register
TOKEN=$(curl -s -X POST $API/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"Pass123!","full_name":"Test"}' \
  | jq -r '.id')

# Test 3: Login
TOKEN=$(curl -s -X POST $API/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"Pass123!"}' \
  | jq -r '.access_token')

# Test 4: Submit Event
test_endpoint "Submit Event" "POST" "/api/v1/events" \
  "-H 'Authorization: Bearer $TOKEN' -H 'Content-Type: application/json'" \
  '{"event_name":"test","event_type":"test"}' "202"

# Test 5: List Events
test_endpoint "List Events" "GET" "/api/v1/events" \
  "-H 'Authorization: Bearer $TOKEN'" "" "200"

# Test 6: Unauthorized
test_endpoint "Unauthorized" "GET" "/api/v1/events" "" "" "401"

echo ""
echo "Results: $PASS passed, $FAIL failed"
```

---

## Test Matrix Summary

| Section | Test ID | Endpoint | Method | Expected Status | Purpose |
|---------|---------|----------|--------|-----------------|---------|
| 1 | 1.1 | /docs | GET | 200 | API docs available |
| 1 | 1.2 | /openapi.json | GET | 200 | OpenAPI schema |
| 1 | 1.3 | /health | GET | 200 | Health check |
| 2 | 2.1 | /api/auth/register | POST | 201 | Register user |
| 2 | 2.2 | /api/auth/register | POST | 400/409 | Duplicate email |
| 2 | 2.3 | /api/auth/login | POST | 200 | Login success |
| 2 | 2.4 | /api/auth/login | POST | 401 | Invalid password |
| 2 | 2.5 | /api/auth/login | POST | 401 | Non-existent user |
| 3 | 3.1 | /api/v1/events | GET | 401 | No token |
| 3 | 3.2 | /api/v1/events | GET | 401 | Invalid token |
| 3 | 3.3 | /api/v1/events | GET | 401 | Malformed token |
| 3 | 3.4 | /api/v1/events | GET | 200 | Valid token |
| 4 | 4.1 | /api/v1/events | POST | 202 | Submit event |
| 4 | 4.2 | /api/v1/events | POST | 422 | Missing field |
| 4 | 4.3 | /api/v1/events | POST | 422 | Empty field |
| 4 | 4.4 | /api/v1/events | POST | 400 | Oversized payload |
| 5 | 5.1 | /api/v1/events/batch | POST | 202 | Batch submit |
| 5 | 5.2 | /api/v1/events/batch | POST | 422 | Empty batch |
| 5 | 5.3 | /api/v1/events/batch | POST | 422 | Batch too large |
| 6 | 6.1 | /api/v1/events | POST | 202 | Async queuing |
| 6 | 6.2 | /api/v1/events/{id} | GET | 200 | Event before processing |
| 6 | 6.3 | /api/v1/events/{id} | GET | 200 | Event after processing |
| 6 | 6.4 | /api/v1/events/{id} | GET | 200 | Poll for completion |
| 6 | 6.5 | /api/v1/events/{id} | GET | 200 | Metadata verification |
| 7 | 7.1 | /api/v1/events/batch | POST | 202 | Batch creation |
| 7 | 7.2 | /api/v1/events/{id} | GET | 200 | Batch processing |
| 8 | 8.1 | /api/v1/events | GET | 200 | List events |
| 8 | 8.2 | /api/v1/events | GET | 200 | Pagination |
| 8 | 8.3 | /api/v1/events/{id} | GET | 200 | Get by ID |
| 8 | 8.4 | /api/v1/events/999999 | GET | 404 | Non-existent |
| 8 | 8.5 | /api/v1/events/{other_user} | GET | 403 | User isolation |
| 9 | 9.1 | /api/v1/events | POST | 400 | Malformed JSON |
| 9 | 9.2 | /api/v1/events | POST | 415 | Wrong Content-Type |
| 9 | 9.3 | /api/v1/events | PUT | 405 | Method not allowed |
| 10 | 10.1 | /api/v1/events | POST | 202 | Rapid submission |
| 10 | 10.2 | /api/v1/events | POST | 202 | Concurrent requests |
| 11 | 11.1 | /api/v1/events/status/unprocessed | GET | 200 | Get stats |
| 11 | 11.2 | /api/v1/events/status/unprocessed | GET | 200 | Stats update |

**Total Tests**: 42
**Critical Path Tests**: 10 (Sections 1-4, 6, 8.1)

---

## Pass/Fail Criteria Summary

### Must Pass (Critical)
- Health check returns 200 ✓
- User registration succeeds ✓
- User login returns JWT ✓
- Protected endpoints reject without token ✓
- Event submission returns 202 with task_id ✓
- Event becomes processed within 10 seconds ✓
- Processed event has timestamp and metadata ✓

### Should Pass (Important)
- Batch events processed ✓
- User isolation enforced ✓
- Pagination works ✓
- Error validation (422 on bad input) ✓

### Can Fail (Nice to Have)
- Rate limiting (if not implemented)
- Advanced filtering (if not implemented)

---

## Notes for Testers

1. **No Source Code Inspection**: All tests are based on expected behavior via API contracts only
2. **Observable Effects Only**: Testing verifies state changes (processed=true, processed_at set, properties updated)
3. **Timing Assumptions**: Async processing assumed to complete within 5-10 seconds per event
4. **Stateless Tests**: Each test is independent and can run in any order
5. **Clean Setup**: Use separate test user email per test run to avoid conflicts
6. **Error Messages**: Focus on HTTP status codes, not error message text (implementation detail)
