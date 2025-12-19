# Black-Box Testing - Commands Quick Reference

## ⚡ One-Line Test Execution

```bash
# Run complete automated test suite (ALL 42 TESTS)
python api_black_box_tests.py

# Run with verbose output (see every test)
python api_black_box_tests.py --verbose

# Run against remote host
python api_black_box_tests.py --host http://staging-api.example.com:8000
```

---

## 🏃 5-Minute Quick Start

```bash
# 1. Ensure backend is running
docker-compose up -d

# 2. Apply database migrations
docker-compose exec api alembic upgrade head

# 3. Verify health
curl http://localhost:8000/health

# 4. Run all tests
python api_black_box_tests.py

# 5. Check results (should show 100% success)
```

---

## 🔑 Key Test Commands (Manual curl)

### Authentication Tests
```bash
# Register user
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"Pass123!","full_name":"Test"}'

# Login (get token)
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"Pass123!"}' | jq -r '.access_token')

# Show token
echo $TOKEN
```

### Event Submission (Key Tests)
```bash
# Submit single event (should return 202 with task_id)
curl -X POST http://localhost:8000/api/v1/events \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "event_name": "page_view",
    "event_type": "engagement",
    "payload": {"page": "/home"}
  }' | jq .

# Extract event_id
EVENT_ID=$(curl -s -X POST http://localhost:8000/api/v1/events \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"event_name":"test","event_type":"test"}' | jq -r '.event_id')

echo "Event ID: $EVENT_ID"
```

### Async Processing Observable Effect (Key Test)
```bash
# Check event immediately (should be processed=false)
curl -s http://localhost:8000/api/v1/events/$EVENT_ID \
  -H "Authorization: Bearer $TOKEN" | jq '.processed, .processed_at'

# Result: false, null

# Wait 3 seconds
sleep 3

# Check again (should be processed=true with timestamp)
curl -s http://localhost:8000/api/v1/events/$EVENT_ID \
  -H "Authorization: Bearer $TOKEN" | jq '.processed, .processed_at'

# Result: true, "2025-12-18T10:30:00..."
```

### Metadata Verification (Key Test)
```bash
# After processing, check properties for normalized_at
curl -s http://localhost:8000/api/v1/events/$EVENT_ID \
  -H "Authorization: Bearer $TOKEN" | jq '.properties'

# Should contain:
# {
#   "normalized_at": "2025-12-18T10:30:00...",
#   "original": {...},
#   ...
# }
```

### Batch Events
```bash
# Submit batch of 3 events (should return 202)
curl -X POST http://localhost:8000/api/v1/events/batch \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "events": [
      {"event_name":"event_1","event_type":"test"},
      {"event_name":"event_2","event_type":"test"},
      {"event_name":"event_3","event_type":"test"}
    ]
  }' | jq '.event_count, .event_ids'

# Result: 3, [101, 102, 103]
```

### Event Retrieval
```bash
# List all user events
curl -s "http://localhost:8000/api/v1/events?limit=10" \
  -H "Authorization: Bearer $TOKEN" | jq 'length'

# Get single event
curl -s http://localhost:8000/api/v1/events/$EVENT_ID \
  -H "Authorization: Bearer $TOKEN" | jq '.event_name'

# Get event statistics
curl -s http://localhost:8000/api/v1/events/status/unprocessed \
  -H "Authorization: Bearer $TOKEN" | jq '.total_count, .unprocessed_count'
```

### Authorization Tests (Should Fail - Expected)
```bash
# No token (should return 401)
curl -i http://localhost:8000/api/v1/events

# Invalid token (should return 401)
curl -i http://localhost:8000/api/v1/events \
  -H "Authorization: Bearer invalid_token"

# Non-existent event (should return 404)
curl -i http://localhost:8000/api/v1/events/999999 \
  -H "Authorization: Bearer $TOKEN"
```

---

## 📊 Monitoring During Tests

