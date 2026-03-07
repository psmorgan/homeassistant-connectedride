"""BMW Connected Ride sensor platform."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timezone
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.components.sensor.const import SensorDeviceClass, SensorStateClass
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfLength, UnitOfPressure, UnitOfSpeed, UnitOfTemperature, UnitOfTime, UnitOfVolume
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


def _fuel_tank_capacity_value(vi: dict[str, Any]) -> float | None:
    """Extract fuel tank capacity in liters from vehicle info."""
    return vi.get("fuelCapacity")  # type: ignore[return-value]  # API returns float or None; dict.get type is unknown


def _construction_date_value(vi: dict[str, Any]) -> str | None:
    """Extract construction date (date only) from vehicle info."""
    raw: str | None = vi.get("constructionDate")  # type: ignore[return-value]
    if raw is None:
        return None
    try:
        return datetime.fromisoformat(raw).strftime("%Y-%m-%d")
    except ValueError:
        return raw


VEHICLE_INFO_DESCRIPTIONS: tuple[BMWBikeSensorEntityDescription, ...] = (
    BMWBikeSensorEntityDescription(
        key="fuel_tank_capacity",
        translation_key="fuel_tank_capacity",
        name="Fuel tank capacity",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_fuel_tank_capacity_value,
    ),
    BMWBikeSensorEntityDescription(
        key="construction_date",
        translation_key="construction_date",
        name="Construction date",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_construction_date_value,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BMWConnectedRideConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BMW Connected Ride sensor entities from a config entry."""
    coordinator: BMWConnectedRideCoordinator = entry.runtime_data
    entities: list[BMWBikeSensor | BMWLastRideSensor | BMWVehicleInfoSensor] = []
    for vin in coordinator.data:
        for description in SENSOR_DESCRIPTIONS:
            entities.append(BMWBikeSensor(coordinator, vin, description))
        for description in LAST_RIDE_DESCRIPTIONS:
            entities.append(BMWLastRideSensor(coordinator, vin, description))
        for description in AGGREGATE_DESCRIPTIONS:
            entities.append(BMWLastRideSensor(coordinator, vin, description))
        for description in VEHICLE_INFO_DESCRIPTIONS:
            entities.append(BMWVehicleInfoSensor(coordinator, vin, description))
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


# ---------------------------------------------------------------------------
# Last-ride and aggregate sensor descriptions
# ---------------------------------------------------------------------------


class BMWLastRideSensorEntityDescription(SensorEntityDescription, frozen_or_thawed=True):
    """Describes a sensor derived from recorded tracks data."""

    value_fn: Callable[[list[dict[str, Any]]], object | None] = lambda t: None

    def __init__(  # noqa: PLR0913 - explicit __init__ needed for pyright to see all params
        self,
        *,
        key: str,
        value_fn: Callable[[list[dict[str, Any]]], object | None],
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
        """Initialize BMWLastRideSensorEntityDescription."""
        ...


# -- Last-ride value functions (take tracks list, use index [0]) --


def _last_ride_distance_value(tracks: list[dict[str, Any]]) -> float | None:
    if not tracks:
        return None
    raw = tracks[0].get("rideDistance")
    if raw is None:
        return None
    return round(raw / 1000, 1)  # type: ignore[operator]  # API returns numeric


def _last_ride_duration_value(tracks: list[dict[str, Any]]) -> int | None:
    if not tracks:
        return None
    return tracks[0].get("rideTime")  # type: ignore[return-value]


def _last_ride_avg_speed_value(tracks: list[dict[str, Any]]) -> float | None:
    if not tracks:
        return None
    return tracks[0].get("speedAverageKmh")  # type: ignore[return-value]


  # type: ignore[return-value]


def _last_ride_max_temp_value(tracks: list[dict[str, Any]]) -> float | None:
    if not tracks:
        return None
    return tracks[0].get("temperatureMaxC")  # type: ignore[return-value]


def _last_ride_min_temp_value(tracks: list[dict[str, Any]]) -> float | None:
    if not tracks:
        return None
    return tracks[0].get("temperatureMinC")  # type: ignore[return-value]


def _last_ride_max_elevation_value(tracks: list[dict[str, Any]]) -> float | None:
    if not tracks:
        return None
    return tracks[0].get("elevationMaxM")  # type: ignore[return-value]


def _last_ride_min_elevation_value(tracks: list[dict[str, Any]]) -> float | None:
    if not tracks:
        return None
    return tracks[0].get("elevationMinM")  # type: ignore[return-value]


def _last_ride_lean_angle_left_value(tracks: list[dict[str, Any]]) -> float | None:
    if not tracks:
        return None
    raw = tracks[0].get("leanAngleLeftMax")
    if raw is None:
        return None
    return abs(raw)  # type: ignore[arg-type]  # API returns numeric; can be negative


def _last_ride_lean_angle_right_value(tracks: list[dict[str, Any]]) -> float | None:
    if not tracks:
        return None
    raw = tracks[0].get("leanAngleRightMax")
    if raw is None:
        return None
    return abs(raw)  # type: ignore[arg-type]  # API returns numeric


def _last_ride_max_acceleration_value(tracks: list[dict[str, Any]]) -> float | None:
    if not tracks:
        return None
    return tracks[0].get("accelerationMax")  # type: ignore[return-value]


def _last_ride_max_deceleration_value(tracks: list[dict[str, Any]]) -> float | None:
    if not tracks:
        return None
    return tracks[0].get("decelerationMax")  # type: ignore[return-value]


def _last_ride_start_time_value(tracks: list[dict[str, Any]]) -> datetime | None:
    if not tracks:
        return None
    ts = tracks[0].get("startTimestamp")
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc)  # type: ignore[arg-type]


