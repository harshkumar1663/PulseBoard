"""WebSocket endpoint for real-time metric updates."""
import json
import asyncio
from typing import Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from redis.asyncio import Redis

from app.db.redis import redis_client
from app.core.security import decode_token

router = APIRouter(prefix="/ws", tags=["WebSocket"])


class ConnectionManager:
    """Manages WebSocket connections and broadcasts."""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket):
        """Accept and store WebSocket connection."""
        await websocket.accept()
        self.active_connections.add(websocket)
    
    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection."""
        self.active_connections.discard(websocket)
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients."""
        disconnected = set()
        
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.add(connection)
        
        # Clean up disconnected clients
        for connection in disconnected:
            self.disconnect(connection)


manager = ConnectionManager()


async def verify_websocket_token(token: str) -> bool:
    """Verify JWT token for WebSocket connection."""
    try:
        payload = decode_token(token)
        return payload.get("sub") is not None
    except Exception:
        return False


async def redis_listener():
    """Listen to Redis pub/sub for metric updates."""
    pubsub = redis_client.redis.pubsub()
    await pubsub.subscribe("metrics:updates")
    
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    await manager.broadcast(data)
                except json.JSONDecodeError:
                    pass
    finally:
        await pubsub.unsubscribe("metrics:updates")
        await pubsub.close()


@router.websocket("/metrics")
async def websocket_metrics_endpoint(
    websocket: WebSocket,
    token: str = Query(...)
):
    """WebSocket endpoint for real-time metric updates.
    
    Clients must provide a valid JWT token as a query parameter.
    Broadcasts metric updates published to Redis channel 'metrics:updates'.
    """
    # Verify token
    if not await verify_websocket_token(token):
        await websocket.close(code=4001, reason="Unauthorized")
        return
    
    await manager.connect(websocket)
    
    # Start Redis listener if first connection
    if len(manager.active_connections) == 1:
        asyncio.create_task(redis_listener())
    
    try:
        # Keep connection alive and handle client messages
        while True:
            data = await websocket.receive_text()
            
            # Optional: Handle client messages (e.g., subscribe to specific metrics)
            try:
                message = json.loads(data)
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except json.JSONDecodeError:
                pass
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
