"""Tests for the BMW Connected Ride image platform."""

import collections
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from custom_components.bmw_connected_ride.image import (
    async_setup_entry,
    BMWBikeImage,
)
from custom_components.bmw_connected_ride.const import DOMAIN

TEST_VIN = "WB10A0100P1234567"
TEST_BIKE = {"name": "My R1250GS", "vin": TEST_VIN}


def _make_coordinator(bikes=None, vehicle_info=None):
    """Create a mock coordinator with bike data and vehicle info."""
    coordinator = MagicMock()
    coordinator.data = bikes or {TEST_VIN: TEST_BIKE}
    coordinator.vehicle_info = vehicle_info or {}
    coordinator.hass = MagicMock()
    return coordinator


@pytest.fixture(autouse=True)
def patch_get_async_client():
    """Patch get_async_client so ImageEntity.__init__ does not need a real HA instance."""
    with patch("homeassistant.components.image.get_async_client", return_value=MagicMock()):
        yield


class TestBMWBikeImage:
    """Tests for BMWBikeImage entity."""

    def test_entity_attributes_from_side_view(self):
        """Entity has correct unique_id, name, and image_url from side view."""
        coordinator = _make_coordinator()
        view = {"key": "sideViews", "label": "Side View", "url": "https://example.com/side.png"}
        entity = BMWBikeImage(coordinator, TEST_VIN, view)
        assert entity.unique_id == f"{TEST_VIN}_image_sideViews"
        assert entity.name == "Side View"
        assert entity.image_url == "https://example.com/side.png"
        assert entity.content_type == "image/png"

    def test_entity_attributes_from_rider_view(self):
        """Entity has correct unique_id and name from rider view."""
        coordinator = _make_coordinator()
        view = {"key": "riderViews", "label": "Rider View", "url": "https://example.com/rider.png"}
        entity = BMWBikeImage(coordinator, TEST_VIN, view)
        assert entity.unique_id == f"{TEST_VIN}_image_riderViews"
        assert entity.name == "Rider View"
        assert entity.image_url == "https://example.com/rider.png"

    def test_entity_linked_to_device(self):
        """Entity is linked to the correct HA device via DeviceInfo."""
        coordinator = _make_coordinator()
        view = {"key": "sideViews", "label": "Side View", "url": "https://example.com/side.png"}
        entity = BMWBikeImage(coordinator, TEST_VIN, view)
        assert entity.device_info["identifiers"] == {(DOMAIN, TEST_VIN)}
        assert entity.device_info["name"] == "My R1250GS"
        assert entity.device_info["manufacturer"] == "BMW Motorrad"

    def test_image_last_updated_is_set(self):
        """image_last_updated is set (not None) so HA will download the image."""
        coordinator = _make_coordinator()
        view = {"key": "sideViews", "label": "Side View", "url": "https://example.com/side.png"}
        entity = BMWBikeImage(coordinator, TEST_VIN, view)
        assert entity.image_last_updated is not None
        assert isinstance(entity.image_last_updated, datetime)

    def test_has_entity_name_true(self):
        """has_entity_name is True so HA prepends device name."""
        coordinator = _make_coordinator()
        view = {"key": "sideViews", "label": "Side View", "url": "https://example.com/side.png"}
        entity = BMWBikeImage(coordinator, TEST_VIN, view)
        assert entity.has_entity_name is True

    def test_device_name_fallback_to_vin(self):
        """Device name falls back to VIN when bike has no name."""
        coordinator = _make_coordinator(bikes={TEST_VIN: {"vin": TEST_VIN}})
        view = {"key": "sideViews", "label": "Side View", "url": "https://example.com/side.png"}
        entity = BMWBikeImage(coordinator, TEST_VIN, view)
        assert entity.device_info["name"] == TEST_VIN

    def test_indexed_view_key(self):
        """Multiple views of same type get indexed unique_ids."""
        coordinator = _make_coordinator()
        view = {"key": "sideViews_0", "label": "Side View 1", "url": "https://example.com/side1.png"}
        entity = BMWBikeImage(coordinator, TEST_VIN, view)
        assert entity.unique_id == f"{TEST_VIN}_image_sideViews_0"
        assert entity.name == "Side View 1"

    def test_has_access_tokens_attribute(self):
        """BMWBikeImage has access_tokens attribute (deque) — regression for MRO gap."""
        coordinator = _make_coordinator()
        view = {"key": "sideViews", "label": "Side View", "url": "https://example.com/side.png"}
        entity = BMWBikeImage(coordinator, TEST_VIN, view)
        assert hasattr(entity, "access_tokens"), "access_tokens attribute missing — ImageEntity.__init__ not called"
        assert isinstance(entity.access_tokens, collections.deque)

    def test_has_http_client_attribute(self):
        """BMWBikeImage has _client attribute — regression for MRO gap."""
        coordinator = _make_coordinator()
        view = {"key": "sideViews", "label": "Side View", "url": "https://example.com/side.png"}
        entity = BMWBikeImage(coordinator, TEST_VIN, view)
        assert hasattr(entity, "_client"), "_client attribute missing — ImageEntity.__init__ not called"


