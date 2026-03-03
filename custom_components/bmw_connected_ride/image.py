"""Image platform for BMW Connected Ride -- motorcycle view images."""

from __future__ import annotations

from homeassistant.components.image import Image, ImageEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .api import _extract_image_views
from .const import DOMAIN
from .coordinator import BMWConnectedRideCoordinator


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up BMW Connected Ride image entities from a config entry."""
    coordinator: BMWConnectedRideCoordinator = entry.runtime_data
    entities: list[BMWBikeImage] = []
    for vin in coordinator.data:
        vehicle_info = coordinator.vehicle_info.get(vin, {})
        views = _extract_image_views(vehicle_info)
        for view in views:
            entities.append(BMWBikeImage(coordinator, vin, view))
    async_add_entities(entities)


class BMWBikeImage(CoordinatorEntity[BMWConnectedRideCoordinator], ImageEntity):
    """An image entity for one view of a BMW motorcycle."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BMWConnectedRideCoordinator,
        vin: str,
        view: dict,
    ) -> None:
        """Initialize the image entity."""
        super().__init__(coordinator)
        ImageEntity.__init__(self, coordinator.hass)
        self._vin = vin
        self._attr_unique_id = f"{vin}_image_{view['key']}"
        self._attr_translation_key = view["key"]
        self._attr_image_last_updated = dt_util.utcnow()
        bike = coordinator.data[vin]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, vin)},
            name=bike.get("name") or vin,
            manufacturer="BMW Motorrad",
        )

        # Populate HA's native cache from coordinator image_cache
        cached = coordinator.image_cache.get(vin, {}).get(view["key"])
        if cached:
            image_bytes, content_type = cached
            self._cached_image = Image(content_type=content_type, content=image_bytes)
            self._attr_content_type = content_type
        # If not cached, _cached_image stays None -- async_image() returns None, HA shows placeholder
