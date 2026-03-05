"""Tests for BMW Connected Ride sensor platform."""

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, AsyncMock

import pytest

# Add the project root to sys.path so we can import without HA
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfLength, UnitOfPressure

from custom_components.bmw_connected_ride.const import DOMAIN
from custom_components.bmw_connected_ride.sensor import (
    BMWBikeSensor,
    BMWBikeSensorEntityDescription,
    BMWLastRideSensor,
    BMWLastRideSensorEntityDescription,
    SENSOR_DESCRIPTIONS,
    LAST_RIDE_DESCRIPTIONS,
    AGGREGATE_DESCRIPTIONS,
    _fuel_level_value,
    _remaining_range_value,
    _last_sync_value,
    _energy_level_value,
    _electric_range_value,
    _front_tire_pressure_value,
    _rear_tire_pressure_value,
    _mileage_value,
    _trip_distance_value,
    _next_service_date_value,
    _next_service_distance_value,
    _last_activated_value,
    _total_connected_distance_value,
    _total_connected_duration_value,
    _charging_mode_value,
    _charging_time_estimation_value,
    _last_ride_distance_value,
    _last_ride_duration_value,
    _last_ride_avg_speed_value,
    _last_ride_max_speed_value,
    _last_ride_max_temp_value,
    _last_ride_min_temp_value,
    _last_ride_max_elevation_value,
    _last_ride_min_elevation_value,
    _last_ride_lean_angle_left_value,
    _last_ride_lean_angle_right_value,
    _last_ride_max_acceleration_value,
    _last_ride_max_deceleration_value,
    _last_ride_start_time_value,
    _last_ride_engine_max_rpm_value,
    _total_ride_count_value,
    _total_ride_distance_value,
    _total_ride_duration_value,
    _avg_ride_distance_value,
    _avg_ride_duration_value,
    _longest_ride_value,
    _highest_lean_angle_value,
    async_setup_entry,
)


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

BIKE_WITH_NAME = {
    "vin": "WB10X0X00X0000001",
    "name": "My R 1300 GS",
    "fuelLevel": 72,
    "remainingRange": 245000.0,
    "lastConnectedTime": 1735689600,
    "energyLevel": 85,
    "remainingRangeElectric": 130000.0,
    "tirePressureFront": 2.5,
    "tirePressureRear": 2.9,
    "totalMileage": 25432000.0,
    "trip1": 345600.0,
    "nextServiceDueDate": 1751328000,
    "nextServiceRemainingDistance": 8500000.0,
    "lastActivatedTime": 1735689600,
    "totalConnectedDistance": 50000.0,
    "totalConnectedDuration": 98765.0,
    "chargingMode": "AC",
    "chargingTimeEstimationElectric": 3600,
    "absType": "0K03",
    "_deleted": False,
}

BIKE_NO_NAME = {
    "vin": "WB10X0X00X0000002",
    "name": None,
    "fuelLevel": 45,
    "remainingRange": 120000.0,
    "lastConnectedTime": 1735600000,
    "energyLevel": 85,
    "remainingRangeElectric": 130000.0,
    "tirePressureFront": 2.5,
    "tirePressureRear": 2.9,
    "totalMileage": 25432000.0,
    "trip1": 345600.0,
    "nextServiceDueDate": 1751328000,
    "nextServiceRemainingDistance": 8500000.0,
    "_deleted": False,
}

BIKE_EMPTY_NAME = {
    "vin": "WB10X0X00X0000003",
    "name": "",
    "fuelLevel": 90,
    "remainingRange": 300000.0,
    "lastConnectedTime": 1735700000,
    "energyLevel": 85,
    "remainingRangeElectric": 130000.0,
    "tirePressureFront": 2.5,
    "tirePressureRear": 2.9,
    "totalMileage": 25432000.0,
    "trip1": 345600.0,
    "nextServiceDueDate": 1751328000,
    "nextServiceRemainingDistance": 8500000.0,
    "_deleted": False,
}

BIKE_MISSING_FIELDS = {
    "vin": "WB10X0X00X0000004",
    "name": "Sparse Bike",
    "_deleted": False,
}


def _make_mock_coordinator(bikes_dict):
    """Create a mock coordinator with given data."""
    coordinator = MagicMock()
    coordinator.data = bikes_dict
    return coordinator


# ---------------------------------------------------------------------------
# Value function tests
# ---------------------------------------------------------------------------


class TestFuelLevelValue:
    """Tests for _fuel_level_value."""

    def test_returns_fuel_level_integer(self):
        """ENTY-03: Returns integer fuelLevel directly."""
        assert _fuel_level_value(BIKE_WITH_NAME) == 72

    def test_returns_none_when_missing(self):
        """ENTY-03: Returns None when fuelLevel key is missing."""
        assert _fuel_level_value(BIKE_MISSING_FIELDS) is None


