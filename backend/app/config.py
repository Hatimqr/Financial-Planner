"""
Configuration management for the Financial Planning Application.

This module provides Pydantic-based configuration parsing with support for:
- YAML file configuration
- Environment variable overrides  
- Configuration validation
- Local-first principles (adapters disabled by default)
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, Field, validator


class DatabaseConfig(BaseModel):
    """Database configuration settings."""
    path: str = Field(default="./data/app.db", description="SQLite database file path")
    echo: bool = Field(default=False, description="Enable SQL query logging")
    
    @validator('path')
    def validate_path(cls, v):
        """Ensure the database directory exists."""
        db_path = Path(v)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return v


class APIConfig(BaseModel):
    """API server configuration settings."""
    host: str = Field(default="localhost", description="API server host")
    port: int = Field(default=8000, ge=1024, le=65535, description="API server port")
    debug: bool = Field(default=True, description="Enable debug mode")
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
    
    @validator('level')
    def validate_level(cls, v):
        """Validate logging level."""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid logging level. Must be one of: {valid_levels}")
        return v.upper()
    
    @validator('file')
    def validate_file(cls, v):
        """Ensure the log directory exists if file logging is enabled."""
        if v:
            log_path = Path(v)
            log_path.parent.mkdir(parents=True, exist_ok=True)
        return v


class PriceAdapterConfig(BaseModel):
    """Price adapter configuration settings."""
    enabled: bool = Field(default=False, description="Enable price adapter")
    provider: Optional[str] = Field(default=None, description="Price data provider")
    api_key: Optional[str] = Field(default=None, description="API key for provider")
    cache_ttl: int = Field(default=3600, ge=0, description="Cache TTL in seconds")


class FXAdapterConfig(BaseModel):
    """FX adapter configuration settings."""
    enabled: bool = Field(default=False, description="Enable FX adapter")
    provider: Optional[str] = Field(default=None, description="FX data provider")
    api_key: Optional[str] = Field(default=None, description="API key for provider")
    cache_ttl: int = Field(default=3600, ge=0, description="Cache TTL in seconds")


class BrokerImportConfig(BaseModel):
    """Broker import adapter configuration settings."""
    enabled: bool = Field(default=False, description="Enable broker import adapters")
    providers: List[str] = Field(default_factory=list, description="Enabled broker adapters")


class AdaptersConfig(BaseModel):
    """All adapter configuration settings."""
    price_adapter: PriceAdapterConfig = Field(default_factory=PriceAdapterConfig)
    fx_adapter: FXAdapterConfig = Field(default_factory=FXAdapterConfig)
    broker_import: BrokerImportConfig = Field(default_factory=BrokerImportConfig)


class AppConfig(BaseModel):
    """Application-specific configuration settings."""
    timezone: str = Field(default="UTC", description="Default timezone")
    base_currency: str = Field(default="USD", description="Default base currency")
    backup_on_startup: bool = Field(default=True, description="Create backup on startup")
    backup_retention_days: int = Field(default=30, ge=1, description="Backup retention period")


class Config(BaseModel):
    """
    Main configuration class that loads settings from YAML file and environment variables.
    
    Environment variables take precedence over YAML file settings.
    Use double underscore to represent nested keys (e.g., DATABASE__PATH).
    """
    
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    adapters: AdaptersConfig = Field(default_factory=AdaptersConfig)
    app: AppConfig = Field(default_factory=AppConfig)
    
    def __init__(self, config_file: Optional[Union[str, Path]] = None, **kwargs):
        """
        Initialize configuration from YAML file and environment variables.
        
        Args:
            config_file: Path to YAML configuration file. Defaults to 'config.yaml'
            **kwargs: Additional configuration overrides
        """
        if config_file is None:
            config_file = Path("config.yaml")
        
        # Load configuration from YAML file
        yaml_config = self._load_yaml_config(config_file)
        
        # Apply environment variable overrides
        env_config = self._load_env_overrides()
        
        # Merge configs: YAML < env vars < kwargs
        merged_config = {**yaml_config, **env_config, **kwargs}
        
        # Initialize with merged configuration
        super().__init__(**merged_config)
    
    @staticmethod
    def _load_yaml_config(config_file: Union[str, Path]) -> Dict:
        """
        Load configuration from YAML file.
        
        Args:
            config_file: Path to YAML configuration file
            
        Returns:
            Dictionary with configuration data
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If config file has invalid YAML
        """
        config_path = Path(config_file)
        
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in configuration file: {e}")
        
        return config_data
    
    @staticmethod
    def _load_env_overrides() -> Dict:
        """
        Load configuration overrides from environment variables.
        
        Environment variables follow the pattern: APP__SECTION__KEY
        For example: APP__DATABASE__PATH, APP__API__PORT, etc.
        
        Returns:
            Dictionary with environment overrides
        """
        env_config = {}
        
        for key, value in os.environ.items():
            if key.startswith('APP__'):
                # Remove APP__ prefix and split by __
                parts = key[5:].lower().split('__')
                
                if len(parts) >= 2:
                    section = parts[0]
                    field = parts[1]
                    
                    # Initialize section if not exists
                    if section not in env_config:
                        env_config[section] = {}
                    
                    # Handle nested fields (like adapters__price_adapter__enabled)
                    if len(parts) == 3:
                        subsection = parts[1]
                        field = parts[2]
                        
                        if subsection not in env_config[section]:
                            env_config[section][subsection] = {}
                        
                        env_config[section][subsection][field] = _parse_env_value(value)
                    else:
                        env_config[section][field] = _parse_env_value(value)
        
        return env_config
    
    def get_database_url(self) -> str:
        """
        Get SQLite database URL for SQLAlchemy.
        
        Returns:
            SQLite database URL string
        """
        return f"sqlite:///{self.database.path}"
    
    def get_api_url(self) -> str:
        """
        Get full API URL.
        
        Returns:
            Full API URL string
        """
        return f"http://{self.api.host}:{self.api.port}"
    
    def is_local_first_mode(self) -> bool:
        """
        Check if application is in local-first mode (all adapters disabled).
        
        Returns:
            True if all adapters are disabled, False otherwise
        """
        return not any([
            self.adapters.price_adapter.enabled,
            self.adapters.fx_adapter.enabled,
            self.adapters.broker_import.enabled
        ])


def _parse_env_value(value: str) -> Union[str, int, bool, None]:
    """
    Parse environment variable value to appropriate Python type.
    
    Args:
        value: String value from environment
        
    Returns:
        Parsed value with appropriate type
    """
    # Handle boolean values
    if value.lower() in ('true', '1', 'yes', 'on'):
        return True
    elif value.lower() in ('false', '0', 'no', 'off'):
        return False
    
    # Handle None/null values
    if value.lower() in ('null', 'none', ''):
        return None
    
    # Try to parse as integer
    try:
        return int(value)
    except ValueError:
        pass
    
    # Return as string
    return value


# Global configuration instance
config: Optional[Config] = None


def load_config(config_file: Optional[Union[str, Path]] = None) -> Config:
    """
    Load and return the application configuration.
    
    Args:
        config_file: Path to YAML configuration file
        
    Returns:
        Loaded configuration instance
    """
    global config
    config = Config(config_file=config_file)
    return config


def get_config() -> Config:
    """
    Get the current configuration instance.
    
    Returns:
        Current configuration instance
        
    Raises:
        RuntimeError: If configuration hasn't been loaded yet
    """
    if config is None:
        raise RuntimeError("Configuration not loaded. Call load_config() first.")
    return config