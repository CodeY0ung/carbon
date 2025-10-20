"""
Unit tests for carbon_client module.
Tests the CarbonClient class including mocked httpx responses.
"""

import pytest
import time
from unittest.mock import AsyncMock, patch
from app.carbon_client import CarbonClient


@pytest.mark.asyncio
async def test_fetch_latest_success():
    """Test successful carbon intensity fetch with mocked httpx response."""
    client = CarbonClient(api_key="test_api_key", poll_interval=30)

    # Mock response data
    mock_response_data = {
        "zone": "US-CA",
        "carbonIntensity": 245,
        "datetime": "2024-01-15T10:00:00.000Z",
        "updatedAt": "2024-01-15T10:05:23.145Z",
        "emissionFactorType": "lifecycle",
        "isEstimated": False
    }

    # Mock httpx.AsyncClient
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Fetch data
        result = await client.fetch_latest(zone="US-CA")

        # Assertions
        assert result is not None
        assert result["zone"] == "US-CA"
        assert result["carbonIntensity"] == 245
        assert "fetchedAt" in result
        assert isinstance(result["fetchedAt"], float)

        # Verify httpx was called correctly
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert call_args[1]["params"]["zone"] == "US-CA"
        assert call_args[1]["headers"]["auth-token"] == "test_api_key"


@pytest.mark.asyncio
async def test_fetch_latest_http_error():
    """Test handling of HTTP errors during fetch."""
    client = CarbonClient(api_key="test_api_key", poll_interval=30)

    # Mock httpx.AsyncClient with HTTPStatusError
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = Exception("HTTP 401 Unauthorized")
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Fetch data should return None on error
        result = await client.fetch_latest(zone="US-CA")

        assert result is None


@pytest.mark.asyncio
async def test_fetch_latest_request_error():
    """Test handling of network request errors."""
    client = CarbonClient(api_key="test_api_key", poll_interval=30)

    # Mock httpx.AsyncClient with RequestError
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Network error")
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Fetch data should return None on error
        result = await client.fetch_latest(zone="DE")

        assert result is None


@pytest.mark.asyncio
async def test_start_polling():
    """Test starting background polling."""
    client = CarbonClient(api_key="test_api_key", poll_interval=30)

    mock_data = {
        "zone": "US-CA",
        "carbonIntensity": 200,
        "datetime": "2024-01-15T10:00:00.000Z"
    }

    # Mock fetch_latest
    with patch.object(client, 'fetch_latest', return_value=mock_data) as mock_fetch:
        await client.start_polling(zone="US-CA")

        # Verify initial fetch was called
        mock_fetch.assert_called_once_with("US-CA")

        # Verify data was stored
        assert client.latest_data is not None
        assert client.latest_data["carbonIntensity"] == 200

        # Verify polling is running
        assert client._running is True
        assert client._polling_task is not None

        # Stop polling
        await client.stop_polling()


@pytest.mark.asyncio
async def test_stop_polling():
    """Test stopping background polling."""
    client = CarbonClient(api_key="test_api_key", poll_interval=30)

    mock_data = {
        "zone": "US-CA",
        "carbonIntensity": 200,
        "datetime": "2024-01-15T10:00:00.000Z"
    }

    # Mock fetch_latest
    with patch.object(client, 'fetch_latest', return_value=mock_data):
        await client.start_polling(zone="US-CA")

        # Verify polling started
        assert client._running is True

        # Stop polling
        await client.stop_polling()

        # Verify polling stopped
        assert client._running is False


@pytest.mark.asyncio
async def test_latest_data_property():
    """Test the latest_data property."""
    client = CarbonClient(api_key="test_api_key", poll_interval=30)

    # Initially should be None
    assert client.latest_data is None

    # Set data
    test_data = {"zone": "DE", "carbonIntensity": 350}
    client._latest_data = test_data

    # Verify property returns data
    assert client.latest_data == test_data