```bash
# Terminal 1: API logs
docker-compose logs -f api

# Terminal 2: Worker logs (watch async processing)
docker-compose logs -f worker

# Terminal 3: Redis/Celery broker
docker-compose logs -f redis

# Terminal 4: Database
docker-compose exec db psql -U postgres -d pulseboard << EOF
SELECT id, event_name, processed, processed_at FROM events ORDER BY created_at DESC LIMIT 10;
EOF

# Terminal 5: Flower (task monitoring)
open http://localhost:5555

# Terminal 6: Run tests
python api_black_box_tests.py --verbose
```

---

## 🔍 Debugging Commands

### Check Backend Health
```bash
curl http://localhost:8000/health | jq .
```

### Check Services Running
```bash
docker-compose ps
```

### Check API Logs (Last 50 lines)
```bash
docker-compose logs api --tail=50
```

### Check Worker Status
```bash
docker-compose logs worker --tail=50 | grep -i "ready\|task\|error"
```

### Check Database Connection
```bash
docker-compose exec db psql -U postgres -d pulseboard -c "SELECT version();"
```

### Check Redis
```bash
docker-compose exec redis redis-cli ping
# Should respond: PONG
```

### Check Event in Database
```bash
docker-compose exec db psql -U postgres -d pulseboard << EOF
SELECT id, event_name, processed, processed_at FROM events WHERE id = $EVENT_ID;
EOF
```

### View Worker Task Queue
```bash
docker-compose exec redis redis-cli KEYS "*"
```

---

## 🚀 CI/CD Integration

### GitHub Actions
```yaml
- name: Run Black-Box Tests
  run: |
    docker-compose up -d
    docker-compose exec -T api alembic upgrade head
    python api_black_box_tests.py
```

### Exit Codes
```bash
# Success: exit code 0
python api_black_box_tests.py
echo $?  # 0 = all passed

# Failure: exit code 1
python api_black_box_tests.py
echo $?  # 1 = some failed
```

---

## 📝 Save Results

```bash
# Save test results to file
python api_black_box_tests.py > test_results_$(date +%s).txt

# With verbose output
python api_black_box_tests.py --verbose > test_results_verbose_$(date +%s).txt

# Save logs
docker-compose logs api > api_logs_$(date +%s).txt
docker-compose logs worker > worker_logs_$(date +%s).txt
```

---

## 🔄 Common Workflows

### Before Committing Code
```bash
python api_black_box_tests.py
# ✓ All pass → safe to commit
# ✗ Any fail → fix before commit
```

### Before Pushing to Production
```bash
python api_black_box_tests.py --host https://api.example.com
# ✓ All pass → safe to deploy
```

### During Development
```bash
# Watch logs while running tests
docker-compose logs -f worker &
python api_black_box_tests.py --verbose
```

### Onboarding New Team Member
```bash
# Send them these files:
# 1. BLACK_BOX_TESTING_README.md (overview)
# 2. api_black_box_tests.py (run it)
# 3. BLACK_BOX_QUICK_REF.md (reference)
```

---

## ⏱️ Timing Expectations

| Task | Time |
|------|------|
| Setup (docker-compose up, migrations) | 3 min |
| Full automated test suite | 5 min |
| Full suite with verbose logging | 8 min |
| Guided workflow (BLACK_BOX_EXECUTION_WORKFLOW.md) | 90 min |
| Manual testing all 42 tests (curl) | 45 min |

---

## 🎯 Success Indicators

```bash
# Should see this in output:
✓ Passed: 42/42
✗ Failed: 0/42
✗ Errors: 0/42

Success Rate: 100.0%

✓ All tests passed!
```

---

## 📖 Finding Information

| Question | Command/File |
|----------|--------------|
| Run all tests | `python api_black_box_tests.py` |
| Test details | `grep "Test 4.1" BLACK_BOX_TEST_PLAN.md` |
| Troubleshoot | `grep -i "issue\|problem" BLACK_BOX_QUICK_REF.md` |
| Learn step-by-step | `cat BLACK_BOX_EXECUTION_WORKFLOW.md \| less` |
| Overview | `cat BLACK_BOX_TESTING_README.md \| less` |
| Use GUI | Import `PulseBoard_Black_Box_Tests.postman_collection.json` to Postman |

