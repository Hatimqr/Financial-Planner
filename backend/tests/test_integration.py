"""
Integration tests for the application components.
"""

import tempfile
from pathlib import Path

import pytest

from app.config import Config
from app.logging import setup_logging, get_logger


class TestConfigIntegration:
    """Test integration between configuration and other components."""
    
    def test_logging_with_config(self):
        """Test that logging can be configured via config object."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create config with custom logging settings
            config_data = {
                "logging": {
                    "level": "DEBUG",
                    "file": str(Path(temp_dir) / "test.log")
                }
            }
            config = Config(**config_data)
            
            # Setup logging with config
            setup_logging(
                level=config.logging.level,
                log_file="test.log",
                log_dir=temp_dir,
                enable_console=False,
            )
            
            # Test logging
            logger = get_logger("test.integration")
            logger.debug("Debug message")
            logger.info("Info message")
            
            # Verify log file was created and contains messages
            log_file = Path(temp_dir) / "test.log"
            assert log_file.exists()
            
            with open(log_file) as f:
                content = f.read()
                assert "Debug message" in content
                assert "Info message" in content
    
    def test_config_local_first_mode(self):
        """Test local-first mode detection."""
        # Default config should be in local-first mode
        config = Config()
        assert config.is_local_first_mode() is True
        
        # Config with enabled adapters should not be local-first
        config_data = {
            "adapters": {
                "price_adapter": {"enabled": True}
            }
        }
        config = Config(**config_data)
        assert config.is_local_first_mode() is False
    
    def test_config_urls(self):
        """Test URL generation from config."""
        config_data = {
            "api": {"host": "localhost", "port": 8080},
            "database": {"path": "./test.db"}
        }
        config = Config(**config_data)
        
        assert config.get_api_url() == "http://localhost:8080"
        assert config.get_database_url() == "sqlite:///./test.db"