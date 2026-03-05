"""Tests for BMW Connected Ride auth module."""

import asyncio
import base64
import hashlib
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

# Add the project root to sys.path so we can import without HA
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from custom_components.bmw_connected_ride.auth import (
    BMWAuthClient,
    BMWAuthError,
    BMWTransientError,
    generate_pkce,
)
from custom_components.bmw_connected_ride.const import (
    BMW_CLIENT_ID,
    BMW_CLIENT_SECRET,
    GCDM_BASE_URL,
    OAUTH_SCOPES,
    TOKEN_REFRESH_BUFFER_SECONDS,
)


# ---------------------------------------------------------------------------
# generate_pkce tests
# ---------------------------------------------------------------------------

class TestGeneratePkce:
    def test_returns_tuple_of_two_strings(self):
        result = generate_pkce()
        assert isinstance(result, tuple)
        assert len(result) == 2
        verifier, challenge = result
        assert isinstance(verifier, str)
        assert isinstance(challenge, str)

    def test_verifier_is_url_safe_base64(self):
        verifier, _ = generate_pkce()
        # URL-safe base64 chars only: A-Z, a-z, 0-9, -, _
        import re
        assert re.match(r'^[A-Za-z0-9\-_]+$', verifier), \
            f"Verifier contains non-URL-safe chars: {verifier}"

    def test_verifier_length(self):
        verifier, _ = generate_pkce()
        # secrets.token_urlsafe(64) produces 86 chars
        assert len(verifier) == 86

    def test_challenge_is_s256_of_verifier(self):
        verifier, challenge = generate_pkce()
        # Compute expected: SHA-256 of verifier bytes, base64url no padding
        digest = hashlib.sha256(verifier.encode('ascii')).digest()
        expected = base64.urlsafe_b64encode(digest).rstrip(b'=').decode('ascii')
        assert challenge == expected

    def test_challenge_has_no_padding(self):
        _, challenge = generate_pkce()
        assert '=' not in challenge

    def test_each_call_returns_different_verifier(self):
        v1, _ = generate_pkce()
        v2, _ = generate_pkce()
        assert v1 != v2


# ---------------------------------------------------------------------------
# BMWAuthClient construction tests
# ---------------------------------------------------------------------------

class TestBMWAuthClientConstruction:
    def _make_session(self):
        return MagicMock(spec=aiohttp.ClientSession)

    def test_constructs_with_required_args(self):
        session = self._make_session()
        client = BMWAuthClient(region="ROW", session=session)
        assert client is not None

    def test_tokens_changed_initially_false(self):
        session = self._make_session()
        client = BMWAuthClient(region="ROW", session=session)
        assert client.tokens_changed is False

    def test_access_token_property(self):
        session = self._make_session()
        client = BMWAuthClient(
            region="ROW", session=session, access_token="test_access"
        )
        assert client.access_token == "test_access"

    def test_refresh_token_property(self):
        session = self._make_session()
        client = BMWAuthClient(
            region="ROW", session=session, refresh_token="test_refresh"
        )
        assert client.refresh_token == "test_refresh"

    def test_token_expiry_property(self):
        session = self._make_session()
        expiry = int(time.time()) + 3600
        client = BMWAuthClient(region="ROW", session=session, token_expiry=expiry)
        assert client.token_expiry == expiry


# ---------------------------------------------------------------------------
# request_device_code tests
# ---------------------------------------------------------------------------

