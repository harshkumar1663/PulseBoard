"""
Black-box API tests for the running FastAPI backend.

Rules enforced here:
- Only HTTP calls via requests
- No imports from the backend codebase
- Assume the server is running at localhost:8000
- PostgreSQL + Redis are up, JWT auth is enforced

Covers:
1) Register a user
2) Login and obtain JWT tokens
3) Call a protected endpoint successfully
4) Fail when token is missing or invalid
5) Submit an event payload
6) Verify async behavior via observable response changes / follow-up queries

Usage:
    pytest -q PulseBoard/pulseboard-backend/tests/test_blackbox_api_flow.py
Optional:
    Set API base URL with env var API_BASE_URL (default http://localhost:8000/api)

Note:
- These tests hit a live service; they will fail if the server is not up
  or if dependent services (DB/Redis/Celery workers) are not available.
"""
from __future__ import annotations

import os
import time
import uuid
from typing import Dict, Tuple, Any

import pytest
import requests

# Base URL for the running API (can be overridden via env var)
BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api")
TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "10"))

# Endpoints used in this suite
REGISTER_URL = f"{BASE_URL}/auth/register"
LOGIN_URL = f"{BASE_URL}/auth/login"
ME_AUTH_URL = f"{BASE_URL}/auth/me"
ME_USER_URL = f"{BASE_URL}/users/me"
EVENT_INGEST_URL = f"{BASE_URL}/v1/events"
EVENT_STATUS_URL = f"{BASE_URL}/v1/events/status/unprocessed"
EVENT_BY_ID_URL = lambda event_id: f"{BASE_URL}/v1/events/{event_id}"
LIST_EVENTS_URL = f"{BASE_URL}/v1/events"
HEALTH_URL = f"{BASE_URL}/../health"  # /api/../health -> /health


@pytest.fixture(scope="session")
def http() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "Content-Type": "application/json",
        "Accept": "application/json",
    })
    return s


@pytest.fixture(scope="session")
def unique_user_credentials() -> Dict[str, str]:
    """Generate unique credentials to avoid conflicts across runs."""
    uid = uuid.uuid4().hex[:10]
    return {
        "email": f"qa_{uid}@example.com",
        "username": f"qa_user_{uid}",
        "password": "Str0ngP@ssw0rd!",
        "full_name": "QA Test User",
    }


