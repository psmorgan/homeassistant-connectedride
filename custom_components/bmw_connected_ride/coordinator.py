"""BMW Connected Ride DataUpdateCoordinator."""

import asyncio
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import BMWApiClient, extract_image_views
from .auth import BMWAuthClient, BMWAuthError, BMWTransientError

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=30)


def _map_tracks_to_vins(
    tracks: list[dict[str, Any]],
    bikes: dict[str, dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Map recorded tracks to VINs via hashedLongVin -> bikeId matching."""
    hash_to_vin: dict[str, str] = {
        bike.get("hashedLongVin", ""): vin
        for vin, bike in bikes.items()
        if bike.get("hashedLongVin")
    }
    result: dict[str, list[dict[str, Any]]] = {vin: [] for vin in bikes}
    for track in tracks:
        if track.get("_deleted"):
            continue
        bike_id = track.get("bikeId")
        vin = hash_to_vin.get(bike_id or "")
        if vin:
            result[vin].append(track)
        else:
            _LOGGER.debug("Track bikeId %s does not match any known bike", bike_id)
    for vin in result:
        result[vin].sort(key=lambda t: t.get("startTimestamp", 0), reverse=True)
    return result


class BMWConnectedRideCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Coordinator for BMW Connected Ride -- polls Cloud Sync bikes every 30 min."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,  # type: ignore[type-arg]  # ConfigEntry is generic but unparameterized here to avoid circular import
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
        self.vehicle_info: dict[str, dict[str, Any]] = {}
        self.image_cache: dict[str, dict[str, tuple[bytes, str]]] = {}
        self.tracks_data: dict[str, list[dict[str, Any]]] = {}

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch all bikes from Cloud Sync. Returns dict keyed by VIN."""
        try:
            await self._auth_client.async_ensure_token_valid()
        except BMWAuthError as ex:
            raise ConfigEntryAuthFailed(f"BMW auth failed: {ex}") from ex
        except BMWTransientError as ex:
            raise UpdateFailed(
                f"BMW token refresh temporarily unavailable: {ex}"
            ) from ex

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

        access_token = self._auth_client.access_token
        assert access_token is not None, "access_token must be set after ensure_token_valid"

        try:
            bikes = await self._api_client.async_get_bikes(access_token)
        except BMWAuthError as ex:
            raise ConfigEntryAuthFailed(f"BMW auth failed: {ex}") from ex
        except Exception as ex:
            raise UpdateFailed(f"Cannot fetch BMW bike data: {ex}") from ex

        # Key by VIN, filter deleted bikes
        bike_dict = {
            bike["vin"]: bike
            for bike in bikes
            if not bike.get("_deleted", False)
        }

        # Fetch tracks and map to VINs
        try:
            tracks = await self._api_client.async_get_recorded_tracks(access_token)
            self.tracks_data = _map_tracks_to_vins(tracks, bike_dict)
        except Exception as ex:
            _LOGGER.warning("Cannot fetch recorded tracks: %s", ex)
            self.tracks_data = {vin: [] for vin in bike_dict}

        return bike_dict

    async def async_fetch_vehicle_info(self) -> None:
        """Fetch static vehicle info (images, model data) for all bikes.

        Called once per HA restart after initial bike data fetch.
        Uses asyncio.gather for parallel fetches across bikes.
        """

        async def _fetch_one(vin: str, bike: dict[str, Any]) -> tuple[str, dict[str, Any]]:
            try:
                info = await self._api_client.async_get_vehicle_info(
                    vin=vin,
                    type_key=bike.get("typeKey"),
                    abs_type=bike.get("absType"),
                )
                return vin, info
            except Exception:
                _LOGGER.warning("Could not fetch vehicle info for %s", vin)
                return vin, {}

        results = await asyncio.gather(
            *[_fetch_one(vin, bike) for vin, bike in self.data.items()]
        )
        self.vehicle_info = dict(results)

        # Download image bytes for all bikes in parallel
        async def _download_views(vin: str) -> tuple[str, dict[str, tuple[bytes, str]]]:
            info = self.vehicle_info.get(vin, {})
            views = extract_image_views(info)
            cache: dict[str, tuple[bytes, str]] = {}
            for view in views:
                result = await self._api_client.async_download_image(view["url"])
                if result is not None:
                    cache[view["key"]] = result
            return vin, cache

        image_results = await asyncio.gather(
            *[_download_views(vin) for vin in self.vehicle_info]
        )
        self.image_cache = dict(image_results)
