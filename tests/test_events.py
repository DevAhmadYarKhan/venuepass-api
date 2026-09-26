"""Verify the /events request contracts and persistence behavior."""

from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from venuepass_api.config import get_test_settings
from venuepass_api.database import get_session
from venuepass_api.main import app
from venuepass_api.models import Event, EventStatus


def valid_event_payload() -> dict[str, Any]:
    """Build a valid payload whose timestamps stay safely in the future."""
    starts_at = datetime.now(UTC) + timedelta(days=7)
    return {
        "name": "VenuePass Launch",
        "description": "Opening night",
        "venue": "London",
        "starts_at": starts_at.isoformat(),
        "ends_at": (starts_at + timedelta(hours=3)).isoformat(),
        "capacity": 250,
    }


@pytest.fixture
def event_client(
    migrated_test_database: None,
) -> Iterator[tuple[TestClient, list[int]]]:
    """Serve requests in transactions that are rolled back after each request."""
    inserted_row_counts: list[int] = []

    async def override_session() -> AsyncIterator[AsyncSession]:
        """Bind the route session to an isolated test-database transaction."""
        engine = create_async_engine(get_test_settings().test_database_url)

        try:
            async with engine.connect() as connection:
                transaction = await connection.begin()

                try:
                    # Hide committed rows from previous local test runs while
                    # the outer rollback guarantees they are restored later.
                    await connection.execute(delete(Event))
                    before_count = await connection.scalar(
                        select(func.count()).select_from(Event)
                    )

                    # Route-level commits affect a savepoint while the outer
                    # transaction remains available for complete cleanup.
                    async with AsyncSession(
                        bind=connection,
                        expire_on_commit=False,
                        join_transaction_mode="create_savepoint",
                    ) as session:
                        yield session

                    after_count = await connection.scalar(
                        select(func.count()).select_from(Event)
                    )
                    inserted_row_counts.append(after_count - before_count)
                finally:
                    await transaction.rollback()
        finally:
            await engine.dispose()

    app.dependency_overrides[get_session] = override_session
    try:
        with TestClient(app) as client:
            yield client, inserted_row_counts
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def published_event_client(
    migrated_test_database: None,
) -> Iterator[TestClient]:
    """Serve requests with published and non-public Events in the database."""

    async def override_session() -> AsyncIterator[AsyncSession]:
        """Seed an isolated transaction before serving a listing request."""
        engine = create_async_engine(get_test_settings().test_database_url)
        first_start = datetime.now(UTC) + timedelta(days=1)

        try:
            async with engine.connect() as connection:
                transaction = await connection.begin()

                try:
                    # Make exact result assertions independent of committed
                    # rows already present in the shared test database.
                    await connection.execute(delete(Event))

                    async with AsyncSession(
                        bind=connection,
                        expire_on_commit=False,
                        join_transaction_mode="create_savepoint",
                    ) as session:
                        # Equal start times and explicit UUIDs exercise the
                        # tie-breaker; the other statuses exercise visibility.
                        session.add_all(
                            [
                                Event(
                                    id=UUID("00000000-0000-0000-0000-000000000002"),
                                    name="Second at first time",
                                    venue="London",
                                    starts_at=first_start,
                                    ends_at=first_start + timedelta(hours=2),
                                    capacity=100,
                                    status=EventStatus.PUBLISHED,
                                ),
                                Event(
                                    id=UUID("00000000-0000-0000-0000-000000000001"),
                                    name="First at first time",
                                    venue="Manchester",
                                    starts_at=first_start,
                                    ends_at=first_start + timedelta(hours=1),
                                    capacity=75,
                                    status=EventStatus.PUBLISHED,
                                ),
                                Event(
                                    id=UUID("00000000-0000-0000-0000-000000000003"),
                                    name="Later published event",
                                    venue="Bristol",
                                    starts_at=first_start + timedelta(days=1),
                                    ends_at=first_start + timedelta(days=1, hours=1),
                                    capacity=50,
                                    status=EventStatus.PUBLISHED,
                                ),
                                Event(
                                    name="Hidden draft",
                                    venue="Leeds",
                                    starts_at=first_start,
                                    ends_at=first_start + timedelta(hours=1),
                                    capacity=25,
                                    status=EventStatus.DRAFT,
                                ),
                                Event(
                                    name="Hidden cancelled event",
                                    venue="York",
                                    starts_at=first_start,
                                    ends_at=first_start + timedelta(hours=1),
                                    capacity=25,
                                    status=EventStatus.CANCELLED,
                                ),
                                Event(
                                    name="Hidden completed event",
                                    venue="Bath",
                                    starts_at=first_start,
                                    ends_at=first_start + timedelta(hours=1),
                                    capacity=25,
                                    status=EventStatus.COMPLETED,
                                ),
                            ]
                        )
                        await session.flush()
                        yield session
                finally:
                    await transaction.rollback()
        finally:
            await engine.dispose()

    app.dependency_overrides[get_session] = override_session
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def test_create_event_returns_and_persists_a_draft(
    event_client: tuple[TestClient, list[int]],
) -> None:
    """Return 201 with a complete draft Event after persisting one row."""
    client, inserted_row_counts = event_client
    payload = valid_event_payload()

    response = client.post("/events", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert UUID(body["id"])
    assert body["name"] == payload["name"]
    assert body["description"] == payload["description"]
    assert body["venue"] == payload["venue"]
    assert body["capacity"] == payload["capacity"]
    assert body["status"] == "draft"
    assert datetime.fromisoformat(body["starts_at"]).tzinfo is not None
    assert datetime.fromisoformat(body["ends_at"]).tzinfo is not None
    assert datetime.fromisoformat(body["created_at"]).tzinfo is not None
    assert datetime.fromisoformat(body["updated_at"]).tzinfo is not None
    assert inserted_row_counts == [1]


def test_create_event_allows_an_omitted_description(
    event_client: tuple[TestClient, list[int]],
) -> None:
    """Treat an omitted optional description as null."""
    client, inserted_row_counts = event_client
    payload = valid_event_payload()
    del payload["description"]

    response = client.post("/events", json=payload)

    assert response.status_code == 201
    assert response.json()["description"] is None
    assert inserted_row_counts == [1]


def test_list_events_returns_only_published_events_in_start_order(
    published_event_client: TestClient,
) -> None:
    """Return published Events ordered by start time and then ID."""
    response = published_event_client.get("/events")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["limit"] == 20
    assert body["offset"] == 0
    assert [event["id"] for event in body["items"]] == [
        "00000000-0000-0000-0000-000000000001",
        "00000000-0000-0000-0000-000000000002",
        "00000000-0000-0000-0000-000000000003",
    ]
    assert {event["status"] for event in body["items"]} == {"published"}


def test_list_events_applies_pagination_without_changing_total(
    published_event_client: TestClient,
) -> None:
    """Apply limit and offset while counting all matching Events."""
    response = published_event_client.get("/events?limit=1&offset=1")

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == "00000000-0000-0000-0000-000000000002"
    assert body["total"] == 3
    assert body["limit"] == 1
    assert body["offset"] == 1


def test_list_events_returns_an_empty_page_beyond_the_total(
    published_event_client: TestClient,
) -> None:
    """Preserve count metadata when an offset passes the final Event."""
    response = published_event_client.get("/events?offset=100")

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total"] == 3
    assert response.json()["offset"] == 100


def test_list_events_accepts_the_largest_database_offset(
    event_client: tuple[TestClient, list[int]],
) -> None:
    """Allow an offset at PostgreSQL's signed BIGINT boundary."""
    client, inserted_row_counts = event_client

    response = client.get("/events?offset=9223372036854775807")

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["offset"] == 9_223_372_036_854_775_807
    assert inserted_row_counts == [0]


def test_list_events_returns_an_empty_envelope_without_matches(
    event_client: tuple[TestClient, list[int]],
) -> None:
    """Return a successful empty page when no published Events exist."""
    client, inserted_row_counts = event_client

    response = client.get("/events")

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "total": 0,
        "limit": 20,
        "offset": 0,
    }
    assert inserted_row_counts == [0]