class TestRemainingRangeValue:
    """Tests for _remaining_range_value."""

    def test_converts_meters_to_km(self):
        """ENTY-04: Converts 245000.0 meters to 245.0 km."""
        assert _remaining_range_value(BIKE_WITH_NAME) == 245.0

    def test_rounds_to_one_decimal(self):
        """ENTY-04: Rounds to 1 decimal place."""
        bike = {"remainingRange": 123456.7}
        assert _remaining_range_value(bike) == 123.5

    def test_returns_none_when_missing(self):
        """ENTY-04: Returns None when remainingRange key is missing."""
        assert _remaining_range_value(BIKE_MISSING_FIELDS) is None

    def test_returns_none_when_none(self):
        """ENTY-04: Returns None when remainingRange is None."""
        bike = {"remainingRange": None}
        assert _remaining_range_value(bike) is None


class TestLastSyncValue:
    """Tests for _last_sync_value."""

    def test_returns_timezone_aware_datetime(self):
        """ENTY-05: Returns timezone-aware UTC datetime."""
        result = _last_sync_value(BIKE_WITH_NAME)
        assert isinstance(result, datetime)
        assert result.tzinfo is not None
        assert result.tzinfo == timezone.utc

    def test_correct_timestamp_conversion(self):
        """ENTY-05: Correctly converts epoch seconds to datetime."""
        result = _last_sync_value(BIKE_WITH_NAME)
        expected = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_returns_none_when_missing(self):
        """ENTY-05: Returns None when lastConnectedTime key is missing."""
        assert _last_sync_value(BIKE_MISSING_FIELDS) is None

    def test_returns_none_when_none(self):
        """ENTY-05: Returns None when lastConnectedTime is None."""
        bike = {"lastConnectedTime": None}
        assert _last_sync_value(bike) is None


class TestEnergyLevelValue:
    """Tests for _energy_level_value."""

    def test_returns_energy_level_integer(self):
        assert _energy_level_value(BIKE_WITH_NAME) == 85

    def test_returns_none_when_missing(self):
        assert _energy_level_value(BIKE_MISSING_FIELDS) is None


class TestElectricRangeValue:
    """Tests for _electric_range_value."""

    def test_converts_meters_to_km(self):
        assert _electric_range_value(BIKE_WITH_NAME) == 130.0

    def test_returns_none_when_missing(self):
        assert _electric_range_value(BIKE_MISSING_FIELDS) is None

    def test_returns_none_when_none(self):
        assert _electric_range_value({"remainingRangeElectric": None}) is None


class TestFrontTirePressureValue:
    """Tests for _front_tire_pressure_value."""

    def test_returns_pressure_float(self):
        assert _front_tire_pressure_value(BIKE_WITH_NAME) == 2.5

    def test_returns_none_when_missing(self):
        assert _front_tire_pressure_value(BIKE_MISSING_FIELDS) is None


class TestRearTirePressureValue:
    """Tests for _rear_tire_pressure_value."""

    def test_returns_pressure_float(self):
        assert _rear_tire_pressure_value(BIKE_WITH_NAME) == 2.9

    def test_returns_none_when_missing(self):
        assert _rear_tire_pressure_value(BIKE_MISSING_FIELDS) is None


class TestMileageValue:
    """Tests for _mileage_value."""

    def test_converts_meters_to_km(self):
        assert _mileage_value(BIKE_WITH_NAME) == 25432.0

    def test_returns_none_when_missing(self):
        assert _mileage_value(BIKE_MISSING_FIELDS) is None

    def test_returns_none_when_none(self):
        assert _mileage_value({"totalMileage": None}) is None


class TestTripDistanceValue:
    """Tests for _trip_distance_value."""

    def test_converts_meters_to_km(self):
        assert _trip_distance_value(BIKE_WITH_NAME) == 345.6

    def test_returns_none_when_missing(self):
        assert _trip_distance_value(BIKE_MISSING_FIELDS) is None

    def test_returns_none_when_none(self):
        assert _trip_distance_value({"trip1": None}) is None


class TestNextServiceDateValue:
    """Tests for _next_service_date_value."""

    def test_returns_date_not_datetime(self):
        result = _next_service_date_value(BIKE_WITH_NAME)
        assert isinstance(result, date)
        assert not isinstance(result, datetime)  # date, NOT datetime

    def test_correct_date_conversion(self):
        result = _next_service_date_value(BIKE_WITH_NAME)
        assert result == date(2025, 7, 1)  # epoch 1751328000 = 2025-07-01 UTC

    def test_returns_none_when_missing(self):
        assert _next_service_date_value(BIKE_MISSING_FIELDS) is None

    def test_returns_none_when_none(self):
        assert _next_service_date_value({"nextServiceDueDate": None}) is None


