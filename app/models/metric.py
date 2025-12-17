"""Metric model for aggregated analytics."""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, DateTime, Float, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base


class Metric(Base):
    """Metric model for storing aggregated analytics data."""
    
    __tablename__ = "metrics"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    # Metric identification
    metric_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    metric_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # counter, gauge, histogram
    
    # Metric value
    value: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Dimensions for grouping and filtering
    dimensions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Tags for additional metadata
    tags: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Time granularity
    time_bucket: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # minute, hour, day
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    
    # Aggregation metadata
    count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    min_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sum_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
    
    # Composite indexes for efficient querying
    __table_args__ = (
        Index('idx_metric_name_time', 'metric_name', 'timestamp'),
        Index('idx_metric_type_time', 'metric_type', 'timestamp'),
        Index('idx_time_bucket_timestamp', 'time_bucket', 'timestamp'),
    )
    
    def __repr__(self) -> str:
        return f"<Metric {self.metric_name}={self.value} at {self.timestamp}>"
