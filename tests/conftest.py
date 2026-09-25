"""Provide database preparation shared by integration test modules."""

import pytest
from alembic import command
from alembic.config import Config

from venuepass_api.config import get_test_settings


@pytest.fixture(scope="session")
def migrated_test_database() -> None:
    """Upgrade the configured test database before integration tests execute."""
    alembic_config = Config("alembic.ini")

    # Pass the test URL directly to Alembic so runtime settings are not involved.
    alembic_config.attributes["database_url"] = (
        get_test_settings().test_database_url
    )
    command.upgrade(alembic_config, "head")