class TestNextServiceDistanceValue:
    """Tests for _next_service_distance_value."""

    def test_converts_meters_to_km(self):
        assert _next_service_distance_value(BIKE_WITH_NAME) == 8500.0

    def test_returns_none_when_missing(self):
        assert _next_service_distance_value(BIKE_MISSING_FIELDS) is None

    def test_returns_none_when_none(self):
        assert _next_service_distance_value({"nextServiceRemainingDistance": None}) is None


class TestLastActivatedValue:
    """Tests for _last_activated_value."""

    def test_returns_utc_datetime(self):
        result = _last_activated_value(BIKE_WITH_NAME)
        assert isinstance(result, datetime)
        assert result.tzinfo == timezone.utc
        expected = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_returns_none_when_missing(self):
        assert _last_activated_value(BIKE_MISSING_FIELDS) is None

    def test_returns_none_when_none(self):
        assert _last_activated_value({"lastActivatedTime": None}) is None


class TestTotalConnectedDistanceValue:
    """Tests for _total_connected_distance_value."""

    def test_converts_meters_to_km(self):
        assert _total_connected_distance_value(BIKE_WITH_NAME) == 50.0

    def test_returns_none_when_missing(self):
        assert _total_connected_distance_value(BIKE_MISSING_FIELDS) is None

    def test_returns_none_when_none(self):
        assert _total_connected_distance_value({"totalConnectedDistance": None}) is None


class TestTotalConnectedDurationValue:
    """Tests for _total_connected_duration_value."""

    def test_returns_float_passthrough(self):
        assert _total_connected_duration_value(BIKE_WITH_NAME) == 98765.0

    def test_returns_none_when_missing(self):
        assert _total_connected_duration_value(BIKE_MISSING_FIELDS) is None


class TestChargingModeValue:
    """Tests for _charging_mode_value."""

    def test_returns_string_passthrough(self):
        assert _charging_mode_value(BIKE_WITH_NAME) == "AC"

    def test_returns_none_when_missing(self):
        assert _charging_mode_value(BIKE_MISSING_FIELDS) is None


class TestChargingTimeEstimationValue:
    """Tests for _charging_time_estimation_value."""

    def test_returns_integer_passthrough(self):
        assert _charging_time_estimation_value(BIKE_WITH_NAME) == 3600

    def test_returns_none_when_missing(self):
        assert _charging_time_estimation_value(BIKE_MISSING_FIELDS) is None


# ---------------------------------------------------------------------------
# Sensor description tests
# ---------------------------------------------------------------------------


