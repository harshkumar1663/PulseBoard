"""Metric schemas for request/response validation."""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class MetricBase(BaseModel):
    """Base metric schema."""
    metric_name: str = Field(..., min_length=1, max_length=255)
    metric_type: str = Field(..., pattern="^(counter|gauge|histogram)$")
    value: float
    dimensions: Optional[Dict[str, Any]] = None
    tags: Optional[Dict[str, Any]] = None


class MetricCreate(MetricBase):
    """Schema for creating a new metric."""
    time_bucket: str = Field(default="minute", pattern="^(minute|hour|day)$")
    timestamp: Optional[datetime] = None


class MetricResponse(MetricBase):
    """Schema for metric response."""
    id: int
    time_bucket: str
    timestamp: datetime
    count: int
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    sum_value: Optional[float] = None
    avg_value: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}


class MetricFilter(BaseModel):
    """Schema for filtering metrics."""
    metric_name: Optional[str] = None
    metric_type: Optional[str] = None
    time_bucket: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    dimensions: Optional[Dict[str, Any]] = None
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


class MetricAggregation(BaseModel):
    """Schema for metric aggregation response."""
    metric_name: str
    metric_type: str
    time_bucket: str
    total_count: int
    total_sum: float
    average: float
    minimum: float
    maximum: float
    start_time: datetime
    end_time: datetime


class MetricUpdate(BaseModel):
    """Schema for real-time metric update via WebSocket."""
    metric_name: str
    value: float
    timestamp: datetime
    dimensions: Optional[Dict[str, Any]] = None