class TestImagePlatformSetup:
    """Tests for async_setup_entry in image platform."""

    @pytest.mark.asyncio
    async def test_creates_entities_from_vehicle_info(self):
        """Creates one entity per image view from vehicle info."""
        vehicle_info = {
            TEST_VIN: {
                "images": {
                    "sideViews": [{"url": "https://example.com/side.png"}],
                    "riderViews": [{"url": "https://example.com/rider.png"}],
                }
            }
        }
        coordinator = _make_coordinator(vehicle_info=vehicle_info)
        entry = MagicMock()
        entry.runtime_data = coordinator
        added_entities = []
        async_add_entities = lambda entities: added_entities.extend(entities)
        await async_setup_entry(None, entry, async_add_entities)
        assert len(added_entities) == 2
        keys = {e.unique_id for e in added_entities}
        assert f"{TEST_VIN}_image_sideViews" in keys
        assert f"{TEST_VIN}_image_riderViews" in keys

    @pytest.mark.asyncio
    async def test_no_entities_when_vehicle_info_empty(self):
        """No image entities created when vehicle info is empty dict."""
        coordinator = _make_coordinator(vehicle_info={TEST_VIN: {}})
        entry = MagicMock()
        entry.runtime_data = coordinator
        added_entities = []
        async_add_entities = lambda entities: added_entities.extend(entities)
        await async_setup_entry(None, entry, async_add_entities)
        assert len(added_entities) == 0

    @pytest.mark.asyncio
    async def test_no_entities_when_vehicle_info_missing_vin(self):
        """No image entities when VIN has no vehicle info entry (403 case)."""
        coordinator = _make_coordinator(vehicle_info={})
        entry = MagicMock()
        entry.runtime_data = coordinator
        added_entities = []
        async_add_entities = lambda entities: added_entities.extend(entities)
        await async_setup_entry(None, entry, async_add_entities)
        assert len(added_entities) == 0

    @pytest.mark.asyncio
    async def test_multiple_bikes_get_separate_entities(self):
        """Each bike gets its own set of image entities."""
        vin2 = "WB10B0200Q9876543"
        bikes = {
            TEST_VIN: {"name": "Bike 1", "vin": TEST_VIN},
            vin2: {"name": "Bike 2", "vin": vin2},
        }
        vehicle_info = {
            TEST_VIN: {"images": {"sideViews": [{"url": "https://example.com/bike1_side.png"}]}},
            vin2: {"images": {"sideViews": [{"url": "https://example.com/bike2_side.png"}]}},
        }
        coordinator = _make_coordinator(bikes=bikes, vehicle_info=vehicle_info)
        entry = MagicMock()
        entry.runtime_data = coordinator
        added_entities = []
        async_add_entities = lambda entities: added_entities.extend(entities)
        await async_setup_entry(None, entry, async_add_entities)
        assert len(added_entities) == 2
        vins = {e._vin for e in added_entities}
        assert vins == {TEST_VIN, vin2}

    @pytest.mark.asyncio
    async def test_bike_with_403_gets_no_entities_others_unaffected(self):
        """One bike's 403 (empty vehicle_info) doesn't block other bikes' image entities."""
        vin2 = "WB10B0200Q9876543"
        bikes = {
            TEST_VIN: {"name": "Bike 1", "vin": TEST_VIN},
            vin2: {"name": "Bike 2", "vin": vin2},
        }
        vehicle_info = {
            TEST_VIN: {},  # 403 -> empty dict
            vin2: {"images": {"sideViews": [{"url": "https://example.com/side.png"}]}},
        }
        coordinator = _make_coordinator(bikes=bikes, vehicle_info=vehicle_info)
        entry = MagicMock()
        entry.runtime_data = coordinator
        added_entities = []
        async_add_entities = lambda entities: added_entities.extend(entities)
        await async_setup_entry(None, entry, async_add_entities)
        assert len(added_entities) == 1
        assert added_entities[0]._vin == vin2
