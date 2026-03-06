"""Tests for BMW Connected Ride DataUpdateCoordinator."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add the project root to sys.path so we can import without HA
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from custom_components.bmw_connected_ride.auth import BMWAuthError, BMWTransientError
from custom_components.bmw_connected_ride.coordinator import (
    BMWConnectedRideCoordinator,
    SCAN_INTERVAL,
    _map_tracks_to_vins,
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
        "vehicleId": "abc123hash",
        "_deleted": False,
    },
    {
        "vin": "WB10X0X00X0000002",
        "name": "My S 1000 RR",
        "fuelLevel": 45,
        "remainingRange": 120000.0,
        "lastConnectedTime": 1735600000,
        "vehicleId": "def456hash",
        "_deleted": False,
    },
]

SAMPLE_TRACKS = [
    {
        "bikeId": "abc123hash",
        "startTimestamp": 1735600000,
        "rideDistance": 30000,
        "rideTime": 1800,
        "speedAverageKmh": 60.0,
        "_deleted": None,
    },
    {
        "bikeId": "abc123hash",
        "startTimestamp": 1735689600,
        "rideDistance": 45000,
        "rideTime": 3600,
        "speedAverageKmh": 45.5,
        "_deleted": None,
    },
    {
        "bikeId": "def456hash",
        "startTimestamp": 1735650000,
        "rideDistance": 20000,
        "rideTime": 1200,
        "speedAverageKmh": 55.0,
        "_deleted": None,
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


def _make_mock_api_client(bikes=None, tracks=None):
    """Create a mock BMWApiClient."""
    api = MagicMock()
    api.async_get_bikes = AsyncMock(return_value=bikes if bikes is not None else SAMPLE_BIKES)
    api.async_get_recorded_tracks = AsyncMock(return_value=tracks if tracks is not None else SAMPLE_TRACKS)
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
    async def test_transient_error_from_auth_raises_update_failed(self):
        """BMWTransientError from auth_client raises UpdateFailed (retryable), not ConfigEntryAuthFailed."""
        hass = _make_mock_hass()
        entry = _make_mock_entry()
        auth = _make_mock_auth_client()
        auth.async_ensure_token_valid = AsyncMock(
            side_effect=BMWTransientError("HTTP 500 — server error")
        )
        api = _make_mock_api_client()

        coordinator = BMWConnectedRideCoordinator(hass, entry, auth, api)

        with pytest.raises(UpdateFailed, match="temporarily unavailable"):
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


# ---------------------------------------------------------------------------
# Image cache tests
# ---------------------------------------------------------------------------

SAMPLE_VEHICLE_INFO = {
    "WB10X0X00X0000001": {
        "colorCode": "P0H0L",
        "images": {
            "sideViews": [{"url": "https://s3.example.com/side.png", "colorCode": "P0H0L"}],
        },
    }
}


def _make_api_client_with_images(bikes=None, vehicle_info=None, image_result=(b"img", "image/png")):
    """Create a mock API client with vehicle info and image download support."""
    _vi = vehicle_info or SAMPLE_VEHICLE_INFO
    api = MagicMock()
    api.async_get_bikes = AsyncMock(return_value=bikes if bikes is not None else SAMPLE_BIKES)
    api.async_get_vehicle_info = AsyncMock(
        side_effect=lambda vin, **kwargs: _vi.get(vin, {})
    )
    api.async_download_image = AsyncMock(return_value=image_result)
    return api


class TestImageCache:
    """Tests for coordinator.image_cache."""

    def test_image_cache_initialized_empty(self):
        """coordinator.image_cache is {} at init."""
        hass = _make_mock_hass()
        entry = _make_mock_entry()
        auth = _make_mock_auth_client()
        api = _make_mock_api_client()

        coordinator = BMWConnectedRideCoordinator(hass, entry, auth, api)

        assert coordinator.image_cache == {}

    @pytest.mark.asyncio
    async def test_image_cache_populated_after_fetch(self):
        """image_cache has entries keyed by VIN -> view_key -> (bytes, content_type)."""
        hass = _make_mock_hass()
        entry = _make_mock_entry()
        auth = _make_mock_auth_client()
        api = _make_api_client_with_images(
            bikes=[SAMPLE_BIKES[0]],
            vehicle_info=SAMPLE_VEHICLE_INFO,
            image_result=(b"img-bytes", "image/png"),
        )

        coordinator = BMWConnectedRideCoordinator(hass, entry, auth, api)
        coordinator.data = {"WB10X0X00X0000001": SAMPLE_BIKES[0]}
        coordinator.vehicle_info = SAMPLE_VEHICLE_INFO
        await coordinator.async_fetch_vehicle_info()

        assert "WB10X0X00X0000001" in coordinator.image_cache
        assert "sideViews" in coordinator.image_cache["WB10X0X00X0000001"]
        cached = coordinator.image_cache["WB10X0X00X0000001"]["sideViews"]
        assert cached[0] == b"img-bytes"
        assert cached[1] == "image/png"

    @pytest.mark.asyncio
    async def test_image_cache_empty_on_download_failure(self):
        """image_cache has empty dict for VIN when all downloads fail."""
        hass = _make_mock_hass()
        entry = _make_mock_entry()
        auth = _make_mock_auth_client()
        api = _make_api_client_with_images(
            bikes=[SAMPLE_BIKES[0]],
            vehicle_info=SAMPLE_VEHICLE_INFO,
            image_result=None,  # download failure
        )

        coordinator = BMWConnectedRideCoordinator(hass, entry, auth, api)
        coordinator.data = {"WB10X0X00X0000001": SAMPLE_BIKES[0]}
        coordinator.vehicle_info = SAMPLE_VEHICLE_INFO
        await coordinator.async_fetch_vehicle_info()

        assert "WB10X0X00X0000001" in coordinator.image_cache
        assert coordinator.image_cache["WB10X0X00X0000001"] == {}


# ---------------------------------------------------------------------------
# Tracks data tests
# ---------------------------------------------------------------------------


class TestTracksData:
    """Tests for coordinator tracks_data."""

    def test_tracks_data_initialized_empty(self):
        hass = _make_mock_hass()
        entry = _make_mock_entry()
        auth = _make_mock_auth_client()
        api = _make_mock_api_client()
        coordinator = BMWConnectedRideCoordinator(hass, entry, auth, api)
        assert coordinator.tracks_data == {}

    @pytest.mark.asyncio
    async def test_tracks_data_populated_after_update(self):
        hass = _make_mock_hass()
        entry = _make_mock_entry()
        auth = _make_mock_auth_client()
        api = _make_mock_api_client()
        coordinator = BMWConnectedRideCoordinator(hass, entry, auth, api)
        await coordinator._async_update_data()
        assert "WB10X0X00X0000001" in coordinator.tracks_data
        assert "WB10X0X00X0000002" in coordinator.tracks_data

    @pytest.mark.asyncio
    async def test_tracks_mapped_by_hashed_long_vin(self):
        hass = _make_mock_hass()
        entry = _make_mock_entry()
        auth = _make_mock_auth_client()
        api = _make_mock_api_client()
        coordinator = BMWConnectedRideCoordinator(hass, entry, auth, api)
        await coordinator._async_update_data()
        # Tracks with bikeId="abc123hash" should be under VIN WB10X0X00X0000001
        assert len(coordinator.tracks_data["WB10X0X00X0000001"]) == 2
        assert len(coordinator.tracks_data["WB10X0X00X0000002"]) == 1

    @pytest.mark.asyncio
    async def test_tracks_sorted_descending_by_start_timestamp(self):
        hass = _make_mock_hass()
        entry = _make_mock_entry()
        auth = _make_mock_auth_client()
        api = _make_mock_api_client()
        coordinator = BMWConnectedRideCoordinator(hass, entry, auth, api)
        await coordinator._async_update_data()
        tracks = coordinator.tracks_data["WB10X0X00X0000001"]
        assert tracks[0]["startTimestamp"] > tracks[1]["startTimestamp"]

    @pytest.mark.asyncio
    async def test_deleted_tracks_filtered(self):
        tracks_with_deleted = SAMPLE_TRACKS + [
            {"bikeId": "abc123hash", "startTimestamp": 1735700000, "rideDistance": 5000, "_deleted": True},
        ]
        hass = _make_mock_hass()
        entry = _make_mock_entry()
        auth = _make_mock_auth_client()
        api = _make_mock_api_client(tracks=tracks_with_deleted)
        coordinator = BMWConnectedRideCoordinator(hass, entry, auth, api)
        await coordinator._async_update_data()
        # VIN001 should still have 2 tracks (deleted one excluded)
        assert len(coordinator.tracks_data["WB10X0X00X0000001"]) == 2

    @pytest.mark.asyncio
    async def test_tracks_fetch_failure_logs_warning_continues(self):
        hass = _make_mock_hass()
        entry = _make_mock_entry()
        auth = _make_mock_auth_client()
        api = _make_mock_api_client()
        api.async_get_recorded_tracks = AsyncMock(side_effect=Exception("Network error"))
        coordinator = BMWConnectedRideCoordinator(hass, entry, auth, api)
        result = await coordinator._async_update_data()
        # Bike data still returned
        assert "WB10X0X00X0000001" in result
        # tracks_data has empty lists
        assert coordinator.tracks_data["WB10X0X00X0000001"] == []

    @pytest.mark.asyncio
    async def test_unmatched_track_bike_id_skipped(self):
        tracks_with_unknown = SAMPLE_TRACKS + [
            {"bikeId": "unknown_hash", "startTimestamp": 1735700000, "rideDistance": 999, "_deleted": None},
        ]
        hass = _make_mock_hass()
        entry = _make_mock_entry()
        auth = _make_mock_auth_client()
        api = _make_mock_api_client(tracks=tracks_with_unknown)
        coordinator = BMWConnectedRideCoordinator(hass, entry, auth, api)
        await coordinator._async_update_data()
        total = sum(len(t) for t in coordinator.tracks_data.values())
        assert total == 3  # Only the 3 matched tracks

    @pytest.mark.asyncio
    async def test_bike_data_still_returned_when_tracks_fail(self):
        hass = _make_mock_hass()
        entry = _make_mock_entry()
        auth = _make_mock_auth_client()
        api = _make_mock_api_client()
        api.async_get_recorded_tracks = AsyncMock(side_effect=Exception("Boom"))
        coordinator = BMWConnectedRideCoordinator(hass, entry, auth, api)
        result = await coordinator._async_update_data()
        assert result["WB10X0X00X0000001"]["name"] == "My R 1300 GS"
