"""
Black-box tests for the FastAPI backend using only HTTP calls.

Rules:
- Only use HTTP via `requests` (no imports from backend code).
- Treat server as external service at localhost:8000.
- Verify JWT-protected endpoints and async event processing behavior.

These tests cover:
1. User registration
2. Login to obtain JWT tokens
3. Access a protected endpoint successfully
4. Failures when token is missing or invalid
5. Submit a single event payload
6. Verify async processing via follow-up queries (polling for state changes)
"""
import os
import time
import uuid
from typing import Dict, Optional

import pytest
import requests


# Base URLs
BASE_ROOT = os.environ.get("API_BASE_ROOT", "http://localhost:8000")
API_BASE = os.environ.get("API_BASE_URL", f"{BASE_ROOT}/api")

# Endpoints (from repository docs)
REGISTER_URL = f"{API_BASE}/auth/register"
LOGIN_URL = f"{API_BASE}/auth/login"
EVENTS_URL = f"{API_BASE}/v1/events"
EVENT_STATS_URL = f"{API_BASE}/v1/events/status/unprocessed"


@pytest.fixture(scope="session")
def http_session() -> requests.Session:
    """Provide a shared HTTP session for connection reuse."""
    sess = requests.Session()
    sess.headers.update({"Accept": "application/json"})
    return sess


@pytest.fixture(scope="session")
def server_ready(http_session: requests.Session):
    """
    Check that the server is up. If not reachable, skip entire test session.
    We use `/openapi.json` as a lightweight readiness probe.
    """
    try:
        resp = http_session.get(f"{BASE_ROOT}/openapi.json", timeout=5)
        if resp.status_code != 200:
            pytest.skip(f"Server not ready: GET /openapi.json -> {resp.status_code}")
    except requests.RequestException as e:
        pytest.skip(f"Server not reachable at {BASE_ROOT}: {e}")


@pytest.fixture(scope="session")
def unique_credentials() -> Dict[str, str]:
    """
    Generate unique user credentials to avoid collisions across runs.
    """
    suffix = uuid.uuid4().hex[:10]
    return {
        "email": f"qa_{suffix}@example.com",
        "username": f"qa_user_{suffix}",
        "password": f"TestPass_{suffix}!",
        "full_name": "QA Tester",
    }


@pytest.fixture(scope="session")
def tokens(server_ready, http_session: requests.Session, unique_credentials: Dict[str, str]) -> Dict[str, str]:
    """
    Register (if possible) and login, returning JWT tokens.
    Handles duplicate registration gracefully by proceeding to login.
    """
    # Attempt registration
    reg_payload = {
        "email": unique_credentials["email"],
        "username": unique_credentials["username"],
        "password": unique_credentials["password"],
        "full_name": unique_credentials["full_name"],
    }
    reg_resp = http_session.post(REGISTER_URL, json=reg_payload, timeout=10)
    if reg_resp.status_code not in (201, 200, 400, 409):  # 400/409 may indicate duplicate
        pytest.fail(f"Registration failed: {reg_resp.status_code} {reg_resp.text}")

    # Login to obtain tokens
    login_payload = {
        "username": unique_credentials["username"],
        "password": unique_credentials["password"],
    }
    login_resp = http_session.post(LOGIN_URL, json=login_payload, timeout=10)
    assert login_resp.status_code == 200, f"Login failed: {login_resp.status_code} {login_resp.text}"
    body = login_resp.json()

    # Expected fields based on repository docs
    assert isinstance(body.get("access_token"), str) and body["access_token"], "Missing access_token"
    # refresh_token may exist depending on implementation; assert if present
    if "refresh_token" in body:
        assert isinstance(body["refresh_token"], str) and body["refresh_token"], "Missing refresh_token"
    if "token_type" in body:
        assert body["token_type"].lower() == "bearer"

    return {
        "access_token": body["access_token"],
        "refresh_token": body.get("refresh_token", ""),
        "token_type": body.get("token_type", "bearer"),
    }


