"""Tests for BMW Connected Ride API client."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

# Add the project root to sys.path so we can import without HA
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from custom_components.bmw_connected_ride.api import (
    BMWApiClient,
    BIKES_PATH,
    STATICDATA_PATH,
    STATICDATA_API_KEY,
    _extract_image_views,
)
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


def _make_mock_post_session(response):
    """Create a mock aiohttp session with a POST response."""
    session = MagicMock(spec=aiohttp.ClientSession)
    session.post = MagicMock(return_value=response)
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


# ---------------------------------------------------------------------------
# TestAsyncGetVehicleInfo
# ---------------------------------------------------------------------------


class TestAsyncGetVehicleInfo:
    """Tests for BMWApiClient.async_get_vehicle_info."""

    @pytest.mark.asyncio
    async def test_returns_first_item_from_list(self):
        """Returns first item from a list response."""
        item = {"vin": "WB10X0X00X0XXXXXX", "images": {}}
        resp = _make_mock_response(200, json_data=[item])
        session = _make_mock_post_session(resp)
        client = BMWApiClient(session=session, region=TEST_REGION, client_id_header=TEST_CLIENT_ID_HEADER)
        result = await client.async_get_vehicle_info(vin="WB10X0X00X0XXXXXX", type_key="K66", abs_type="0K03")
        assert result == item

    @pytest.mark.asyncio
    async def test_returns_empty_dict_for_empty_list(self):
        """Returns {} when response is an empty list."""
        resp = _make_mock_response(200, json_data=[])
        session = _make_mock_post_session(resp)
        client = BMWApiClient(session=session, region=TEST_REGION, client_id_header=TEST_CLIENT_ID_HEADER)
        result = await client.async_get_vehicle_info(vin="WB10X0X00X0XXXXXX")
        assert result == {}

    @pytest.mark.asyncio
    async def test_returns_empty_dict_on_403(self):
        """Returns {} (and logs warning) on 403 response."""
        resp = _make_mock_response(403)
        session = _make_mock_post_session(resp)
        client = BMWApiClient(session=session, region=TEST_REGION, client_id_header=TEST_CLIENT_ID_HEADER)
        result = await client.async_get_vehicle_info(vin="WB10X0X00X0XXXXXX")
        assert result == {}

    @pytest.mark.asyncio
    async def test_401_raises_bmw_auth_error(self):
        """HTTP 401 raises BMWAuthError."""
        resp = _make_mock_response(401)
        session = _make_mock_post_session(resp)
        client = BMWApiClient(session=session, region=TEST_REGION, client_id_header=TEST_CLIENT_ID_HEADER)
        with pytest.raises(BMWAuthError, match="401"):
            await client.async_get_vehicle_info(vin="WB10X0X00X0XXXXXX")

    @pytest.mark.asyncio
    async def test_sends_correct_headers_and_body(self):
        """Sends x-cd-apigw-key header (not Bearer) and correct JSON body."""
        resp = _make_mock_response(200, json_data=[{}])
        session = _make_mock_post_session(resp)
        client = BMWApiClient(session=session, region=TEST_REGION, client_id_header=TEST_CLIENT_ID_HEADER)
        await client.async_get_vehicle_info(vin="WB10X0X00X0XXXXXX", type_key="K66", abs_type="0K03")
        call_kwargs = session.post.call_args
        headers = call_kwargs.kwargs.get("headers", {})
        assert "x-cd-apigw-key" in headers
        assert headers["x-cd-apigw-key"] == STATICDATA_API_KEY
        assert "Authorization" not in headers
        body = call_kwargs.kwargs.get("json", {})
        assert body == {"vin": "WB10X0X00X0XXXXXX", "typeKey": "K66", "absType": "0K03"}

    @pytest.mark.asyncio
    async def test_omits_optional_params_when_none(self):
        """Body omits typeKey and absType when not provided."""
        resp = _make_mock_response(200, json_data=[{}])
        session = _make_mock_post_session(resp)
        client = BMWApiClient(session=session, region=TEST_REGION, client_id_header=TEST_CLIENT_ID_HEADER)
        await client.async_get_vehicle_info(vin="WB10X0X00X0XXXXXX")
        call_kwargs = session.post.call_args
        body = call_kwargs.kwargs.get("json", {})
        assert body == {"vin": "WB10X0X00X0XXXXXX"}
        assert "typeKey" not in body
        assert "absType" not in body

    @pytest.mark.asyncio
    async def test_uses_staticdata_url(self):
        """POSTs to the correct staticdata URL."""
        resp = _make_mock_response(200, json_data=[{}])
        session = _make_mock_post_session(resp)
        client = BMWApiClient(session=session, region=TEST_REGION, client_id_header=TEST_CLIENT_ID_HEADER)
        await client.async_get_vehicle_info(vin="WB10X0X00X0XXXXXX")
        expected_url = f"{TEST_BASE_URL}/{STATICDATA_PATH}"
        call_args = session.post.call_args
        assert call_args.args[0] == expected_url


# ---------------------------------------------------------------------------
# TestExtractImageViews
# ---------------------------------------------------------------------------


class TestExtractImageViews:
    """Tests for _extract_image_views helper."""

    def test_extracts_side_view(self):
        info = {"images": {"sideViews": [{"url": "https://example.com/side.png", "colorCode": "P0H0L"}]}}
        views = _extract_image_views(info)
        assert len(views) == 1
        assert views[0] == {"key": "sideViews", "label": "Side View", "url": "https://example.com/side.png"}

    def test_extracts_rider_view(self):
        info = {"images": {"riderViews": [{"url": "https://example.com/rider.png"}]}}
        views = _extract_image_views(info)
        assert len(views) == 1
        assert views[0] == {"key": "riderViews", "label": "Rider View", "url": "https://example.com/rider.png"}

    def test_extracts_both_views(self):
        info = {"images": {
            "sideViews": [{"url": "https://example.com/side.png"}],
            "riderViews": [{"url": "https://example.com/rider.png"}],
        }}
        views = _extract_image_views(info)
        assert len(views) == 2
        assert views[0]["key"] == "sideViews"
        assert views[1]["key"] == "riderViews"

    def test_returns_empty_when_no_images(self):
        assert _extract_image_views({}) == []

    def test_returns_empty_when_images_is_none(self):
        assert _extract_image_views({"images": None}) == []

    def test_skips_entries_without_url(self):
        info = {"images": {"sideViews": [{"colorCode": "P0H0L"}]}}
        assert _extract_image_views(info) == []

    def test_multiple_entries_returns_one_per_type(self):
        """Multiple entries for a view type produce only one result (first entry fallback)."""
        info = {"images": {"sideViews": [
            {"url": "https://example.com/side1.png", "colorCode": "AAA"},
            {"url": "https://example.com/side2.png", "colorCode": "BBB"},
        ]}}
        views = _extract_image_views(info)
        assert len(views) == 1
        assert views[0] == {"key": "sideViews", "label": "Side View", "url": "https://example.com/side1.png"}

    def test_selects_entry_matching_color_code(self):
        """Selects the entry whose colorCode matches the bike's top-level colorCode."""
        info = {
            "colorCode": "P0H0L",
            "images": {"sideViews": [
                {"url": "https://example.com/wrong.png", "colorCode": "OTHER"},
                {"url": "https://example.com/correct.png", "colorCode": "P0H0L"},
            ]},
        }
        views = _extract_image_views(info)
        assert len(views) == 1
        assert views[0]["url"] == "https://example.com/correct.png"

    def test_falls_back_to_nocolor_when_no_match(self):
        """Falls back to NOCOLOR entry when no exact colorCode match exists."""
        info = {
            "colorCode": "NONEXISTENT",
            "images": {"riderViews": [
                {"url": "https://example.com/other.png", "colorCode": "AAA"},
                {"url": "https://example.com/nocolor.png", "colorCode": "NOCOLOR"},
            ]},
        }
        views = _extract_image_views(info)
        assert len(views) == 1
        assert views[0]["url"] == "https://example.com/nocolor.png"

    def test_falls_back_to_first_when_no_match_or_nocolor(self):
        """Falls back to first entry when neither exact match nor NOCOLOR exists."""
        info = {
            "colorCode": "NONEXISTENT",
            "images": {"sideViews": [
                {"url": "https://example.com/first.png", "colorCode": "AAA"},
                {"url": "https://example.com/second.png", "colorCode": "BBB"},
            ]},
        }
        views = _extract_image_views(info)
        assert len(views) == 1
        assert views[0]["url"] == "https://example.com/first.png"

    def test_color_code_none_falls_back(self):
        """When bike has no top-level colorCode, skips exact match and uses NOCOLOR or first."""
        info = {"images": {"sideViews": [
            {"url": "https://example.com/first.png", "colorCode": "AAA"},
            {"url": "https://example.com/nocolor.png", "colorCode": "NOCOLOR"},
        ]}}
        views = _extract_image_views(info)
        assert len(views) == 1
        assert views[0]["url"] == "https://example.com/nocolor.png"

    def test_color_code_none_no_nocolor_uses_first(self):
        """When bike has no colorCode and no NOCOLOR entry, uses first entry."""
        info = {"images": {"sideViews": [
            {"url": "https://example.com/first.png", "colorCode": "AAA"},
            {"url": "https://example.com/second.png", "colorCode": "BBB"},
        ]}}
        views = _extract_image_views(info)
        assert len(views) == 1
        assert views[0]["url"] == "https://example.com/first.png"

    def test_handles_empty_side_views_list(self):
        info = {"images": {"sideViews": []}}
        assert _extract_image_views(info) == []

    def test_includes_color_tile(self):
        """colorTiles view type is included and produces a Color Tile entry."""
        info = {
            "colorCode": "P0H0L",
            "images": {
                "colorTiles": [
                    {"url": "https://example.com/tile.png", "colorCode": "P0H0L"},
                ]
            },
        }
        views = _extract_image_views(info)
        assert len(views) == 1
        assert views[0]["key"] == "colorTiles"
        assert views[0]["label"] == "Color Tile"
        assert views[0]["url"] == "https://example.com/tile.png"
