"""BMW Connected Ride OAuth authentication client."""

import asyncio
import base64
import hashlib
import logging
import secrets
import time
from typing import Any

import aiohttp

from .const import (
    BMW_CLIENT_ID,
    BMW_CLIENT_SECRET,
    GCDM_BASE_URL,
    OAUTH_SCOPES,
    TOKEN_REFRESH_BUFFER_SECONDS,
)

_LOGGER = logging.getLogger(__name__)


class BMWAuthError(Exception):
    """Raised for BMW authentication failures."""


def generate_pkce() -> tuple[str, str]:
    """Generate a PKCE code_verifier and code_challenge pair.

    Returns:
        A (code_verifier, code_challenge) tuple where code_challenge is
        the SHA-256 hash of code_verifier, base64url-encoded without padding.
    """
    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge


class BMWAuthClient:
    """Client for BMW GCDM OAuth device code flow and token management.

    Handles PKCE generation, device code requests, token exchange (using plain
    client_secret in form data), and token refresh (using Basic auth header).
    These two auth patterns are intentionally different per BMW's GCDM spec.
    """

    def __init__(
        self,
        region: str,
        session: aiohttp.ClientSession,
        access_token: str | None = None,
        refresh_token: str | None = None,
        token_expiry: int = 0,
    ) -> None:
        """Initialize the BMW auth client.

        Args:
            region: Region code ("ROW" or "NA").
            session: Shared aiohttp session.
            access_token: Existing access token, if any.
            refresh_token: Existing refresh token, if any.
            token_expiry: Epoch seconds when access token expires (0 if unknown).
        """
        self._region = region
        self._session = session
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._token_expiry = token_expiry
        self._code_verifier: str | None = None
        self._tokens_changed = False

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def access_token(self) -> str | None:
        """Current access token."""
        return self._access_token

    @property
    def refresh_token(self) -> str | None:
        """Current refresh token."""
        return self._refresh_token

    @property
    def token_expiry(self) -> int:
        """Epoch seconds when the current access token expires."""
        return self._token_expiry

    @property
    def tokens_changed(self) -> bool:
        """True if tokens have been modified since this client was constructed."""
        return self._tokens_changed

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def request_device_code(self) -> dict[str, Any]:
        """Request a device code from BMW GCDM to begin device code flow.

        Generates a PKCE pair and stores the code_verifier for later use in
        poll_for_token().

        Returns:
            Dict with device_code, user_code, verification_uri, expires_in, interval.

        Raises:
            BMWAuthError: On unexpected HTTP responses.
        """
        code_verifier, code_challenge = generate_pkce()
        self._code_verifier = code_verifier

        url = f"{GCDM_BASE_URL}/gcdm/oauth/device/code"
        data = {
            "client_id": BMW_CLIENT_ID,
            "response_type": "device_code",
            "code_challenge_method": "S256",
            "code_challenge": code_challenge,
            "scope": OAUTH_SCOPES,
        }
        headers = {"Accept": "application/json"}

        _LOGGER.debug("Requesting BMW device code from %s", url)

        async with self._session.post(url, data=data, headers=headers) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise BMWAuthError(
                    f"Device code request failed: HTTP {resp.status} — {text}"
                )
            result: dict[str, Any] = await resp.json()

        _LOGGER.debug(
            "Device code received, expires_in=%s interval=%s",
            result.get("expires_in"),
            result.get("interval"),
        )
        return result

    async def poll_for_token(
        self,
        device_code: str,
        interval: int,
        expires_in: int,
    ) -> dict[str, Any]:
        """Poll BMW GCDM until the user authorizes the device or the code expires.

        Uses plain client_secret as a form field (NOT Basic auth) — this is
        distinct from _refresh_tokens() which uses Basic auth.

        Args:
            device_code: Device code returned from request_device_code().
            interval: Polling interval in seconds.
            expires_in: Device code lifetime in seconds.

        Returns:
            Token dict with access_token, refresh_token, expires_in.

        Raises:
            BMWAuthError: If the device code expires or an unexpected error occurs.
        """
        url = f"{GCDM_BASE_URL}/gcdm/oauth/token"
        start_time = time.time()

        _LOGGER.debug("Polling for device code token, expires_in=%s", expires_in)

        while True:
            elapsed = time.time() - start_time
            if elapsed >= expires_in:
                raise BMWAuthError(
                    "Device code expired — user did not authorize in time"
                )

            data = {
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": device_code,
                "client_id": BMW_CLIENT_ID,
                "client_secret": BMW_CLIENT_SECRET,
                "code_verifier": self._code_verifier,
            }

            async with self._session.post(url, data=data) as resp:
                if resp.status == 200:
                    token_data: dict[str, Any] = await resp.json()
                    self._store_tokens(token_data)
                    _LOGGER.debug(
                        "Token obtained, access_token length=%d, expires_in=%s",
                        len(self._access_token or ""),
                        token_data.get("expires_in"),
                    )
                    return token_data

                error_data: dict[str, Any] = await resp.json()
                error = error_data.get("error", "")

                if error == "authorization_pending":
                    _LOGGER.debug(
                        "Authorization pending, retrying in %s seconds", interval
                    )
                    await asyncio.sleep(interval)
                elif error == "slow_down":
                    interval += 5
                    _LOGGER.debug(
                        "Slow down requested, new interval=%s", interval
                    )
                    await asyncio.sleep(interval)
                else:
                    raise BMWAuthError(
                        f"Token poll failed: HTTP {resp.status} — {error_data}"
                    )

    async def _refresh_tokens(self) -> None:
        """Refresh the access token using the refresh token.

        Uses Authorization: Basic header (NOT plain client_secret form field).
        This is intentionally different from poll_for_token() per BMW's spec.

        Raises:
            BMWAuthError: On 401/403 (re-auth required) or other HTTP errors.
        """
        url = f"{GCDM_BASE_URL}/gcdm/oauth/token"
        credentials = f"{BMW_CLIENT_ID}:{BMW_CLIENT_SECRET}"
        basic_auth = base64.b64encode(credentials.encode("utf-8")).decode("ascii")

        data = {
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
        }
        headers = {
            "Authorization": f"Basic {basic_auth}",
        }

        _LOGGER.debug("Refreshing BMW access token")

        async with self._session.post(url, data=data, headers=headers) as resp:
            if resp.status in (401, 403):
                raise BMWAuthError(
                    f"Token refresh failed — re-authentication required (HTTP {resp.status})"
                )
            if resp.status != 200:
                text = await resp.text()
                raise BMWAuthError(
                    f"Token refresh failed: HTTP {resp.status} — {text}"
                )
            token_data: dict[str, Any] = await resp.json()

        self._store_tokens(token_data)
        _LOGGER.debug(
            "Access token refreshed, length=%d, new_expiry=%d",
            len(self._access_token or ""),
            self._token_expiry,
        )

    async def async_ensure_token_valid(self) -> None:
        """Ensure the access token is valid, refreshing it if necessary.

        Refreshes proactively if the token expires within TOKEN_REFRESH_BUFFER_SECONDS.

        Raises:
            BMWAuthError: If token refresh fails and re-authentication is required.
        """
        if time.time() + TOKEN_REFRESH_BUFFER_SECONDS >= self._token_expiry:
            _LOGGER.debug(
                "Access token expiring soon (expiry=%d), refreshing", self._token_expiry
            )
            await self._refresh_tokens()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _store_tokens(self, token_data: dict[str, Any]) -> None:
        """Store tokens from a token response dict and mark tokens_changed."""
        self._access_token = token_data.get("access_token")
        self._refresh_token = token_data.get("refresh_token", self._refresh_token)
        expires_in = token_data.get("expires_in", 3600)
        self._token_expiry = int(time.time()) + int(expires_in)
        self._tokens_changed = True