class TestSensorDescriptions:
    """Tests for SENSOR_DESCRIPTIONS tuple."""

    def test_sixteen_descriptions_defined(self):
        """Sixteen sensor types defined (11 existing + 5 new)."""
        assert len(SENSOR_DESCRIPTIONS) == 16

    def test_fuel_level_description(self):
        """ENTY-03: Fuel level has correct attributes."""
        desc = SENSOR_DESCRIPTIONS[0]
        assert desc.key == "fuel_level"
        assert desc.native_unit_of_measurement == PERCENTAGE
        assert desc.state_class == SensorStateClass.MEASUREMENT
        # device_class should be None (NOT BATTERY -- fuel is not a battery)
        assert desc.device_class is None

    def test_remaining_range_description(self):
        """ENTY-04: Remaining range has DISTANCE device class and KILOMETERS unit."""
        desc = SENSOR_DESCRIPTIONS[1]
        assert desc.key == "remaining_range"
        assert desc.device_class == SensorDeviceClass.DISTANCE
        assert desc.native_unit_of_measurement == UnitOfLength.KILOMETERS
        assert desc.state_class == SensorStateClass.MEASUREMENT

    def test_last_sync_description(self):
        """ENTY-05: Last sync has TIMESTAMP device class."""
        desc = SENSOR_DESCRIPTIONS[2]
        assert desc.key == "last_sync"
        assert desc.device_class == SensorDeviceClass.TIMESTAMP

    def test_energy_level_description(self):
        desc = [d for d in SENSOR_DESCRIPTIONS if d.key == "energy_level"][0]
        assert desc.native_unit_of_measurement == PERCENTAGE
        assert desc.state_class == SensorStateClass.MEASUREMENT
        assert desc.device_class is None
        assert desc.entity_registry_enabled_default is False

    def test_electric_range_description(self):
        desc = [d for d in SENSOR_DESCRIPTIONS if d.key == "electric_range"][0]
        assert desc.device_class == SensorDeviceClass.DISTANCE
        assert desc.native_unit_of_measurement == UnitOfLength.KILOMETERS
        assert desc.entity_registry_enabled_default is False

    def test_front_tire_pressure_description(self):
        desc = [d for d in SENSOR_DESCRIPTIONS if d.key == "front_tire_pressure"][0]
        assert desc.device_class == SensorDeviceClass.PRESSURE
        assert desc.native_unit_of_measurement == UnitOfPressure.BAR
        assert desc.state_class == SensorStateClass.MEASUREMENT

    def test_rear_tire_pressure_description(self):
        desc = [d for d in SENSOR_DESCRIPTIONS if d.key == "rear_tire_pressure"][0]
        assert desc.device_class == SensorDeviceClass.PRESSURE
        assert desc.native_unit_of_measurement == UnitOfPressure.BAR

    def test_mileage_description(self):
        desc = [d for d in SENSOR_DESCRIPTIONS if d.key == "mileage"][0]
        assert desc.device_class == SensorDeviceClass.DISTANCE
        assert desc.native_unit_of_measurement == UnitOfLength.KILOMETERS
        assert desc.state_class == SensorStateClass.TOTAL_INCREASING

    def test_trip_distance_description(self):
        desc = [d for d in SENSOR_DESCRIPTIONS if d.key == "trip_distance"][0]
        assert desc.device_class == SensorDeviceClass.DISTANCE
        assert desc.state_class == SensorStateClass.MEASUREMENT

    def test_next_service_date_description(self):
        desc = [d for d in SENSOR_DESCRIPTIONS if d.key == "next_service_date"][0]
        assert desc.device_class == SensorDeviceClass.DATE

    def test_next_service_distance_description(self):
        desc = [d for d in SENSOR_DESCRIPTIONS if d.key == "next_service_distance"][0]
        assert desc.device_class == SensorDeviceClass.DISTANCE
        assert desc.state_class is None  # remaining distance decreases, not a measurement

    def test_last_activated_description(self):
        desc = [d for d in SENSOR_DESCRIPTIONS if d.key == "last_activated"][0]
        assert desc.device_class == SensorDeviceClass.TIMESTAMP

    def test_total_connected_distance_description(self):
        desc = [d for d in SENSOR_DESCRIPTIONS if d.key == "total_connected_distance"][0]
        assert desc.device_class == SensorDeviceClass.DISTANCE
        assert desc.state_class == SensorStateClass.TOTAL_INCREASING

    def test_total_connected_duration_description(self):
        desc = [d for d in SENSOR_DESCRIPTIONS if d.key == "total_connected_duration"][0]
        assert desc.device_class == SensorDeviceClass.DURATION
        assert desc.state_class == SensorStateClass.TOTAL_INCREASING

    def test_charging_mode_description(self):
        desc = [d for d in SENSOR_DESCRIPTIONS if d.key == "charging_mode"][0]
        assert desc.entity_registry_enabled_default is False

    def test_charging_time_estimation_description(self):
        desc = [d for d in SENSOR_DESCRIPTIONS if d.key == "charging_time_estimation"][0]
        assert desc.entity_registry_enabled_default is False
        assert desc.device_class == SensorDeviceClass.DURATION

    def test_all_descriptions_have_explicit_name(self):
        """Every description sets name (not UNDEFINED) for custom-component entity ID generation."""
        for desc in SENSOR_DESCRIPTIONS:
            assert desc.name is not None, (
                f"{desc.key}: entity_description.name must be set explicitly "
                "so HA generates descriptive entity IDs for custom components"
            )


# ---------------------------------------------------------------------------
# BMWBikeSensor entity tests
# ---------------------------------------------------------------------------


