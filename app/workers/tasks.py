"""Celery tasks for async event processing."""
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.workers.celery_app import celery_app
from app.db.session import sync_session_maker
from app.models.event import Event
from app.models.user import User
from app.core.config import settings

logger = logging.getLogger(__name__)


class PayloadValidationError(Exception):
    """Raised when event payload validation fails."""
    pass


def validate_payload_shape(payload: Any) -> dict:
    """
    Validate event payload shape and structure.
    
    - Must be dict or None
    - All values must be JSON-serializable
    - Max depth: 10 levels
    - Max size: 1MB
    """
    if payload is None:
        return {}
    
    if not isinstance(payload, dict):
        raise PayloadValidationError(f"Payload must be dict, got {type(payload).__name__}")
    
    # Check JSON serializability
    try:
        payload_json = json.dumps(payload)
    except (TypeError, ValueError) as e:
        raise PayloadValidationError(f"Payload not JSON-serializable: {str(e)}")
    
    # Check size limit (1MB)
    if len(payload_json) > 1024 * 1024:
        raise PayloadValidationError("Payload exceeds 1MB size limit")
    
    # Validate depth (max 10 levels)
    def check_depth(obj, depth=0):
        if depth > 10:
            raise PayloadValidationError("Payload exceeds max nesting depth (10)")
        if isinstance(obj, dict):
            for v in obj.values():
                check_depth(v, depth + 1)
        elif isinstance(obj, (list, tuple)):
            for v in obj:
                check_depth(v, depth + 1)
    
    check_depth(payload)
    return payload


def normalize_event_payload(payload: dict) -> dict:
    """
    Normalize event payload and attach metadata.
    
    Preserves original payload and adds:
    - processed_timestamp: When normalization occurred
    - normalized_at: ISO timestamp
    """
    normalized = {
        "original": payload,
        "normalized_at": datetime.utcnow().isoformat(),
    }
    
    # Extract and normalize common fields
    if "page" in payload:
        normalized["page"] = str(payload.get("page", "")).strip()
    
    if "referrer" in payload:
        normalized["referrer"] = str(payload.get("referrer", "")).strip()
    
    if "duration" in payload:
        try:
            normalized["duration"] = float(payload.get("duration", 0))
        except (ValueError, TypeError):
            normalized["duration"] = 0.0
    
    if "scroll_depth" in payload:
        try:
            normalized["scroll_depth"] = float(payload.get("scroll_depth", 0))
        except (ValueError, TypeError):
            normalized["scroll_depth"] = 0.0
    
    return normalized


def fetch_event_with_user(session: Session, event_id: int) -> tuple[Optional[Event], Optional[User]]:
    """
    Fetch event and associated user.
    
    Returns:
        (event, user) tuple or (None, None) if not found
    """
    stmt = select(Event).where(Event.id == event_id)
    result = session.execute(stmt)
    event = result.scalar_one_or_none()
    
    if not event:
        return None, None
    
    user_stmt = select(User).where(User.id == event.user_id)
    user_result = session.execute(user_stmt)
    user = user_result.scalar_one_or_none()
    
    return event, user


def persist_event_to_db(session: Session, event: Optional[Event] = None) -> None:
    """
    Persist event changes to database.
    
    Args:
        session: Database session
        event: Event to flush (optional, used for logging)
    
    If event is None, commits all pending changes in session.
    """
    session.flush()
    session.commit()
    if event:
        logger.debug(f"Event {event.id} persisted to database")
    else:
        logger.debug("Batch events persisted to database")