@pytest.mark.parametrize(
    "query",
    [
        pytest.param("limit=0", id="zero-limit"),
        pytest.param("limit=101", id="limit-above-maximum"),
        pytest.param("offset=-1", id="negative-offset"),
        pytest.param(
            "offset=9223372036854775808",
            id="offset-above-postgresql-bigint",
        ),
    ],
)
def test_list_events_rejects_invalid_pagination(
    event_client: tuple[TestClient, list[int]],
    query: str,
) -> None:
    """Return 422 when pagination parameters are outside their bounds."""
    client, inserted_row_counts = event_client

    response = client.get(f"/events?{query}")

    assert response.status_code == 422
    assert response.json()["detail"]
    assert inserted_row_counts in ([], [0])


def invalid_event_payloads() -> list[Any]:
    """Build invalid payloads covering every public validation rule."""
    future_start = datetime.now(UTC) + timedelta(days=7)
    past_start = datetime.now(UTC) - timedelta(days=1)

    cases: list[tuple[str, dict[str, Any]]] = []

    payload = valid_event_payload()
    payload["starts_at"] = past_start.isoformat()
    cases.append(("past-start", payload))

    payload = valid_event_payload()
    payload["starts_at"] = future_start.replace(tzinfo=None).isoformat()
    cases.append(("timezone-naive-start", payload))

    payload = valid_event_payload()
    payload["ends_at"] = payload["starts_at"]
    cases.append(("end-equals-start", payload))

    payload = valid_event_payload()
    payload["capacity"] = 0
    cases.append(("non-positive-capacity", payload))

    payload = valid_event_payload()
    payload["capacity"] = 2_147_483_648
    cases.append(("capacity-exceeds-postgresql-integer", payload))

    payload = valid_event_payload()
    payload["name"] = "   "
    cases.append(("blank-name", payload))

    payload = valid_event_payload()
    payload["name"] = "n" * 201
    cases.append(("oversized-name", payload))

    payload = valid_event_payload()
    payload["venue"] = "   "
    cases.append(("blank-venue", payload))

    payload = valid_event_payload()
    payload["venue"] = "v" * 256
    cases.append(("oversized-venue", payload))

    payload = valid_event_payload()
    payload["status"] = "published"
    cases.append(("client-supplied-status", payload))

    payload = valid_event_payload()
    payload["unexpected"] = "value"
    cases.append(("unknown-field", payload))

    return [pytest.param(payload, id=name) for name, payload in cases]


@pytest.mark.parametrize("payload", invalid_event_payloads())
def test_create_event_rejects_invalid_input(
    event_client: tuple[TestClient, list[int]],
    payload: dict[str, Any],
) -> None:
    """Return FastAPI's standard 422 response for invalid client data."""
    client, inserted_row_counts = event_client

    response = client.post("/events", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"]
    assert inserted_row_counts in ([], [0])
