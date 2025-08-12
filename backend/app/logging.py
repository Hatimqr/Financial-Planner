"""
Structured logging configuration for the financial planning application.

This module provides configurable logging with structured output for both
file and console, using Python's standard logging module.
"""

import json
import logging
import logging.config
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


class StructuredFormatter(logging.Formatter):
    """Custom formatter that outputs structured JSON logs."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
            
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        return json.dumps(log_entry, default=str)


class SimpleConsoleFormatter(logging.Formatter):
    """Simple console formatter for human-readable output."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record for console output."""
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        level = record.levelname.ljust(8)
        
        # Add request ID if present
        request_info = ""
        if hasattr(record, "request_id"):
            request_info = f" [{record.request_id}]"
        
        return f"{timestamp} {level} {record.name}{request_info}: {record.getMessage()}"


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    log_dir: str = "data/logs",
    enable_console: bool = True,
    structured_console: bool = False,
) -> None:
    """
    Configure structured logging for the application.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional specific log file name (defaults to app.log)
        log_dir: Directory for log files (created if doesn't exist)
        enable_console: Whether to enable console logging
        structured_console: Whether to use structured JSON format for console
    """
    # Create log directory if it doesn't exist
    if log_file:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        full_log_file = log_path / (log_file if log_file.endswith('.log') else f"{log_file}.log")
    else:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        full_log_file = log_path / "app.log"
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Clear any existing handlers
    root_logger.handlers.clear()
    
    # File handler with structured JSON format
    if full_log_file:
        file_handler = logging.FileHandler(full_log_file, encoding='utf-8')
        file_handler.setLevel(getattr(logging, level.upper()))
        file_handler.setFormatter(StructuredFormatter())
        root_logger.addHandler(file_handler)
    
    # Console handler
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, level.upper()))
        
        if structured_console:
            console_handler.setFormatter(StructuredFormatter())
        else:
            console_handler.setFormatter(SimpleConsoleFormatter())
        
        root_logger.addHandler(console_handler)
    
    # Set levels for noisy third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for the given name."""
    return logging.getLogger(name)


def log_request(
    logger: logging.Logger,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    request_id: Optional[str] = None,
    user_id: Optional[str] = None,
    **kwargs: Any,
) -> None:
    """
    Log an HTTP request with structured data.
    
    Args:
        logger: Logger instance to use
        method: HTTP method (GET, POST, etc.)
        path: Request path
        status_code: HTTP status code
        duration_ms: Request duration in milliseconds
        request_id: Optional request ID for tracing
        user_id: Optional user ID
        **kwargs: Additional fields to log
    """
    extra_fields = {
        "request_id": request_id,
        "duration_ms": duration_ms,
    }
    
    if user_id:
        extra_fields["user_id"] = user_id
    
    # Add any additional fields
    extra_fields.update(kwargs)
    
    message = f"{method} {path} {status_code} ({duration_ms:.1f}ms)"
    
    if status_code >= 500:
        logger.error(message, extra=extra_fields)
    elif status_code >= 400:
        logger.warning(message, extra=extra_fields)
    else:
        logger.info(message, extra=extra_fields)


def log_error(
    logger: logging.Logger,
    error: Exception,
    context: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> None:
    """
    Log an error with structured context.
    
    Args:
        logger: Logger instance to use
        error: Exception that occurred
        context: Optional context dictionary
        request_id: Optional request ID for tracing
    """
    extra_fields = {}
    
    if request_id:
        extra_fields["request_id"] = request_id
    
    if context:
        extra_fields.update(context)
    
    logger.error(f"Error occurred: {str(error)}", extra=extra_fields, exc_info=True)


# Application-specific loggers
app_logger = get_logger("financial_planning.app")
db_logger = get_logger("financial_planning.db")
api_logger = get_logger("financial_planning.api")
auth_logger = get_logger("financial_planning.auth")