"""
Unit tests for main FastAPI application.
Tests the /current endpoint and validates response structure.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
from app.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


def test_root_endpoint(client):
    """Test the root health check endpoint."""
    response = client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "carbon-aware-scheduler"
    assert "version" in data


def test_current_endpoint_with_data():
    """Test /current endpoint returns valid structure when data is available."""
    # Mock carbon client with data
    mock_data = {
        "zone": "US-CA",
        "carbonIntensity": 245,
        "datetime": "2024-01-15T10:00:00.000Z",
        "updatedAt": "2024-01-15T10:05:23.145Z",
        "fetchedAt": 1705315523.145
    }

    with patch("app.main.carbon_client") as mock_client:
        mock_client.latest_data = mock_data

        client = TestClient(app)
        response = client.get("/current")

        assert response.status_code == 200
        data = response.json()

        # Validate response structure
        assert "zone" in data
        assert "carbonIntensity" in data
        assert "datetime" in data
        assert "fetchedAt" in data

        # Validate data values
        assert data["zone"] == "US-CA"
        assert data["carbonIntensity"] == 245
        assert isinstance(data["fetchedAt"], float)


def test_current_endpoint_no_data():
    """Test /current endpoint when no data is available."""
    with patch("app.main.carbon_client") as mock_client:
        mock_client.latest_data = None

        client = TestClient(app)
        response = client.get("/current")

        # Should return error when no data available
        assert response.status_code == 503 or response.status_code == 200
        data = response.json()

        # Check if error response or empty response
        if response.status_code == 503:
            assert "error" in data or "message" in data


def test_metrics_endpoint():
    """Test /metrics endpoint returns Prometheus format."""
    client = TestClient(app)
    response = client.get("/metrics")

    assert response.status_code == 200

    # Check content type
    assert "text/plain" in response.headers.get("content-type", "")

    # Check for expected metrics in output
    content = response.text
    assert "grid_carbon_intensity_gco2_per_kwh" in content or "carbon_last_updated_unix" in content or "api_requests_total" in content


def test_current_endpoint_structure():
    """Test that /current endpoint returns expected JSON structure."""
    mock_data = {
        "zone": "DE",
        "carbonIntensity": 350,
        "datetime": "2024-01-15T12:00:00.000Z",
        "updatedAt": "2024-01-15T12:05:00.000Z",
        "fetchedAt": 1705323900.0
    }

    with patch("app.main.carbon_client") as mock_client:
        mock_client.latest_data = mock_data

        client = TestClient(app)
        response = client.get("/current")

        assert response.status_code == 200
        data = response.json()

        # Validate all expected fields are present
        required_fields = ["zone", "carbonIntensity", "datetime", "fetchedAt"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Validate data types
        assert isinstance(data["zone"], str)
        assert isinstance(data["carbonIntensity"], (int, float))
        assert isinstance(data["datetime"], str)
        assert isinstance(data["fetchedAt"], (int, float))


@pytest.mark.asyncio
async def test_current_endpoint_cached_data():
    """Test that /current uses cached data from carbon_client."""
    mock_data = {
        "zone": "FR",
        "carbonIntensity": 100,
        "datetime": "2024-01-15T14:00:00.000Z",
        "updatedAt": "2024-01-15T14:05:00.000Z",
        "fetchedAt": 1705330800.0
    }

    with patch("app.main.carbon_client") as mock_client:
        mock_client.latest_data = mock_data

        client = TestClient(app)
        response = client.get("/current")

        assert response.status_code == 200
        data = response.json()

        # Verify it returns the cached data
        assert data["zone"] == "FR"
        assert data["carbonIntensity"] == 100
