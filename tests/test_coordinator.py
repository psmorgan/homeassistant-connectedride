"""Tests for BMW Connected Ride DataUpdateCoordinator."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add the project root to sys.path so we can import without HA
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from custom_components.bmw_connected_ride.auth import BMWAuthError
from custom_components.bmw_connected_ride.coordinator import (
    BMWConnectedRideCoordinator,
    SCAN_INTERVAL,
)

# We need to mock HA imports used by coordinator
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_BIKES = [
    {
        "vin": "WB10X0X00X0000001",
        "name": "My R 1300 GS",
        "fuelLevel": 72,
        "remainingRange": 245000.0,
        "lastConnectedTime": 1735689600,
        "_deleted": False,
    },
    {
        "vin": "WB10X0X00X0000002",
        "name": "My S 1000 RR",
        "fuelLevel": 45,
        "remainingRange": 120000.0,
        "lastConnectedTime": 1735600000,
        "_deleted": False,
    },
]


def _make_mock_hass():
    """Create a minimal mock HomeAssistant instance."""
    hass = MagicMock()
    hass.config_entries = MagicMock()
    hass.config_entries.async_update_entry = MagicMock()
    # DataUpdateCoordinator needs these
    hass.loop = None
    hass.async_create_task = MagicMock()
    return hass


def _make_mock_entry(data=None):
    """Create a minimal mock ConfigEntry."""
    entry = MagicMock()
    entry.data = data or {
        "region": "ROW",
        "access_token": "test-access",
        "refresh_token": "test-refresh",
        "token_expiry": 9999999999,
        "client_id_header": "test-uuid",
    }
    return entry


def _make_mock_auth_client(tokens_changed=False):
    """Create a mock BMWAuthClient."""
    auth = MagicMock()
    auth.async_ensure_token_valid = AsyncMock()
    auth.access_token = "test-access-token"
    auth.refresh_token = "test-refresh-token"
    auth.token_expiry = 9999999999
    auth.tokens_changed = tokens_changed
    return auth


def _make_mock_api_client(bikes=None):
    """Create a mock BMWApiClient."""
    api = MagicMock()
    api.async_get_bikes = AsyncMock(return_value=bikes if bikes is not None else SAMPLE_BIKES)
    return api


# ---------------------------------------------------------------------------
# Coordinator tests
# ---------------------------------------------------------------------------


class TestCoordinatorInit:
    """Tests for BMWConnectedRideCoordinator constructor."""

    def test_update_interval_is_30_minutes(self):
        """DATA-01: Coordinator polls every 30 minutes."""
        assert SCAN_INTERVAL == timedelta(minutes=30)

    def test_coordinator_has_correct_update_interval(self):
        """Coordinator instance uses SCAN_INTERVAL."""
        hass = _make_mock_hass()
        entry = _make_mock_entry()
        auth = _make_mock_auth_client()
        api = _make_mock_api_client()

        coordinator = BMWConnectedRideCoordinator(hass, entry, auth, api)

        assert coordinator.update_interval == timedelta(minutes=30)

    def test_coordinator_name(self):
        """Coordinator has descriptive name."""
        hass = _make_mock_hass()
        entry = _make_mock_entry()
        auth = _make_mock_auth_client()
        api = _make_mock_api_client()

        coordinator = BMWConnectedRideCoordinator(hass, entry, auth, api)

        assert coordinator.name == "BMW Connected Ride"


class TestAsyncUpdateData:
    """Tests for BMWConnectedRideCoordinator._async_update_data."""

    @pytest.mark.asyncio
    async def test_returns_vin_keyed_dict(self):
        """DATA-02: Returns dict keyed by VIN with all active bikes."""
        hass = _make_mock_hass()
        entry = _make_mock_entry()
        auth = _make_mock_auth_client()
        api = _make_mock_api_client(bikes=SAMPLE_BIKES)

        coordinator = BMWConnectedRideCoordinator(hass, entry, auth, api)
        result = await coordinator._async_update_data()

        assert "WB10X0X00X0000001" in result
        assert "WB10X0X00X0000002" in result
        assert result["WB10X0X00X0000001"]["name"] == "My R 1300 GS"
        assert result["WB10X0X00X0000002"]["name"] == "My S 1000 RR"

    @pytest.mark.asyncio
    async def test_filters_deleted_bikes(self):
        """DATA-02: Deleted bikes are excluded from result."""
        bikes = [
            {"vin": "VIN001", "name": "Active Bike", "_deleted": False},
            {"vin": "VIN002", "name": "Deleted Bike", "_deleted": True},
        ]
        hass = _make_mock_hass()
        entry = _make_mock_entry()
        auth = _make_mock_auth_client()
        api = _make_mock_api_client(bikes=bikes)

        coordinator = BMWConnectedRideCoordinator(hass, entry, auth, api)
        result = await coordinator._async_update_data()

        assert "VIN001" in result
        assert "VIN002" not in result

    @pytest.mark.asyncio
    async def test_no_deleted_field_treated_as_active(self):
        """Bikes without _deleted field are treated as active."""
        bikes = [{"vin": "VIN001", "name": "Bike"}]
        hass = _make_mock_hass()
        entry = _make_mock_entry()
        auth = _make_mock_auth_client()
        api = _make_mock_api_client(bikes=bikes)

        coordinator = BMWConnectedRideCoordinator(hass, entry, auth, api)
        result = await coordinator._async_update_data()

        assert "VIN001" in result

    @pytest.mark.asyncio
    async def test_calls_ensure_token_valid_before_get_bikes(self):
        """Auth token is validated before API call."""
        hass = _make_mock_hass()
        entry = _make_mock_entry()
        auth = _make_mock_auth_client()
        api = _make_mock_api_client()

        coordinator = BMWConnectedRideCoordinator(hass, entry, auth, api)
        await coordinator._async_update_data()

        auth.async_ensure_token_valid.assert_awaited_once()
        api.async_get_bikes.assert_awaited_once_with(auth.access_token)

    @pytest.mark.asyncio
    async def test_auth_error_from_auth_client_raises_config_entry_auth_failed(self):
        """BMWAuthError from auth_client raises ConfigEntryAuthFailed."""
        hass = _make_mock_hass()
        entry = _make_mock_entry()
        auth = _make_mock_auth_client()
        auth.async_ensure_token_valid = AsyncMock(
            side_effect=BMWAuthError("Token expired")
        )
        api = _make_mock_api_client()

        coordinator = BMWConnectedRideCoordinator(hass, entry, auth, api)

        with pytest.raises(ConfigEntryAuthFailed, match="BMW auth failed"):
            await coordinator._async_update_data()

    @pytest.mark.asyncio
    async def test_auth_error_from_api_client_raises_config_entry_auth_failed(self):
        """BMWAuthError from api_client raises ConfigEntryAuthFailed."""
        hass = _make_mock_hass()
        entry = _make_mock_entry()
        auth = _make_mock_auth_client()
        api = _make_mock_api_client()
        api.async_get_bikes = AsyncMock(
            side_effect=BMWAuthError("HTTP 401")
        )

        coordinator = BMWConnectedRideCoordinator(hass, entry, auth, api)

        with pytest.raises(ConfigEntryAuthFailed, match="BMW auth failed"):
            await coordinator._async_update_data()

    @pytest.mark.asyncio
    async def test_other_exception_from_api_raises_update_failed(self):
        """DATA-03: Non-auth exceptions raise UpdateFailed."""
        hass = _make_mock_hass()
        entry = _make_mock_entry()
        auth = _make_mock_auth_client()
        api = _make_mock_api_client()
        api.async_get_bikes = AsyncMock(
            side_effect=ConnectionError("Network unreachable")
        )

        coordinator = BMWConnectedRideCoordinator(hass, entry, auth, api)

        with pytest.raises(UpdateFailed, match="Cannot fetch BMW bike data"):
            await coordinator._async_update_data()

    @pytest.mark.asyncio
    async def test_token_persistence_when_tokens_changed(self):
        """Tokens persisted to config entry when auth_client.tokens_changed is True."""
        hass = _make_mock_hass()
        entry = _make_mock_entry()
        auth = _make_mock_auth_client(tokens_changed=True)
        api = _make_mock_api_client()

        coordinator = BMWConnectedRideCoordinator(hass, entry, auth, api)
        await coordinator._async_update_data()

        hass.config_entries.async_update_entry.assert_called_once()
        call_kwargs = hass.config_entries.async_update_entry.call_args
        updated_data = call_kwargs[1]["data"]
        assert updated_data["access_token"] == auth.access_token
        assert updated_data["refresh_token"] == auth.refresh_token
        assert updated_data["token_expiry"] == auth.token_expiry

    @pytest.mark.asyncio
    async def test_no_token_persistence_when_tokens_unchanged(self):
        """No config entry update when tokens have not changed."""
        hass = _make_mock_hass()
        entry = _make_mock_entry()
        auth = _make_mock_auth_client(tokens_changed=False)
        api = _make_mock_api_client()

        coordinator = BMWConnectedRideCoordinator(hass, entry, auth, api)
        await coordinator._async_update_data()

        hass.config_entries.async_update_entry.assert_not_called()
