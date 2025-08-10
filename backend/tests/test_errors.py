"""
Tests for the error handling system.
"""

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.errors import (
    FinancialPlanningError,
    ValidationError,
    NotFoundError,
    ConflictError,
    AuthenticationError,
    AuthorizationError,
    BusinessLogicError,
    ExternalServiceError,
    create_error_response,
)


class TestCustomExceptions:
    """Test custom exception classes."""
    
    def test_financial_planning_error(self):
        """Test base exception class."""
        error = FinancialPlanningError(
            message="Test error",
            code="TEST_ERROR",
            details={"field": "value"},
            status_code=400,
        )
        
        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.code == "TEST_ERROR"
        assert error.details == {"field": "value"}
        assert error.status_code == 400
    
    def test_validation_error(self):
        """Test validation error."""
        error = ValidationError("Invalid input", {"field": "name"})
        
        assert error.code == "VALIDATION_ERROR"
        assert error.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert error.details == {"field": "name"}
    
    def test_not_found_error(self):
        """Test not found error."""
        error = NotFoundError("User", "123")
        
        assert error.code == "NOT_FOUND"
        assert error.status_code == status.HTTP_404_NOT_FOUND
        assert "User not found (ID: 123)" in error.message
    
    def test_not_found_error_without_id(self):
        """Test not found error without ID."""
        error = NotFoundError("Account")
        
        assert "Account not found" in error.message
        assert "(ID:" not in error.message
    
    def test_conflict_error(self):
        """Test conflict error."""
        error = ConflictError("Resource already exists")
        
        assert error.code == "CONFLICT"
        assert error.status_code == status.HTTP_409_CONFLICT
    
    def test_authentication_error(self):
        """Test authentication error."""
        error = AuthenticationError()
        
        assert error.code == "AUTHENTICATION_ERROR"
        assert error.status_code == status.HTTP_401_UNAUTHORIZED
        assert error.message == "Authentication required"
    
    def test_authorization_error(self):
        """Test authorization error."""
        error = AuthorizationError()
        
        assert error.code == "AUTHORIZATION_ERROR"
        assert error.status_code == status.HTTP_403_FORBIDDEN
        assert error.message == "Insufficient permissions"
    
    def test_business_logic_error(self):
        """Test business logic error."""
        error = BusinessLogicError("Transaction must be balanced")
        
        assert error.code == "BUSINESS_LOGIC_ERROR"
        assert error.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_external_service_error(self):
        """Test external service error."""
        error = ExternalServiceError("Price API", "Connection timeout")
        
        assert error.code == "EXTERNAL_SERVICE_ERROR"
        assert error.status_code == status.HTTP_502_BAD_GATEWAY
        assert "Price API service error: Connection timeout" in error.message


class TestErrorResponse:
    """Test error response creation."""
    
    def test_create_error_response(self):
        """Test creating standardized error response."""
        response = create_error_response(
            code="TEST_ERROR",
            message="Test message",
            details={"field": "value"},
            request_id="test-123",
        )
        
        assert response.ok is False
        assert response.error.code == "TEST_ERROR"
        assert response.error.message == "Test message"
        assert response.error.details == {"field": "value"}
        assert response.request_id == "test-123"
    
    def test_create_error_response_minimal(self):
        """Test creating error response with minimal data."""
        response = create_error_response(
            code="SIMPLE_ERROR",
            message="Simple message",
        )
        
        assert response.ok is False
        assert response.error.code == "SIMPLE_ERROR"
        assert response.error.message == "Simple message"
        assert response.error.details is None
        assert response.request_id is None


class TestErrorHandlers:
    """Test error handlers with FastAPI."""
    
    def test_test_error_endpoint(self):
        """Test the test error endpoint."""
        # Import here to avoid circular imports
        from main import app
        
        client = TestClient(app)
        response = client.get("/test-error")
        
        assert response.status_code == 422
        
        data = response.json()
        assert data["ok"] is False
        assert data["error"]["code"] == "VALIDATION_ERROR"
        assert data["error"]["message"] == "This is a test error"
        assert data["error"]["details"] == {"field": "test"}
        assert "request_id" in data
    
    def test_404_error_handling(self):
        """Test 404 error handling."""
        from main import app
        
        client = TestClient(app)
        response = client.get("/nonexistent-endpoint")
        
        assert response.status_code == 404
        
        data = response.json()
        assert data["ok"] is False
        assert data["error"]["code"] == "NOT_FOUND"
        assert "request_id" in data
    
    def test_successful_request(self):
        """Test successful request doesn't trigger error handlers."""
        from main import app
        
        client = TestClient(app)
        response = client.get("/")
        
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert data["service"] == "Financial Planning API"