"""BMW Connected Ride integration for Home Assistant."""

import aiohttp
import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .auth import BMWAuthClient, BMWAuthError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type BMWConnectedRideConfigEntry = ConfigEntry[BMWAuthClient]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BMWConnectedRideConfigEntry,
) -> bool:
    """Set up BMW Connected Ride from a config entry."""
    session = async_get_clientsession(hass)
    client = BMWAuthClient(
        region=entry.data["region"],
        access_token=entry.data["access_token"],
        refresh_token=entry.data["refresh_token"],
        token_expiry=entry.data["token_expiry"],
        session=session,
    )
    try:
        await client.async_ensure_token_valid()
    except BMWAuthError as ex:
        raise ConfigEntryAuthFailed(f"BMW auth failed: {ex}") from ex
    except (aiohttp.ClientError, asyncio.TimeoutError) as ex:
        raise ConfigEntryNotReady(f"Cannot reach BMW API: {ex}") from ex

    # Persist refreshed tokens if they changed
    if client.tokens_changed:
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                "access_token": client.access_token,
                "refresh_token": client.refresh_token,
                "token_expiry": client.token_expiry,
            },
        )

    entry.runtime_data = client
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: BMWConnectedRideConfigEntry,
) -> bool:
    """Unload a config entry."""
    return True