def bearer_headers(access_token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def poll_event_processed(
    session: requests.Session,
    token: str,
    event_id: int,
    timeout_seconds: int = 30,
    interval_seconds: float = 1.0,
) -> Optional[Dict]:
    """
    Poll `/api/v1/events/{id}` until `processed` becomes true or timeout.
    Returns the final event JSON on success, None on timeout.
    """
    deadline = time.time() + timeout_seconds
    url = f"{EVENTS_URL}/{event_id}"

    while time.time() < deadline:
        resp = session.get(url, headers=bearer_headers(token), timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("processed") is True:
                return data
        time.sleep(interval_seconds)

    return None


def test_register_user(server_ready, http_session: requests.Session, unique_credentials: Dict[str, str]):
    """1) Register a user (201 Created or 409 Conflict if already exists)."""
    payload = {
        "email": unique_credentials["email"],
        "username": unique_credentials["username"],
        "password": unique_credentials["password"],
        "full_name": unique_credentials["full_name"],
    }
    resp = http_session.post(REGISTER_URL, json=payload, timeout=10)

    # Accept creation or duplicate; fail on other statuses
    assert resp.status_code in (201, 200, 400, 409), f"Unexpected status: {resp.status_code}, body={resp.text}"


def test_login_obtain_tokens(server_ready, http_session: requests.Session, unique_credentials: Dict[str, str]):
    """2) Login and obtain JWT tokens (expect `access_token`)."""
    payload = {"username": unique_credentials["username"], "password": unique_credentials["password"]}
    resp = http_session.post(LOGIN_URL, json=payload, timeout=10)
    assert resp.status_code == 200, f"Login failed: {resp.status_code} {resp.text}"
    body = resp.json()
    assert isinstance(body.get("access_token"), str) and body["access_token"], "Missing access_token"


def test_protected_endpoint_success(server_ready, http_session: requests.Session, tokens: Dict[str, str]):
    """3) Call a protected endpoint successfully (GET /api/v1/events)."""
    resp = http_session.get(EVENTS_URL, headers=bearer_headers(tokens["access_token"]), timeout=10)
    assert resp.status_code == 200, f"Protected endpoint failed: {resp.status_code} {resp.text}"


def test_protected_endpoint_failures(server_ready, http_session: requests.Session, tokens: Dict[str, str]):
    """4) Fail when token is missing or invalid (GET /api/v1/events)."""
    # No token
    resp_no = http_session.get(EVENTS_URL, timeout=10)
    assert resp_no.status_code in (401, 403), f"Expected 401/403, got {resp_no.status_code}"

    # Invalid token
    resp_bad = http_session.get(EVENTS_URL, headers={"Authorization": "Bearer invalid_token_string"}, timeout=10)
    assert resp_bad.status_code in (401, 403), f"Expected 401/403, got {resp_bad.status_code}"


def test_submit_event_and_verify_async(server_ready, http_session: requests.Session, tokens: Dict[str, str]):
    """
    5) Submit an event payload (POST /api/v1/events, expect 202 Accepted).
    6) Verify async behavior by polling GET /api/v1/events/{id} until `processed` flips to true,
       and cross-check stats or list responses to observe changes.
    """
    # Capture initial stats (optional; ignore failures if endpoint differs)
    initial_unprocessed = None
    stats_resp = http_session.get(EVENT_STATS_URL, headers=bearer_headers(tokens["access_token"]), timeout=10)
    if stats_resp.status_code == 200:
        stats = stats_resp.json()
        initial_unprocessed = stats.get("unprocessed_count")

    # Submit single event
    event_payload = {
        "event_name": "page_view",
        "event_type": "engagement",
        "source": "web",
        "session_id": f"sess_{uuid.uuid4().hex[:8]}",
        "payload": {"page": "/dashboard", "duration": 12, "scroll_depth": 42},
        "ip_address": "127.0.0.1",
        "user_agent": "pytest/black-box-tests",
    }
    post_resp = http_session.post(EVENTS_URL, json=event_payload, headers=bearer_headers(tokens["access_token"]), timeout=10)
    assert post_resp.status_code == 202, f"Event submit failed: {post_resp.status_code} {post_resp.text}"
    post_body = post_resp.json()

    # Basic validations
    assert "event_id" in post_body and isinstance(post_body["event_id"], int)
    assert post_body.get("status") in ("enqueued", "queued", "accepted")

    event_id = post_body["event_id"]

    # Verify event appears in event listing
    list_resp = http_session.get(EVENTS_URL, headers=bearer_headers(tokens["access_token"]), timeout=10)
    assert list_resp.status_code == 200
    maybe_ids = [e.get("id") for e in list_resp.json() if isinstance(e, dict)]
    assert event_id in maybe_ids, "New event not present in listing"

    # Poll for async processing completion
    processed_event = poll_event_processed(http_session, tokens["access_token"], event_id, timeout_seconds=45, interval_seconds=1.5)
    assert processed_event is not None, "Event did not reach processed state within timeout"
    assert processed_event.get("processed") is True
    assert processed_event.get("processed_at") is not None

    # Verify stats reflect progress (if available)
    if initial_unprocessed is not None:
        final_stats_resp = http_session.get(EVENT_STATS_URL, headers=bearer_headers(tokens["access_token"]), timeout=10)
        if final_stats_resp.status_code == 200:
            final_stats = final_stats_resp.json()
            # Generally, unprocessed should decrease or stay the same after processing completes
            assert final_stats.get("unprocessed_count") <= initial_unprocessed
