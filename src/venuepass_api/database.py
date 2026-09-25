"""Provide the shared asynchronous SQLAlchemy engine and session dependency."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from venuepass_api.config import get_settings


# Maintain one connection pool for the lifetime of the application process.
engine = create_async_engine(get_settings().database_url)

# Keep loaded attributes available after commits so response serialization does
# not unexpectedly trigger additional asynchronous database queries.
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield one session and guarantee that it closes after the request."""
    async with async_session_factory() as session:
        yield session
