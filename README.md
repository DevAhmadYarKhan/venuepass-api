# venuepass-api
FastAPI ticket reservation system

## Development

Install the project and its development dependencies:

```bash
uv sync --dev
```

Create the local environment file and update its PostgreSQL credentials if
needed:

```bash
cp .env.example .env
```

Apply all database migrations:

```bash
uv run alembic upgrade head
```

Apply migrations to the integration-test database:

```bash
uv run alembic -x database=test upgrade head
```

Create a migration after changing a database model:

```bash
uv run alembic revision --autogenerate -m "describe the change"
```

Roll back the most recent migration:

```bash
uv run alembic downgrade -1
```

Run the API locally:

```bash
uv run uvicorn venuepass_api.main:app --reload
```

Run the tests:

```bash
uv run pytest
```

Database tests use `TEST_DATABASE_URL` and automatically upgrade that database
to the current Alembic revision before exercising it.

## Create an event

New events are created in `draft` status. Event times must include a timezone,
the start must be in the future, and the end must be later than the start.

```bash
curl -X POST http://127.0.0.1:8000/events \
  -H "Content-Type: application/json" \
  -d '{
    "name": "VenuePass Launch",
    "description": "Opening night",
    "venue": "London",
    "starts_at": "2026-10-20T18:00:00Z",
    "ends_at": "2026-10-20T21:00:00Z",
    "capacity": 250
  }'
```

A successful request returns `201 Created` with the stored event:

```json
{
  "id": "3c2499b3-c76f-45e4-85f5-ab2766b077a8",
  "name": "VenuePass Launch",
  "description": "Opening night",
  "venue": "London",
  "starts_at": "2026-10-20T18:00:00Z",
  "ends_at": "2026-10-20T21:00:00Z",
  "capacity": 250,
  "status": "draft",
  "created_at": "2026-09-25T12:00:00Z",
  "updated_at": "2026-09-25T12:00:00Z"
}
```

## List events

Published events can be listed in ascending start-time order. The endpoint
accepts an `offset` between 0 and 9,223,372,036,854,775,807 (default `0`) and a
`limit` between 1 and 100 (default `20`). Draft, cancelled, and completed
events are not returned.

```bash
curl "http://127.0.0.1:8000/events?limit=20&offset=0"
```

A successful request returns `200 OK` with the selected page and the total
number of published events:

```json
{
  "items": [
    {
      "id": "3c2499b3-c76f-45e4-85f5-ab2766b077a8",
      "name": "VenuePass Launch",
      "description": "Opening night",
      "venue": "London",
      "starts_at": "2026-10-20T18:00:00Z",
      "ends_at": "2026-10-20T21:00:00Z",
      "capacity": 250,
      "status": "published",
      "created_at": "2026-09-25T12:00:00Z",
      "updated_at": "2026-09-25T12:00:00Z"
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

## Get an event

A published event can be retrieved by its UUID:

```bash
curl http://127.0.0.1:8000/events/3c2499b3-c76f-45e4-85f5-ab2766b077a8
```

A successful request returns `200 OK` using the same event representation as
the create and list endpoints. Unknown, draft, cancelled, and completed event
IDs return `404 Not Found` without revealing whether a non-public event exists:

```json
{
  "detail": "Event not found"
}
```

Malformed UUIDs return FastAPI's standard `422 Unprocessable Entity` response.
