"""Configuration management for the Financial Planning application."""

import os
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field


class DatabaseConfig(BaseModel):
    """Database configuration."""

    type: str = "sqlite"
    path: str = "./data/app.db"
    echo: bool = False


class APIConfig(BaseModel):
    """API configuration."""

    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = True
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:5173"]
    )


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = "INFO"
    format: str = "json"
    file: Optional[str] = "./data/logs/app.log"


class AppConfig(BaseModel):
    """Application-specific configuration."""

    base_currency: str = "USD"
    timezone: str = "UTC"
    data_adapters: dict[str, Any] = Field(
        default_factory=lambda: {
            "enabled": False,
            "price_adapter": None,
            "fx_adapter": None,
        }
    )


class SecurityConfig(BaseModel):
    """Security configuration."""

    db_encryption: bool = False
    backup_encryption: bool = False
    max_backup_files: int = 10


class PerformanceConfig(BaseModel):
    """Performance configuration."""

    cache_prices: bool = True
    cache_ttl: int = 3600
    max_db_connections: int = 10


class Config(BaseModel):
    """Main configuration class."""

    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    app: AppConfig = Field(default_factory=AppConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)

    @classmethod
    def load_from_file(cls, config_path: Optional[str] = None) -> "Config":
        """Load configuration from YAML file with environment variable overrides."""
        if config_path is None:
            # Look for config file in project root
            project_root = Path(__file__).parent.parent.parent
            config_path = project_root / "config.yaml"

        config_data = {}

        # Load from YAML file if it exists
        if Path(config_path).exists():
            with open(config_path) as f:
                config_data = yaml.safe_load(f) or {}

        # Override with environment variables
        config_data = cls._apply_env_overrides(config_data)

        return cls(**config_data)

    @staticmethod
    def _apply_env_overrides(config_data: dict[str, Any]) -> dict[str, Any]:
        """Apply environment variable overrides to config data."""
        env_mappings = {
            "FP_DB_PATH": ("database", "path"),
            "FP_DB_ECHO": ("database", "echo"),
            "FP_API_HOST": ("api", "host"),
            "FP_API_PORT": ("api", "port"),
            "FP_LOG_LEVEL": ("logging", "level"),
            "FP_BASE_CURRENCY": ("app", "base_currency"),
            "FP_TIMEZONE": ("app", "timezone"),
        }

        for env_var, (section, key) in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                if section not in config_data:
                    config_data[section] = {}

                # Convert string values to appropriate types
                if key in [
                    "port",
                    "cache_ttl",
                    "max_db_connections",
                    "max_backup_files",
                ]:
                    config_data[section][key] = int(value)
                elif key in [
                    "echo",
                    "reload",
                    "cache_prices",
                    "db_encryption",
                    "backup_encryption",
                ]:
                    config_data[section][key] = value.lower() in ("true", "1", "yes")
                else:
                    config_data[section][key] = value

        return config_data


# Global configuration instance
config = Config.load_from_file()