def _last_ride_engine_max_rpm_value(tracks: list[dict[str, Any]]) -> int | None:
    if not tracks:
        return None
    return tracks[0].get("engineMaxRpm")  # type: ignore[return-value]


LAST_RIDE_DESCRIPTIONS: tuple[BMWLastRideSensorEntityDescription, ...] = (
    BMWLastRideSensorEntityDescription(
        key="last_ride_distance",
        translation_key="last_ride_distance",
        name="Last ride distance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_last_ride_distance_value,
    ),
    BMWLastRideSensorEntityDescription(
        key="last_ride_duration",
        translation_key="last_ride_duration",
        name="Last ride duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_last_ride_duration_value,
    ),
    BMWLastRideSensorEntityDescription(
        key="last_ride_avg_speed",
        translation_key="last_ride_avg_speed",
        name="Last ride avg speed",
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_last_ride_avg_speed_value,
    ),
    BMWLastRideSensorEntityDescription(
        key="last_ride_max_temp",
        translation_key="last_ride_max_temp",
        name="Last ride max temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_last_ride_max_temp_value,
    ),
    BMWLastRideSensorEntityDescription(
        key="last_ride_min_temp",
        translation_key="last_ride_min_temp",
        name="Last ride min temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_last_ride_min_temp_value,
    ),
    BMWLastRideSensorEntityDescription(
        key="last_ride_max_elevation",
        translation_key="last_ride_max_elevation",
        name="Last ride max elevation",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_last_ride_max_elevation_value,
    ),
    BMWLastRideSensorEntityDescription(
        key="last_ride_min_elevation",
        translation_key="last_ride_min_elevation",
        name="Last ride min elevation",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_last_ride_min_elevation_value,
    ),
    BMWLastRideSensorEntityDescription(
        key="last_ride_lean_angle_left",
        translation_key="last_ride_lean_angle_left",
        name="Last ride max lean angle left",
        native_unit_of_measurement="°",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:angle-acute",
        value_fn=_last_ride_lean_angle_left_value,
    ),
    BMWLastRideSensorEntityDescription(
        key="last_ride_lean_angle_right",
        translation_key="last_ride_lean_angle_right",
        name="Last ride max lean angle right",
        native_unit_of_measurement="°",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:angle-acute",
        value_fn=_last_ride_lean_angle_right_value,
    ),
    BMWLastRideSensorEntityDescription(
        key="last_ride_max_acceleration",
        translation_key="last_ride_max_acceleration",
        name="Last ride max acceleration",
        native_unit_of_measurement="g",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        icon="mdi:speedometer",
        value_fn=_last_ride_max_acceleration_value,
    ),
    BMWLastRideSensorEntityDescription(
        key="last_ride_max_deceleration",
        translation_key="last_ride_max_deceleration",
        name="Last ride max deceleration",
        native_unit_of_measurement="g",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        icon="mdi:speedometer-slow",
        value_fn=_last_ride_max_deceleration_value,
    ),
    BMWLastRideSensorEntityDescription(
        key="last_ride_start_time",
        translation_key="last_ride_start_time",
        name="Last ride start time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_last_ride_start_time_value,
    ),
    BMWLastRideSensorEntityDescription(
        key="last_ride_engine_max_rpm",
        translation_key="last_ride_engine_max_rpm",
        name="Last ride engine max RPM",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:engine",
        value_fn=_last_ride_engine_max_rpm_value,
    ),
)


# -- Aggregate value functions (take tracks list, compute across all) --


def _total_ride_count_value(tracks: list[dict[str, Any]]) -> int:
    return len(tracks)


def _total_ride_distance_value(tracks: list[dict[str, Any]]) -> float | None:
    if not tracks:
        return None
    total = sum(t.get("rideDistance") or 0 for t in tracks)
    return round(total / 1000, 1)  # type: ignore[operator]


def _total_ride_duration_value(tracks: list[dict[str, Any]]) -> int | None:
    if not tracks:
        return None
    return sum(t.get("rideTime") or 0 for t in tracks)


def _avg_ride_distance_value(tracks: list[dict[str, Any]]) -> float | None:
    if not tracks:
        return None
    total = sum(t.get("rideDistance") or 0 for t in tracks)
    return round(total / len(tracks) / 1000, 1)  # type: ignore[operator]


def _avg_ride_duration_value(tracks: list[dict[str, Any]]) -> int | None:
    if not tracks:
        return None
    total = sum(t.get("rideTime") or 0 for t in tracks)
    return round(total / len(tracks))


