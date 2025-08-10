"""Logging configuration for the Financial Planning application."""

import logging
import logging.config
import sys
from pathlib import Path
from typing import Any

from .config import config


def setup_logging() -> None:
    """Set up logging configuration based on config settings."""
    log_config = _get_logging_config()

    # Ensure log directory exists
    if config.logging.file:
        log_path = Path(config.logging.file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

    logging.config.dictConfig(log_config)


def _get_logging_config() -> dict[str, Any]:
    """Generate logging configuration dictionary."""
    log_level = config.logging.level.upper()

    handlers = {
        "console": {
            "class": "logging.StreamHandler",
            "stream": sys.stdout,
            "level": log_level,
        }
    }

    # Configure formatter based on format setting
    if config.logging.format == "json":
        handlers["console"]["formatter"] = "json"
        formatters = {
            "json": {
                "class": "pythonjsonlogger.jsonlogger.JsonFormatter",
                "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
            }
        }
    else:
        handlers["console"]["formatter"] = "standard"
        formatters = {
            "standard": {
                "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            }
        }

    # Add file handler if configured
    if config.logging.file:
        handlers["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": config.logging.file,
            "maxBytes": 10 * 1024 * 1024,  # 10MB
            "backupCount": 5,
            "level": log_level,
            "formatter": "json" if config.logging.format == "json" else "standard",
        }

    handler_list = ["console"]
    if config.logging.file:
        handler_list.append("file")

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": formatters,
        "handlers": handlers,
        "loggers": {
            "": {  # root logger
                "level": log_level,
                "handlers": handler_list,
            },
            "uvicorn": {
                "level": "INFO",
                "handlers": handler_list,
                "propagate": False,
            },
            "sqlalchemy.engine": {
                "level": "INFO" if config.database.echo else "WARNING",
                "handlers": handler_list,
                "propagate": False,
            },
        },
    }
