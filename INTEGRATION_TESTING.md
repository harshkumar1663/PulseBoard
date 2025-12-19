# Integration & Testing Guide

## Quick Start

### 1. Start Services
```bash
cd g:\Portfolio\PulseBoard\pulseboard-backend

docker-compose up -d

# Verify all containers running
docker-compose ps
```

### 2. Run Migrations
```bash
docker-compose exec api alembic upgrade head
```

### 3. Test Event Submission

#### Register User
```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "TestPass123!",
    "full_name": "Test User"
  }'
```

#### Login
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "TestPass123!"
  }'

# Save access_token from response
export TOKEN="<access_token>"
```

#### Submit Event
```bash
curl -X POST http://localhost:8000/api/v1/events \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "event_name": "page_view",
    "event_type": "engagement",
    "source": "web",
    "session_id": "sess_123",
    "payload": {
      "page": "/dashboard",
      "duration": 45,
      "scroll_depth": 75
    }
  }'

# Response (202 Accepted):
# {
#   "event_id": 1,
#   "task_id": "abc-def-123...",
#   "status": "enqueued",
#   "message": "Event enqueued for processing"
# }
```

#### Check Event Status
```bash
# Wait a few seconds for worker to process
sleep 2

curl -X GET http://localhost:8000/api/v1/events/1 \
  -H "Authorization: Bearer $TOKEN"

# Response:
# {
#   "id": 1,
#   "processed": true,
#   "processed_at": "2025-12-18T10:30:00.123456",
#   "properties": {
#     "original": {"page": "/dashboard", ...},
#     "normalized_at": "2025-12-18T10:30:00.123456",
#     "page": "/dashboard",
#     "duration": 45.0,
#     "scroll_depth": 75.0
#   }
# }
```

---

## Verification Workflow

### Step 1: API Creates Event
```bash
API receives POST /api/v1/events
  ↓
1. Validates input (Pydantic schema)
2. Creates Event in DB: processed=false
3. Returns 202 with event_id and task_id
4. Client receives immediately (non-blocking)
```

**Check DB**:
```bash
docker-compose exec db psql -U postgres -d pulseboard -c \
  "SELECT id, event_name, processed, processed_at FROM events WHERE id=1;"

# Result:
#  id | event_name | processed | processed_at
# ----+------------+-----------+---------------
#  1  | page_view  | f         | (null)
```

### Step 2: Worker Processes Event
```bash
Worker receives process_event(event_id=1)
  ↓
1. [FETCH] Get event + user from DB
2. [VALIDATE] Check payload shape
   - Is dict? ✓
   - JSON-safe? ✓
   - Size < 1MB? ✓
   - Depth < 10? ✓
3. [VALIDATE] Check required fields
   - event_name? ✓
   - event_type? ✓
4. [NORMALIZE] Attach metadata
   - normalized_at = NOW
   - Type-convert: duration → float
5. [MARK] Set processed_at = NOW
   - processed = True
   - processed_at = NOW
6. [PERSIST] Commit to DB
7. Return success
```

**Check Logs**:
```bash
docker-compose logs -f worker | grep "Event 1\]"

# Output:
# worker | [Event 1] Starting processing
# worker | [Event 1] User: test@example.com
# worker | [Event 1] Payload validation passed
# worker | [Event 1] Marked processed at 2025-12-18T10:30:00.123456
# worker | [Event 1] Processing completed successfully
```

### Step 3: Verify Results
```bash
# Check DB - event should be processed
docker-compose exec db psql -U postgres -d pulseboard -c \
  "SELECT id, event_name, processed, processed_at, properties FROM events WHERE id=1;"

# Result:
#  id | event_name | processed |      processed_at      |          properties
# ----+------------+-----------+------------------------+-----------------------------
#  1  | page_view  | t         | 2025-12-18 10:30:00.12 | {
#    |            |           |                        |   "original": {...},
#    |            |           |                        |   "normalized_at": "...",
#    |            |           |                        |   "page": "/dashboard",
#    |            |           |                        |   "duration": 45.0
#    |            |           |                        | }
```

**Check API Response**:
```bash
curl http://localhost:8000/api/v1/events/1 -H "Authorization: Bearer $TOKEN" | jq

# Verify:
# - processed: true
# - processed_at: "2025-12-18T10:30:00..."
# - properties: {...with normalized_at...}
```

---

## Error Scenarios

### Scenario 1: Invalid Payload (Too Large)
```bash
# Create huge payload > 1MB
curl -X POST http://localhost:8000/api/v1/events \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "event_name": "page_view",
    "event_type": "engagement",
    "payload": {huge data > 1MB}
  }'

# 202 Accepted (stored in DB)
```

**Worker processes**:
- Validates payload shape
- ✗ Fails: Payload exceeds 1MB
- Stores error: `event.processing_error = "Payload exceeds 1MB size limit"`
- ✓ Persists to DB
- Returns: Status "validation_error" (no retry)

**Check result**:
```bash
curl http://localhost:8000/api/v1/events/<id> -H "Authorization: Bearer $TOKEN" | jq

# Result:
# {
#   "processed": false,
#   "processed_at": null,
#   "processing_error": "Payload exceeds 1MB size limit"
# }
```

### Scenario 2: Missing Required Field
```bash
curl -X POST http://localhost:8000/api/v1/events \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "event_type": "engagement",
    "payload": {}
  }'
# Fails at API level - Pydantic validation
```

### Scenario 3: Database Error During Processing
```bash
# Kill database temporarily
docker-compose stop db

