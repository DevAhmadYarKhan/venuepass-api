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
