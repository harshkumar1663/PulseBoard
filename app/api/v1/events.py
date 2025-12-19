"""Event ingestion API endpoints."""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_user
from app.models.user import User
from app.schemas.event import EventCreate, EventBatchCreate, EventResponse, EventEnqueueResponse
from app.services.event_service import event_service
from app.workers.tasks import process_event, process_events_batch
from app.db.session import engine, Base

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/events", tags=["events"])


async def _ensure_tables() -> None:
    """Create tables if they do not exist (idempotent, safeguards missing migrations)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def _dispatch_task_safely(task_func, *args) -> Optional[str]:
    """Try to dispatch a Celery task but never fail the HTTP request if broker is down."""
    try:
        task = task_func(*args)
        return str(task.id)
    except Exception as exc:  # pragma: no cover - defensive guard for broker outages
        logger.warning("Celery dispatch failed; continuing without queue", exc_info=exc)
        return None


@router.post(
    "",
    response_model=EventEnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest a single event",
    description="Submit a single event for async processing. Returns immediately with task ID.",
)
async def ingest_event(
    event_in: EventCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    request: Request = None,
) -> EventEnqueueResponse:
    """
    Submit a single event for async processing.
    
    - **JWT Required**: Yes
    - **Async Processing**: Yes
    - **Non-blocking**: Returns immediately with task ID
    
    The event will be:
    1. Stored in database immediately
    2. Enqueued for async processing
    3. Processed by Celery worker asynchronously
    """
    try:
        await _ensure_tables()
        
        # Extract client info from request
        ip_address = event_in.ip_address or (
            request.headers.get("x-forwarded-for", "").split(",")[0].strip()
            if request
            else None
        )
        user_agent = event_in.user_agent or (request.headers.get("user-agent") if request else None)
        
        # Set user_agent and ip_address if provided in request
        event_in.user_agent = user_agent
        event_in.ip_address = ip_address
        
        # Create event record (no blocking DB writes)
        db_event = await event_service.create(db, event_in, current_user.id)
        await db.commit()
        
        logger.info(f"Event {db_event.id} created for user {current_user.id}")
        
        # Enqueue async processing task immediately (non-blocking). If broker is down, continue.
        task_id = _dispatch_task_safely(process_event.delay, db_event.id)
        status_label = "enqueued" if task_id else "stored"
        message = "Event enqueued for processing" if task_id else "Event stored; queue unavailable"
        
        logger.info(f"Event {db_event.id} dispatched status={status_label} task_id={task_id}")
        
        return EventEnqueueResponse(
            event_id=db_event.id,
            task_id=task_id or "n/a",
            status=status_label,
            message=message,
        )
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error ingesting event: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to ingest event",
        )


@router.post(
    "/batch",
    response_model=dict,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest multiple events",
    description="Submit multiple events in batch for async processing.",
)
async def ingest_events_batch(
    batch_in: EventBatchCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    request: Request = None,
) -> dict:
    """
    Submit multiple events in batch for async processing.
    
    - **JWT Required**: Yes
    - **Async Processing**: Yes
    - **Batch Size**: 1-100 events per request
    """
    try:
        await _ensure_tables()
        
        if not batch_in.events:
            raise ValueError("No events provided")
        
        # Extract client info
        ip_address = (
            request.headers.get("x-forwarded-for", "").split(",")[0].strip()
            if request
            else None
        )
        user_agent = request.headers.get("user-agent") if request else None
        
        # Create event records
        created_events = []
        event_ids = []
        
        for event_in in batch_in.events:
            event_in.user_agent = event_in.user_agent or user_agent
            event_in.ip_address = event_in.ip_address or ip_address
            
            db_event = await event_service.create(db, event_in, current_user.id)
            created_events.append(db_event)
            event_ids.append(db_event.id)
        
        await db.commit()
        
        logger.info(f"Batch of {len(created_events)} events created for user {current_user.id}")
        
        # Enqueue batch processing task (best-effort)
        task_id = _dispatch_task_safely(process_events_batch.delay, event_ids)
        status_label = "enqueued" if task_id else "stored"
        message = (
            f"Batch of {len(created_events)} events enqueued for processing"
            if task_id
            else f"Batch stored; queue unavailable"
        )
        
        logger.info(f"Batch of {len(event_ids)} events dispatched status={status_label} task_id={task_id}")
        
        return {
            "event_count": len(created_events),
            "event_ids": event_ids,
            "task_id": task_id or "n/a",
            "status": status_label,
            "message": message,
        }
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error ingesting batch: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to ingest events batch",
        )


@router.get(
    "/{event_id}",
    response_model=EventResponse,
    summary="Get event by ID",
    description="Retrieve a specific event by ID.",
)
async def get_event(
    event_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EventResponse:
    """
    Retrieve a specific event by ID.
    
    - **JWT Required**: Yes
    - **Authorization**: User can only access their own events
    """
    try:
        await _ensure_tables()
        event = await event_service.get_by_id(db, event_id)
        
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found",
            )
        
        if event.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )
        
        return EventResponse.model_validate(event)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving event: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve event",
        )


@router.get(
    "",
    response_model=List[EventResponse],
    summary="List user events",
    description="Retrieve events for the current user with optional pagination.",
)
async def list_user_events(
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[EventResponse]:
    """
    Retrieve events for the current user.
    
    - **JWT Required**: Yes
    - **Pagination**: Supports limit and offset
    - **Default Limit**: 100
    """
    try:
        await _ensure_tables()
        if limit < 1 or limit > 1000:
            raise ValueError("Limit must be between 1 and 1000")
        if offset < 0:
            raise ValueError("Offset must be non-negative")
        
        events = await event_service.get_by_user_id(
            db,
            current_user.id,
            limit=limit,
            offset=offset,
        )
        
        return [EventResponse.model_validate(event) for event in events]
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error listing events: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve events",
        )


@router.get(
    "/status/unprocessed",
    response_model=dict,
    summary="Get unprocessed event count",
    description="Get count of events pending processing.",
)
async def get_unprocessed_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get count of events pending processing for current user.
    
    - **JWT Required**: Yes
    - **Use Case**: Monitor processing queue
    """
    try:
        await _ensure_tables()
        count = await event_service.count_unprocessed(db)
        total_count = await event_service.count_by_user(db, current_user.id)
        
        return {
            "unprocessed_count": count,
            "total_count": total_count,
            "user_id": current_user.id,
        }
        
    except Exception as e:
        logger.error(f"Error getting event counts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve event counts",
        )
