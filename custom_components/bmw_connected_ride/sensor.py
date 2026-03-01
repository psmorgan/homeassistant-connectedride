"""BMW Connected Ride sensor platform."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfLength
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


SENSOR_DESCRIPTIONS: tuple[BMWBikeSensorEntityDescription, ...] = (
    BMWBikeSensorEntityDescription(
        key="fuel_level",
        translation_key="fuel_level",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_fuel_level_value,
    ),
    BMWBikeSensorEntityDescription(
        key="remaining_range",
        translation_key="remaining_range",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_remaining_range_value,
    ),
    BMWBikeSensorEntityDescription(
        key="last_sync",
        translation_key="last_sync",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_last_sync_value,
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
