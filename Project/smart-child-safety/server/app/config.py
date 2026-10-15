"""Application configuration module using Pydantic Settings."""

import json
from functools import lru_cache
from typing import List, Union

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly typed application settings loaded from environment variables."""

    # Project metadata
    project_name: str = Field(
        default="Smart Child Monitoring and Safety System",
        description="Application title displayed in OpenAPI docs",
    )
    environment: str = Field(
        default="development",
        description="Current deployment environment (development, testing, staging, production)",
    )
    api_v1_prefix: str = Field(
        default="/api/v1",
        description="Route prefix for version 1 REST APIs",
    )
    host: str = Field(
        default="0.0.0.0",
        description="Bind host address",
    )
    port: int = Field(
        default=8000,
        description="Bind port address (Render sets PORT)",
    )
    log_level: str = Field(
        default="INFO",
        description="Log verbosity level (DEBUG, INFO, WARNING, ERROR)",
    )

    # Database Configuration
    database_url: str = Field(
        default="sqlite:///./test.db",
        description="SQLAlchemy database connection URI (PostgreSQL or SQLite)",
    )
    database_pool_size: int = Field(
        default=10,
        description="SQLAlchemy engine pool size for PostgreSQL",
    )
    database_max_overflow: int = Field(
        default=20,
        description="SQLAlchemy engine max overflow connections",
    )
    database_pool_timeout: int = Field(
        default=30,
        description="SQLAlchemy engine pool timeout in seconds",
    )

    # CORS & Security
    cors_origins: Union[List[str], str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        description="Allowed CORS origins list or JSON array string",
    )
    allowed_hosts: Union[List[str], str] = Field(
        default=["localhost", "127.0.0.1", "0.0.0.0"],
        description="Allowed host headers",
    )

    # Pairing & Safety thresholds
    pairing_code_expiry_minutes: int = Field(
        default=15,
        description="Expiration time for pairing invitation codes in minutes",
    )
    pairing_max_attempts: int = Field(
        default=5,
        description="Max failed pairing attempts before lock/rate-limit",
    )
    location_stale_minutes: int = Field(
        default=15,
        description="Threshold after which child location is marked stale",
    )
    location_retention_days: int = Field(
        default=30,
        description="Retention period in days for historical location records",
    )

    # Firebase Authentication & FCM
    firebase_project_id: str = Field(
        default="smart-child-safety-demo",
        description="Firebase Project ID",
    )
    firebase_credentials_path: str = Field(
        default="",
        description="Local filesystem path to service account credentials JSON file",
    )
    firebase_credentials_json: str = Field(
        default="",
        description="Raw JSON string containing Firebase service account credentials (for cloud deployments)",
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        """Render and some PaaS services supply postgres:// instead of postgresql:// or postgresql+psycopg://."""
        if not isinstance(v, str):
            return v
        stripped = v.strip()
        if stripped.startswith("postgres://"):
            return "postgresql+psycopg://" + stripped[len("postgres://"):]
        if stripped.startswith("postgresql://") and not stripped.startswith("postgresql+"):
            return "postgresql+psycopg://" + stripped[len("postgresql://"):]
        return stripped

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """Parse string/JSON representations of CORS origins into a list of strings."""
        if isinstance(v, list):
            return [origin.strip() for origin in v if origin.strip()]
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                try:
                    parsed = json.loads(stripped)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except json.JSONDecodeError:
                    pass
            return [origin.strip() for origin in stripped.split(",") if origin.strip()]
        return []

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Retrieve cached application settings instance."""
    return Settings()