@celery_app.task(
    bind=True,
    name="app.workers.tasks.process_event",
    max_retries=settings.EVENT_MAX_RETRIES,
    default_retry_delay=settings.EVENT_RETRY_DELAY,
    time_limit=settings.EVENT_PROCESSING_TIMEOUT,
)
def process_event(self, event_id: int) -> Dict[str, Any]:
    """
    Process single event synchronously.
    
    Workflow:
    1. Fetch event and user from DB
    2. Validate payload shape
    3. Normalize payload (attach metadata)
    4. Update event properties
    5. Mark processed_at with current timestamp
    6. Persist to DB
    7. Retry on failure with exponential backoff
    """
    with sync_session_maker() as session:
        try:
            logger.info(f"[Event {event_id}] Starting processing")
            
            # 1. Fetch event and user
            event, user = fetch_event_with_user(session, event_id)
            
            if not event:
                logger.warning(f"[Event {event_id}] Event not found in database")
                return {
                    "status": "error",
                    "event_id": event_id,
                    "message": "Event not found",
                }
            
            if event.processed:
                logger.info(f"[Event {event_id}] Already processed, skipping")
                return {
                    "status": "skipped",
                    "event_id": event_id,
                    "message": "Event already processed",
                }
            
            logger.debug(f"[Event {event_id}] User: {user.email if user else 'unknown'}")
            
            # 2. Validate payload shape
            try:
                validated_payload = validate_payload_shape(event.payload)
                logger.debug(f"[Event {event_id}] Payload validation passed")
            except PayloadValidationError as e:
                error_msg = f"Payload validation failed: {str(e)}"
                logger.error(f"[Event {event_id}] {error_msg}")
                event.processing_error = error_msg[:255]
                persist_event_to_db(session, event)
                return {
                    "status": "validation_error",
                    "event_id": event_id,
                    "error": error_msg,
                }
            
            # 3. Validate required event fields
            if not event.event_name or not event.event_type:
                error_msg = "Missing required fields: event_name and/or event_type"
                logger.error(f"[Event {event_id}] {error_msg}")
                event.processing_error = error_msg[:255]
                persist_event_to_db(session, event)
                return {
                    "status": "validation_error",
                    "event_id": event_id,
                    "error": error_msg,
                }
            
            # 4. Normalize payload with metadata
            normalized_payload = normalize_event_payload(validated_payload)
            event.properties = normalized_payload
            logger.debug(f"[Event {event_id}] Payload normalized")
            
            # 5. Attach metadata to event
            event.processing_error = None
            
            # 6. Mark processed_at with current timestamp
            now = datetime.utcnow()
            event.processed = True
            event.processed_at = now
            logger.debug(f"[Event {event_id}] Marked processed at {now.isoformat()}")
            
            # 7. Persist to database
            persist_event_to_db(session, event)
            
            logger.info(f"[Event {event_id}] Processing completed successfully")
            return {
                "status": "success",
                "event_id": event_id,
                "event_name": event.event_name,
                "event_type": event.event_type,
                "user_id": str(event.user_id),
                "processed_at": event.processed_at.isoformat(),
            }
            
        except PayloadValidationError as e:
            session.rollback()
            logger.error(f"[Event {event_id}] Payload validation error: {str(e)}")
            return {
                "status": "validation_error",
                "event_id": event_id,
                "error": str(e),
            }
        
        except Exception as e:
            session.rollback()
            error_msg = f"Processing error: {str(e)}"
            logger.error(f"[Event {event_id}] {error_msg}", exc_info=True)
            
            # Attempt to update event with error before retrying
            try:
                with sync_session_maker() as error_session:
                    event, _ = fetch_event_with_user(error_session, event_id)
                    if event:
                        event.processing_error = error_msg[:255]
                        persist_event_to_db(error_session, event)
            except Exception as update_error:
                logger.error(f"[Event {event_id}] Failed to log error: {str(update_error)}")
            
            # Retry with exponential backoff
            if self.request.retries < settings.EVENT_MAX_RETRIES:
                retry_in = 2 ** self.request.retries
                logger.info(
                    f"[Event {event_id}] Retrying in {retry_in}s "
                    f"(attempt {self.request.retries + 1}/{settings.EVENT_MAX_RETRIES})"
                )
                raise self.retry(exc=e, countdown=retry_in)
            else:
                logger.error(f"[Event {event_id}] Max retries ({settings.EVENT_MAX_RETRIES}) exceeded")
                return {
                    "status": "failed",
                    "event_id": event_id,
                    "error": error_msg,
                    "retries_exhausted": True,
                }


