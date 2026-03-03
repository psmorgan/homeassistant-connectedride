"""BMW Connected Ride Cloud Sync API client."""

import logging
from typing import Any

import aiohttp

from .const import REGION_CONFIGS

BIKES_PATH = "cnrd/cloudsync/v2/bikes"
STATICDATA_PATH = "cnrd/bike/v2/staticdata"
STATICDATA_API_KEY = "9dcd9fb1-3118-468d-86fc-d6dfca50c492"

_LOGGER = logging.getLogger(__name__)

_VIEW_TYPES = ("sideViews", "riderViews")


def extract_image_views(vehicle_info: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract one image per view type from VehicleInfoResponse.

    Selects a single entry per view type using three-tier colorCode matching:
    1. Exact match on the bike's top-level colorCode
    2. Entry with colorCode == "NOCOLOR"
    3. First entry as last resort

    Returns list of dicts with keys: key, url.
    """
    views: list[dict[str, Any]] = []
    images: dict[str, Any] = vehicle_info.get("images") or {}
    color_code: str | None = vehicle_info.get("colorCode")
    for view_type in _VIEW_TYPES:
        entries: list[dict[str, Any]] = images.get(view_type) or []
        if not entries:
            continue
        entry: dict[str, Any] | None = None
        if color_code is not None:
            entry = next((e for e in entries if e.get("colorCode") == color_code), None)
        if entry is None:
            entry = next((e for e in entries if e.get("colorCode") == "NOCOLOR"), None)
        if entry is None:
            entry = entries[0]
        url = entry.get("url")
        if url:
            views.append({"key": view_type, "url": url})
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
        self._base_url: str = REGION_CONFIGS[region]["api_base_url"]
        self._client_id_header = client_id_header

    async def async_get_bikes(self, access_token: str) -> list[dict[str, Any]]:
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
            data: dict[str, Any] = await resp.json()
        bikes: list[dict[str, Any]] = data.get("bikes", [])
        return bikes

    async def async_download_image(self, url: str) -> tuple[bytes, str] | None:
        """Download image bytes from a URL. Returns (bytes, content_type) or None.

        No auth header needed -- S3 pre-signed URLs include auth in query params.
        """
        try:
            async with self._session.get(
                url, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                resp.raise_for_status()
                content_type = resp.headers.get("Content-Type", "image/jpeg")
                return await resp.read(), content_type
        except Exception:
            _LOGGER.warning("Could not download image from %s", url)
            return None

    async def async_get_vehicle_info(
        self,
        vin: str,
        type_key: str | None = None,
        abs_type: str | None = None,
    ) -> dict[str, Any]:
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
        body: dict[str, Any] = {"vin": vin}
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
            data: dict[str, Any] | list[dict[str, Any]] = await resp.json()
        if isinstance(data, list) and data:
            return data[0]
        return {}