class TestRequestDeviceCode:
    def _make_mock_session(self, response_data: dict, status: int = 200):
        """Create a mock aiohttp session that returns the given response."""
        mock_response = AsyncMock()
        mock_response.status = status
        mock_response.json = AsyncMock(return_value=response_data)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock(spec=aiohttp.ClientSession)
        mock_session.post = MagicMock(return_value=mock_response)
        return mock_session

    @pytest.mark.asyncio
    async def test_posts_to_correct_url(self):
        response_data = {
            "device_code": "dev_code",
            "user_code": "USER-CODE",
            "verification_uri": "https://example.com/activate",
            "expires_in": 300,
            "interval": 5,
        }
        session = self._make_mock_session(response_data)
        client = BMWAuthClient(region="ROW", session=session)
        result = await client.request_device_code()

        session.post.assert_called_once()
        call_args = session.post.call_args
        url = call_args[0][0] if call_args[0] else call_args[1].get("url") or call_args[0][0]
        assert GCDM_BASE_URL in url
        assert "device/code" in url

    @pytest.mark.asyncio
    async def test_includes_client_id_in_form(self):
        response_data = {
            "device_code": "dev_code",
            "user_code": "USER-CODE",
            "verification_uri": "https://example.com/activate",
            "expires_in": 300,
            "interval": 5,
        }
        session = self._make_mock_session(response_data)
        client = BMWAuthClient(region="ROW", session=session)
        await client.request_device_code()

        call_args = session.post.call_args
        data = call_args[1].get("data") or {}
        assert BMW_CLIENT_ID in str(data)

    @pytest.mark.asyncio
    async def test_includes_pkce_challenge_in_form(self):
        response_data = {
            "device_code": "dev_code",
            "user_code": "USER-CODE",
            "verification_uri": "https://example.com/activate",
            "expires_in": 300,
            "interval": 5,
        }
        session = self._make_mock_session(response_data)
        client = BMWAuthClient(region="ROW", session=session)
        await client.request_device_code()

        call_args = session.post.call_args
        data = call_args[1].get("data") or {}
        data_str = str(data)
        assert "code_challenge" in data_str

    @pytest.mark.asyncio
    async def test_returns_response_dict(self):
        response_data = {
            "device_code": "dev_code",
            "user_code": "USER-CODE",
            "verification_uri": "https://example.com/activate",
            "expires_in": 300,
            "interval": 5,
        }
        session = self._make_mock_session(response_data)
        client = BMWAuthClient(region="ROW", session=session)
        result = await client.request_device_code()

        assert result["device_code"] == "dev_code"
        assert result["user_code"] == "USER-CODE"
        assert result["verification_uri"] == "https://example.com/activate"

    @pytest.mark.asyncio
    async def test_stores_code_verifier_on_self(self):
        response_data = {
            "device_code": "dev_code",
            "user_code": "USER-CODE",
            "verification_uri": "https://example.com/activate",
            "expires_in": 300,
            "interval": 5,
        }
        session = self._make_mock_session(response_data)
        client = BMWAuthClient(region="ROW", session=session)
        await client.request_device_code()
        # _code_verifier should be set after calling request_device_code
        assert client._code_verifier is not None
        assert len(client._code_verifier) == 86


# ---------------------------------------------------------------------------
# poll_for_token tests
# ---------------------------------------------------------------------------

