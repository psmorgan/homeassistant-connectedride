"""BMW Connected Ride Cloud Sync API client."""

import logging

import aiohttp

from .const import REGION_CONFIGS

BIKES_PATH = "cnrd/cloudsync/v2/bikes"
STATICDATA_PATH = "cnrd/bike/v2/staticdata"
STATICDATA_API_KEY = "9dcd9fb1-3118-468d-86fc-d6dfca50c492"

_LOGGER = logging.getLogger(__name__)

_VIEW_TYPES = (
    ("sideViews", "Side View"),
    ("riderViews", "Rider View"),
)


def _extract_image_views(vehicle_info: dict) -> list[dict]:
    """Extract all image views from VehicleInfoResponse.

    Returns list of dicts with keys: key, label, url.
    Includes sideViews and riderViews (not colorTiles -- those are tiny color swatches).
    """
    views: list[dict] = []
    images = vehicle_info.get("images") or {}
    for view_type, label in _VIEW_TYPES:
        entries = images.get(view_type) or []
        for i, entry in enumerate(entries):
            url = entry.get("url")
            if not url:
                continue
            suffix = f"_{i}" if len(entries) > 1 else ""
            name = f"{label} {i + 1}" if len(entries) > 1 else label
            views.append({"key": f"{view_type}{suffix}", "label": name, "url": url})
    return views


class BMWApiClient:
    """HTTP client for BMW Connected Ride Cloud Sync API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        region: str,
        client_id_header: str,
    ) -> None:
        self._session = session
        self._base_url = REGION_CONFIGS[region]["api_base_url"]
        self._client_id_header = client_id_header

    async def async_get_bikes(self, access_token: str) -> list[dict]:
        """GET /cnrd/cloudsync/v2/bikes?limit=200 -- returns all linked bikes.

        Args:
            access_token: Valid BMW OAuth access token.

        Returns:
            List of bike dicts from the Cloud Sync API.

        Raises:
            BMWAuthError: On HTTP 401 (token invalid/expired).
            aiohttp.ClientResponseError: On other non-200 responses.
        """
        url = f"{self._base_url}/{BIKES_PATH}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Client-ID": self._client_id_header,
        }
        async with self._session.get(
            url, params={"limit": 200}, headers=headers
        ) as resp:
            if resp.status == 401:
                from .auth import BMWAuthError

                raise BMWAuthError(
                    "Unauthorized (HTTP 401) -- token invalid or expired"
                )
            resp.raise_for_status()
            data = await resp.json()
        return data.get("bikes", [])

    async def async_get_vehicle_info(
        self,
        vin: str,
        type_key: str | None = None,
        abs_type: str | None = None,
    ) -> dict:
        """POST /cnrd/bike/v2/staticdata -- returns static vehicle info including images.

        Uses x-cd-apigw-key header auth (not Bearer token -- Bearer returns 401).

        Args:
            vin: Vehicle Identification Number.
            type_key: Optional type key from Cloud Sync bike data.
            abs_type: Optional abs type from Cloud Sync bike data.

        Returns:
            First item from the VehicleInfoResponse list, or {} if empty/403.

        Raises:
            BMWAuthError: On HTTP 401 (token invalid/expired).
            aiohttp.ClientResponseError: On other non-200/non-403 responses.
        """
        url = f"{self._base_url}/{STATICDATA_PATH}"
        headers = {
            "x-cd-apigw-key": STATICDATA_API_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        body: dict = {"vin": vin}
        if type_key is not None:
            body["typeKey"] = type_key
        if abs_type is not None:
            body["absType"] = abs_type

        async with self._session.post(url, json=body, headers=headers) as resp:
            if resp.status == 401:
                from .auth import BMWAuthError

                raise BMWAuthError(
                    "Unauthorized (HTTP 401) -- token invalid or expired"
                )
            if resp.status == 403:
                _LOGGER.warning(
                    "Vehicle info endpoint returned 403 for VIN %s"
                    " -- endpoint may require different auth or may be unavailable",
                    vin,
                )
                return {}
            resp.raise_for_status()
            data = await resp.json()
        if isinstance(data, list) and data:
            return data[0]
        return {}
