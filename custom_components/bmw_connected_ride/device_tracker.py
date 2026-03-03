"""BMW Connected Ride device tracker platform."""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker.config_entry import TrackerEntity, TrackerEntityDescription
from homeassistant.components.device_tracker.const import SourceType
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import UNDEFINED, UndefinedType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BMWConnectedRideConfigEntry
from .const import DOMAIN
from .coordinator import BMWConnectedRideCoordinator


class BMWBikeTrackerEntityDescription(TrackerEntityDescription, frozen_or_thawed=True):
    """Describes a BMW bike device tracker entity."""

    def __init__(
        self,
        *,
        key: str,
        device_class: str | None = None,
        entity_category: EntityCategory | None = None,
        entity_registry_enabled_default: bool = True,
        entity_registry_visible_default: bool = True,
        force_update: bool = False,
        icon: str | None = None,
        has_entity_name: bool = False,
        name: str | UndefinedType | None = UNDEFINED,
        translation_key: str | None = None,
    ) -> None:
        """Initialize BMWBikeTrackerEntityDescription.

        Explicit __init__ is required because pyright cannot infer the combined
        __init__ signature from the FrozenOrThawed metaclass.
        """
        ...


TRACKER_DESCRIPTIONS: tuple[BMWBikeTrackerEntityDescription, ...] = (
    BMWBikeTrackerEntityDescription(
        key="gps_location",
        translation_key="gps_location",
        name="GPS location",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BMWConnectedRideConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BMW Connected Ride device tracker entities from a config entry."""
    coordinator: BMWConnectedRideCoordinator = entry.runtime_data
    entities: list[BMWBikeDeviceTracker] = []
    for vin in coordinator.data:
        for description in TRACKER_DESCRIPTIONS:
            entities.append(BMWBikeDeviceTracker(coordinator, vin, description))
    async_add_entities(entities)


class BMWBikeDeviceTracker(CoordinatorEntity[BMWConnectedRideCoordinator], TrackerEntity):
    """A device tracker entity for one BMW bike's GPS location."""

    _attr_has_entity_name = True
    _attr_source_type = SourceType.GPS
    entity_description: BMWBikeTrackerEntityDescription  # type: ignore[override]  # Narrowing entity_description type for this entity subclass

    def __init__(
        self,
        coordinator: BMWConnectedRideCoordinator,
        vin: str,
        description: BMWBikeTrackerEntityDescription,
    ) -> None:
        """Initialize the device tracker."""
        super().__init__(coordinator)
        self.entity_description = description  # type: ignore[override]  # Narrowing entity_description to subclass type; standard HA pattern
        self._attr_translation_key = description.translation_key
        self._vin = vin
        self._attr_unique_id = f"{vin}_{description.key}"
        bike: dict[str, Any] = coordinator.data[vin]
        self._attr_device_info = DeviceInfo(  # type: ignore[assignment]  # BaseTrackerEntity stubs type _attr_device_info as None; runtime correct
            identifiers={(DOMAIN, vin)},
            name=bike.get("name") or vin,
            manufacturer="BMW Motorrad",
        )

    @property
    def latitude(self) -> float | None:  # type: ignore[override]  # HA base uses cached_property; runtime behavior is correct
        """Return the latitude from the coordinator data."""
        bike = self.coordinator.data.get(self._vin, {})
        lat = bike.get("lastConnectedLat")
        if lat is None:
            return None
        return float(lat)

    @property
    def longitude(self) -> float | None:  # type: ignore[override]  # HA base uses cached_property; runtime behavior is correct
        """Return the longitude from the coordinator data."""
        bike = self.coordinator.data.get(self._vin, {})
        lon = bike.get("lastConnectedLon")
        if lon is None:
            return None
        return float(lon)