class TestBMWBikeSensor:
    """Tests for BMWBikeSensor entity class."""

    def _make_sensor(self, bike, description_index=0, bikes_dict=None):
        """Create a sensor entity for testing."""
        vin = bike["vin"]
        if bikes_dict is None:
            bikes_dict = {vin: bike}
        coordinator = _make_mock_coordinator(bikes_dict)
        return BMWBikeSensor(coordinator, vin, SENSOR_DESCRIPTIONS[description_index])

    # Device info tests

    def test_device_identifiers(self):
        """ENTY-01: DeviceInfo has identifiers = {(DOMAIN, vin)}."""
        sensor = self._make_sensor(BIKE_WITH_NAME)
        assert sensor._attr_device_info["identifiers"] == {
            (DOMAIN, "WB10X0X00X0000001")
        }

    def test_device_name_with_nickname(self):
        """ENTY-02: DeviceInfo name uses bike nickname when present."""
        sensor = self._make_sensor(BIKE_WITH_NAME)
        assert sensor._attr_device_info["name"] == "My R 1300 GS"

    def test_device_name_fallback_none(self):
        """ENTY-02: DeviceInfo name falls back to VIN when name is None."""
        sensor = self._make_sensor(BIKE_NO_NAME)
        assert sensor._attr_device_info["name"] == "WB10X0X00X0000002"

    def test_device_name_fallback_empty(self):
        """ENTY-02: DeviceInfo name falls back to VIN when name is empty string."""
        sensor = self._make_sensor(BIKE_EMPTY_NAME)
        assert sensor._attr_device_info["name"] == "WB10X0X00X0000003"

    def test_manufacturer(self):
        """DeviceInfo manufacturer is BMW Motorrad."""
        sensor = self._make_sensor(BIKE_WITH_NAME)
        assert sensor._attr_device_info["manufacturer"] == "BMW Motorrad"

    # Unique ID tests

    def test_unique_id_fuel_level(self):
        """Unique ID format: {vin}_fuel_level."""
        sensor = self._make_sensor(BIKE_WITH_NAME, description_index=0)
        assert sensor._attr_unique_id == "WB10X0X00X0000001_fuel_level"

    def test_unique_id_remaining_range(self):
        """Unique ID format: {vin}_remaining_range."""
        sensor = self._make_sensor(BIKE_WITH_NAME, description_index=1)
        assert sensor._attr_unique_id == "WB10X0X00X0000001_remaining_range"

    def test_unique_id_last_sync(self):
        """Unique ID format: {vin}_last_sync."""
        sensor = self._make_sensor(BIKE_WITH_NAME, description_index=2)
        assert sensor._attr_unique_id == "WB10X0X00X0000001_last_sync"

    # has_entity_name tests

    def test_has_entity_name(self):
        """_attr_has_entity_name is True."""
        sensor = self._make_sensor(BIKE_WITH_NAME)
        assert sensor._attr_has_entity_name is True

    # native_value tests

    def test_fuel_level_native_value(self):
        """ENTY-03: Fuel level returns integer percentage."""
        sensor = self._make_sensor(BIKE_WITH_NAME, description_index=0)
        assert sensor.native_value == 72

    def test_remaining_range_native_value(self):
        """ENTY-04: Remaining range converts meters to km."""
        sensor = self._make_sensor(BIKE_WITH_NAME, description_index=1)
        assert sensor.native_value == 245.0

    def test_last_sync_native_value(self):
        """ENTY-05: Last sync returns timezone-aware datetime."""
        sensor = self._make_sensor(BIKE_WITH_NAME, description_index=2)
        result = sensor.native_value
        assert isinstance(result, datetime)
        assert result.tzinfo == timezone.utc

    def test_native_value_none_when_field_missing(self):
        """Returns None when sensor field is missing from bike data."""
        sensor = self._make_sensor(BIKE_MISSING_FIELDS, description_index=0)
        assert sensor.native_value is None

    def test_native_value_none_when_bike_missing(self):
        """Returns None when VIN is not in coordinator data."""
        vin = "WB10X0X00X0000001"
        # Create sensor with bike present, then remove bike from coordinator data
        coordinator = _make_mock_coordinator({vin: BIKE_WITH_NAME})
        sensor = BMWBikeSensor(coordinator, vin, SENSOR_DESCRIPTIONS[0])
        # Simulate bike disappearing from coordinator
        coordinator.data = {}
        assert sensor.native_value is None

    # translation_key instance tests

    def test_sensor_instance_translation_key(self):
        """Entity instance exposes translation_key from its description."""
        sensor = self._make_sensor(BIKE_WITH_NAME, description_index=0)
        assert sensor._attr_translation_key == "fuel_level"

    def test_all_sensors_have_instance_translation_key(self):
        """Every sensor description's translation_key is bridged to entity instance."""
        vin = BIKE_WITH_NAME["vin"]
        coordinator = _make_mock_coordinator({vin: BIKE_WITH_NAME})
        for desc in SENSOR_DESCRIPTIONS:
            entity = BMWBikeSensor(coordinator, vin, desc)
            assert entity._attr_translation_key == desc.translation_key, (
                f"{desc.key}: _attr_translation_key not set"
            )


# ---------------------------------------------------------------------------
# Mileage extra_state_attributes tests
# ---------------------------------------------------------------------------