class TestPollForToken:
    def _make_pending_then_success_session(self):
        """Returns a session that first returns authorization_pending then success."""
        pending_response = AsyncMock()
        pending_response.status = 400
        pending_response.json = AsyncMock(return_value={"error": "authorization_pending"})
        pending_response.__aenter__ = AsyncMock(return_value=pending_response)
        pending_response.__aexit__ = AsyncMock(return_value=None)

        success_response = AsyncMock()
        success_response.status = 200
        success_response.json = AsyncMock(return_value={
            "access_token": "access123",
            "refresh_token": "refresh456",
            "expires_in": 3600,
        })
        success_response.__aenter__ = AsyncMock(return_value=success_response)
        success_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock(spec=aiohttp.ClientSession)
        mock_session.post = MagicMock(side_effect=[pending_response, success_response])
        return mock_session

    def _make_success_session(self, token_data: dict | None = None):
        if token_data is None:
            token_data = {
                "access_token": "access123",
                "refresh_token": "refresh456",
                "expires_in": 3600,
            }
        success_response = AsyncMock()
        success_response.status = 200
        success_response.json = AsyncMock(return_value=token_data)
        success_response.__aenter__ = AsyncMock(return_value=success_response)
        success_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock(spec=aiohttp.ClientSession)
        mock_session.post = MagicMock(return_value=success_response)
        return mock_session

    @pytest.mark.asyncio
    async def test_returns_token_dict_on_success(self):
        session = self._make_success_session()
        client = BMWAuthClient(region="ROW", session=session)
        client._code_verifier = "test_verifier" * 6  # simulate stored verifier

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await client.poll_for_token(
                device_code="dev_code", interval=1, expires_in=60
            )

        assert result["access_token"] == "access123"
        assert result["refresh_token"] == "refresh456"

    @pytest.mark.asyncio
    async def test_sets_tokens_changed_on_success(self):
        session = self._make_success_session()
        client = BMWAuthClient(region="ROW", session=session)
        client._code_verifier = "test_verifier" * 6

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await client.poll_for_token(
                device_code="dev_code", interval=1, expires_in=60
            )

        assert client.tokens_changed is True

    @pytest.mark.asyncio
    async def test_updates_access_token_on_success(self):
        session = self._make_success_session()
        client = BMWAuthClient(region="ROW", session=session)
        client._code_verifier = "test_verifier" * 6

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await client.poll_for_token(
                device_code="dev_code", interval=1, expires_in=60
            )

        assert client.access_token == "access123"
        assert client.refresh_token == "refresh456"

    @pytest.mark.asyncio
    async def test_handles_authorization_pending(self):
        session = self._make_pending_then_success_session()
        client = BMWAuthClient(region="ROW", session=session)
        client._code_verifier = "test_verifier" * 6

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await client.poll_for_token(
                device_code="dev_code", interval=2, expires_in=60
            )

        # Should have slept at least once
        mock_sleep.assert_called()
        assert result["access_token"] == "access123"

    @pytest.mark.asyncio
    async def test_uses_plain_client_secret_not_basic_auth(self):
        """Critical: device code exchange uses plain client_secret, not Basic auth."""
        session = self._make_success_session()
        client = BMWAuthClient(region="ROW", session=session)
        client._code_verifier = "test_verifier" * 6

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await client.poll_for_token(
                device_code="dev_code", interval=1, expires_in=60
            )

        call_args = session.post.call_args
        # Check headers do NOT contain Basic auth
        headers = call_args[1].get("headers") or {}
        auth_header = headers.get("Authorization", "")
        assert not auth_header.startswith("Basic"), \
            "poll_for_token must NOT use Basic auth - use plain client_secret in form data"
        # Check that client_secret IS in form data
        data = call_args[1].get("data") or {}
        data_str = str(data)
        assert BMW_CLIENT_SECRET in data_str, \
            "poll_for_token must include client_secret as a form field"

    @pytest.mark.asyncio
    async def test_raises_on_expired_device_code(self):
        """Should raise BMWAuthError when device code expires."""
        # Return authorization_pending continuously so it times out
        pending_response = AsyncMock()
        pending_response.status = 400
        pending_response.json = AsyncMock(return_value={"error": "authorization_pending"})
        pending_response.__aenter__ = AsyncMock(return_value=pending_response)
        pending_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock(spec=aiohttp.ClientSession)
        mock_session.post = MagicMock(return_value=pending_response)

        client = BMWAuthClient(region="ROW", session=mock_session)
        client._code_verifier = "test_verifier" * 6

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with patch("time.time", side_effect=[0, 0, 200]):  # expires_in=10
                with pytest.raises(BMWAuthError, match="expired"):
                    await client.poll_for_token(
                        device_code="dev_code", interval=1, expires_in=10
                    )


# ---------------------------------------------------------------------------
# _refresh_tokens tests
# ---------------------------------------------------------------------------

