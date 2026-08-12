"""
Configuration Module

Manages application configuration using Pydantic Settings.
Loads settings from environment variables with validation.
"""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All settings can be overridden via environment variables or .env file.
    """

    # Coinbase API Configuration
    coinbase_api_key: str
    coinbase_api_secret: str
    coinbase_base_url: str = "https://api.coinbase.com"

    # Database Configuration
    database_url: str

    # Application Settings
    log_level: str = "INFO"
    environment: str = "development"

    # Azure Configuration (optional)
    azure_storage_connection_string: Optional[str] = None
    azure_functions_environment: str = "development"

    # Email Configuration (for future approval workflow)
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    approval_email: Optional[str] = None

    # Trading Configuration (for future execution)
    max_position_size: float = 1000.0
    risk_percentage: float = 0.02
    enable_live_trading: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def __init__(self, **kwargs):  # type: ignore
        """Initialize settings and validate required fields."""
        super().__init__(**kwargs)
        self._validate_required_settings()

    def _validate_required_settings(self) -> None:
        """Validate that required settings are present."""
        if not self.coinbase_api_key or self.coinbase_api_key == "your_coinbase_api_key_here":
            raise ValueError(
                "COINBASE_API_KEY is required. "
                "Get your API key from https://www.coinbase.com/settings/api"
            )
        if not self.coinbase_api_secret or self.coinbase_api_secret == "your_coinbase_api_secret_here":
            raise ValueError(
                "COINBASE_API_SECRET is required. "
                "Get your API secret from https://www.coinbase.com/settings/api"
            )
        if not self.database_url:
            raise ValueError("DATABASE_URL is required")

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment.lower() == "development"


@lru_cache
def get_settings() -> Settings:
    """
    Get cached application settings.

    Returns:
        Settings: Application configuration instance

    Example:
        >>> from cryptoquant.config.settings import get_settings
        >>> settings = get_settings()
        >>> print(settings.coinbase_api_key)
    """
    return Settings()
