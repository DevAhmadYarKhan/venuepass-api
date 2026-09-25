"""Define the public request and response contracts for events."""

from datetime import UTC, datetime
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from venuepass_api.models import EventStatus


class EventCreate(BaseModel):
    """Validate the client-controlled fields used to create an Event."""

    # Reject misspelled fields and lifecycle values that clients cannot set.
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    venue: str = Field(min_length=1, max_length=255)
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    # Match PostgreSQL's signed INTEGER range so invalid values return 422
    # instead of reaching the database and becoming an internal error.
    capacity: int = Field(gt=0, le=2_147_483_647)

    @field_validator("starts_at")
    @classmethod
    def start_must_be_in_the_future(cls, starts_at: datetime) -> datetime:
        """Reject events that have already started or start immediately."""
        if starts_at <= datetime.now(UTC):
            raise ValueError("starts_at must be in the future")
        return starts_at

    @model_validator(mode="after")
    def end_must_follow_start(self) -> "EventCreate":
        """Reject empty or backwards event time ranges."""
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be later than starts_at")
        return self


class EventResponse(BaseModel):
    """Serialize a stored Event, including database-generated fields."""

    # Read values directly from SQLAlchemy model attributes.
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    venue: str
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    capacity: int
    status: EventStatus
    created_at: AwareDatetime
    updated_at: AwareDatetime
