"""BMW Connected Ride Cloud Sync API client."""

import aiohttp

from .const import REGION_CONFIGS

BIKES_PATH = "cnrd/cloudsync/v2/bikes"


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
