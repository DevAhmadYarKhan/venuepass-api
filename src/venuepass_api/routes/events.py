"""Handle HTTP operations for events."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from venuepass_api.database import get_session
from venuepass_api.models import Event, EventStatus
from venuepass_api.schemas import EventCreate, EventListResponse, EventResponse


router = APIRouter(prefix="/events", tags=["events"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
# Keep responses bounded while still allowing clients to choose smaller pages.
LimitQuery = Annotated[int, Query(ge=1, le=100)]
# Reject values that asyncpg cannot bind to PostgreSQL's signed BIGINT OFFSET.
OffsetQuery = Annotated[int, Query(ge=0, le=9_223_372_036_854_775_807)]


@router.get("", response_model=EventListResponse)
async def list_events(
    session: SessionDependency,
    limit: LimitQuery = 20,
    offset: OffsetQuery = 0,
) -> EventListResponse:
    """Return one page of published Events in chronological order."""
    # The unauthenticated catalog must not expose internal drafts or events in
    # terminal states.
    published_filter = Event.status == EventStatus.PUBLISHED

    # Count before pagination so total describes the complete filtered result,
    # including when the requested page itself is empty.
    total = await session.scalar(
        select(func.count()).select_from(Event).where(published_filter)
    )
    # UUID provides a stable tie-breaker when Events share the same start time,
    # preventing records from moving unpredictably between offset-based pages.
    events = await session.scalars(
        select(Event)
        .where(published_filter)
        .order_by(Event.starts_at.asc(), Event.id.asc())
        .offset(offset)
        .limit(limit)
    )

    return EventListResponse(
        items=list(events),
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@router.post(
    "",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_event(
    event_data: EventCreate,
    session: SessionDependency,
) -> Event:
    """Create a draft Event and return its database-generated values."""
    # EventCreate deliberately excludes status, so the model's draft default is
    # always used for newly created events.
    event = Event(**event_data.model_dump())
    session.add(event)

    try:
        # Flush the INSERT and load server-generated values while rollback is
        # still possible. Commit remains the final database operation so the
        # response cannot fail because of a post-commit refresh.
        await session.flush()
        await session.refresh(event)
        await session.commit()
    except SQLAlchemyError:
        # Restore the session before FastAPI handles the unexpected DB failure.
        await session.rollback()
        raise

    return event
