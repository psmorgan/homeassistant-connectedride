"""BMW Connected Ride DataUpdateCoordinator."""

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import BMWApiClient
from .auth import BMWAuthClient, BMWAuthError

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=30)


class BMWConnectedRideCoordinator(DataUpdateCoordinator[dict[str, dict]]):
    """Coordinator for BMW Connected Ride -- polls Cloud Sync bikes every 30 min."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        auth_client: BMWAuthClient,
        api_client: BMWApiClient,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="BMW Connected Ride",
            update_interval=SCAN_INTERVAL,
        )
        self._entry = entry
        self._auth_client = auth_client
        self._api_client = api_client

    async def _async_update_data(self) -> dict[str, dict]:
        """Fetch all bikes from Cloud Sync. Returns dict keyed by VIN."""
        try:
            await self._auth_client.async_ensure_token_valid()
        except BMWAuthError as ex:
            raise ConfigEntryAuthFailed(f"BMW auth failed: {ex}") from ex

        # Persist refreshed tokens to config entry if they changed
        if self._auth_client.tokens_changed:
            self.hass.config_entries.async_update_entry(
                self._entry,
                data={
                    **self._entry.data,
                    "access_token": self._auth_client.access_token,
                    "refresh_token": self._auth_client.refresh_token,
                    "token_expiry": self._auth_client.token_expiry,
                },
            )

        try:
            bikes = await self._api_client.async_get_bikes(
                self._auth_client.access_token
            )
        except BMWAuthError as ex:
            raise ConfigEntryAuthFailed(f"BMW auth failed: {ex}") from ex
        except Exception as ex:
            raise UpdateFailed(f"Cannot fetch BMW bike data: {ex}") from ex

        # Key by VIN, filter deleted bikes
        return {
            bike["vin"]: bike
            for bike in bikes
            if not bike.get("_deleted", False)
        }
