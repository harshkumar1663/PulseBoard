"""Event service for business logic."""
from datetime import datetime
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.event import Event
from app.schemas.event import EventCreate, EventFilter
from app.db.redis import redis_client


class EventService:
    """Service layer for event operations."""
    
    @staticmethod
    async def create(
        db: AsyncSession,
        user_id: int,
        event_in: EventCreate,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Event:
        """Create new event."""
        event = Event(
            user_id=user_id,
            event_name=event_in.event_name,
            event_type=event_in.event_type,
            source=event_in.source,
            session_id=event_in.session_id,
            properties=event_in.properties,
            ip_address=ip_address or event_in.ip_address,
            user_agent=user_agent or event_in.user_agent,
            event_timestamp=event_in.event_timestamp or datetime.utcnow(),
        )
        
        db.add(event)
        await db.commit()
        await db.refresh(event)
        
        # Cache event for real-time processing
        await redis_client.set(
            f"event:{event.id}",
            {
                "id": event.id,
                "user_id": event.user_id,
                "event_name": event.event_name,
                "event_type": event.event_type,
                "timestamp": event.event_timestamp.isoformat(),
            },
            expire=3600  # 1 hour
        )
        
        return event
    
    @staticmethod
    async def create_batch(
        db: AsyncSession,
        user_id: int,
        events_in: List[EventCreate],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> List[Event]:
        """Create multiple events in batch."""
        events = []
        for event_in in events_in:
            event = Event(
                user_id=user_id,
                event_name=event_in.event_name,
                event_type=event_in.event_type,
                source=event_in.source,
                session_id=event_in.session_id,
                properties=event_in.properties,
                ip_address=ip_address or event_in.ip_address,
                user_agent=user_agent or event_in.user_agent,
                event_timestamp=event_in.event_timestamp or datetime.utcnow(),
            )
            events.append(event)
        
        db.add_all(events)
        await db.commit()
        
        # Refresh all events
        for event in events:
            await db.refresh(event)
        
        return events
    
    @staticmethod
    async def get_by_id(db: AsyncSession, event_id: int) -> Optional[Event]:
        """Get event by ID."""
        result = await db.execute(select(Event).where(Event.id == event_id))
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_user_events(
        db: AsyncSession,
        user_id: int,
        filters: EventFilter
    ) -> List[Event]:
        """Get events for a user with filters."""
        query = select(Event).where(Event.user_id == user_id)
        
        # Apply filters
        conditions = []
        if filters.event_name:
            conditions.append(Event.event_name == filters.event_name)
        if filters.event_type:
            conditions.append(Event.event_type == filters.event_type)
        if filters.source:
            conditions.append(Event.source == filters.source)
        if filters.session_id:
            conditions.append(Event.session_id == filters.session_id)
        if filters.start_date:
            conditions.append(Event.event_timestamp >= filters.start_date)
        if filters.end_date:
            conditions.append(Event.event_timestamp <= filters.end_date)
        if filters.processed is not None:
            conditions.append(Event.processed == filters.processed)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(Event.event_timestamp.desc())
        query = query.limit(filters.limit).offset(filters.offset)
        
        result = await db.execute(query)
        return list(result.scalars().all())
    
    @staticmethod
    async def mark_processed(db: AsyncSession, event_id: int) -> Optional[Event]:
        """Mark event as processed."""
        event = await EventService.get_by_id(db, event_id)
        if event:
            event.processed = True
            event.processed_at = datetime.utcnow()
            await db.commit()
            await db.refresh(event)
        return event


event_service = EventService()
