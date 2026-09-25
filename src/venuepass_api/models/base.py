"""Define the declarative base shared by all SQLAlchemy models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Collect mapped-table metadata for Alembic and SQLAlchemy."""