class TestMileageExtraStateAttributes:
    """Tests for absType as extra_state_attributes on mileage sensor."""

    def test_mileage_sensor_has_abs_type(self):
        """absType appears as extra_state_attributes on the mileage sensor."""
        vin = BIKE_WITH_NAME["vin"]
        coordinator = _make_mock_coordinator({vin: BIKE_WITH_NAME})
        mileage_desc = [d for d in SENSOR_DESCRIPTIONS if d.key == "mileage"][0]
        sensor = BMWBikeSensor(coordinator, vin, mileage_desc)
        assert sensor.extra_state_attributes == {"abs_type": "0K03"}

    def test_non_mileage_sensor_no_extra_attributes(self):
        """Non-mileage sensors return None for extra_state_attributes."""
        vin = BIKE_WITH_NAME["vin"]
        coordinator = _make_mock_coordinator({vin: BIKE_WITH_NAME})
        fuel_desc = [d for d in SENSOR_DESCRIPTIONS if d.key == "fuel_level"][0]
        sensor = BMWBikeSensor(coordinator, vin, fuel_desc)
        assert sensor.extra_state_attributes is None

    def test_mileage_no_abs_type_returns_none(self):
        """Mileage sensor returns None when bike has no absType."""
        vin = BIKE_MISSING_FIELDS["vin"]
        coordinator = _make_mock_coordinator({vin: BIKE_MISSING_FIELDS})
        mileage_desc = [d for d in SENSOR_DESCRIPTIONS if d.key == "mileage"][0]
        sensor = BMWBikeSensor(coordinator, vin, mileage_desc)
        assert sensor.extra_state_attributes is None


# ---------------------------------------------------------------------------
# async_setup_entry tests
# ---------------------------------------------------------------------------


class TestAsyncSetupEntry:
    """Tests for async_setup_entry."""

    @pytest.mark.asyncio
    async def test_creates_thirtyseven_sensors_per_bike(self):
        """37 sensors per bike: 16 bike + 14 last-ride + 7 aggregate."""
        coordinator = _make_mock_coordinator({"VIN001": BIKE_WITH_NAME})
        coordinator.tracks_data = {"VIN001": []}
        entry = MagicMock()
        entry.runtime_data = coordinator
        added_entities = []
        async_add_entities = MagicMock(side_effect=lambda e: added_entities.extend(e))
        await async_setup_entry(MagicMock(), entry, async_add_entities)
        assert len(added_entities) == 37

    @pytest.mark.asyncio
    async def test_creates_seventyfour_sensors_for_two_bikes(self):
        """2 bikes = 74 entities total."""
        coordinator = _make_mock_coordinator({"VIN001": BIKE_WITH_NAME, "VIN002": BIKE_NO_NAME})
        coordinator.tracks_data = {"VIN001": [], "VIN002": []}
        entry = MagicMock()
        entry.runtime_data = coordinator
        added_entities = []
        async_add_entities = MagicMock(side_effect=lambda e: added_entities.extend(e))
        await async_setup_entry(MagicMock(), entry, async_add_entities)
        assert len(added_entities) == 74

    @pytest.mark.asyncio
    async def test_all_entities_are_sensor_types(self):
        """All created entities are BMWBikeSensor or BMWLastRideSensor."""
        coordinator = _make_mock_coordinator({"VIN001": BIKE_WITH_NAME})
        coordinator.tracks_data = {"VIN001": []}
        entry = MagicMock()
        entry.runtime_data = coordinator
        added_entities = []
        async_add_entities = MagicMock(side_effect=lambda e: added_entities.extend(e))
        await async_setup_entry(MagicMock(), entry, async_add_entities)
        for entity in added_entities:
            assert isinstance(entity, (BMWBikeSensor, BMWLastRideSensor))


# ---------------------------------------------------------------------------
# Last-ride and aggregate sensor tests
# ---------------------------------------------------------------------------

SAMPLE_TRACK_1 = {
    "bikeId": "abc123hash",
    "startTimestamp": 1735689600,
    "rideDistance": 45000,
    "rideTime": 3600,
    "speedAverageKmh": 45.5,
    "speedMaxKmh": 120.3,
    "temperatureMaxC": 28.5,
    "temperatureMinC": 12.0,
    "elevationMaxM": 1500.0,
    "elevationMinM": 200.0,
    "leanAngleLeftMax": -35.2,
    "leanAngleRightMax": 32.1,
    "accelerationMax": 0.75,
    "decelerationMax": 0.67,
    "engineMaxRpm": 8500,
    "_deleted": None,
}

