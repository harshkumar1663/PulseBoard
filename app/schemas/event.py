"""Event schemas for request/response validation."""
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID as UUIDType
from pydantic import BaseModel, Field, validator


class EventBase(BaseModel):
    """Base schema for events."""
    event_name: str
    event_type: str
    source: Optional[str] = None


class EventCreate(BaseModel):
    """Schema for creating a single event."""
    event_name: str = Field(..., min_length=1, max_length=255, description="Event name")
    event_type: str = Field(..., min_length=1, max_length=100, description="Event type/category")
    source: Optional[str] = Field(None, max_length=100, description="Event source")
    session_id: Optional[str] = Field(None, max_length=255, description="Session identifier")
    payload: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Event payload as JSONB")
    properties: Optional[Dict[str, Any]] = Field(None, description="Normalized properties")
    event_timestamp: Optional[datetime] = Field(None, description="Event occurrence time")
    ip_address: Optional[str] = Field(None, max_length=45, description="Client IP address")
    user_agent: Optional[str] = Field(None, description="Client user agent string")

    @validator("payload", pre=True, always=True)
    def default_payload(cls, v):
        return v or {}

    class Config:
        json_schema_extra = {
            "example": {
                "event_name": "page_view",
                "event_type": "engagement",
                "source": "web",
                "session_id": "sess_123",
                "payload": {"page": "/dashboard", "duration": 45},
                "event_timestamp": "2025-12-18T10:30:00Z",
                "ip_address": "192.168.1.1",
                "user_agent": "Mozilla/5.0..."
            }
        }


class EventBatchCreate(BaseModel):
    """Schema for batch event creation."""
    events: list[EventCreate] = Field(..., min_length=1, max_length=100, description="List of events to create")

    class Config:
        json_schema_extra = {
            "example": {
                "events": [
                    {
                        "event_name": "page_view",
                        "event_type": "engagement",
                        "payload": {"page": "/home"}
                    }
                ]
            }
        }


class EventResponse(BaseModel):
    """Schema for event response."""
    id: int
    user_id: UUIDType
    event_name: str
    event_type: str
    source: Optional[str] = None
    session_id: Optional[str] = None
    payload: Dict[str, Any]
    properties: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    event_timestamp: datetime
    created_at: datetime
    processed: bool
    processed_at: Optional[datetime] = None
    processing_error: Optional[str] = None
    
    model_config = {"from_attributes": True}


class EventEnqueueResponse(BaseModel):
    """Schema for event enqueue response."""
    event_id: int
    task_id: str
    status: str = "enqueued"
    message: str = "Event enqueued for processing"

    class Config:
        json_schema_extra = {
            "example": {
                "event_id": 1,
                "task_id": "task_uuid_here",
                "status": "enqueued",
                "message": "Event enqueued for processing"
            }
        }


class EventFilter(BaseModel):
    """Schema for filtering events."""
    event_name: Optional[str] = None
    event_type: Optional[str] = None
    source: Optional[str] = None
    session_id: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    processed: Optional[bool] = None
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
