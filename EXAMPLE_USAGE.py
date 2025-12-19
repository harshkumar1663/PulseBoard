#!/usr/bin/env python3
"""
Example usage of the async event ingestion system.

This script demonstrates how to:
1. Register a user
2. Obtain JWT tokens
3. Submit events to the API
4. Monitor processing status
"""

import requests
import json
from datetime import datetime
import time

# Configuration
BASE_URL = "http://localhost:8000"
API_URL = f"{BASE_URL}/api"

# Sample credentials
TEST_USER = {
    "email": "test@example.com",
    "password": "testpassword123"
}


def register_user():
    """Register a new user."""
    url = f"{API_URL}/auth/register"
    response = requests.post(
        url,
        json={
            "email": TEST_USER["email"],
            "password": TEST_USER["password"],
            "full_name": "Test User"
        }
    )
    if response.status_code == 201:
        print("✓ User registered successfully")
        return response.json()
    else:
        print(f"✗ Registration failed: {response.text}")
        return None


def login_user():
    """Login and get access token."""
    url = f"{API_URL}/auth/login"
    response = requests.post(
        url,
        json={
            "email": TEST_USER["email"],
            "password": TEST_USER["password"]
        }
    )
    if response.status_code == 200:
        data = response.json()
        print("✓ Login successful")
        return data["access_token"]
    else:
        print(f"✗ Login failed: {response.text}")
        return None


def submit_single_event(token):
    """Submit a single event for async processing."""
    url = f"{API_URL}/v1/events"
    headers = {"Authorization": f"Bearer {token}"}
    
    event_payload = {
        "event_name": "page_view",
        "event_type": "engagement",
        "source": "web",
        "session_id": "sess_12345",
        "payload": {
            "page": "/dashboard",
            "duration": 45,
            "scroll_depth": 75
        },
        "ip_address": "192.168.1.1",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    
    response = requests.post(url, json=event_payload, headers=headers)
    
    if response.status_code == 202:
        data = response.json()
        print(f"✓ Event submitted successfully")
        print(f"  Event ID: {data['event_id']}")
        print(f"  Task ID: {data['task_id']}")
        print(f"  Status: {data['status']}")
        return data
    else:
        print(f"✗ Event submission failed: {response.text}")
        return None


def submit_batch_events(token):
    """Submit multiple events in batch."""
    url = f"{API_URL}/v1/events/batch"
    headers = {"Authorization": f"Bearer {token}"}
    
    events = [
        {
            "event_name": "page_view",
            "event_type": "engagement",
            "source": "web",
            "payload": {"page": "/home", "duration": 10}
        },
        {
            "event_name": "button_click",
            "event_type": "interaction",
            "source": "web",
            "payload": {"button_id": "btn_1", "label": "Sign Up"}
        },
        {
            "event_name": "form_submit",
            "event_type": "conversion",
            "source": "web",
            "payload": {"form_id": "form_contact", "fields": 5}
        }
    ]
    
    response = requests.post(
        url,
        json={"events": events},
        headers=headers
    )
    
    if response.status_code == 202:
        data = response.json()
        print(f"✓ Batch submitted successfully")
        print(f"  Event count: {data['event_count']}")
        print(f"  Event IDs: {data['event_ids']}")
        print(f"  Task ID: {data['task_id']}")
        return data
    else:
        print(f"✗ Batch submission failed: {response.text}")
        return None


def get_event(token, event_id):
    """Retrieve event by ID."""
    url = f"{API_URL}/v1/events/{event_id}"
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        event = response.json()
        print(f"✓ Event retrieved")
        print(f"  ID: {event['id']}")
        print(f"  Name: {event['event_name']}")
        print(f"  Type: {event['event_type']}")
        print(f"  Processed: {event['processed']}")
        print(f"  Processed at: {event['processed_at']}")
        return event
    else:
        print(f"✗ Failed to retrieve event: {response.text}")
        return None


def list_user_events(token):
    """List events for current user."""
    url = f"{API_URL}/v1/events"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"limit": 10, "offset": 0}
    
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        events = response.json()
        print(f"✓ Retrieved {len(events)} events")
        for event in events[:5]:  # Show first 5
            print(f"  - {event['event_name']} ({event['event_type']}) - Processed: {event['processed']}")
        return events
    else:
        print(f"✗ Failed to list events: {response.text}")
        return None


def get_event_stats(token):
    """Get event processing statistics."""
    url = f"{API_URL}/v1/events/status/unprocessed"
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        stats = response.json()
        print(f"✓ Event statistics")
        print(f"  Unprocessed: {stats['unprocessed_count']}")
        print(f"  Total: {stats['total_count']}")
        return stats
    else:
        print(f"✗ Failed to get stats: {response.text}")
        return None


def main():
    """Run example workflow."""
    print("=" * 60)
    print("Async Event Ingestion System - Example Usage")
    print("=" * 60)
    print()
    
    # 1. Register user
    print("1. Registering user...")
    user = register_user()
    if not user:
        print("Failed to register user. Trying login instead...")
    print()
    
    # 2. Login and get token
    print("2. Logging in...")
    token = login_user()
    if not token:
        return
    print()
    
    # 3. Submit single event
    print("3. Submitting single event...")
    event_result = submit_single_event(token)
    if event_result:
        event_id = event_result["event_id"]
        task_id = event_result["task_id"]
    print()
    
    # 4. Submit batch events
    print("4. Submitting batch events...")
    batch_result = submit_batch_events(token)
    if batch_result:
        batch_event_ids = batch_result["event_ids"]
    print()
    
    # 5. Wait for processing
    print("5. Waiting for async processing...")
    time.sleep(3)
    print()
    
    # 6. Retrieve single event
    print("6. Retrieving single event...")
    if event_result:
        get_event(token, event_id)
    print()
    
    # 7. List user events
    print("7. Listing user events...")
    list_user_events(token)
    print()
    
    # 8. Get statistics
    print("8. Getting event statistics...")
    get_event_stats(token)
    print()
    
    print("=" * 60)
    print("✓ Example completed successfully!")
    print("=" * 60)
    print()
    print("API Endpoints:")
    print(f"  POST   {BASE_URL}/api/v1/events              - Submit single event")
    print(f"  POST   {BASE_URL}/api/v1/events/batch       - Submit batch events")
    print(f"  GET    {BASE_URL}/api/v1/events            - List user events")
    print(f"  GET    {BASE_URL}/api/v1/events/{{id}}      - Get event by ID")
    print(f"  GET    {BASE_URL}/api/v1/events/status/unprocessed - Get stats")
    print()
    print("UI Tools:")
    print(f"  API Docs:     {BASE_URL}/docs")
    print(f"  Flower:       http://localhost:5555")
    print()


if __name__ == "__main__":
    main()