SAMPLE_TRACK_2 = {
    "bikeId": "abc123hash",
    "startTimestamp": 1735600000,
    "rideDistance": 30000,
    "rideTime": 1800,
    "speedAverageKmh": 60.0,
    "speedMaxKmh": 110.0,
    "temperatureMaxC": 25.0,
    "temperatureMinC": 15.0,
    "elevationMaxM": 800.0,
    "elevationMinM": 100.0,
    "leanAngleLeftMax": -28.0,
    "leanAngleRightMax": 40.5,
    "accelerationMax": 0.60,
    "decelerationMax": 0.55,
    "engineMaxRpm": 7200,
    "_deleted": None,
}

SAMPLE_TRACKS = [SAMPLE_TRACK_1, SAMPLE_TRACK_2]


class TestLastRideDistanceValue:
    def test_converts_meters_to_km(self):
        assert _last_ride_distance_value(SAMPLE_TRACKS) == 45.0

    def test_returns_none_when_empty(self):
        assert _last_ride_distance_value([]) is None

    def test_returns_none_when_field_none(self):
        assert _last_ride_distance_value([{"rideDistance": None}]) is None


class TestLastRideDurationValue:
    def test_returns_ride_time(self):
        assert _last_ride_duration_value(SAMPLE_TRACKS) == 3600

    def test_returns_none_when_empty(self):
        assert _last_ride_duration_value([]) is None


class TestLastRideAvgSpeedValue:
    def test_returns_speed(self):
        assert _last_ride_avg_speed_value(SAMPLE_TRACKS) == 45.5

    def test_returns_none_when_empty(self):
        assert _last_ride_avg_speed_value([]) is None


class TestLastRideMaxSpeedValue:
    def test_returns_max_speed(self):
        assert _last_ride_max_speed_value(SAMPLE_TRACKS) == 120.3

    def test_returns_none_when_empty(self):
        assert _last_ride_max_speed_value([]) is None


class TestLastRideTemperatureValues:
    def test_max_temp(self):
        assert _last_ride_max_temp_value(SAMPLE_TRACKS) == 28.5

    def test_min_temp(self):
        assert _last_ride_min_temp_value(SAMPLE_TRACKS) == 12.0

    def test_max_temp_none_when_empty(self):
        assert _last_ride_max_temp_value([]) is None

    def test_min_temp_none_when_empty(self):
        assert _last_ride_min_temp_value([]) is None


class TestLastRideElevationValues:
    def test_max_elevation(self):
        assert _last_ride_max_elevation_value(SAMPLE_TRACKS) == 1500.0

    def test_min_elevation(self):
        assert _last_ride_min_elevation_value(SAMPLE_TRACKS) == 200.0

    def test_none_when_empty(self):
        assert _last_ride_max_elevation_value([]) is None


class TestLastRideLeanAngleValues:
    def test_left_returns_abs_value(self):
        """Lean angle left can be negative -- abs() applied."""
        assert _last_ride_lean_angle_left_value(SAMPLE_TRACKS) == 35.2

    def test_right_returns_abs_value(self):
        assert _last_ride_lean_angle_right_value(SAMPLE_TRACKS) == 32.1

    def test_left_none_when_empty(self):
        assert _last_ride_lean_angle_left_value([]) is None

    def test_left_none_when_field_none(self):
        assert _last_ride_lean_angle_left_value([{"leanAngleLeftMax": None}]) is None


class TestLastRideAccelerationValues:
    def test_max_acceleration(self):
        assert _last_ride_max_acceleration_value(SAMPLE_TRACKS) == 0.75

    def test_max_deceleration(self):
        assert _last_ride_max_deceleration_value(SAMPLE_TRACKS) == 0.67

    def test_none_when_empty(self):
        assert _last_ride_max_acceleration_value([]) is None


class TestLastRideStartTimeValue:
    def test_returns_utc_datetime(self):
        result = _last_ride_start_time_value(SAMPLE_TRACKS)
        assert isinstance(result, datetime)
        assert result.tzinfo == timezone.utc
        assert result == datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    def test_returns_none_when_empty(self):
        assert _last_ride_start_time_value([]) is None

    def test_returns_none_when_field_none(self):
        assert _last_ride_start_time_value([{"startTimestamp": None}]) is None


class TestLastRideEngineMaxRpmValue:
    def test_returns_rpm(self):
        assert _last_ride_engine_max_rpm_value(SAMPLE_TRACKS) == 8500

    def test_returns_none_when_empty(self):
        assert _last_ride_engine_max_rpm_value([]) is None


class TestTotalRideCountValue:
    def test_returns_count(self):
        assert _total_ride_count_value(SAMPLE_TRACKS) == 2

    def test_returns_zero_when_empty(self):
        assert _total_ride_count_value([]) == 0


class TestTotalRideDistanceValue:
    def test_returns_sum_in_km(self):
        assert _total_ride_distance_value(SAMPLE_TRACKS) == 75.0

    def test_returns_none_when_empty(self):
        assert _total_ride_distance_value([]) is None


