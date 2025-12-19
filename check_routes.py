#!/usr/bin/env python3
"""Check registered routes."""

try:
    from app.api import api_router
    print(f"api_router loaded: {api_router}")
    print(f"Number of routes: {len(api_router.routes)}")
    for route in api_router.routes:
        print(f"Route: {route.path}")
except Exception as e:
    print(f"Error loading api_router: {e}")
    import traceback
    traceback.print_exc()
