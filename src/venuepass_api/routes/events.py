"""Handle HTTP operations for events."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from venuepass_api.database import get_session
from venuepass_api.models import Event
from venuepass_api.schemas import EventCreate, EventResponse


router = APIRouter(prefix="/events", tags=["events"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


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
