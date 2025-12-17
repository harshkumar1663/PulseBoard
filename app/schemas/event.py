"""Event schemas for request/response validation."""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class EventBase(BaseModel):
    """Base event schema."""
    event_name: str = Field(..., min_length=1, max_length=255)
    event_type: str = Field(..., min_length=1, max_length=100)
    source: Optional[str] = Field(None, max_length=100)
    session_id: Optional[str] = Field(None, max_length=255)
    properties: Optional[Dict[str, Any]] = None


class EventCreate(EventBase):
    """Schema for creating a new event."""
    event_timestamp: Optional[datetime] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class EventBatchCreate(BaseModel):
    """Schema for batch event creation."""
    events: list[EventCreate] = Field(..., min_length=1, max_length=100)


class EventResponse(EventBase):
    """Schema for event response."""
    id: int
    user_id: int
    event_timestamp: datetime
    created_at: datetime
    processed: bool
    processed_at: Optional[datetime] = None
    
    model_config = {"from_attributes": True}


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
