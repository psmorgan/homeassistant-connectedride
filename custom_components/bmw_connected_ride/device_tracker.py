"""BMW Connected Ride device tracker platform."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.device_tracker import SourceType, TrackerEntity, TrackerEntityDescription
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BMWConnectedRideCoordinator


@dataclass(frozen=True, kw_only=True)
class BMWBikeTrackerEntityDescription(TrackerEntityDescription):
    """Describes a BMW bike device tracker entity."""


TRACKER_DESCRIPTIONS: tuple[BMWBikeTrackerEntityDescription, ...] = (
    BMWBikeTrackerEntityDescription(
        key="gps_location",
        translation_key="gps_location",
        name="GPS location",
    ),
)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up BMW Connected Ride device tracker entities from a config entry."""
    coordinator: BMWConnectedRideCoordinator = entry.runtime_data
    entities: list[BMWBikeDeviceTracker] = []
    for vin, bike in coordinator.data.items():
        for description in TRACKER_DESCRIPTIONS:
            entities.append(BMWBikeDeviceTracker(coordinator, vin, description))
    async_add_entities(entities)


class BMWBikeDeviceTracker(CoordinatorEntity[BMWConnectedRideCoordinator], TrackerEntity):
    """A device tracker entity for one BMW bike's GPS location."""

    _attr_has_entity_name = True
    _attr_source_type = SourceType.GPS
    entity_description: BMWBikeTrackerEntityDescription

    def __init__(
        self,
        coordinator: BMWConnectedRideCoordinator,
        vin: str,
        description: BMWBikeTrackerEntityDescription,
    ) -> None:
        """Initialize the device tracker."""
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
    def latitude(self) -> float | None:
        """Return the latitude from the coordinator data."""
        bike = self.coordinator.data.get(self._vin, {})
        return bike.get("lastConnectedLat")

    @property
    def longitude(self) -> float | None:
        """Return the longitude from the coordinator data."""
        bike = self.coordinator.data.get(self._vin, {})
        return bike.get("lastConnectedLon")
