"""Tests for BMW Connected Ride device tracker platform."""

from unittest.mock import MagicMock

import pytest

# Add the project root to sys.path so we can import without HA
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from homeassistant.components.device_tracker import SourceType

from custom_components.bmw_connected_ride.device_tracker import (
    BMWBikeDeviceTracker,
    BMWBikeTrackerEntityDescription,
    BMWRideLocationTracker,
    TRACKER_DESCRIPTIONS,
    RIDE_LOCATION_DESCRIPTIONS,
    async_setup_entry,
)
from custom_components.bmw_connected_ride.const import DOMAIN, PLATFORMS


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

BIKE_WITH_GPS = {
    "vin": "WB10X0X00X0XXXXXX",
    "name": "My R1250GS",
    "lastConnectedLat": 48.13513,
    "lastConnectedLon": 11.58198,
}

BIKE_NO_GPS = {
    "vin": "WB10X0X00X0XXXXXX",
    "name": "My R1250GS",
}

BIKE_NULL_GPS = {
    "vin": "WB10X0X00X0XXXXXX",
    "name": "My R1250GS",
    "lastConnectedLat": None,
    "lastConnectedLon": None,
}

BIKE_NO_NAME = {
    "vin": "WB10X0X00X0XXXXXX",
    "lastConnectedLat": 48.13513,
    "lastConnectedLon": 11.58198,
}


def _make_mock_coordinator(bikes_dict):
    """Create a mock coordinator with given data."""
    coordinator = MagicMock()
    coordinator.data = bikes_dict
    return coordinator


def _make_tracker(bike_dict, vin="WB10X0X00X0XXXXXX"):
    """Create a device tracker entity for testing."""
    coordinator = _make_mock_coordinator({vin: bike_dict})
    description = TRACKER_DESCRIPTIONS[0]
    return BMWBikeDeviceTracker(coordinator, vin, description)


# ---------------------------------------------------------------------------
# Latitude property tests
# ---------------------------------------------------------------------------


class TestLatitudeValue:
    """Tests for the latitude property."""

    def test_returns_latitude_float(self):
        """Returns float latitude when lastConnectedLat is present."""
        entity = _make_tracker(BIKE_WITH_GPS)
        assert entity.latitude == 48.13513

    def test_returns_none_when_missing(self):
        """Returns None when lastConnectedLat key is missing."""
        entity = _make_tracker(BIKE_NO_GPS)
        assert entity.latitude is None

    def test_returns_none_when_null(self):
        """Returns None when lastConnectedLat is explicitly None."""
        entity = _make_tracker(BIKE_NULL_GPS)
        assert entity.latitude is None


# ---------------------------------------------------------------------------
# Longitude property tests
# ---------------------------------------------------------------------------


class TestLongitudeValue:
    """Tests for the longitude property."""

    def test_returns_longitude_float(self):
        """Returns float longitude when lastConnectedLon is present."""
        entity = _make_tracker(BIKE_WITH_GPS)
        assert entity.longitude == 11.58198

    def test_returns_none_when_missing(self):
        """Returns None when lastConnectedLon key is missing."""
        entity = _make_tracker(BIKE_NO_GPS)
        assert entity.longitude is None

    def test_returns_none_when_null(self):
        """Returns None when lastConnectedLon is explicitly None."""
        entity = _make_tracker(BIKE_NULL_GPS)
        assert entity.longitude is None


# ---------------------------------------------------------------------------
# TRACKER_DESCRIPTIONS tuple tests
# ---------------------------------------------------------------------------


class TestTrackerDescriptions:
    """Tests for TRACKER_DESCRIPTIONS tuple."""

    def test_one_description_defined(self):
        """Exactly one tracker description is defined."""
        assert len(TRACKER_DESCRIPTIONS) == 1

    def test_last_connected_location_key(self):
        """The description key is 'last_connected_location'."""
        assert TRACKER_DESCRIPTIONS[0].key == "last_connected_location"

    def test_last_connected_location_translation_key(self):
        """The description translation_key is 'last_connected_location'."""
        assert TRACKER_DESCRIPTIONS[0].translation_key == "last_connected_location"


class TestRideLocationDescriptions:
    """Tests for RIDE_LOCATION_DESCRIPTIONS tuple."""

    def test_two_descriptions_defined(self):
        assert len(RIDE_LOCATION_DESCRIPTIONS) == 2

    def test_last_ride_start_key(self):
        assert RIDE_LOCATION_DESCRIPTIONS[0].key == "last_ride_start"

    def test_last_ride_end_key(self):
        assert RIDE_LOCATION_DESCRIPTIONS[1].key == "last_ride_end"


# ---------------------------------------------------------------------------
# BMWBikeDeviceTracker entity tests
# ---------------------------------------------------------------------------


