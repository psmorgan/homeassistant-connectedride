"""BMW Connected Ride sensor platform."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timezone
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.components.sensor.const import SensorDeviceClass, SensorStateClass
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfLength, UnitOfPressure, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import UNDEFINED, UndefinedType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BMWConnectedRideConfigEntry
from .const import DOMAIN
from .coordinator import BMWConnectedRideCoordinator


class BMWBikeSensorEntityDescription(SensorEntityDescription, frozen_or_thawed=True):
    """Describes a BMW bike sensor entity."""

    value_fn: Callable[[dict[str, Any]], object | None] = lambda b: None

    def __init__(  # noqa: PLR0913 - explicit __init__ needed for pyright to see all params
        self,
        *,
        key: str,
        value_fn: Callable[[dict[str, Any]], object | None],
        device_class: SensorDeviceClass | None = None,
        entity_category: EntityCategory | None = None,
        entity_registry_enabled_default: bool = True,
        entity_registry_visible_default: bool = True,
        force_update: bool = False,
        icon: str | None = None,
        has_entity_name: bool = False,
        name: str | UndefinedType | None = UNDEFINED,
        translation_key: str | None = None,
        native_unit_of_measurement: str | None = None,
        state_class: SensorStateClass | str | None = None,
        suggested_display_precision: int | None = None,
    ) -> None:
        """Initialize BMWBikeSensorEntityDescription.

        Explicit __init__ is required because pyright cannot infer the combined
        __init__ signature from the FrozenOrThawed metaclass and our extra field.
        """
        ...


def _fuel_level_value(bike: dict[str, Any]) -> int | None:
    """Extract fuel level percentage -- no conversion needed."""
    return bike.get("fuelLevel")  # type: ignore[return-value]  # API returns int or None; dict.get type is unknown


def _remaining_range_value(bike: dict[str, Any]) -> float | None:
    """Convert remaining range from meters to kilometres."""
    raw = bike.get("remainingRange")
    if raw is None:
        return None
    return round(raw / 1000, 1)  # type: ignore[operator]  # API returns numeric; dict.get type is unknown


def _last_sync_value(bike: dict[str, Any]) -> datetime | None:
    """Convert epoch seconds to timezone-aware UTC datetime."""
    ts = bike.get("lastConnectedTime")
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc)  # type: ignore[arg-type]  # API returns numeric; dict.get type is unknown


def _energy_level_value(bike: dict[str, Any]) -> int | None:
    """Extract energy level (battery percentage) -- no conversion needed."""
    return bike.get("energyLevel")  # type: ignore[return-value]  # API returns int or None; dict.get type is unknown


def _electric_range_value(bike: dict[str, Any]) -> float | None:
    """Convert electric remaining range from meters to kilometres."""
    raw = bike.get("remainingRangeElectric")
    if raw is None:
        return None
    return round(raw / 1000, 1)  # type: ignore[operator]  # API returns numeric; dict.get type is unknown


def _front_tire_pressure_value(bike: dict[str, Any]) -> float | None:
    """Extract front tire pressure in bar -- no conversion needed."""
    return bike.get("tirePressureFront")  # type: ignore[return-value]  # API returns float or None; dict.get type is unknown


def _rear_tire_pressure_value(bike: dict[str, Any]) -> float | None:
    """Extract rear tire pressure in bar -- no conversion needed."""
    return bike.get("tirePressureRear")  # type: ignore[return-value]  # API returns float or None; dict.get type is unknown


def _mileage_value(bike: dict[str, Any]) -> float | None:
    """Convert total mileage from meters to kilometres."""
    raw = bike.get("totalMileage")
    if raw is None:
        return None
    return round(raw / 1000, 1)  # type: ignore[operator]  # API returns numeric; dict.get type is unknown


def _trip_distance_value(bike: dict[str, Any]) -> float | None:
    """Convert trip distance from meters to kilometres."""
    raw = bike.get("trip1")
    if raw is None:
        return None
    return round(raw / 1000, 1)  # type: ignore[operator]  # API returns numeric; dict.get type is unknown


def _next_service_date_value(bike: dict[str, Any]) -> date | None:
    """Convert next service due date from epoch seconds to date."""
    ts = bike.get("nextServiceDueDate")
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).date()  # type: ignore[arg-type]  # API returns numeric; dict.get type is unknown


def _next_service_distance_value(bike: dict[str, Any]) -> float | None:
    """Convert next service remaining distance from meters to kilometres."""
    raw = bike.get("nextServiceRemainingDistance")
    if raw is None:
        return None
    return round(raw / 1000, 1)  # type: ignore[operator]  # API returns numeric; dict.get type is unknown


def _last_activated_value(bike: dict[str, Any]) -> datetime | None:
    """Convert lastActivatedTime epoch seconds to UTC datetime."""
    ts = bike.get("lastActivatedTime")
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc)  # type: ignore[arg-type]  # API returns numeric; dict.get type is unknown


def _total_connected_distance_value(bike: dict[str, Any]) -> float | None:
    """Convert totalConnectedDistance from meters to kilometres."""
    raw = bike.get("totalConnectedDistance")
    if raw is None:
        return None
    return round(raw / 1000, 1)  # type: ignore[operator]  # API returns numeric; dict.get type is unknown


def _total_connected_duration_value(bike: dict[str, Any]) -> float | None:
    """Return totalConnectedDuration in seconds (no conversion needed)."""
    return bike.get("totalConnectedDuration")  # type: ignore[return-value]  # API returns float or None; dict.get type is unknown


def _charging_mode_value(bike: dict[str, Any]) -> str | None:
    """Return chargingMode as plain text string."""
    return bike.get("chargingMode")  # type: ignore[return-value]  # API returns str or None; dict.get type is unknown


def _charging_time_estimation_value(bike: dict[str, Any]) -> int | None:
    """Return chargingTimeEstimationElectric (unit assumed seconds)."""
    return bike.get("chargingTimeEstimationElectric")  # type: ignore[return-value]  # API returns int or None; dict.get type is unknown


SENSOR_DESCRIPTIONS: tuple[BMWBikeSensorEntityDescription, ...] = (
    BMWBikeSensorEntityDescription(
        key="fuel_level",
        translation_key="fuel_level",
        name="Fuel level",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_fuel_level_value,
    ),
    BMWBikeSensorEntityDescription(
        key="remaining_range",
        translation_key="remaining_range",
        name="Remaining range",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_remaining_range_value,
    ),
    BMWBikeSensorEntityDescription(
        key="last_sync",
        translation_key="last_sync",
        name="Last sync",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_last_sync_value,
    ),
    BMWBikeSensorEntityDescription(
        key="energy_level",
        translation_key="energy_level",
        name="Energy level",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=_energy_level_value,
    ),
    BMWBikeSensorEntityDescription(
        key="electric_range",
        translation_key="electric_range",
        name="Electric range",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=_electric_range_value,
    ),
    BMWBikeSensorEntityDescription(
        key="front_tire_pressure",
        translation_key="front_tire_pressure",
        name="Front tire pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.BAR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_front_tire_pressure_value,
    ),
    BMWBikeSensorEntityDescription(
        key="rear_tire_pressure",
        translation_key="rear_tire_pressure",
        name="Rear tire pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.BAR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_rear_tire_pressure_value,
    ),
    BMWBikeSensorEntityDescription(
        key="mileage",
        translation_key="mileage",
        name="Mileage",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        value_fn=_mileage_value,
    ),
    BMWBikeSensorEntityDescription(
        key="trip_distance",
        translation_key="trip_distance",
        name="Trip distance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_trip_distance_value,
    ),
    BMWBikeSensorEntityDescription(
        key="next_service_date",
        translation_key="next_service_date",
        name="Next service date",
        device_class=SensorDeviceClass.DATE,
        value_fn=_next_service_date_value,
    ),
    BMWBikeSensorEntityDescription(
        key="next_service_distance",
        translation_key="next_service_distance",
        name="Next service distance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        suggested_display_precision=1,
        value_fn=_next_service_distance_value,
    ),
    BMWBikeSensorEntityDescription(
        key="last_activated",
        translation_key="last_activated",
        name="Last activated",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_last_activated_value,
    ),
    BMWBikeSensorEntityDescription(
        key="total_connected_distance",
        translation_key="total_connected_distance",
        name="Total connected distance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        value_fn=_total_connected_distance_value,
    ),
    BMWBikeSensorEntityDescription(
        key="total_connected_duration",
        translation_key="total_connected_duration",
        name="Total connected duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_total_connected_duration_value,
    ),
    BMWBikeSensorEntityDescription(
        key="charging_mode",
        translation_key="charging_mode",
        name="Charging mode",
        entity_registry_enabled_default=False,
        value_fn=_charging_mode_value,
    ),
    BMWBikeSensorEntityDescription(
        key="charging_time_estimation",
        translation_key="charging_time_estimation",
        name="Charging time estimation",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_registry_enabled_default=False,
        value_fn=_charging_time_estimation_value,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BMWConnectedRideConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BMW Connected Ride sensor entities from a config entry."""
    coordinator: BMWConnectedRideCoordinator = entry.runtime_data
    entities: list[BMWBikeSensor] = []
    for vin in coordinator.data:
        for description in SENSOR_DESCRIPTIONS:
            entities.append(BMWBikeSensor(coordinator, vin, description))
    async_add_entities(entities)