def _longest_ride_value(tracks: list[dict[str, Any]]) -> float | None:
    distances = [t.get("rideDistance") for t in tracks if t.get("rideDistance") is not None]
    if not distances:
        return None
    return round(max(distances) / 1000, 1)  # type: ignore[arg-type, operator]


def _highest_lean_angle_value(tracks: list[dict[str, Any]]) -> float | None:
    angles: list[float] = []
    for t in tracks:
        left = t.get("leanAngleLeftMax")
        right = t.get("leanAngleRightMax")
        if left is not None:
            angles.append(abs(left))  # type: ignore[arg-type]
        if right is not None:
            angles.append(abs(right))  # type: ignore[arg-type]
    if not angles:
        return None
    return max(angles)


AGGREGATE_DESCRIPTIONS: tuple[BMWLastRideSensorEntityDescription, ...] = (
    BMWLastRideSensorEntityDescription(
        key="total_ride_count",
        translation_key="total_ride_count",
        name="Total ride count",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:counter",
        value_fn=_total_ride_count_value,
    ),
    BMWLastRideSensorEntityDescription(
        key="total_ride_distance",
        translation_key="total_ride_distance",
        name="Total ride distance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_total_ride_distance_value,
    ),
    BMWLastRideSensorEntityDescription(
        key="total_ride_duration",
        translation_key="total_ride_duration",
        name="Total ride duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_total_ride_duration_value,
    ),
    BMWLastRideSensorEntityDescription(
        key="avg_ride_distance",
        translation_key="avg_ride_distance",
        name="Average ride distance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_avg_ride_distance_value,
    ),
    BMWLastRideSensorEntityDescription(
        key="avg_ride_duration",
        translation_key="avg_ride_duration",
        name="Average ride duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_avg_ride_duration_value,
    ),
    BMWLastRideSensorEntityDescription(
        key="longest_ride",
        translation_key="longest_ride",
        name="Longest ride",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_longest_ride_value,
    ),
    BMWLastRideSensorEntityDescription(
        key="highest_lean_angle",
        translation_key="highest_lean_angle",
        name="Highest lean angle",
        native_unit_of_measurement="°",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:angle-acute",
        value_fn=_highest_lean_angle_value,
    ),
)


class BMWLastRideSensor(CoordinatorEntity[BMWConnectedRideCoordinator], SensorEntity):
    """Sensor showing data from recorded rides (last ride or aggregate)."""

    _attr_has_entity_name = True
    entity_description: BMWLastRideSensorEntityDescription  # type: ignore[override]  # Narrowing entity_description type for this entity subclass

    def __init__(
        self,
        coordinator: BMWConnectedRideCoordinator,
        vin: str,
        description: BMWLastRideSensorEntityDescription,
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
        """Return the sensor value from coordinator tracks data."""
        tracks = self.coordinator.tracks_data.get(self._vin, [])
        return self.entity_description.value_fn(tracks)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:  # type: ignore[override]  # HA base uses cached_property; runtime behavior is correct
        """Return start/end GPS coordinates on last_ride_distance sensor."""
        if self.entity_description.key != "last_ride_distance":
            return None
        tracks = self.coordinator.tracks_data.get(self._vin, [])
        if not tracks:
            return None
        track = tracks[0]
        attr_map = {
            "startLat": "start_latitude",
            "startLon": "start_longitude",
            "endLat": "end_latitude",
            "endLon": "end_longitude",
        }
        attrs: dict[str, Any] = {}
        for api_key, attr_name in attr_map.items():
            val = track.get(api_key)
            if val is not None:
                attrs[attr_name] = val
        return attrs if attrs else None


class BMWVehicleInfoSensor(CoordinatorEntity[BMWConnectedRideCoordinator], SensorEntity):
    """Sensor from vehicle info (static data fetched once at startup)."""

    _attr_has_entity_name = True
    entity_description: BMWBikeSensorEntityDescription  # type: ignore[override]  # Narrowing entity_description type for this entity subclass

    def __init__(
        self,
        coordinator: BMWConnectedRideCoordinator,
        vin: str,
        description: BMWBikeSensorEntityDescription,
    ) -> None:
        """Initialize the vehicle info sensor."""
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
        """Return the sensor value from coordinator vehicle info data."""
        vi = self.coordinator.vehicle_info.get(self._vin)
        if vi is None:
            return None
        return self.entity_description.value_fn(vi)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:  # type: ignore[override]  # HA base uses cached_property; runtime behavior is correct
        """Return capability flags on construction_date sensor."""
        if self.entity_description.key != "construction_date":
            return None
        vi = self.coordinator.vehicle_info.get(self._vin, {})
        attrs: dict[str, Any] = {}
        for api_key, attr_name in (
            ("hasSensorBox", "has_sensor_box"),
            ("isElectricVehicle", "is_electric_vehicle"),
            ("hasV2bCapability", "has_v2b_capability"),
        ):
            val = vi.get(api_key)
            if val is not None:
                attrs[attr_name] = val
        return attrs if attrs else None