class TestBMWBikeDeviceTracker:
    """Tests for BMWBikeDeviceTracker entity class."""

    def test_device_identifiers(self):
        """DeviceInfo has identifiers = {(DOMAIN, vin)}."""
        vin = "WB10X0X00X0XXXXXX"
        entity = _make_tracker(BIKE_WITH_GPS, vin=vin)
        assert entity._attr_device_info["identifiers"] == {(DOMAIN, vin)}

    def test_device_name_with_nickname(self):
        """DeviceInfo name uses bike nickname when present."""
        entity = _make_tracker(BIKE_WITH_GPS)
        assert entity._attr_device_info["name"] == "My R1250GS"

    def test_device_name_fallback_no_name(self):
        """DeviceInfo name falls back to VIN when name key is absent."""
        vin = "WB10X0X00X0XXXXXX"
        entity = _make_tracker(BIKE_NO_NAME, vin=vin)
        assert entity._attr_device_info["name"] == vin

    def test_manufacturer(self):
        """DeviceInfo manufacturer is BMW Motorrad."""
        entity = _make_tracker(BIKE_WITH_GPS)
        assert entity._attr_device_info["manufacturer"] == "BMW Motorrad"

    def test_unique_id(self):
        """Unique ID follows pattern {vin}_last_connected_location."""
        vin = "WB10X0X00X0XXXXXX"
        entity = _make_tracker(BIKE_WITH_GPS, vin=vin)
        assert entity._attr_unique_id == f"{vin}_last_connected_location"

    def test_has_entity_name(self):
        """_attr_has_entity_name is True."""
        entity = _make_tracker(BIKE_WITH_GPS)
        assert entity._attr_has_entity_name is True

    def test_source_type(self):
        """source_type is SourceType.GPS."""
        entity = _make_tracker(BIKE_WITH_GPS)
        assert entity._attr_source_type == SourceType.GPS

    def test_latitude_from_coordinator(self):
        """latitude property returns correct float from coordinator data."""
        entity = _make_tracker(BIKE_WITH_GPS)
        assert entity.latitude == 48.13513

    def test_longitude_from_coordinator(self):
        """longitude property returns correct float from coordinator data."""
        entity = _make_tracker(BIKE_WITH_GPS)
        assert entity.longitude == 11.58198

    def test_latitude_none_when_bike_missing(self):
        """latitude returns None when VIN is not in coordinator data."""
        vin = "WB10X0X00X0XXXXXX"
        coordinator = _make_mock_coordinator({vin: BIKE_WITH_GPS})
        description = TRACKER_DESCRIPTIONS[0]
        entity = BMWBikeDeviceTracker(coordinator, vin, description)
        # Simulate bike disappearing from coordinator
        coordinator.data = {}
        assert entity.latitude is None

    def test_longitude_none_when_bike_missing(self):
        """longitude returns None when VIN is not in coordinator data."""
        vin = "WB10X0X00X0XXXXXX"
        coordinator = _make_mock_coordinator({vin: BIKE_WITH_GPS})
        description = TRACKER_DESCRIPTIONS[0]
        entity = BMWBikeDeviceTracker(coordinator, vin, description)
        # Simulate bike disappearing from coordinator
        coordinator.data = {}
        assert entity.longitude is None

    def test_tracker_instance_translation_key(self):
        """Entity instance exposes translation_key from its description."""
        entity = _make_tracker(BIKE_WITH_GPS)
        assert entity._attr_translation_key == "last_connected_location"

    def test_extra_state_attributes_has_last_connected_time(self):
        """extra_state_attributes includes last_connected_time ISO string."""
        bike = {**BIKE_WITH_GPS, "lastConnectedTime": 1735689600}
        entity = _make_tracker(bike)
        attrs = entity.extra_state_attributes
        assert attrs is not None
        assert "last_connected_time" in attrs
        assert attrs["last_connected_time"] == "2025-01-01T00:00:00+00:00"

    def test_extra_state_attributes_none_when_no_timestamp(self):
        """extra_state_attributes is None when lastConnectedTime is missing."""
        entity = _make_tracker(BIKE_NO_GPS)
        assert entity.extra_state_attributes is None


# ---------------------------------------------------------------------------
# BMWRideLocationTracker tests
# ---------------------------------------------------------------------------

SAMPLE_TRACK_WITH_GPS = {
    "bikeId": "abc123hash",
    "startTimestamp": 1735689600,
    "rideDistance": 45000,
    "startLat": 48.123456,
    "startLon": 11.654321,
    "endLat": 48.234567,
    "endLon": 11.765432,
}

SAMPLE_TRACK_NO_GPS = {
    "bikeId": "abc123hash",
    "startTimestamp": 1735689600,
    "rideDistance": 45000,
}


def _make_ride_tracker(bike_dict, tracks, description_index=0, vin="WB10X0X00X0XXXXXX"):
    """Create a ride location tracker for testing."""
    coordinator = _make_mock_coordinator({vin: bike_dict})
    coordinator.tracks_data = {vin: tracks}
    description = RIDE_LOCATION_DESCRIPTIONS[description_index]
    return BMWRideLocationTracker(coordinator, vin, description)


