"""Load application configuration from environment variables and `.env`."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Define the environment variables required by the running application."""

    # Main database used by the API and by Alembic unless explicitly overridden.
    database_url: str

    # Read local development values from `.env` while still allowing real
    # environment variables to take precedence in deployments and commands.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Create the validated settings object once per Python process."""
    return Settings()


class DatabaseTestSettings(BaseSettings):
    """Define configuration used exclusively by database integration tests."""

    # Keeping this separate prevents the application and production migrations
    # from requiring credentials for a test-only database.
    test_database_url: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_test_settings() -> DatabaseTestSettings:
    """Create the validated test settings object once per Python process."""
    return DatabaseTestSettings()