class TestRefreshTokens:
    def _make_refresh_session(self, status: int = 200, response_data: dict | None = None):
        if response_data is None:
            response_data = {
                "access_token": "new_access",
                "refresh_token": "new_refresh",
                "expires_in": 3600,
            }
        mock_response = AsyncMock()
        mock_response.status = status
        mock_response.json = AsyncMock(return_value=response_data)
        mock_response.text = AsyncMock(return_value=json.dumps(response_data))
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock(spec=aiohttp.ClientSession)
        mock_session.post = MagicMock(return_value=mock_response)
        return mock_session

    @pytest.mark.asyncio
    async def test_uses_basic_auth_header(self):
        """Critical: token refresh MUST use Basic auth, not plain client_secret."""
        session = self._make_refresh_session()
        client = BMWAuthClient(
            region="ROW",
            session=session,
            refresh_token="old_refresh",
            token_expiry=int(time.time()) + 60,
        )
        await client._refresh_tokens()

        call_args = session.post.call_args
        headers = call_args[1].get("headers") or {}
        auth_header = headers.get("Authorization", "")
        assert auth_header.startswith("Basic "), \
            "_refresh_tokens must use Basic auth header"

    @pytest.mark.asyncio
    async def test_basic_auth_encodes_client_id_and_secret(self):
        session = self._make_refresh_session()
        client = BMWAuthClient(
            region="ROW",
            session=session,
            refresh_token="old_refresh",
            token_expiry=int(time.time()) + 60,
        )
        await client._refresh_tokens()

        call_args = session.post.call_args
        headers = call_args[1].get("headers") or {}
        auth_header = headers.get("Authorization", "")
        assert auth_header.startswith("Basic ")
        b64_part = auth_header[6:]
        decoded = base64.b64decode(b64_part).decode("utf-8")
        assert decoded == f"{BMW_CLIENT_ID}:{BMW_CLIENT_SECRET}"

    @pytest.mark.asyncio
    async def test_updates_access_token_on_success(self):
        session = self._make_refresh_session()
        client = BMWAuthClient(
            region="ROW",
            session=session,
            refresh_token="old_refresh",
            token_expiry=int(time.time()) + 60,
        )
        await client._refresh_tokens()

        assert client.access_token == "new_access"
        assert client.refresh_token == "new_refresh"

    @pytest.mark.asyncio
    async def test_sets_tokens_changed_on_success(self):
        session = self._make_refresh_session()
        client = BMWAuthClient(
            region="ROW",
            session=session,
            refresh_token="old_refresh",
            token_expiry=int(time.time()) + 60,
        )
        await client._refresh_tokens()

        assert client.tokens_changed is True

    @pytest.mark.asyncio
    async def test_raises_on_401(self):
        session = self._make_refresh_session(status=401, response_data={"error": "invalid_token"})
        client = BMWAuthClient(
            region="ROW",
            session=session,
            refresh_token="old_refresh",
            token_expiry=int(time.time()) + 60,
        )
        with pytest.raises(BMWAuthError, match="re-authentication"):
            await client._refresh_tokens()

    @pytest.mark.asyncio
    async def test_raises_on_403(self):
        session = self._make_refresh_session(status=403, response_data={"error": "forbidden"})
        client = BMWAuthClient(
            region="ROW",
            session=session,
            refresh_token="old_refresh",
            token_expiry=int(time.time()) + 60,
        )
        with pytest.raises(BMWAuthError, match="re-authentication"):
            await client._refresh_tokens()

    @pytest.mark.asyncio
    async def test_does_not_put_client_secret_in_form_data(self):
        """Ensure client_secret is NOT included as plain form field in refresh."""
        session = self._make_refresh_session()
        client = BMWAuthClient(
            region="ROW",
            session=session,
            refresh_token="old_refresh",
            token_expiry=int(time.time()) + 60,
        )
        await client._refresh_tokens()

        call_args = session.post.call_args
        data = call_args[1].get("data") or {}
        data_str = str(data)
        assert BMW_CLIENT_SECRET not in data_str, \
            "_refresh_tokens must NOT include client_secret in form data (use Basic auth)"

    @pytest.mark.asyncio
    async def test_raises_transient_error_on_500(self):
        """HTTP 500 raises BMWTransientError, not BMWAuthError."""
        session = self._make_refresh_session(status=500, response_data={"error": "server_error"})
        client = BMWAuthClient(
            region="ROW",
            session=session,
            refresh_token="old_refresh",
            token_expiry=int(time.time()) + 60,
        )
        with pytest.raises(BMWTransientError, match="transient"):
            await client._refresh_tokens()

    @pytest.mark.asyncio
    async def test_raises_transient_error_on_502(self):
        """HTTP 502 raises BMWTransientError."""
        session = self._make_refresh_session(status=502, response_data={"error": "bad_gateway"})
        client = BMWAuthClient(
            region="ROW",
            session=session,
            refresh_token="old_refresh",
            token_expiry=int(time.time()) + 60,
        )
        with pytest.raises(BMWTransientError, match="transient"):
            await client._refresh_tokens()

    @pytest.mark.asyncio
    async def test_raises_transient_error_on_503(self):
        """HTTP 503 raises BMWTransientError."""
        session = self._make_refresh_session(status=503, response_data={"error": "unavailable"})
        client = BMWAuthClient(
            region="ROW",
            session=session,
            refresh_token="old_refresh",
            token_expiry=int(time.time()) + 60,
        )
        with pytest.raises(BMWTransientError, match="transient"):
            await client._refresh_tokens()

    @pytest.mark.asyncio
    async def test_raises_transient_error_on_429(self):
        """HTTP 429 (rate limit) raises BMWTransientError."""
        session = self._make_refresh_session(status=429, response_data={"error": "rate_limited"})
        client = BMWAuthClient(
            region="ROW",
            session=session,
            refresh_token="old_refresh",
            token_expiry=int(time.time()) + 60,
        )
        with pytest.raises(BMWTransientError, match="transient"):
            await client._refresh_tokens()

    @pytest.mark.asyncio
    async def test_raises_transient_error_on_network_error(self):
        """Network errors (aiohttp.ClientError) raise BMWTransientError."""
        mock_session = MagicMock(spec=aiohttp.ClientSession)
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(side_effect=aiohttp.ClientConnectionError("Connection reset"))
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_session.post = MagicMock(return_value=mock_cm)

        client = BMWAuthClient(
            region="ROW",
            session=mock_session,
            refresh_token="old_refresh",
            token_expiry=int(time.time()) + 60,
        )
        with pytest.raises(BMWTransientError, match="network error"):
            await client._refresh_tokens()

    @pytest.mark.asyncio
    async def test_raises_transient_error_on_timeout(self):
        """Timeout errors raise BMWTransientError."""
        mock_session = MagicMock(spec=aiohttp.ClientSession)
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_session.post = MagicMock(return_value=mock_cm)

        client = BMWAuthClient(
            region="ROW",
            session=mock_session,
            refresh_token="old_refresh",
            token_expiry=int(time.time()) + 60,
        )
        with pytest.raises(BMWTransientError, match="network error"):
            await client._refresh_tokens()