class TestBMWRideLocationTracker:
    """Tests for BMWRideLocationTracker entity class."""

    def test_start_latitude(self):
        entity = _make_ride_tracker(BIKE_WITH_GPS, [SAMPLE_TRACK_WITH_GPS], description_index=0)
        assert entity.latitude == 48.123456

    def test_start_longitude(self):
        entity = _make_ride_tracker(BIKE_WITH_GPS, [SAMPLE_TRACK_WITH_GPS], description_index=0)
        assert entity.longitude == 11.654321

    def test_end_latitude(self):
        entity = _make_ride_tracker(BIKE_WITH_GPS, [SAMPLE_TRACK_WITH_GPS], description_index=1)
        assert entity.latitude == 48.234567

    def test_end_longitude(self):
        entity = _make_ride_tracker(BIKE_WITH_GPS, [SAMPLE_TRACK_WITH_GPS], description_index=1)
        assert entity.longitude == 11.765432

    def test_returns_none_when_no_tracks(self):
        entity = _make_ride_tracker(BIKE_WITH_GPS, [], description_index=0)
        assert entity.latitude is None
        assert entity.longitude is None

    def test_returns_none_when_gps_missing(self):
        entity = _make_ride_tracker(BIKE_WITH_GPS, [SAMPLE_TRACK_NO_GPS], description_index=0)
        assert entity.latitude is None
        assert entity.longitude is None

    def test_unique_id_start(self):
        vin = "WB10X0X00X0XXXXXX"
        entity = _make_ride_tracker(BIKE_WITH_GPS, [], description_index=0, vin=vin)
        assert entity._attr_unique_id == f"{vin}_last_ride_start"

    def test_unique_id_end(self):
        vin = "WB10X0X00X0XXXXXX"
        entity = _make_ride_tracker(BIKE_WITH_GPS, [], description_index=1, vin=vin)
        assert entity._attr_unique_id == f"{vin}_last_ride_end"

    def test_device_info(self):
        entity = _make_ride_tracker(BIKE_WITH_GPS, [], description_index=0)
        assert entity._attr_device_info["manufacturer"] == "BMW Motorrad"

    def test_source_type_is_gps(self):
        entity = _make_ride_tracker(BIKE_WITH_GPS, [], description_index=0)
        assert entity._attr_source_type == SourceType.GPS


# ---------------------------------------------------------------------------
# async_setup_entry tests
# ---------------------------------------------------------------------------


class TestAsyncSetupEntry:
    """Tests for async_setup_entry."""

    @pytest.mark.asyncio
    async def test_creates_three_trackers_per_bike(self):
        """1 bike -> 3 entities (1 GPS + 2 ride locations)."""
        coordinator = _make_mock_coordinator({
            "VIN001": BIKE_WITH_GPS,
        })
        coordinator.tracks_data = {"VIN001": []}
        entry = MagicMock()
        entry.runtime_data = coordinator
        added_entities = []
        async_add_entities = MagicMock(side_effect=lambda e: added_entities.extend(e))

        await async_setup_entry(MagicMock(), entry, async_add_entities)

        assert len(added_entities) == 3

    @pytest.mark.asyncio
    async def test_creates_six_trackers_for_two_bikes(self):
        """2 bikes -> 6 entities."""
        coordinator = _make_mock_coordinator({
            "VIN001": BIKE_WITH_GPS,
            "VIN002": BIKE_NO_GPS,
        })
        coordinator.tracks_data = {"VIN001": [], "VIN002": []}
        entry = MagicMock()
        entry.runtime_data = coordinator
        added_entities = []
        async_add_entities = MagicMock(side_effect=lambda e: added_entities.extend(e))

        await async_setup_entry(MagicMock(), entry, async_add_entities)

        assert len(added_entities) == 6

    @pytest.mark.asyncio
    async def test_all_entities_are_device_trackers(self):
        """All created entities are BMWBikeDeviceTracker or BMWRideLocationTracker."""
        coordinator = _make_mock_coordinator({
            "VIN001": BIKE_WITH_GPS,
        })
        coordinator.tracks_data = {"VIN001": []}
        entry = MagicMock()
        entry.runtime_data = coordinator
        added_entities = []
        async_add_entities = MagicMock(side_effect=lambda e: added_entities.extend(e))

        await async_setup_entry(MagicMock(), entry, async_add_entities)

        for entity in added_entities:
            assert isinstance(entity, (BMWBikeDeviceTracker, BMWRideLocationTracker))


# ---------------------------------------------------------------------------
# PLATFORMS registration tests
# ---------------------------------------------------------------------------


class TestPlatforms:
    """Tests for PLATFORMS registration."""

    def test_device_tracker_in_platforms(self):
        """device_tracker is registered in PLATFORMS."""
        assert "device_tracker" in PLATFORMS

    def test_sensor_still_in_platforms(self):
        """sensor is still in PLATFORMS (regression guard)."""
        assert "sensor" in PLATFORMS