class TestTotalRideDurationValue:
    def test_returns_sum(self):
        assert _total_ride_duration_value(SAMPLE_TRACKS) == 5400

    def test_returns_none_when_empty(self):
        assert _total_ride_duration_value([]) is None


class TestAvgRideDistanceValue:
    def test_returns_average_in_km(self):
        assert _avg_ride_distance_value(SAMPLE_TRACKS) == 37.5

    def test_returns_none_when_empty(self):
        assert _avg_ride_distance_value([]) is None


class TestAvgRideDurationValue:
    def test_returns_average(self):
        assert _avg_ride_duration_value(SAMPLE_TRACKS) == 2700

    def test_returns_none_when_empty(self):
        assert _avg_ride_duration_value([]) is None


class TestLongestRideValue:
    def test_returns_max_in_km(self):
        assert _longest_ride_value(SAMPLE_TRACKS) == 45.0

    def test_returns_none_when_empty(self):
        assert _longest_ride_value([]) is None


class TestHighestLeanAngleValue:
    def test_returns_max_abs_across_both_sides(self):
        assert _highest_lean_angle_value(SAMPLE_TRACKS) == 40.5

    def test_returns_none_when_empty(self):
        assert _highest_lean_angle_value([]) is None

    def test_returns_none_when_all_angles_none(self):
        assert _highest_lean_angle_value([{"leanAngleLeftMax": None, "leanAngleRightMax": None}]) is None

    def test_handles_negative_left_angle(self):
        assert _highest_lean_angle_value([{"leanAngleLeftMax": -50.0, "leanAngleRightMax": 30.0}]) == 50.0


class TestLastRideDescriptions:
    def test_fourteen_descriptions_defined(self):
        assert len(LAST_RIDE_DESCRIPTIONS) == 14

    def test_all_have_explicit_name(self):
        for desc in LAST_RIDE_DESCRIPTIONS:
            assert desc.name is not None, f"{desc.key}: name must be set"


class TestAggregateDescriptions:
    def test_seven_descriptions_defined(self):
        assert len(AGGREGATE_DESCRIPTIONS) == 7

    def test_all_use_measurement_state_class(self):
        for desc in AGGREGATE_DESCRIPTIONS:
            assert desc.state_class == SensorStateClass.MEASUREMENT, f"{desc.key} should be MEASUREMENT"

    def test_all_have_explicit_name(self):
        for desc in AGGREGATE_DESCRIPTIONS:
            assert desc.name is not None, f"{desc.key}: name must be set"


class TestBMWLastRideSensor:
    def test_reads_from_tracks_data(self):
        vin = "WB10X0X00X0000001"
        coordinator = _make_mock_coordinator({vin: BIKE_WITH_NAME})
        coordinator.tracks_data = {vin: SAMPLE_TRACKS}
        sensor = BMWLastRideSensor(coordinator, vin, LAST_RIDE_DESCRIPTIONS[0])
        assert sensor.native_value == 45.0

    def test_returns_none_when_no_tracks(self):
        vin = "WB10X0X00X0000001"
        coordinator = _make_mock_coordinator({vin: BIKE_WITH_NAME})
        coordinator.tracks_data = {vin: []}
        sensor = BMWLastRideSensor(coordinator, vin, LAST_RIDE_DESCRIPTIONS[0])
        assert sensor.native_value is None

    def test_returns_none_when_vin_missing(self):
        vin = "WB10X0X00X0000001"
        coordinator = _make_mock_coordinator({vin: BIKE_WITH_NAME})
        coordinator.tracks_data = {}
        sensor = BMWLastRideSensor(coordinator, vin, LAST_RIDE_DESCRIPTIONS[0])
        assert sensor.native_value is None

    def test_unique_id(self):
        vin = "WB10X0X00X0000001"
        coordinator = _make_mock_coordinator({vin: BIKE_WITH_NAME})
        coordinator.tracks_data = {vin: []}
        sensor = BMWLastRideSensor(coordinator, vin, LAST_RIDE_DESCRIPTIONS[0])
        assert sensor._attr_unique_id == f"{vin}_last_ride_distance"

    def test_device_info_matches_bike(self):
        vin = "WB10X0X00X0000001"
        coordinator = _make_mock_coordinator({vin: BIKE_WITH_NAME})
        coordinator.tracks_data = {vin: []}
        sensor = BMWLastRideSensor(coordinator, vin, LAST_RIDE_DESCRIPTIONS[0])
        assert sensor._attr_device_info["identifiers"] == {(DOMAIN, vin)}
