"""Tests for BMW Connected Ride API client."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

# Add the project root to sys.path so we can import without HA
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from custom_components.bmw_connected_ride.api import BMWApiClient, BIKES_PATH
from custom_components.bmw_connected_ride.auth import BMWAuthError
from custom_components.bmw_connected_ride.const import REGION_CONFIGS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TEST_ACCESS_TOKEN = "test-access-token-abc123"
TEST_CLIENT_ID_HEADER = "550e8400-e29b-41d4-a716-446655440000"
TEST_REGION = "ROW"
TEST_BASE_URL = REGION_CONFIGS[TEST_REGION]["api_base_url"]

SAMPLE_BIKES = [
    {
        "vin": "WB10X0X00X0000001",
        "name": "My R 1300 GS",
        "fuelLevel": 72,
        "remainingRange": 245000.0,
        "lastConnectedTime": 1735689600,
        "_deleted": False,
    },
    {
        "vin": "WB10X0X00X0000002",
        "name": "My S 1000 RR",
        "fuelLevel": 45,
        "remainingRange": 120000.0,
        "lastConnectedTime": 1735600000,
        "_deleted": False,
    },
]


def _make_mock_response(status, json_data=None, text_data=""):
    """Create a mock aiohttp response."""
    resp = MagicMock()
    resp.status = status
    resp.json = AsyncMock(return_value=json_data or {})
    resp.text = AsyncMock(return_value=text_data)
    resp.raise_for_status = MagicMock()
    if status >= 400:
        resp.raise_for_status.side_effect = aiohttp.ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=status,
            message=f"HTTP {status}",
        )
    # Make it usable as async context manager
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    return resp


def _make_mock_session(response):
    """Create a mock aiohttp session with a GET response."""
    session = MagicMock(spec=aiohttp.ClientSession)
    session.get = MagicMock(return_value=response)
    return session


# ---------------------------------------------------------------------------
# BMWApiClient tests
# ---------------------------------------------------------------------------


class TestBMWApiClientInit:
    """Tests for BMWApiClient constructor."""

    def test_stores_region_base_url(self):
        session = MagicMock()
        client = BMWApiClient(session=session, region="ROW", client_id_header="uuid1")
        assert client._base_url == REGION_CONFIGS["ROW"]["api_base_url"]

    def test_stores_na_region_base_url(self):
        session = MagicMock()
        client = BMWApiClient(session=session, region="NA", client_id_header="uuid1")
        assert client._base_url == REGION_CONFIGS["NA"]["api_base_url"]

    def test_stores_client_id_header(self):
        session = MagicMock()
        client = BMWApiClient(
            session=session, region="ROW", client_id_header=TEST_CLIENT_ID_HEADER
        )
        assert client._client_id_header == TEST_CLIENT_ID_HEADER


class TestAsyncGetBikes:
    """Tests for BMWApiClient.async_get_bikes."""

    @pytest.mark.asyncio
    async def test_returns_list_of_bikes(self):
        """Successful GET returns list of bikes from the 'bikes' key."""
        resp = _make_mock_response(200, json_data={"bikes": SAMPLE_BIKES})
        session = _make_mock_session(resp)
        client = BMWApiClient(
            session=session, region=TEST_REGION, client_id_header=TEST_CLIENT_ID_HEADER
        )

        result = await client.async_get_bikes(TEST_ACCESS_TOKEN)

        assert result == SAMPLE_BIKES
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_correct_url(self):
        """Calls the correct Cloud Sync bikes URL."""
        resp = _make_mock_response(200, json_data={"bikes": []})
        session = _make_mock_session(resp)
        client = BMWApiClient(
            session=session, region=TEST_REGION, client_id_header=TEST_CLIENT_ID_HEADER
        )

        await client.async_get_bikes(TEST_ACCESS_TOKEN)

        expected_url = f"{TEST_BASE_URL}/{BIKES_PATH}"
        session.get.assert_called_once()
        call_args = session.get.call_args
        assert call_args[0][0] == expected_url

    @pytest.mark.asyncio
    async def test_correct_headers(self):
        """Sends Authorization, Content-Type, and X-Client-ID headers."""
        resp = _make_mock_response(200, json_data={"bikes": []})
        session = _make_mock_session(resp)
        client = BMWApiClient(
            session=session, region=TEST_REGION, client_id_header=TEST_CLIENT_ID_HEADER
        )

        await client.async_get_bikes(TEST_ACCESS_TOKEN)

        call_kwargs = session.get.call_args[1]
        headers = call_kwargs["headers"]
        assert headers["Authorization"] == f"Bearer {TEST_ACCESS_TOKEN}"
        assert headers["Content-Type"] == "application/json"
        assert headers["X-Client-ID"] == TEST_CLIENT_ID_HEADER

    @pytest.mark.asyncio
    async def test_correct_query_params(self):
        """Sends limit=200 query parameter."""
        resp = _make_mock_response(200, json_data={"bikes": []})
        session = _make_mock_session(resp)
        client = BMWApiClient(
            session=session, region=TEST_REGION, client_id_header=TEST_CLIENT_ID_HEADER
        )

        await client.async_get_bikes(TEST_ACCESS_TOKEN)

        call_kwargs = session.get.call_args[1]
        assert call_kwargs["params"] == {"limit": 200}

    @pytest.mark.asyncio
    async def test_401_raises_bmw_auth_error(self):
        """HTTP 401 raises BMWAuthError."""
        resp = _make_mock_response(401)
        session = _make_mock_session(resp)
        client = BMWApiClient(
            session=session, region=TEST_REGION, client_id_header=TEST_CLIENT_ID_HEADER
        )

        with pytest.raises(BMWAuthError, match="401"):
            await client.async_get_bikes(TEST_ACCESS_TOKEN)

    @pytest.mark.asyncio
    async def test_500_raises_client_response_error(self):
        """Non-401 HTTP errors raise aiohttp.ClientResponseError via raise_for_status."""
        resp = _make_mock_response(500)
        session = _make_mock_session(resp)
        client = BMWApiClient(
            session=session, region=TEST_REGION, client_id_header=TEST_CLIENT_ID_HEADER
        )

        with pytest.raises(aiohttp.ClientResponseError):
            await client.async_get_bikes(TEST_ACCESS_TOKEN)

    @pytest.mark.asyncio
    async def test_empty_bikes_key(self):
        """Returns empty list when response JSON has no 'bikes' key."""
        resp = _make_mock_response(200, json_data={"otherField": "value"})
        session = _make_mock_session(resp)
        client = BMWApiClient(
            session=session, region=TEST_REGION, client_id_header=TEST_CLIENT_ID_HEADER
        )

        result = await client.async_get_bikes(TEST_ACCESS_TOKEN)

        assert result == []

    @pytest.mark.asyncio
    async def test_empty_bikes_list(self):
        """Returns empty list when bikes array is empty."""
        resp = _make_mock_response(200, json_data={"bikes": []})
        session = _make_mock_session(resp)
        client = BMWApiClient(
            session=session, region=TEST_REGION, client_id_header=TEST_CLIENT_ID_HEADER
        )

        result = await client.async_get_bikes(TEST_ACCESS_TOKEN)

        assert result == []

    @pytest.mark.asyncio
    async def test_na_region_uses_correct_base_url(self):
        """NA region uses the NA-specific base URL."""
        resp = _make_mock_response(200, json_data={"bikes": []})
        session = _make_mock_session(resp)
        client = BMWApiClient(
            session=session, region="NA", client_id_header=TEST_CLIENT_ID_HEADER
        )

        await client.async_get_bikes(TEST_ACCESS_TOKEN)

        expected_url = f"{REGION_CONFIGS['NA']['api_base_url']}/{BIKES_PATH}"
        call_args = session.get.call_args
        assert call_args[0][0] == expected_url
