"""Test cases for main application."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_endpoint():
    """Test root endpoint returns correct message."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Financial Planning API is running"}


def test_health_endpoint():
    """Test health endpoint returns healthy status."""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
