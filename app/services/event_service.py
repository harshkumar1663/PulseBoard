"""Event service for business logic."""
import logging
from datetime import datetime
from typing import Optional, List
from uuid import UUID as UUIDType

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event
from app.schemas.event import EventCreate, EventResponse

logger = logging.getLogger(__name__)


class EventService:
    """Service for managing events."""
    
    async def create(self, db: AsyncSession, event_in: EventCreate, user_id: UUIDType) -> Event:
        """Create a new event."""
        db_event = Event(
            user_id=user_id,
            event_name=event_in.event_name,
            event_type=event_in.event_type,
            source=event_in.source,
            session_id=event_in.session_id,
            payload=event_in.payload or {},
            properties=event_in.properties,
            ip_address=event_in.ip_address,
            user_agent=event_in.user_agent,
            event_timestamp=event_in.event_timestamp or datetime.utcnow(),
        )
        db.add(db_event)
        await db.flush()
        return db_event
    
    async def get_by_id(self, db: AsyncSession, event_id: int) -> Optional[Event]:
        """Get event by ID."""
        stmt = select(Event).where(Event.id == event_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_by_user_id(
        self,
        db: AsyncSession,
        user_id: UUIDType,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Event]:
        """Get events for a user."""
        stmt = (
            select(Event)
            .where(Event.user_id == user_id)
            .order_by(Event.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(stmt)
        return result.scalars().all()
    
    async def get_unprocessed(
        self,
        db: AsyncSession,
        limit: int = 100,
    ) -> List[Event]:
        """Get unprocessed events."""
        stmt = (
            select(Event)
            .where(Event.processed == False)
            .order_by(Event.created_at.asc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return result.scalars().all()
    
    async def get_by_session(
        self,
        db: AsyncSession,
        user_id: UUIDType,
        session_id: str,
    ) -> List[Event]:
        """Get events by session."""
        stmt = select(Event).where(
            and_(
                Event.user_id == user_id,
                Event.session_id == session_id
            )
        ).order_by(Event.event_timestamp.asc())
        result = await db.execute(stmt)
        return result.scalars().all()
    
    async def get_by_type(
        self,
        db: AsyncSession,
        user_id: UUIDType,
        event_type: str,
        limit: int = 100,
    ) -> List[Event]:
        """Get events by type."""
        stmt = (
            select(Event)
            .where(
                and_(
                    Event.user_id == user_id,
                    Event.event_type == event_type
                )
            )
            .order_by(Event.event_timestamp.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return result.scalars().all()
    
    async def count_unprocessed(self, db: AsyncSession) -> int:
        """Count unprocessed events."""
        stmt = select(func.count(Event.id)).where(Event.processed == False)
        result = await db.execute(stmt)
        return result.scalar() or 0
    
    async def count_by_user(self, db: AsyncSession, user_id: UUIDType) -> int:
        """Count events for user."""
        stmt = select(func.count(Event.id)).where(Event.user_id == user_id)
        result = await db.execute(stmt)
        return result.scalar() or 0
    
    async def mark_processed(
        self,
        db: AsyncSession,
        event_id: int,
        processed_at: Optional[datetime] = None,
    ) -> Optional[Event]:
        """Mark event as processed."""
        event = await self.get_by_id(db, event_id)
        if event:
            event.processed = True
            event.processed_at = processed_at or datetime.utcnow()
            await db.flush()
        return event
    
    async def update_error(
        self,
        db: AsyncSession,
        event_id: int,
        error: str,
    ) -> Optional[Event]:
        """Update event processing error."""
        event = await self.get_by_id(db, event_id)
        if event:
            event.processing_error = error[:255]
            await db.flush()
        return event
    
    async def delete(self, db: AsyncSession, event_id: int) -> bool:
        """Delete event."""
        event = await self.get_by_id(db, event_id)
        if event:
            await db.delete(event)
            return True
        return False

event_service = EventService()
