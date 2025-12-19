"""API package initialization."""
from fastapi import APIRouter
from app.api import auth, users
from app.api.v1 import events as v1_events

api_router = APIRouter()

# Include all route modules
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(v1_events.router)

__all__ = ["api_router"]