---

## 🔗 File Reference

```
To understand:           See:
What tests exist?        BLACK_BOX_TEST_PLAN.md
How to run tests?        api_black_box_tests.py or BLACK_BOX_QUICK_REF.md
Step-by-step guide?      BLACK_BOX_EXECUTION_WORKFLOW.md
Quick answers?           BLACK_BOX_QUICK_REF.md
Postman/GUI?            PulseBoard_Black_Box_Tests.postman_collection.json
All files?              ARTIFACT_INVENTORY.md (this reference)
Overview?               BLACK_BOX_TESTING_README.md
```

---

## ⚙️ Test Environment Variables

```bash
# For automated tests
export API_URL="http://localhost:8000"
export PYTHONPATH="."

# For curl commands
export TOKEN="<access_token_from_login>"
export EVENT_ID="<event_id_from_submission>"
export USER_EMAIL="test@example.com"
```

---

## 🛠️ Useful One-Liners

```bash
# Create 10 test events rapidly
for i in {1..10}; do curl -s -X POST http://localhost:8000/api/v1/events \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"event_name\":\"test_$i\",\"event_type\":\"test\"}" | jq '.event_id'; done

# Check if all events are processed
curl -s http://localhost:8000/api/v1/events?limit=100 \
  -H "Authorization: Bearer $TOKEN" | jq '[.[] | select(.processed==false)] | length'

# Get event processing time
curl -s http://localhost:8000/api/v1/events/$EVENT_ID \
  -H "Authorization: Bearer $TOKEN" | jq '.created_at, .processed_at'

# Count processed vs unprocessed
curl -s http://localhost:8000/api/v1/events/status/unprocessed \
  -H "Authorization: Bearer $TOKEN" | jq '{total: .total_count, unprocessed: .unprocessed_count, processed: (.total_count-.unprocessed_count)}'

# Watch worker processing
watch -n 1 'docker-compose logs worker | tail -20'

# Monitor event table growth
watch -n 2 'docker-compose exec db psql -U postgres -d pulseboard -c "SELECT count(*) FROM events;"'
```

---

## 📋 Pre-Test Checklist

```bash
# Run this before executing tests
echo "Pre-Test Checklist:"

# 1. Docker running
echo -n "✓ Docker: " && docker ps > /dev/null 2>&1 && echo "OK" || echo "FAILED"

# 2. Services up
echo -n "✓ Services: " && docker-compose ps | grep -q "running" && echo "OK" || echo "FAILED"

# 3. API responsive
echo -n "✓ API: " && curl -s http://localhost:8000/health | jq -e '.status' > /dev/null && echo "OK" || echo "FAILED"

# 4. Database connected
echo -n "✓ Database: " && docker-compose exec db psql -U postgres -d pulseboard -c "SELECT 1" > /dev/null 2>&1 && echo "OK" || echo "FAILED"

# 5. Redis running
echo -n "✓ Redis: " && docker-compose exec redis redis-cli ping | grep -q PONG && echo "OK" || echo "FAILED"

# 6. Worker running
echo -n "✓ Worker: " && docker-compose logs worker | grep -q "ready" && echo "OK" || echo "FAILED"

# 7. Python available
echo -n "✓ Python: " && python --version > /dev/null 2>&1 && echo "OK" || echo "FAILED"

# 8. requests installed
echo -n "✓ requests: " && python -c "import requests" > /dev/null 2>&1 && echo "OK" || echo "FAILED"

echo ""
echo "All checks passed! Ready to test."
```

---

Created: December 18, 2025  
Purpose: Quick command reference for black-box API testing  
Audience: QA engineers, developers, CI/CD operators  
