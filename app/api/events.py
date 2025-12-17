"""Event routes."""
from typing import List
from fastapi import APIRouter, Depends, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_active_user
from app.models.user import User
from app.schemas.event import EventCreate, EventBatchCreate, EventResponse, EventFilter
from app.services.event_service import event_service
from app.workers.tasks import process_event_task

router = APIRouter(prefix="/events", tags=["Events"])


@router.post("/", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    event_in: EventCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Ingest a single event."""
    # Extract client info
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    # Create event
    event = await event_service.create(
        db,
        user_id=current_user.id,
        event_in=event_in,
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    # Queue for async processing
    process_event_task.delay(event.id)
    
    return event


@router.post("/batch", response_model=List[EventResponse], status_code=status.HTTP_201_CREATED)
async def create_events_batch(
    batch_in: EventBatchCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Ingest multiple events in batch."""
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    events = await event_service.create_batch(
        db,
        user_id=current_user.id,
        events_in=batch_in.events,
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    # Queue each event for async processing
    for event in events:
        process_event_task.delay(event.id)
    
    return events


@router.get("/", response_model=List[EventResponse])
async def get_events(
    filters: EventFilter = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get user's events with filters."""
    events = await event_service.get_user_events(db, current_user.id, filters)
    return events


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific event."""
    event = await event_service.get_by_id(db, event_id)
    
    if not event or event.user_id != current_user.id:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    
    return event
