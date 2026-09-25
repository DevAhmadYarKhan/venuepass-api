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