class BMWBikeSensor(CoordinatorEntity[BMWConnectedRideCoordinator], SensorEntity):
    """A sensor entity for one metric of one BMW bike."""

    _attr_has_entity_name = True
    entity_description: BMWBikeSensorEntityDescription  # type: ignore[override]  # Narrowing entity_description type for this entity subclass

    def __init__(
        self,
        coordinator: BMWConnectedRideCoordinator,
        vin: str,
        description: BMWBikeSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description  # type: ignore[override]  # Narrowing entity_description to subclass type; standard HA pattern
        self._attr_translation_key = description.translation_key
        self._vin = vin
        self._attr_unique_id = f"{vin}_{description.key}"
        bike = coordinator.data[vin]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, vin)},
            name=bike.get("name") or vin,
            manufacturer="BMW Motorrad",
        )

    @property
    def native_value(self) -> object | None:  # type: ignore[override]  # HA base uses cached_property; runtime behavior is correct
        """Return the sensor value from coordinator data."""
        bike = self.coordinator.data.get(self._vin)
        if bike is None:
            return None
        return self.entity_description.value_fn(bike)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:  # type: ignore[override]  # HA base uses cached_property; runtime behavior is correct
        """Return extra state attributes -- absType on mileage sensor."""
        if self.entity_description.key != "mileage":
            return None
        bike = self.coordinator.data.get(self._vin)
        if bike is None:
            return None
        abs_type = bike.get("absType")
        if abs_type is None:
            return None
        return {"abs_type": abs_type}
