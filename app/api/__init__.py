"""API package initialization."""
from fastapi import APIRouter
from app.api import auth, users, events, metrics, websocket

api_router = APIRouter()

# Include all route modules
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(events.router)
api_router.include_router(metrics.router)
api_router.include_router(websocket.router)

__all__ = ["api_router"]