@celery_app.task(
    bind=True,
    name="app.workers.tasks.process_events_batch",
    max_retries=settings.EVENT_MAX_RETRIES,
    default_retry_delay=settings.EVENT_RETRY_DELAY,
)
def process_events_batch(self, event_ids: list[int]) -> Dict[str, Any]:
    """
    Process multiple events in batch synchronously.
    
    Workflow (for each event):
    1. Fetch event and user
    2. Validate payload shape
    3. Normalize payload
    4. Mark processed_at
    5. Persist to DB
    
    Returns:
        Summary with processed count and individual results
    """
    with sync_session_maker() as session:
        processed_count = 0
        failed_count = 0
        results = []
        
        logger.info(f"[Batch] Processing {len(event_ids)} events")
        
        for event_id in event_ids:
            try:
                # 1. Fetch event and user
                event, user = fetch_event_with_user(session, event_id)
                
                if not event:
                    logger.warning(f"[Event {event_id}] Not found in batch")
                    results.append({"event_id": event_id, "status": "not_found"})
                    continue
                
                if event.processed:
                    logger.debug(f"[Event {event_id}] Already processed, skipping")
                    results.append({"event_id": event_id, "status": "already_processed"})
                    continue
                
                # 2. Validate payload shape
                try:
                    validated_payload = validate_payload_shape(event.payload)
                except PayloadValidationError as e:
                    error_msg = f"Payload validation: {str(e)}"
                    logger.error(f"[Event {event_id}] {error_msg}")
                    event.processing_error = error_msg[:255]
                    failed_count += 1
                    results.append({"event_id": event_id, "status": "validation_error", "error": error_msg})
                    continue
                
                # Validate required fields
                if not event.event_name or not event.event_type:
                    error_msg = "Missing event_name or event_type"
                    logger.error(f"[Event {event_id}] {error_msg}")
                    event.processing_error = error_msg[:255]
                    failed_count += 1
                    results.append({"event_id": event_id, "status": "validation_error", "error": error_msg})
                    continue
                
                # 3. Normalize payload with metadata
                normalized_payload = normalize_event_payload(validated_payload)
                event.properties = normalized_payload
                
                # 4. Mark processed_at with current timestamp
                now = datetime.utcnow()
                event.processed = True
                event.processed_at = now
                event.processing_error = None
                
                processed_count += 1
                results.append({
                    "event_id": event_id,
                    "status": "processed",
                    "event_name": event.event_name,
                    "user_id": str(event.user_id),
                    "processed_at": now.isoformat(),
                })
                
                logger.debug(f"[Event {event_id}] Processed in batch")
                
            except Exception as e:
                error_msg = f"Batch processing error: {str(e)}"
                logger.error(f"[Event {event_id}] {error_msg}", exc_info=True)
                failed_count += 1
                results.append({"event_id": event_id, "status": "error", "error": error_msg})
        
        # 5. Persist all changes to DB in single transaction
        try:
            persist_event_to_db(session, None)  # Commit all changes
            logger.info(f"[Batch] Persisted {processed_count} processed events")
        except Exception as e:
            session.rollback()
            logger.error(f"[Batch] Failed to persist changes: {str(e)}")
            return {
                "status": "failed",
                "total_events": len(event_ids),
                "processed": processed_count,
                "failed": failed_count,
                "error": "Failed to persist batch to database",
                "results": results,
            }
        
        logger.info(
            f"[Batch] Completed: {processed_count} processed, "
            f"{failed_count} failed out of {len(event_ids)} total"
        )
        
        return {
            "status": "success" if failed_count == 0 else "partial",
            "total_events": len(event_ids),
            "processed": processed_count,
            "failed": failed_count,
            "results": results,
        }
