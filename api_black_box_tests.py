#!/usr/bin/env python3
"""
Black-Box API Testing Suite for PulseBoard Event Ingestion System

Tests the backend as a black-box service with observable HTTP behavior only.
No source code inspection, no implementation assumptions.

Usage:
    python api_black_box_tests.py [--host http://localhost:8000] [--verbose]
"""

import requests
import json
import time
import sys
import argparse
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
import concurrent.futures

# ANSI color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'


class APITester:
    """Black-box API tester for PulseBoard."""
    
    def __init__(self, host: str = "http://localhost:8000", verbose: bool = False):
        self.host = host.rstrip('/')
        self.verbose = verbose
        self.session = requests.Session()
        self.results = {
            'passed': [],
            'failed': [],
            'errors': []
        }
        self.test_user_email = f"testuser_{int(time.time())}@test.com"
        self.test_user_username = f"testuser_{int(time.time())}"
        self.test_user_password = "TestPassword123!"
        self.access_token = None
        self.test_event_ids = []
        
    def log(self, message: str, level: str = "INFO"):
        """Log message with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        if level == "PASS":
            print(f"{GREEN}[{timestamp}] ✓ {message}{RESET}")
        elif level == "FAIL":
            print(f"{RED}[{timestamp}] ✗ {message}{RESET}")
        elif level == "ERROR":
            print(f"{RED}[{timestamp}] ✗ ERROR: {message}{RESET}")
        elif level == "INFO":
            print(f"{BLUE}[{timestamp}] {message}{RESET}")
        elif level == "DEBUG" and self.verbose:
            print(f"{YELLOW}[{timestamp}] DEBUG: {message}{RESET}")
    
    def assert_status(self, response: requests.Response, expected: int, test_name: str) -> bool:
        """Assert response status code."""
        if response.status_code == expected:
            self.log(f"{test_name} - Status {response.status_code}", "PASS")
            self.results['passed'].append(test_name)
            return True
        else:
            self.log(f"{test_name} - Expected {expected}, got {response.status_code}", "FAIL")
            self.log(f"Response: {response.text[:200]}", "DEBUG")
            self.results['failed'].append(test_name)
            return False
    
    def assert_in(self, response: requests.Response, key: str, test_name: str) -> bool:
        """Assert JSON key exists in response."""
        try:
            data = response.json()
            if key in data:
                self.log(f"{test_name} - Key '{key}' found", "PASS")
                self.results['passed'].append(test_name)
                return True
            else:
                self.log(f"{test_name} - Key '{key}' not found. Keys: {list(data.keys())}", "FAIL")
                self.results['failed'].append(test_name)
                return False
        except Exception as e:
            self.log(f"{test_name} - JSON parse error: {e}", "FAIL")
            self.results['failed'].append(test_name)
            return False
    
    def assert_equals(self, actual: Any, expected: Any, test_name: str) -> bool:
        """Assert equality."""
        if actual == expected:
            self.log(f"{test_name} - Value matches ({actual})", "PASS")
            self.results['passed'].append(test_name)
            return True
        else:
            self.log(f"{test_name} - Expected {expected}, got {actual}", "FAIL")
            self.results['failed'].append(test_name)
            return False
    
    def run_test(self, test_func, test_name: str):
        """Run a test function with error handling."""
        try:
            test_func()
        except Exception as e:
            self.log(f"{test_name} - Exception: {e}", "ERROR")
            self.results['errors'].append((test_name, str(e)))
    
    # ==================== Section 1: API Discovery ====================
    
    def test_health_check(self):
        """Test 1.3: Health Check Endpoint"""
        response = self.session.get(f"{self.host}/health")
        
        if self.assert_status(response, 200, "1.3 Health Check"):
            try:
                data = response.json()
                self.assert_equals(data.get('status'), 'healthy', "1.3 Status field")
                self.assert_in(response, 'service', "1.3 Service field")
            except Exception as e:
                self.log(f"1.3 Health Check - JSON error: {e}", "FAIL")
    
    def test_openapi_schema(self):
        """Test 1.2: Get OpenAPI Schema"""
        response = self.session.get(f"{self.host}/openapi.json")
        
        if self.assert_status(response, 200, "1.2 OpenAPI Schema"):
            try:
                data = response.json()
                has_paths = 'paths' in data
                self.log(f"1.2 OpenAPI Schema - Paths found: {has_paths}", "DEBUG")
                self.results['passed'].append("1.2 OpenAPI Schema JSON valid")
            except Exception as e:
                self.log(f"1.2 OpenAPI Schema - JSON error: {e}", "FAIL")
    
    # ==================== Section 2: Authentication ====================
    
    def test_register_user(self):
        """Test 2.1: User Registration"""
        payload = {
            "email": self.test_user_email,
            "username": self.test_user_username,
            "password": self.test_user_password,
            "full_name": "Test User"
        }
        response = self.session.post(
            f"{self.host}/api/auth/register",
            json=payload
        )
        
        if self.assert_status(response, 201, "2.1 User Registration"):
            try:
                data = response.json()
                self.assert_in(response, 'id', "2.1 User ID field")
                self.assert_equals(data.get('email'), self.test_user_email, "2.1 Email matches")
            except Exception as e:
                self.log(f"2.1 User Registration - Error: {e}", "FAIL")
    
    def test_register_duplicate_email(self):
        """Test 2.2: Duplicate Email Rejection"""
        payload = {
            "email": self.test_user_email,
            "username": f"testuser_{int(time.time())+1}",
            "password": "DifferentPassword456!",
            "full_name": "Another User"
        }
        response = self.session.post(
            f"{self.host}/api/auth/register",
            json=payload
        )
        
        # Status should be 400 or 409
        if response.status_code in [400, 409]:
            self.log("2.2 Duplicate Email Rejection - Status OK", "PASS")
            self.results['passed'].append("2.2 Duplicate Email Rejection")
        else:
            self.log(f"2.2 Duplicate Email Rejection - Expected 400/409, got {response.status_code}", "FAIL")
            self.results['failed'].append("2.2 Duplicate Email Rejection")
    
    def test_login_success(self):
        """Test 2.3: User Login Success"""
        payload = {
            "username": self.test_user_username,
            "password": self.test_user_password
        }
        response = self.session.post(
            f"{self.host}/api/auth/login",
            json=payload
        )
        
        if self.assert_status(response, 200, "2.3 User Login Success"):
            try:
                data = response.json()
                self.assert_in(response, 'access_token', "2.3 Access token field")
                
                if 'access_token' in data and data['access_token']:
                    self.access_token = data['access_token']
                    self.log("2.3 Access token saved for subsequent tests", "DEBUG")
            except Exception as e:
                self.log(f"2.3 User Login - Error: {e}", "FAIL")
    
    def test_login_invalid_password(self):
        """Test 2.4: Login with Invalid Password"""
        payload = {
            "username": self.test_user_username,
            "password": "WrongPassword"
        }
        response = self.session.post(
            f"{self.host}/api/auth/login",
            json=payload
        )
        
        self.assert_status(response, 401, "2.4 Invalid Password Rejection")
    
    def test_login_nonexistent_user(self):
        """Test 2.5: Login Non-existent User"""
        payload = {
            "username": "nonexistent_user_12345",
            "password": "AnyPassword"
        }
        response = self.session.post(
            f"{self.host}/api/auth/login",
            json=payload
        )
        
        self.assert_status(response, 401, "2.5 Non-existent User Rejection")
    
    # ==================== Section 3: Authorization ====================
    
    def test_no_token_access(self):
        """Test 3.1: Access Without Token"""
        response = self.session.get(f"{self.host}/api/v1/events")
        
        if response.status_code in [401, 403]:
            self.log("3.1 No Token Access Denied - Status OK", "PASS")
            self.results['passed'].append("3.1 No Token Access Denied")
        else:
            self.log(f"3.1 No Token Access - Expected 401/403, got {response.status_code}", "FAIL")
            self.results['failed'].append("3.1 No Token Access Denied")
    
    def test_invalid_token(self):
        """Test 3.2: Invalid Token Rejection"""
        headers = {"Authorization": "Bearer invalid_token_string"}
        response = self.session.get(f"{self.host}/api/v1/events", headers=headers)
        
        self.assert_status(response, 401, "3.2 Invalid Token Rejection")
    
    def test_malformed_token(self):
        """Test 3.3: Malformed Token Rejection"""
        headers = {"Authorization": "Bearer abc"}
        response = self.session.get(f"{self.host}/api/v1/events", headers=headers)
        
        self.assert_status(response, 401, "3.3 Malformed Token Rejection")
    
    def test_valid_token_access(self):
        """Test 3.4: Access With Valid Token"""
        if not self.access_token:
            self.log("3.4 Valid Token Access - Token not available", "FAIL")
            return
        
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = self.session.get(f"{self.host}/api/v1/events", headers=headers)
        
        self.assert_status(response, 200, "3.4 Valid Token Access")
    
    # ==================== Section 4: Event Ingestion ====================
    
    def test_submit_single_event(self):
        """Test 4.1: Submit Single Valid Event"""
        if not self.access_token:
            self.log("4.1 Submit Event - Token not available", "FAIL")
            return
        
        payload = {
            "event_name": "page_view",
            "event_type": "engagement",
            "source": "web",
            "payload": {
                "page": "/home",
                "duration": 45,
                "scroll_depth": 75
            }
        }
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        response = self.session.post(
            f"{self.host}/api/v1/events",
            json=payload,
            headers=headers
        )
        
        if self.assert_status(response, 202, "4.1 Submit Single Event"):
            try:
                data = response.json()
                self.assert_in(response, 'event_id', "4.1 Event ID field")
                self.assert_in(response, 'task_id', "4.1 Task ID field")
                self.assert_equals(data.get('status'), 'enqueued', "4.1 Status is enqueued")
                
                if 'event_id' in data:
                    self.test_event_ids.append(data['event_id'])
                    self.log(f"4.1 Event ID {data['event_id']} saved", "DEBUG")
            except Exception as e:
                self.log(f"4.1 Submit Event - Error: {e}", "FAIL")
    
    def test_missing_required_field(self):
        """Test 4.2: Missing Required Field"""
        if not self.access_token:
            self.log("4.2 Missing Field - Token not available", "FAIL")
            return
        
        payload = {
            "event_name": "test",
            # Missing event_type
        }
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        response = self.session.post(
            f"{self.host}/api/v1/events",
            json=payload,
            headers=headers
        )
        
        if response.status_code in [422, 400]:
            self.log("4.2 Missing Required Field - Validation OK", "PASS")
            self.results['passed'].append("4.2 Missing Required Field Validation")
        else:
            self.log(f"4.2 Missing Field - Expected 422/400, got {response.status_code}", "FAIL")
            self.results['failed'].append("4.2 Missing Required Field Validation")
    
    def test_empty_event_name(self):
        """Test 4.3: Empty Event Name"""
        if not self.access_token:
            self.log("4.3 Empty Name - Token not available", "FAIL")
            return
        
        payload = {
            "event_name": "",
            "event_type": "engagement"
        }
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        response = self.session.post(
            f"{self.host}/api/v1/events",
            json=payload,
            headers=headers
        )
        
        self.assert_status(response, 422, "4.3 Empty Event Name Validation")
    
    # ==================== Section 5: Batch Events ====================
    
    def test_batch_events(self):
        """Test 5.1: Submit Batch Events"""
        if not self.access_token:
            self.log("5.1 Batch Events - Token not available", "FAIL")
            return
        
        payload = {
            "events": [
                {"event_name": "event_1", "event_type": "type_1"},
                {"event_name": "event_2", "event_type": "type_2"},
                {"event_name": "event_3", "event_type": "type_3"}
            ]
        }
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        response = self.session.post(
            f"{self.host}/api/v1/events/batch",
            json=payload,
            headers=headers
        )
        
        if self.assert_status(response, 202, "5.1 Batch Events Submission"):
            try:
                data = response.json()
                self.assert_equals(data.get('event_count'), 3, "5.1 Event count is 3")
                self.assert_in(response, 'event_ids', "5.1 Event IDs field")
                self.assert_in(response, 'task_id', "5.1 Task ID field")
                
                if 'event_ids' in data:
                    self.test_event_ids.extend(data['event_ids'])
            except Exception as e:
                self.log(f"5.1 Batch Events - Error: {e}", "FAIL")
    
    def test_empty_batch(self):
        """Test 5.2: Empty Batch Rejection"""
        if not self.access_token:
            self.log("5.2 Empty Batch - Token not available", "FAIL")
            return
        
        payload = {"events": []}
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        response = self.session.post(
            f"{self.host}/api/v1/events/batch",
            json=payload,
            headers=headers
        )
        
        self.assert_status(response, 422, "5.2 Empty Batch Rejection")
    
    # ==================== Section 6: Async & Observable Effects ====================
    
    def test_event_before_processing(self):
        """Test 6.2: Event Before Processing"""
        if not self.access_token or not self.test_event_ids:
            self.log("6.2 Event Before Processing - No test events", "FAIL")
            return
        
        event_id = self.test_event_ids[0]
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        response = self.session.get(
            f"{self.host}/api/v1/events/{event_id}",
            headers=headers
        )
        
        if self.assert_status(response, 200, "6.2 Get Event Before Processing"):
            try:
                data = response.json()
                # Immediately after submission, should not be processed
                # (but might be processed by now if very fast)
                self.log(f"6.2 Event processed={data.get('processed')}, processed_at={data.get('processed_at')}", "DEBUG")
            except Exception as e:
                self.log(f"6.2 Get Event - Error: {e}", "FAIL")
    
    def test_event_after_processing(self):
        """Test 6.3: Event After Processing (Observable Effect)"""
        if not self.access_token or not self.test_event_ids:
            self.log("6.3 Event After Processing - No test events", "FAIL")
            return
        
        event_id = self.test_event_ids[0]
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        # Wait for processing
        self.log("6.3 Waiting for async processing...", "INFO")
        time.sleep(3)
        
        response = self.session.get(
            f"{self.host}/api/v1/events/{event_id}",
            headers=headers
        )
        
        if self.assert_status(response, 200, "6.3 Get Event After Processing"):
            try:
                data = response.json()
                processed = data.get('processed')
                processed_at = data.get('processed_at')
                
                if processed:
                    self.log("6.3 Event Processed - Observable effect confirmed", "PASS")
                    self.results['passed'].append("6.3 Event Processing Observable Effect")
                    
                    if processed_at:
                        self.log(f"6.3 Processed at: {processed_at}", "DEBUG")
                        self.assert_in(response, 'properties', "6.3 Properties field")
                else:
                    self.log("6.3 Event Not Yet Processed - Retrying...", "YELLOW")
                    # Retry once
                    time.sleep(2)
                    response = self.session.get(
                        f"{self.host}/api/v1/events/{event_id}",
                        headers=headers
                    )
                    data = response.json()
                    if data.get('processed'):
                        self.log("6.3 Event Processed on Retry", "PASS")
                        self.results['passed'].append("6.3 Event Processing Observable Effect")
                    else:
                        self.log("6.3 Event Still Not Processed After 5s", "FAIL")
                        self.results['failed'].append("6.3 Event Processing Observable Effect")
            except Exception as e:
                self.log(f"6.3 Get Event - Error: {e}", "FAIL")
    
    def test_metadata_attachment(self):
        """Test 6.5: Metadata Attachment Verification"""
        if not self.access_token or not self.test_event_ids:
            self.log("6.5 Metadata - No test events", "FAIL")
            return
        
        event_id = self.test_event_ids[0]
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        response = self.session.get(
            f"{self.host}/api/v1/events/{event_id}",
            headers=headers
        )
        
        if response.status_code == 200:
            try:
                data = response.json()
                properties = data.get('properties')
                
                if properties and isinstance(properties, dict):
                    has_normalized_at = 'normalized_at' in properties
                    self.log(f"6.5 Properties has normalized_at: {has_normalized_at}", "DEBUG")
                    
                    if has_normalized_at:
                        self.log("6.5 Metadata Attachment - normalized_at present", "PASS")
                        self.results['passed'].append("6.5 Metadata Attachment")
                    else:
                        self.log("6.5 Metadata - normalized_at not found", "FAIL")
                        self.log(f"6.5 Properties keys: {list(properties.keys())}", "DEBUG")
                        self.results['failed'].append("6.5 Metadata Attachment")
                else:
                    self.log("6.5 Properties not yet available or not dict", "FAIL")
                    self.results['failed'].append("6.5 Metadata Attachment")
            except Exception as e:
                self.log(f"6.5 Metadata - Error: {e}", "FAIL")
    
    # ==================== Section 8: Retrieval ====================
    
    def test_list_events(self):
        """Test 8.1: List User Events"""
        if not self.access_token:
            self.log("8.1 List Events - Token not available", "FAIL")
            return
        
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = self.session.get(
            f"{self.host}/api/v1/events?limit=10&offset=0",
            headers=headers
        )
        
        if self.assert_status(response, 200, "8.1 List Events"):
            try:
                data = response.json()
                if isinstance(data, list):
                    self.log(f"8.1 Events returned: {len(data)}", "DEBUG")
                    self.results['passed'].append("8.1 List Events Returns Array")
                else:
                    self.log(f"8.1 Expected list, got {type(data)}", "FAIL")
                    self.results['failed'].append("8.1 List Events Returns Array")
            except Exception as e:
                self.log(f"8.1 List Events - Error: {e}", "FAIL")
    
    def test_get_nonexistent_event(self):
        """Test 8.4: Get Non-existent Event"""
        if not self.access_token:
            self.log("8.4 Non-existent Event - Token not available", "FAIL")
            return
        
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = self.session.get(
            f"{self.host}/api/v1/events/999999",
            headers=headers
        )
        
        self.assert_status(response, 404, "8.4 Non-existent Event Not Found")
    
    # ==================== Section 9: Error Handling ====================
    
    def test_malformed_json(self):
        """Test 9.1: Malformed JSON"""
        if not self.access_token:
            self.log("9.1 Malformed JSON - Token not available", "FAIL")
            return
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        # Send invalid JSON
        response = self.session.post(
            f"{self.host}/api/v1/events",
            data='{invalid json}',
            headers=headers
        )
        
        if response.status_code >= 400:
            self.log("9.1 Malformed JSON Rejection - Status OK", "PASS")
            self.results['passed'].append("9.1 Malformed JSON Rejection")
        else:
            self.log(f"9.1 Malformed JSON - Expected >=400, got {response.status_code}", "FAIL")
            self.results['failed'].append("9.1 Malformed JSON Rejection")
    
    def test_method_not_allowed(self):
        """Test 9.3: Method Not Allowed"""
        if not self.access_token:
            self.log("9.3 Method Not Allowed - Token not available", "FAIL")
            return
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        response = self.session.put(
            f"{self.host}/api/v1/events",
            json={},
            headers=headers
        )
        
        if response.status_code in [404, 405]:
            self.log("9.3 Method Not Allowed - Status OK", "PASS")
            self.results['passed'].append("9.3 Method Not Allowed")
        else:
            self.log(f"9.3 Method Not Allowed - Expected 404/405, got {response.status_code}", "FAIL")
            self.results['failed'].append("9.3 Method Not Allowed")
    
    # ==================== Section 10: Concurrency ====================
    
    def test_rapid_submission(self):
        """Test 10.1: Rapid Sequential Submission"""
        if not self.access_token:
            self.log("10.1 Rapid Submission - Token not available", "FAIL")
            return
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        success_count = 0
        
        for i in range(5):
            payload = {
                "event_name": f"rapid_{i}",
                "event_type": "test"
            }
            
            response = self.session.post(
                f"{self.host}/api/v1/events",
                json=payload,
                headers=headers
            )
            
            if response.status_code == 202:
                success_count += 1
                try:
                    data = response.json()
                    if 'event_id' in data:
                        self.test_event_ids.append(data['event_id'])
                except:
                    pass
        
        if success_count == 5:
            self.log("10.1 Rapid Submission - All 5 succeeded", "PASS")
            self.results['passed'].append("10.1 Rapid Submission")
        else:
            self.log(f"10.1 Rapid Submission - {success_count}/5 succeeded", "FAIL")
            self.results['failed'].append("10.1 Rapid Submission")
    
    def test_concurrent_requests(self):
        """Test 10.2: Concurrent Requests"""
        if not self.access_token:
            self.log("10.2 Concurrent Requests - Token not available", "FAIL")
            return
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        def submit_event(i):
            payload = {
                "event_name": f"concurrent_{i}",
                "event_type": "test"
            }
            return self.session.post(
                f"{self.host}/api/v1/events",
                json=payload,
                headers=headers
            )
        
        success_count = 0
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [submit_event(i) for i in range(5)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        for response in results:
            if response.status_code == 202:
                success_count += 1
                try:
                    data = response.json()
                    if 'event_id' in data:
                        self.test_event_ids.append(data['event_id'])
                except:
                    pass
        
        if success_count == 5:
            self.log("10.2 Concurrent Requests - All 5 succeeded", "PASS")
            self.results['passed'].append("10.2 Concurrent Requests")
        else:
            self.log(f"10.2 Concurrent Requests - {success_count}/5 succeeded", "FAIL")
            self.results['failed'].append("10.2 Concurrent Requests")
    
    # ==================== Section 11: Statistics ====================
    
    def test_event_stats(self):
        """Test 11.1: Get Event Statistics"""
        if not self.access_token:
            self.log("11.1 Event Stats - Token not available", "FAIL")
            return
        
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        response = self.session.get(
            f"{self.host}/api/v1/events/status/unprocessed",
            headers=headers
        )
        
        if self.assert_status(response, 200, "11.1 Event Statistics"):
            try:
                data = response.json()
                self.assert_in(response, 'unprocessed_count', "11.1 Unprocessed count field")
                self.assert_in(response, 'total_count', "11.1 Total count field")
            except Exception as e:
                self.log(f"11.1 Event Stats - Error: {e}", "FAIL")
    
    # ==================== Test Execution ====================
    
    def run_all_tests(self):
        """Run all test suites."""
        print(f"\n{BOLD}{BLUE}=== PulseBoard Black-Box API Testing ==={RESET}\n")
        print(f"Host: {self.host}")
        print(f"Test User: {self.test_user_email}\n")
        
        # Section 1: Discovery
        print(f"\n{BOLD}Section 1: API Discovery{RESET}")
        self.run_test(self.test_health_check, "1.3 Health Check")
        self.run_test(self.test_openapi_schema, "1.2 OpenAPI Schema")
        
        # Section 2: Authentication
        print(f"\n{BOLD}Section 2: Authentication{RESET}")
        self.run_test(self.test_register_user, "2.1 Register User")
        self.run_test(self.test_register_duplicate_email, "2.2 Duplicate Email")
        self.run_test(self.test_login_success, "2.3 Login Success")
        self.run_test(self.test_login_invalid_password, "2.4 Invalid Password")
        self.run_test(self.test_login_nonexistent_user, "2.5 Non-existent User")
        
        # Section 3: Authorization
        print(f"\n{BOLD}Section 3: Authorization{RESET}")
        self.run_test(self.test_no_token_access, "3.1 No Token Access")
        self.run_test(self.test_invalid_token, "3.2 Invalid Token")
        self.run_test(self.test_malformed_token, "3.3 Malformed Token")
        self.run_test(self.test_valid_token_access, "3.4 Valid Token Access")
        
        # Section 4: Event Ingestion
        print(f"\n{BOLD}Section 4: Event Ingestion{RESET}")
        self.run_test(self.test_submit_single_event, "4.1 Submit Single Event")
        self.run_test(self.test_missing_required_field, "4.2 Missing Required Field")
        self.run_test(self.test_empty_event_name, "4.3 Empty Event Name")
        
        # Section 5: Batch Events
        print(f"\n{BOLD}Section 5: Batch Events{RESET}")
        self.run_test(self.test_batch_events, "5.1 Batch Events")
        self.run_test(self.test_empty_batch, "5.2 Empty Batch")
        
        # Section 6: Async & Observable Effects
        print(f"\n{BOLD}Section 6: Async & Observable Effects{RESET}")
        self.run_test(self.test_event_before_processing, "6.2 Event Before Processing")
        self.run_test(self.test_event_after_processing, "6.3 Event After Processing")
        self.run_test(self.test_metadata_attachment, "6.5 Metadata Attachment")
        
        # Section 8: Retrieval
        print(f"\n{BOLD}Section 8: Event Retrieval{RESET}")
        self.run_test(self.test_list_events, "8.1 List Events")
        self.run_test(self.test_get_nonexistent_event, "8.4 Non-existent Event")
        
        # Section 9: Error Handling
        print(f"\n{BOLD}Section 9: Error Handling{RESET}")
        self.run_test(self.test_malformed_json, "9.1 Malformed JSON")
        self.run_test(self.test_method_not_allowed, "9.3 Method Not Allowed")
        
        # Section 10: Concurrency
        print(f"\n{BOLD}Section 10: Concurrency{RESET}")
        self.run_test(self.test_rapid_submission, "10.1 Rapid Submission")
        self.run_test(self.test_concurrent_requests, "10.2 Concurrent Requests")
        
        # Section 11: Statistics
        print(f"\n{BOLD}Section 11: Statistics{RESET}")
        self.run_test(self.test_event_stats, "11.1 Event Statistics")
        
        # Print summary
        self.print_summary()
    
    def print_summary(self):
        """Print test results summary."""
        print(f"\n{BOLD}{'=' * 60}{RESET}")
        print(f"{BOLD}Test Results Summary{RESET}")
        print(f"{BOLD}{'=' * 60}{RESET}\n")
        
        passed = len(self.results['passed'])
        failed = len(self.results['failed'])
        errors = len(self.results['errors'])
        total = passed + failed + errors
        
        print(f"{GREEN}✓ Passed: {passed}/{total}{RESET}")
        print(f"{RED}✗ Failed: {failed}/{total}{RESET}")
        print(f"{RED}✗ Errors: {errors}/{total}{RESET}\n")
        
        if self.results['failed']:
            print(f"{BOLD}Failed Tests:{RESET}")
            for test in self.results['failed']:
                print(f"  {RED}✗ {test}{RESET}")
        
        if self.results['errors']:
            print(f"\n{BOLD}Errors:{RESET}")
            for test, error in self.results['errors']:
                print(f"  {RED}✗ {test}: {error}{RESET}")
        
        success_rate = (passed / total * 100) if total > 0 else 0
        print(f"\n{BOLD}Success Rate: {success_rate:.1f}%{RESET}\n")
        
        if failed == 0 and errors == 0:
            print(f"{GREEN}{BOLD}✓ All tests passed!{RESET}\n")
        else:
            print(f"{RED}{BOLD}✗ Some tests failed. Review details above.{RESET}\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Black-box API testing suite for PulseBoard"
    )
    parser.add_argument(
        "--host",
        default="http://localhost:8000",
        help="Backend host (default: http://localhost:8000)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output with debug messages"
    )
    
    args = parser.parse_args()
    
    tester = APITester(host=args.host, verbose=args.verbose)
    
    try:
        tester.run_all_tests()
    except KeyboardInterrupt:
        print(f"\n{RED}Tests interrupted by user{RESET}\n")
        sys.exit(1)
    except Exception as e:
        print(f"{RED}Fatal error: {e}{RESET}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
