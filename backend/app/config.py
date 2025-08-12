"""
Simple configuration for the Financial Planning Application.

Development-focused configuration with minimal complexity.
"""

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class DatabaseConfig(BaseModel):
    """Database configuration settings."""
    path: str = Field(default="./data/app.db", description="SQLite database file path")
    echo: bool = Field(default=False, description="Enable SQL query logging")
    
    @field_validator('path')
    @classmethod
    def validate_path(cls, v):
        """Ensure the database directory exists."""
        db_path = Path(v)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return v


class APIConfig(BaseModel):
    """API server configuration settings."""
    host: str = Field(default="localhost", description="API server host")
    port: int = Field(default=8000, ge=1024, le=65535, description="API server port")
    reload: bool = Field(default=True, description="Enable auto-reload")


class LoggingConfig(BaseModel):
    """Logging configuration settings."""
    level: str = Field(default="INFO", description="Logging level")
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log message format"
    )
    file: Optional[str] = Field(default="./data/app.log", description="Log file path")
    max_file_size: str = Field(default="10MB", description="Maximum log file size")
    backup_count: int = Field(default=5, ge=0, description="Number of backup log files")
    
    @field_validator('level')
    @classmethod
    def validate_level(cls, v):
        """Validate logging level."""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid logging level. Must be one of: {valid_levels}")
        return v.upper()
    
    @field_validator('file')
    @classmethod
    def validate_file(cls, v):
        """Ensure the log directory exists if file logging is enabled."""
        if v:
            log_path = Path(v)
            log_path.parent.mkdir(parents=True, exist_ok=True)
        return v


class AppConfig(BaseModel):
    """Application-specific configuration settings."""
    timezone: str = Field(default="UTC", description="Default timezone")
    base_currency: str = Field(default="USD", description="Default base currency")


class AdapterConfig(BaseModel):
    """Adapter configuration for external data sources."""
    enabled: bool = Field(default=False, description="Whether the adapter is enabled")


class AdaptersConfig(BaseModel):
    """Configuration for all adapters."""
    price_adapter: AdapterConfig = Field(default_factory=AdapterConfig)
    fx_adapter: AdapterConfig = Field(default_factory=AdapterConfig)


class Config(BaseModel):
    """Simple configuration with sensible defaults for development."""
    
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    app: AppConfig = Field(default_factory=AppConfig)
    adapters: AdaptersConfig = Field(default_factory=AdaptersConfig)
    
    def get_database_url(self) -> str:
        """Get SQLite database URL for SQLAlchemy."""
        return f"sqlite:///{self.database.path}"
    
    def get_api_url(self) -> str:
        """Get full API URL."""
        return f"http://{self.api.host}:{self.api.port}"
    
    def is_local_first_mode(self) -> bool:
        """Check if application is running in local-first mode."""
        # Local-first means no external adapters are enabled
        return not (
            self.adapters.price_adapter.enabled or 
            self.adapters.fx_adapter.enabled
        )


def load_config() -> Config:
    """Load configuration with defaults."""
    return Config()


def get_config() -> Config:
    """Get a default configuration instance."""
    return Config()