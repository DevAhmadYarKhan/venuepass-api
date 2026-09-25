"""Define the persisted Event entity and its lifecycle states."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Enum, String, Text, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from venuepass_api.models.base import Base


class EventStatus(StrEnum):
    """Represent the lifecycle states an event may be stored with."""

    # The event is still being prepared and is not publicly bookable.
    DRAFT = "draft"

    # The event has been published and may be exposed to customers.
    PUBLISHED = "published"

    # The organizer cancelled the event before it took place.
    CANCELLED = "cancelled"

    # The event took place and its lifecycle is finished.
    COMPLETED = "completed"


class Event(Base):
    """Store the scheduling and capacity information for a ticketed event."""

    __tablename__ = "events"

    # Protect core business invariants even when writes bypass the application.
    __table_args__ = (
        CheckConstraint("capacity > 0", name="ck_events_capacity_positive"),
        CheckConstraint("ends_at > starts_at", name="ck_events_valid_time_range"),
    )

    # Generate opaque public identifiers inside PostgreSQL.
    id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    # Human-facing event details.
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    venue: Mapped[str] = mapped_column(String(255))

    # Timezone-aware bounds describe when the event starts and ends.
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # Total number of attendees the event can accommodate.
    capacity: Mapped[int]

    # Store lowercase values in a portable VARCHAR plus CHECK constraint instead
    # of creating a PostgreSQL-specific enum type.
    status: Mapped[EventStatus] = mapped_column(
        Enum(
            EventStatus,
            name="event_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda statuses: [status.value for status in statuses],
        ),
        default=EventStatus.DRAFT,
        server_default=EventStatus.DRAFT.value,
    )
    # Let PostgreSQL assign audit timestamps to keep them consistent across
    # every application instance.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    # SQLAlchemy emits `now()` whenever this model is updated through the ORM.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