# ---------------------------------------------------------------------------
# async_ensure_token_valid tests
# ---------------------------------------------------------------------------

class TestAsyncEnsureTokenValid:
    @pytest.mark.asyncio
    async def test_calls_refresh_when_token_near_expiry(self):
        session = MagicMock(spec=aiohttp.ClientSession)
        # Token expires in 100 seconds (within buffer of 300)
        expiry = int(time.time()) + 100
        client = BMWAuthClient(
            region="ROW",
            session=session,
            access_token="old_access",
            refresh_token="old_refresh",
            token_expiry=expiry,
        )
        with patch.object(client, "_refresh_tokens", new_callable=AsyncMock) as mock_refresh:
            await client.async_ensure_token_valid()
            mock_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_does_not_refresh_when_token_valid(self):
        session = MagicMock(spec=aiohttp.ClientSession)
        # Token expires in 1 hour (well beyond buffer)
        expiry = int(time.time()) + 3600
        client = BMWAuthClient(
            region="ROW",
            session=session,
            access_token="valid_access",
            refresh_token="valid_refresh",
            token_expiry=expiry,
        )
        with patch.object(client, "_refresh_tokens", new_callable=AsyncMock) as mock_refresh:
            await client.async_ensure_token_valid()
            mock_refresh.assert_not_called()

    @pytest.mark.asyncio
    async def test_calls_refresh_when_token_expired(self):
        session = MagicMock(spec=aiohttp.ClientSession)
        # Token already expired
        expiry = int(time.time()) - 100
        client = BMWAuthClient(
            region="ROW",
            session=session,
            access_token="expired_access",
            refresh_token="expired_refresh",
            token_expiry=expiry,
        )
        with patch.object(client, "_refresh_tokens", new_callable=AsyncMock) as mock_refresh:
            await client.async_ensure_token_valid()
            mock_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_calls_refresh_exactly_at_buffer_boundary(self):
        session = MagicMock(spec=aiohttp.ClientSession)
        # Token expires exactly at buffer boundary
        expiry = int(time.time()) + TOKEN_REFRESH_BUFFER_SECONDS
        client = BMWAuthClient(
            region="ROW",
            session=session,
            access_token="access",
            refresh_token="refresh",
            token_expiry=expiry,
        )
        with patch.object(client, "_refresh_tokens", new_callable=AsyncMock) as mock_refresh:
            await client.async_ensure_token_valid()
            mock_refresh.assert_called_once()
