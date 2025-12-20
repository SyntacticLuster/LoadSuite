"""Application configuration using pydantic-settings.

Loads configuration from environment variables and .env file.
"""

from __future__ import annotations

from functools import lru_cache
from typing import List, Literal

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # Database
    database_url: PostgresDsn = Field(
        default="postgresql://localhost:5432/loadsuite",
        description="PostgreSQL connection URL"
    )
    db_pool_min_size: int = Field(default=2, ge=1, le=20)
    db_pool_max_size: int = Field(default=10, ge=1, le=100)
    
    # Application
    environment: Literal["development", "staging", "production"] = "development"
    secret_key: str = Field(default="dev-secret-change-in-production")
    cors_origins: str = Field(
        default="http://localhost:8000,http://localhost:3000",
        description="Comma-separated list of allowed CORS origins"
    )
    
    # Feature flags
    use_database: bool = Field(
        default=False,
        description="Use PostgreSQL for persistence (False = in-memory)"
    )
    generate_synthetic_loads: bool = Field(
        default=True,
        description="Generate synthetic loads on startup"
    )
    synthetic_load_count: int = Field(default=250, ge=0, le=10000)
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins string into list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
    
    @property
    def is_production(self) -> bool:
        return self.environment == "production"
    
    @property
    def is_development(self) -> bool:
        return self.environment == "development"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Convenience export
settings = get_settings()
