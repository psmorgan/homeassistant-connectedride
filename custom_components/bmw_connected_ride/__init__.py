"""BMW Connected Ride integration for Home Assistant."""

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import BMWApiClient
from .auth import BMWAuthClient
from .const import DOMAIN, PLATFORMS
from .coordinator import BMWConnectedRideCoordinator

_LOGGER = logging.getLogger(__name__)

type BMWConnectedRideConfigEntry = ConfigEntry[BMWConnectedRideCoordinator]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BMWConnectedRideConfigEntry,
) -> bool:
    """Set up BMW Connected Ride from a config entry."""
    session = async_get_clientsession(hass)
    auth_client = BMWAuthClient(
        region=entry.data["region"],
        access_token=entry.data["access_token"],
        refresh_token=entry.data["refresh_token"],
        token_expiry=entry.data["token_expiry"],
        session=session,
    )
    api_client = BMWApiClient(
        session=session,
        region=entry.data["region"],
        client_id_header=entry.data["client_id_header"],
    )
    coordinator = BMWConnectedRideCoordinator(hass, entry, auth_client, api_client)

    await coordinator.async_config_entry_first_refresh()
    await coordinator.async_fetch_vehicle_info()

    # Enrich device registry with model info from vehicle info API
    device_registry = dr.async_get(hass)
    for vin, vi in coordinator.vehicle_info.items():
        device = device_registry.async_get_device(identifiers={(DOMAIN, vin)})
        if device is not None:
            updates: dict[str, Any] = {}
            model = vi.get("model")
            if model:
                updates["model"] = model
            if updates:
                device_registry.async_update_device(device.id, **updates)

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: BMWConnectedRideConfigEntry,
) -> bool:
    """Unload a config entry."""
    coordinator: BMWConnectedRideCoordinator = entry.runtime_data
    await coordinator.async_shutdown()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
