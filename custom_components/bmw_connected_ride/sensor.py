"""BMW Connected Ride sensor platform."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timezone

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfLength, UnitOfPressure
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BMWConnectedRideCoordinator


@dataclass(frozen=True, kw_only=True)
class BMWBikeSensorEntityDescription(SensorEntityDescription):
    """Describes a BMW bike sensor entity."""

    value_fn: Callable[[dict], object | None]


def _fuel_level_value(bike: dict) -> int | None:
    """Extract fuel level percentage -- no conversion needed."""
    return bike.get("fuelLevel")


def _remaining_range_value(bike: dict) -> float | None:
    """Convert remaining range from meters to kilometres."""
    raw = bike.get("remainingRange")
    if raw is None:
        return None
    return round(raw / 1000, 1)


def _last_sync_value(bike: dict) -> datetime | None:
    """Convert epoch seconds to timezone-aware UTC datetime."""
    ts = bike.get("lastConnectedTime")
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def _energy_level_value(bike: dict) -> int | None:
    """Extract energy level (battery percentage) -- no conversion needed."""
    return bike.get("energyLevel")


def _electric_range_value(bike: dict) -> float | None:
    """Convert electric remaining range from meters to kilometres."""
    raw = bike.get("remainingRangeElectric")
    if raw is None:
        return None
    return round(raw / 1000, 1)


def _front_tire_pressure_value(bike: dict) -> float | None:
    """Extract front tire pressure in bar -- no conversion needed."""
    return bike.get("tirePressureFront")


def _rear_tire_pressure_value(bike: dict) -> float | None:
    """Extract rear tire pressure in bar -- no conversion needed."""
    return bike.get("tirePressureRear")


def _mileage_value(bike: dict) -> float | None:
    """Convert total mileage from meters to kilometres."""
    raw = bike.get("totalMileage")
    if raw is None:
        return None
    return round(raw / 1000, 1)


def _trip_distance_value(bike: dict) -> float | None:
    """Convert trip distance from meters to kilometres."""
    raw = bike.get("trip1")
    if raw is None:
        return None
    return round(raw / 1000, 1)


def _next_service_date_value(bike: dict) -> date | None:
    """Convert next service due date from epoch seconds to date."""
    ts = bike.get("nextServiceDueDate")
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).date()


def _next_service_distance_value(bike: dict) -> float | None:
    """Convert next service remaining distance from meters to kilometres."""
    raw = bike.get("nextServiceRemainingDistance")
    if raw is None:
        return None
    return round(raw / 1000, 1)


SENSOR_DESCRIPTIONS: tuple[BMWBikeSensorEntityDescription, ...] = (
    BMWBikeSensorEntityDescription(
        key="fuel_level",
        translation_key="fuel_level",
        name="Fuel level",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_fuel_level_value,
    ),
    BMWBikeSensorEntityDescription(
        key="remaining_range",
        translation_key="remaining_range",
        name="Remaining range",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_remaining_range_value,
    ),
    BMWBikeSensorEntityDescription(
        key="last_sync",
        translation_key="last_sync",
        name="Last sync",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_last_sync_value,
    ),
    BMWBikeSensorEntityDescription(
        key="energy_level",
        translation_key="energy_level",
        name="Energy level",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=_energy_level_value,
    ),
    BMWBikeSensorEntityDescription(
        key="electric_range",
        translation_key="electric_range",
        name="Electric range",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=_electric_range_value,
    ),
    BMWBikeSensorEntityDescription(
        key="front_tire_pressure",
        translation_key="front_tire_pressure",
        name="Front tire pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.BAR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_front_tire_pressure_value,
    ),
    BMWBikeSensorEntityDescription(
        key="rear_tire_pressure",
        translation_key="rear_tire_pressure",
        name="Rear tire pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.BAR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_rear_tire_pressure_value,
    ),
    BMWBikeSensorEntityDescription(
        key="mileage",
        translation_key="mileage",
        name="Mileage",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        value_fn=_mileage_value,
    ),
    BMWBikeSensorEntityDescription(
        key="trip_distance",
        translation_key="trip_distance",
        name="Trip distance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_trip_distance_value,
    ),
    BMWBikeSensorEntityDescription(
        key="next_service_date",
        translation_key="next_service_date",
        name="Next service date",
        device_class=SensorDeviceClass.DATE,
        value_fn=_next_service_date_value,
    ),
    BMWBikeSensorEntityDescription(
        key="next_service_distance",
        translation_key="next_service_distance",
        name="Next service distance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        suggested_display_precision=1,
        value_fn=_next_service_distance_value,
    ),
)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up BMW Connected Ride sensor entities from a config entry."""
    coordinator: BMWConnectedRideCoordinator = entry.runtime_data
    entities: list[BMWBikeSensor] = []
    for vin, bike in coordinator.data.items():
        for description in SENSOR_DESCRIPTIONS:
            entities.append(BMWBikeSensor(coordinator, vin, description))
    async_add_entities(entities)


class BMWBikeSensor(CoordinatorEntity[BMWConnectedRideCoordinator], SensorEntity):
    """A sensor entity for one metric of one BMW bike."""

    _attr_has_entity_name = True
    entity_description: BMWBikeSensorEntityDescription

    def __init__(
        self,
        coordinator: BMWConnectedRideCoordinator,
        vin: str,
        description: BMWBikeSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_translation_key = description.translation_key
        self._vin = vin
        self._attr_unique_id = f"{vin}_{description.key}"
        bike = coordinator.data[vin]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, vin)},
            name=bike.get("name") or vin,
            manufacturer="BMW Motorrad",
        )

    @property
    def native_value(self) -> object | None:
        """Return the sensor value from coordinator data."""
        bike = self.coordinator.data.get(self._vin)
        if bike is None:
            return None
        return self.entity_description.value_fn(bike)
