"""Configure Alembic to run migrations with the async PostgreSQL driver."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from venuepass_api.config import get_settings
from venuepass_api.models import Event  # noqa: F401
from venuepass_api.models.base import Base


# Alembic creates this configuration object before importing this module.
config = context.config

# Keep credentials out of alembic.ini. Programmatic callers, such as the test
# suite, may provide a URL directly; the CLI can select test settings with
# `-x database=test`; all other invocations use the runtime DATABASE_URL.
def get_database_url() -> str:
    """Select the database URL for this migration invocation."""
    if database_url := config.attributes.get("database_url"):
        return str(database_url)

    arguments = context.get_x_argument(as_dictionary=True)
    database_target = arguments.get("database", "runtime")

    if database_target == "test":
        # Import lazily so normal runtime migrations never load or validate
        # test-only credentials.
        from venuepass_api.config import get_test_settings

        return get_test_settings().test_database_url

    if database_target != "runtime":
        raise ValueError("database must be either 'runtime' or 'test'")

    return get_settings().database_url


# Percent signs are escaped for ConfigParser interpolation.
config.set_main_option(
    "sqlalchemy.url",
    get_database_url().replace("%", "%%"),
)

# Reuse the logging configuration declared in alembic.ini when available.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Autogeneration compares the live database against all tables on this metadata.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Render SQL without opening a database connection."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations through Alembic's synchronous context on one connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Open an async connection and bridge it into Alembic's sync API."""
    # Migrations use short-lived connections, so they do not need a pool.
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Start the event loop used for a live database migration."""
    asyncio.run(run_async_migrations())


# Alembic selects offline mode for SQL generation and online mode otherwise.
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
