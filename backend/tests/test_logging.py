"""
Tests for the logging system.
"""

import json
import logging
import tempfile
from pathlib import Path

import pytest

from app.logging import (
    StructuredFormatter,
    SimpleConsoleFormatter,
    setup_logging,
    get_logger,
    log_request,
    log_error,
)


class TestStructuredFormatter:
    """Test the structured JSON formatter."""
    
    def test_basic_formatting(self):
        """Test basic log formatting."""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=123,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.funcName = "test_function"
        record.module = "test_module"
        
        result = formatter.format(record)
        log_data = json.loads(result)
        
        assert log_data["level"] == "INFO"
        assert log_data["logger"] == "test.logger"
        assert log_data["message"] == "Test message"
        assert log_data["module"] == "test_module"
        assert log_data["function"] == "test_function"
        assert log_data["line"] == 123
        assert "timestamp" in log_data
    
    def test_extra_fields(self):
        """Test logging with extra fields."""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=123,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.funcName = "test_function"
        record.module = "test_module"
        record.request_id = "test-request-123"
        record.user_id = "user-456"
        record.duration_ms = 123.45
        
        result = formatter.format(record)
        log_data = json.loads(result)
        
        assert log_data["request_id"] == "test-request-123"
        assert log_data["user_id"] == "user-456"
        assert log_data["duration_ms"] == 123.45


class TestSimpleConsoleFormatter:
    """Test the simple console formatter."""
    
    def test_basic_formatting(self):
        """Test basic console formatting."""
        formatter = SimpleConsoleFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=123,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        result = formatter.format(record)
        
        assert "INFO" in result
        assert "test.logger" in result
        assert "Test message" in result
    
    def test_with_request_id(self):
        """Test console formatting with request ID."""
        formatter = SimpleConsoleFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=123,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.request_id = "test-request-123"
        
        result = formatter.format(record)
        
        assert "[test-request-123]" in result


class TestLoggingSetup:
    """Test logging configuration."""
    
    def test_setup_with_file(self):
        """Test logging setup with file output."""
        with tempfile.TemporaryDirectory() as temp_dir:
            setup_logging(
                level="DEBUG",
                log_file="test.log",
                log_dir=temp_dir,
                enable_console=False,
            )
            
            logger = get_logger("test.setup")
            logger.info("Test log message")
            
            log_file = Path(temp_dir) / "test.log"
            assert log_file.exists()
            
            # Check log content
            with open(log_file) as f:
                content = f.read()
                log_data = json.loads(content.strip())
                assert log_data["message"] == "Test log message"
                assert log_data["logger"] == "test.setup"
    
    def test_log_request_function(self):
        """Test the log_request helper function."""
        with tempfile.TemporaryDirectory() as temp_dir:
            setup_logging(
                level="INFO",
                log_file="test.log",
                log_dir=temp_dir,
                enable_console=False,
            )
            
            logger = get_logger("test.request")
            log_request(
                logger,
                method="GET",
                path="/api/test",
                status_code=200,
                duration_ms=123.45,
                request_id="test-123",
            )
            
            log_file = Path(temp_dir) / "test.log"
            with open(log_file) as f:
                content = f.read()
                log_data = json.loads(content.strip())
                assert "GET /api/test 200" in log_data["message"]
                assert log_data["request_id"] == "test-123"
                assert log_data["duration_ms"] == 123.45
    
    def test_log_error_function(self):
        """Test the log_error helper function."""
        with tempfile.TemporaryDirectory() as temp_dir:
            setup_logging(
                level="ERROR",
                log_file="test.log", 
                log_dir=temp_dir,
                enable_console=False,
            )
            
            logger = get_logger("test.error")
            test_error = ValueError("Test error message")
            
            log_error(
                logger,
                test_error,
                context={"test_field": "test_value"},
                request_id="test-456",
            )
            
            log_file = Path(temp_dir) / "test.log"
            with open(log_file) as f:
                content = f.read()
                log_data = json.loads(content.strip())
                assert "Error occurred: Test error message" in log_data["message"]
                assert log_data["request_id"] == "test-456"
                assert "exception" in log_data