"""Exercise database configuration, persistence defaults, and constraints."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from venuepass_api.config import DatabaseTestSettings, Settings, get_test_settings
from venuepass_api.models import Event, EventStatus


def test_database_urls_are_configured() -> None:
    """Accept deployment-specific database names and connection parameters."""
    runtime_url = "postgresql+asyncpg://app:secret@db/runtime_ci?ssl=require"
    test_url = "postgresql+asyncpg://app:secret@db/integration_ci?ssl=require"

    # Disable `.env` loading so this unit test proves each settings class can be
    # constructed independently from explicitly supplied environment values.
    settings = Settings(database_url=runtime_url, _env_file=None)
    test_settings = DatabaseTestSettings(
        test_database_url=test_url,
        _env_file=None,
    )

    assert settings.database_url == runtime_url
    assert test_settings.test_database_url == test_url


@pytest.fixture(scope="module")
def migrated_test_database() -> None:
    """Upgrade the configured test database before integration tests execute."""
    alembic_config = Config("alembic.ini")

    # Pass the test URL directly to Alembic so runtime settings are not involved.
    alembic_config.attributes["database_url"] = (
        get_test_settings().test_database_url
    )
    command.upgrade(alembic_config, "head")


async def create_event_and_roll_back() -> None:
    """Insert one valid Event and roll it back after checking DB defaults."""
    # Create a test-only engine so this helper cannot write to the main database.
    engine = create_async_engine(get_test_settings().test_database_url)

    try:
        async with engine.connect() as connection:
            # The surrounding transaction makes the test repeatable and leaves
            # no rows behind regardless of assertion outcomes.
            transaction = await connection.begin()

            try:
                async with AsyncSession(
                    bind=connection,
                    expire_on_commit=False,
                ) as session:
                    starts_at = datetime.now(UTC) + timedelta(days=1)
                    event = Event(
                        name="VenuePass launch",
                        description="Initial database integration test",
                        venue="London",
                        starts_at=starts_at,
                        ends_at=starts_at + timedelta(hours=2),
                        capacity=100,
                    )
                    # Flushing sends the INSERT and retrieves server-generated
                    # UUID and timestamp values without committing the row.
                    session.add(event)
                    await session.flush()
                    await session.refresh(event)

                    assert isinstance(event.id, UUID)
                    assert event.status is EventStatus.DRAFT
                    assert event.created_at.tzinfo is not None
                    assert event.updated_at.tzinfo is not None
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()


def test_event_can_be_persisted_with_database_defaults(
    migrated_test_database: None,
) -> None:
    """Persist a valid Event with UUID, status, and timestamp defaults."""
    asyncio.run(create_event_and_roll_back())


async def assert_event_insert_is_rejected(
    *,
    capacity: int,
    starts_at: datetime,
    ends_at: datetime,
    status: str,
) -> None:
    """Attempt a raw invalid insert and confirm PostgreSQL rejects it."""
    engine = create_async_engine(get_test_settings().test_database_url)

    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()

            try:
                # Raw SQL deliberately bypasses ORM validation so this assertion
                # proves the database constraints themselves are enforced.
                with pytest.raises(IntegrityError):
                    await connection.execute(
                        text(
                            """
                            INSERT INTO events (
                                name,
                                venue,
                                starts_at,
                                ends_at,
                                capacity,
                                status
                            )
                            VALUES (
                                :name,
                                :venue,
                                :starts_at,
                                :ends_at,
                                :capacity,
                                :status
                            )
                            """
                        ),
                        {
                            "name": "Invalid event",
                            "venue": "London",
                            "starts_at": starts_at,
                            "ends_at": ends_at,
                            "capacity": capacity,
                            "status": status,
                        },
                    )
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()


@pytest.mark.parametrize(
    ("capacity", "time_order_is_valid", "status"),
    [
        (0, True, EventStatus.DRAFT.value),
        (100, False, EventStatus.DRAFT.value),
        (100, True, "unknown"),
    ],
    ids=["non-positive-capacity", "invalid-time-range", "invalid-status"],
)
def test_event_constraints_reject_invalid_data(
    migrated_test_database: None,
    capacity: int,
    time_order_is_valid: bool,
    status: str,
) -> None:
    """Reject invalid capacity, time ordering, and lifecycle status values."""
    starts_at = datetime.now(UTC) + timedelta(days=1)
    ends_at = starts_at + timedelta(hours=2)
    if not time_order_is_valid:
        ends_at = starts_at - timedelta(hours=2)

    asyncio.run(
        assert_event_insert_is_rejected(
            capacity=capacity,
            starts_at=starts_at,
            ends_at=ends_at,
            status=status,
        )
    )
