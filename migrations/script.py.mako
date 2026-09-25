"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
# This template is used by `alembic revision` to create new migration modules.
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}


# Alembic uses these identifiers to order the migration graph.
revision: str = ${repr(up_revision)}
down_revision: str | Sequence[str] | None = ${repr(down_revision)}
branch_labels: str | Sequence[str] | None = ${repr(branch_labels)}
depends_on: str | Sequence[str] | None = ${repr(depends_on)}


def upgrade() -> None:
    """Apply the schema changes introduced by this revision."""
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """Reverse the schema changes introduced by this revision."""
    ${downgrades if downgrades else "pass"}
