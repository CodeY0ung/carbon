"""
Unit tests for the carbon-aware scheduling operator.
Tests mock Kubernetes client and FastAPI calls.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from operator import get_current_carbon, determine_scheduling_strategy


@pytest.mark.asyncio
async def test_get_current_carbon_success():
    """Test successful carbon intensity fetch from FastAPI /current endpoint."""
    mock_response_data = {
        "zone": "US-CA",
        "carbonIntensity": 245,
        "datetime": "2024-01-15T10:00:00.000Z",
        "fetchedAt": 1705315523.145
    }

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        result = await get_current_carbon()

        assert result is not None
        assert result["zone"] == "US-CA"
        assert result["carbonIntensity"] == 245
        assert "fetchedAt" in result


@pytest.mark.asyncio
async def test_get_current_carbon_failure():
    """Test handling of HTTP errors when fetching carbon data."""
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Connection failed")
        mock_client_class.return_value.__aenter__.return_value = mock_client

        result = await get_current_carbon()

        assert result is None


def test_determine_scheduling_strategy_high_carbon():
    """Test scheduling strategy for high carbon intensity."""
    strategy = determine_scheduling_strategy(350)

    assert strategy["strategy"] == "low_priority"
    assert strategy["reason"] == "high_carbon_intensity"
    assert strategy["node_selector"] == {"energy_profile": "low_priority"}
    assert strategy["node_affinity"] is not None
    assert "preferredDuringSchedulingIgnoredDuringExecution" in strategy["node_affinity"]


def test_determine_scheduling_strategy_low_carbon():
    """Test scheduling strategy for low carbon intensity."""
    strategy = determine_scheduling_strategy(100)

    assert strategy["strategy"] == "low_carbon"
    assert strategy["reason"] == "low_carbon_intensity"
    assert strategy["node_selector"] is None
    assert strategy["node_affinity"] is not None
    assert "preferredDuringSchedulingIgnoredDuringExecution" in strategy["node_affinity"]


def test_determine_scheduling_strategy_medium_carbon():
    """Test scheduling strategy for medium carbon intensity."""
    strategy = determine_scheduling_strategy(200)

    assert strategy["strategy"] == "default"
    assert strategy["reason"] == "medium_carbon_intensity"
    assert strategy["node_selector"] is None
    assert strategy["node_affinity"] is None


def test_determine_scheduling_strategy_no_data():
    """Test scheduling strategy when carbon data is unavailable."""
    strategy = determine_scheduling_strategy(None)

    assert strategy["strategy"] == "default"
    assert strategy["reason"] == "carbon_data_unavailable"
    assert strategy["node_selector"] is None
    assert strategy["node_affinity"] is None


def test_determine_scheduling_strategy_threshold_boundary():
    """Test scheduling strategy at threshold boundaries."""
    # Exactly at low threshold
    strategy_low = determine_scheduling_strategy(150)
    assert strategy_low["strategy"] == "low_carbon"

    # Just above low threshold
    strategy_medium = determine_scheduling_strategy(151)
    assert strategy_medium["strategy"] == "default"

    # Exactly at high threshold
    strategy_medium_high = determine_scheduling_strategy(300)
    assert strategy_medium_high["strategy"] == "default"

    # Just above high threshold
    strategy_high = determine_scheduling_strategy(301)
    assert strategy_high["strategy"] == "low_priority"


def test_node_affinity_structure_high_carbon():
    """Test that node affinity has correct structure for high carbon."""
    strategy = determine_scheduling_strategy(400)

    affinity = strategy["node_affinity"]
    assert "preferredDuringSchedulingIgnoredDuringExecution" in affinity

    preferences = affinity["preferredDuringSchedulingIgnoredDuringExecution"]
    assert len(preferences) == 1
    assert preferences[0]["weight"] == 100

    match_expressions = preferences[0]["preference"]["matchExpressions"]
    assert len(match_expressions) == 1
    assert match_expressions[0]["key"] == "energy_profile"
    assert match_expressions[0]["operator"] == "In"
    assert "low_priority" in match_expressions[0]["values"]


def test_node_affinity_structure_low_carbon():
    """Test that node affinity has correct structure for low carbon."""
    strategy = determine_scheduling_strategy(100)

    affinity = strategy["node_affinity"]
    assert "preferredDuringSchedulingIgnoredDuringExecution" in affinity

    preferences = affinity["preferredDuringSchedulingIgnoredDuringExecution"]
    assert len(preferences) == 1
    assert preferences[0]["weight"] == 100

    match_expressions = preferences[0]["preference"]["matchExpressions"]
    assert len(match_expressions) == 1
    assert match_expressions[0]["key"] == "energy_profile"
    assert match_expressions[0]["operator"] == "In"
    assert "low_carbon" in match_expressions[0]["values"]
    assert "renewable" in match_expressions[0]["values"]


@pytest.mark.asyncio
async def test_get_current_carbon_timeout():
    """Test handling of timeout when fetching carbon data."""
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Timeout")
        mock_client_class.return_value.__aenter__.return_value = mock_client

        result = await get_current_carbon()

        assert result is None


def test_scheduling_strategy_values():
    """Test that all possible strategies are covered."""
    strategies = {
        determine_scheduling_strategy(None)["strategy"],
        determine_scheduling_strategy(50)["strategy"],
        determine_scheduling_strategy(200)["strategy"],
        determine_scheduling_strategy(400)["strategy"],
    }

    expected = {"default", "low_carbon", "low_priority"}
    assert strategies == expected
