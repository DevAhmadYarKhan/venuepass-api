"""Verify the POST /events request contract and persistence behavior."""

from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from venuepass_api.config import get_test_settings
from venuepass_api.database import get_session
from venuepass_api.main import app
from venuepass_api.models import Event


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
                before_count = await connection.scalar(
                    select(func.count()).select_from(Event)
                )

                try:
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