# Submit event
curl -X POST http://localhost:8000/api/v1/events \
  -H "Authorization: Bearer $TOKEN" \
  -d '{...}'

# 202 Accepted (created in-memory before DB processing)
# Worker tries to process
```

**Worker behavior**:
- Attempts to fetch event from DB
- ✗ Connection fails
- Logs error
- Retry 1: Wait 2s
- Retry 2: Wait 4s
- Retry 3: Wait 8s
- Max retries exceeded → marked failed

**Restart DB**:
```bash
docker-compose start db
docker-compose logs -f worker
```

---

## Batch Processing Test

```bash
curl -X POST http://localhost:8000/api/v1/events/batch \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
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
  }'

# Response (202 Accepted):
# {
#   "event_count": 3,
#   "event_ids": [1, 2, 3],
#   "task_id": "batch_task_id",
#   "status": "enqueued"
# }
```

**Worker processes all 3**:
- Single Celery task
- All events processed in one batch
- Single DB transaction (atomic)
- If any fail, still persists error tracking

**Check result**:
```bash
docker-compose logs -f worker | grep "\[Batch\]"

# Output:
# [Batch] Processing 3 events
# [Event 1] Processed in batch
# [Event 2] Processed in batch
# [Event 3] Processed in batch
# [Batch] Persisted 3 processed events
# [Batch] Completed: 3 processed, 0 failed out of 3 total
```

---

## Monitoring

### Flower Dashboard
```
URL: http://localhost:5555

Shows:
- Task execution history
- Worker status
- Task details
- Real-time stats
```

### Worker Logs
```bash
# Watch worker processing
docker-compose logs -f worker

# Filter by event
docker-compose logs -f worker | grep "\[Event 1\]"

# Filter errors
docker-compose logs -f worker | grep ERROR
```

### API Logs
```bash
# Watch API
docker-compose logs -f api

# Filter by path
docker-compose logs -f api | grep "/v1/events"
```

### Redis Monitor
```bash
# Connect to Redis
docker-compose exec redis redis-cli

# Monitor commands
> MONITOR

# Check task queue
> LLEN celery
> LLEN celery-task-meta-guid:...
```

---

## Cleanup & Reset

### Stop Services
```bash
docker-compose stop
```

### Stop & Remove
```bash
docker-compose down
```

### Remove Volumes (Reset DB)
```bash
docker-compose down -v
```

### Restart Everything
```bash
docker-compose down -v
docker-compose up -d
docker-compose exec api alembic upgrade head
```

---

## Troubleshooting

### Events Not Processing

**Check worker is running**:
```bash
docker-compose ps worker
# Should show "Up"
```

**Check logs**:
```bash
docker-compose logs worker | tail -50
```

**Check Redis connection**:
```bash
docker-compose exec redis redis-cli ping
# Should return "PONG"
```

**Check event queue**:
```bash
docker-compose exec redis redis-cli
> LLEN celery
# Should show pending tasks
```

### High Memory Usage

```bash
# Monitor memory
docker stats pulseboard-worker

# Worker settings (app/workers/celery_app.py):
worker_max_tasks_per_child = 1000  # Restart after 1000 tasks
```

### Processing Slow

```bash
# Scale up workers
docker-compose up -d --scale worker=8

# Check worker concurrency (app/workers/celery_app.py)
worker_prefetch_multiplier = 4  # Tasks per worker
```

### Database Connection Issues

```bash
# Check database
docker-compose logs db

# Restart database
docker-compose restart db

# Check connection
docker-compose exec db psql -U postgres -d pulseboard -c "SELECT 1;"
```

---

## Performance Testing

### Load Test with Python Script
```bash
python EXAMPLE_USAGE.py
```

### Load Test with Locust
```bash
# Create locustfile.py with desired load

locust -f locustfile.py \
  --host=http://localhost:8000 \
  --users 100 \
  --spawn-rate 10 \
  --run-time 60s
```

### Monitor During Load
```bash
# Terminal 1: Watch worker
docker-compose logs -f worker

# Terminal 2: Watch API
docker-compose logs -f api

# Terminal 3: Monitor resources
docker stats

# Terminal 4: Check Flower
open http://localhost:5555
```

---

## Common Commands Reference

```bash
# View all containers
docker-compose ps

# View logs
docker-compose logs -f [service]

# Execute command in container
docker-compose exec [service] [command]

# Scale workers
docker-compose up -d --scale worker=4

# Restart service
docker-compose restart [service]

# Stop services
docker-compose stop

# Start services
docker-compose start

# Remove everything
docker-compose down -v

# Database shell
docker-compose exec db psql -U postgres -d pulseboard

# Redis shell
docker-compose exec redis redis-cli

# API shell (pytest, etc)
docker-compose exec api bash
```

---

## Complete End-to-End Test

```bash
#!/bin/bash
set -e

echo "1. Starting services..."
docker-compose up -d

echo "2. Waiting for services..."
sleep 5

echo "3. Running migrations..."
docker-compose exec api alembic upgrade head

echo "4. Running example workflow..."
python EXAMPLE_USAGE.py

echo "5. Opening Flower dashboard..."
open http://localhost:5555

echo "✓ Test complete!"
echo ""
echo "View logs:"
echo "  docker-compose logs -f worker"
echo "  docker-compose logs -f api"
```

Save as `test-complete.sh` and run:
```bash
chmod +x test-complete.sh
./test-complete.sh
```