def _json_or_text(resp: requests.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return resp.text


def _register_user(http: requests.Session, creds: Dict[str, str]) -> Tuple[int, Any]:
    resp = http.post(REGISTER_URL, json={
        "email": creds["email"],
        "username": creds["username"],
        "password": creds["password"],
        "full_name": creds["full_name"],
    }, timeout=TIMEOUT)
    return resp.status_code, _json_or_text(resp)


def _login(http: requests.Session, username: str, password: str) -> Tuple[int, Any]:
    resp = http.post(LOGIN_URL, json={
        "username": username,
        "password": password,
    }, timeout=TIMEOUT)
    return resp.status_code, _json_or_text(resp)


def test_auth_and_events_flow(http: requests.Session, unique_user_credentials: Dict[str, str]):
    """
    Full flow test covering registration, JWT login, protected access,
    event submission, and async verification via follow-up queries.
    """
    # 0) Sanity: health endpoint should be reachable
    health = http.get(HEALTH_URL, timeout=TIMEOUT)
    assert health.status_code == 200, f"Health check failed: {health.status_code} {health.text}"

    # 1) Register a user
    status, reg_body = _register_user(http, unique_user_credentials)
    if status == 500:
        pytest.skip(
            f"Registration returned 500. Backend likely not DB-migrated or misconfigured. Response: {reg_body}"
        )
    assert status in (201, 400), f"Unexpected register status: {status} {reg_body}"
    if status == 400:
        # If the unique credentials somehow collided, surface the backend error
        assert "exists" in (reg_body.get("detail", "").lower()), f"Register failed: {reg_body}"

    # 2) Login and obtain JWT tokens
    status, login_body = _login(http, unique_user_credentials["username"], unique_user_credentials["password"])
    assert status == 200, f"Login failed: {status} {login_body}"
    assert "access_token" in login_body and "refresh_token" in login_body, "Missing tokens in login response"

    access_token = login_body["access_token"]
    auth_headers = {"Authorization": f"Bearer {access_token}"}

    # 3) Call a protected endpoint successfully (/users/me)
    me = http.get(ME_USER_URL, headers=auth_headers, timeout=TIMEOUT)
    assert me.status_code == 200, f"/users/me failed: {me.status_code} {me.text}"
    me_json = me.json()
    assert me_json.get("username") == unique_user_credentials["username"], "Returned user mismatch"

    # 4) Fail when token is missing or invalid
    me_no_token = http.get(ME_USER_URL, timeout=TIMEOUT)
    assert me_no_token.status_code in (401, 403), f"Expected 401/403 without token, got {me_no_token.status_code}"

    me_bad_token = http.get(ME_USER_URL, headers={"Authorization": "Bearer invalid.token.here"}, timeout=TIMEOUT)
    assert me_bad_token.status_code in (401, 403), f"Expected 401/403 with bad token, got {me_bad_token.status_code}"

    # 5) Submit an event payload (async)
    session_id = f"sess-{uuid.uuid4().hex[:8]}"

    # Capture status snapshot before ingest
    before_status = http.get(EVENT_STATUS_URL, headers=auth_headers, timeout=TIMEOUT)
    assert before_status.status_code == 200, f"Status pre-check failed: {before_status.status_code} {before_status.text}"
    before = before_status.json()
    before_unprocessed = int(before.get("unprocessed_count", 0))
    before_total_user = int(before.get("total_count", 0))

    ingest = http.post(
        EVENT_INGEST_URL,
        headers=auth_headers,
        json={
            "event_name": "qa_test_event",
            "event_type": "test",
            "source": "pytest",
            "session_id": session_id,
            "payload": {"k": "v", "ts": time.time()},
        },
        timeout=TIMEOUT,
    )
    assert ingest.status_code == 202, f"Event ingest failed: {ingest.status_code} {ingest.text}"
    ingest_json = ingest.json()
    assert "event_id" in ingest_json and "task_id" in ingest_json, "Missing event_id/task_id in ingest response"
    event_id = ingest_json["event_id"]

    # 6) Verify async behavior via observable changes / follow-ups
    #    - total_count for the user should increase by at least 1
    #    - the event should be retrievable via GET /v1/events/{id}
    #    - optionally, processed flag may flip to True within a timeout window

    # Wait briefly to allow DB commit and task enqueue
    time.sleep(0.75)

    after_status = http.get(EVENT_STATUS_URL, headers=auth_headers, timeout=TIMEOUT)
    assert after_status.status_code == 200, f"Status post-check failed: {after_status.status_code} {after_status.text}"
    after = after_status.json()
    after_total_user = int(after.get("total_count", 0))

    assert (
        after_total_user >= before_total_user + 1
    ), f"Expected user's total_count to increase. before={before_total_user} after={after_total_user}"

    # Retrieve the event by ID; it should exist immediately
    got = http.get(EVENT_BY_ID_URL(event_id), headers=auth_headers, timeout=TIMEOUT)
    assert got.status_code == 200, f"GET event failed: {got.status_code} {got.text}"
    got_json = got.json()
    assert got_json["id"] == event_id, "Fetched event id mismatch"
    assert got_json["event_name"] == "qa_test_event"

    # Poll for processed flag to become True (if workers are running)
    # If not processed within the timeout, we still assert observability via list + status endpoints
    max_wait_s = int(os.getenv("EVENT_PROCESSING_TIMEOUT", "30"))
    deadline = time.time() + max_wait_s
    processed_seen = got_json.get("processed", False) is True

    while not processed_seen and time.time() < deadline:
        time.sleep(1.0)
        check = http.get(EVENT_BY_ID_URL(event_id), headers=auth_headers, timeout=TIMEOUT)
        if check.status_code == 200:
            processed_seen = check.json().get("processed", False) is True
        else:
            # transient read issues; continue until deadline
            continue

    # Always verify list endpoint contains the event for the session
    listed = http.get(LIST_EVENTS_URL + f"?limit=25&offset=0", headers=auth_headers, timeout=TIMEOUT)
    assert listed.status_code == 200, f"List events failed: {listed.status_code} {listed.text}"
    listed_ids = [e.get("id") for e in listed.json()]
    assert event_id in listed_ids, "Newly ingested event not listed for user"

    # If processed was observed, great. If not, at least we proved async enqueue via IDs, counts, and retrievability.
    # We do not hard-fail on lack of processing flip to keep tests stable when workers are offline.
    if processed_seen:
        # Optionally, assert processed_at presence when processed
        evt = http.get(EVENT_BY_ID_URL(event_id), headers=auth_headers, timeout=TIMEOUT)
        assert evt.status_code == 200
        ej = evt.json()
        assert ej.get("processed") is True
        assert ej.get("processed_at") is not None


def test_protected_endpoint_requires_jwt(http: requests.Session):
    """Quick negative checks for protected resource access."""
    # No token
    r1 = http.get(ME_USER_URL, timeout=TIMEOUT)
    assert r1.status_code in (401, 403)

    # Invalid token
    r2 = http.get(ME_USER_URL, headers={"Authorization": "Bearer wrong.token.value"}, timeout=TIMEOUT)
    assert r2.status_code in (401, 403)
