"""index event listing

Revision ID: 20260926_0002
Revises: 20260925_0001
Create Date: 2026-09-26

"""
from collections.abc import Sequence

from alembic import op


# Alembic uses these identifiers to order the migration graph.
revision: str = "20260926_0002"
down_revision: str | Sequence[str] | None = "20260925_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Support filtering and ordering the public event listing."""
    # Put the equality-filtered status first, followed by the route's complete
    # ordering, so PostgreSQL can filter and order with one index scan.
    op.create_index(
        "ix_events_status_starts_at_id",
        "events",
        ["status", "starts_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove the public event listing index."""
    op.drop_index("ix_events_status_starts_at_id", table_name="events")
