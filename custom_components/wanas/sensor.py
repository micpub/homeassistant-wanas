from datetime import datetime
from typing import Callable, Optional

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import callback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .entity import WanasEntity
from .coordinator import WanasCoordinator
from .recovery import Recovery, compute
from .model_v2 import (
    SENSOR_TYPES,
    FILTER_SENSOR_TYPES,
    DIAGNOSTIC_SENSOR_TYPES,
)


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: WanasCoordinator = data["coordinator"]

    entities = [
        WanasSensor(coordinator, key, unit, device_class, state_class, icon_lambda)
        for key, unit, device_class, state_class, icon_lambda in SENSOR_TYPES
    ]
    entities += [
        WanasFilterSensor(
            coordinator, key, unit, device_class, state_class, icon_lambda
        )
        for key, unit, device_class, state_class, icon_lambda in FILTER_SENSOR_TYPES
    ]
    entities += [
        WanasDiagnosticSensor(coordinator, key, unit, device_class, state_class, icon_lambda)
        for key, unit, device_class, state_class, icon_lambda in DIAGNOSTIC_SENSOR_TYPES
    ]
    entities += [
        WanasWeeklyScheduleSensor(
            coordinator, "weekly_schedule", None, None, None,
            lambda x: "mdi:calendar-week",)
    ]
    entities += [
        WanasRecoveryPowerSensor(coordinator),
        WanasRecoveryEfficiencySensor(coordinator),
        WanasRecoveredEnergySensor(coordinator),
    ]

    async_add_entities(entities)


class WanasSensor(WanasEntity, SensorEntity):
    def __init__(
        self,
        coordinator,
        key: str,
        unit,
        device_class,
        state_class,
        icon_lambda: Optional[Callable[[str | int | float | None], str]],
    ):
        super().__init__(coordinator, key)
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._icon_lambda = icon_lambda

    @property
    def native_value(self):
        return super().native_value

    @property
    def icon(self) -> str | None:
        val = super().native_value
        return self._icon_lambda(None if val is None else val)


class WanasFilterSensor(WanasEntity, SensorEntity):
    def __init__(
        self,
        coordinator: WanasCoordinator,
        key: str,
        unit,
        device_class,
        state_class,
        icon_lambda: Optional[Callable[[str | int | float | None], str]],
    ):
        super().__init__(coordinator, key)
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._icon_lambda = icon_lambda

    @property
    def native_value(self) -> int | None:
        return super().native_value

    @property
    def icon(self) -> str | None:
        val = super().native_value
        return self._icon_lambda(None if val is None else val)

    @property
    def extra_state_attributes(self):
        """Add warning level and message."""
        value = self.native_value
        if value is None:
            return {}

        attrs = {}
        if value == 0:
            attrs["warning_level"] = "urgent"
            attrs["status"] = "Replace filter now!"
            attrs["severity"] = "critical"
        elif value <= 7:
            attrs["warning_level"] = "low"
            attrs["status"] = f"Only {value} day(s) left"
            attrs["severity"] = "warning"
        elif value <= 14:
            attrs["warning_level"] = "medium"
            attrs["status"] = f"{value} days remaining"
            attrs["severity"] = "info"
        else:
            attrs["warning_level"] = "ok"
            attrs["status"] = "Filter OK"
            attrs["severity"] = "normal"

        return attrs


class WanasDiagnosticSensor(WanasEntity, SensorEntity):
    def __init__(
        self,
        coordinator,
        key: str,
        unit,
        device_class,
        state_class,
        icon_lambda: Optional[Callable[[str | int | float | None], str]],
    ):
        super().__init__(coordinator, key)
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_entity_registry_visible_default = False
        self._icon_lambda = icon_lambda

    @property
    def native_value(self):
        return super().native_value

    @property
    def icon(self) -> str | None:
        val = super().native_value
        return self._icon_lambda(None if val is None else val)


class WanasWeeklyScheduleSensor(WanasEntity, SensorEntity):
    def __init__(
        self,
        coordinator: WanasCoordinator,
        key: str,
        unit,
        device_class,
        state_class,
        icon_lambda: Optional[Callable[[str | int | float | None], str]],
    ):
        super().__init__(coordinator, key)
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_entity_registry_visible_default = False
        self._icon_lambda = icon_lambda

    @property
    def native_value(self) -> str | None:
        return (
            "attributes"
            if self.coordinator.data is not None
            and self.coordinator.data.weekly_schedule is not None
            else None
        )

    @property
    def icon(self) -> str | None:
        val = super().native_value
        return self._icon_lambda(None if val is None else val)

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data
        if not data or not data.weekly_schedule:
            return {}

        # day / zone_id may end up as str - watch out when reading back
        return {
            day: {
                zone_id: {
                    "start": zone.start.strftime("%H:%M") if zone.start else None,
                    "speed": zone.speed,
                    "comfort_temp": zone.comfort_temp,
                }
                for zone_id, zone in day_zones.items()
            }
            for day, day_zones in data.weekly_schedule.items()
        }


# With any of these running, the supply temperature is no longer the exchanger's doing.
RECOVERY_BLOCKERS = ("summer_bypass", "heater", "cooler", "ghe")


def current_recovery(coordinator: WanasCoordinator) -> Recovery | None:
    """Recovery from the last poll, or None when it is unknown or not happening."""
    data = coordinator.data
    if data is None:
        return None
    for key in RECOVERY_BLOCKERS:
        state = getattr(data, key, None)
        if state is None or state:
            return None
    return compute(
        outdoor=data.outdoor_temp,
        supply=data.supply_temp,
        indoor=data.extract_temp,
        supply_airflow=data.supply_airflow,
        exhaust=data.exhaust_temp,
        exhaust_airflow=data.extract_airflow,
    )


class WanasRecoveryPowerSensor(WanasEntity, SensorEntity):
    """Heat (or, in summer, cooling) the exchanger hands to the supply air, in W.

    Unknown with the bypass open or a heater, cooler or ground heat exchanger running.
    """

    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_icon = "mdi:heat-wave"

    def __init__(self, coordinator: WanasCoordinator):
        super().__init__(coordinator, "heat_recovery_power")

    @property
    def native_value(self) -> float | None:
        recovery = current_recovery(self.coordinator)
        return recovery.power if recovery else None

    @property
    def extra_state_attributes(self):
        recovery = current_recovery(self.coordinator)
        if not recovery:
            return {}
        return {
            "mode": recovery.mode,
            "temperature_gain": recovery.delta,
            "extract_side_power": recovery.extract_power,
        }


class WanasRecoveryEfficiencySensor(WanasEntity, SensorEntity):
    """Supply-side temperature ratio, (supply - outdoor) / (indoor - outdoor), in %."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = "mdi:percent-circle"

    def __init__(self, coordinator: WanasCoordinator):
        super().__init__(coordinator, "heat_recovery_efficiency")

    @property
    def native_value(self) -> float | None:
        recovery = current_recovery(self.coordinator)
        return recovery.efficiency if recovery else None


class WanasRecoveredEnergySensor(WanasEntity, RestoreSensor):
    """Recovered power integrated over time, in kWh, for statistics and the Energy dashboard.

    Integrated on every poll with the trapezoid rule. A gap longer than MAX_GAP (Home
    Assistant stopped, the unit unreachable) is skipped rather than bridged, and while
    recovery is not happening nothing is added.
    """

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:home-thermometer"

    MAX_GAP = 600  # s

    def __init__(self, coordinator: WanasCoordinator):
        super().__init__(coordinator, "heat_recovery_energy")
        self._total = 0.0
        self._last: tuple[datetime, float] | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        restored = await self.async_get_last_sensor_data()
        if restored is not None and isinstance(restored.native_value, (int, float)):
            self._total = float(restored.native_value)

    @callback
    def _handle_coordinator_update(self) -> None:
        recovery = (
            current_recovery(self.coordinator)
            if self.coordinator.last_update_success
            else None
        )
        now = dt_util.utcnow()
        if recovery is None:
            self._last = None
        else:
            if self._last is not None:
                since, power = self._last
                seconds = (now - since).total_seconds()
                if 0 < seconds <= self.MAX_GAP:
                    self._total += (power + recovery.power) / 2 * seconds / 3_600_000
            self._last = (now, recovery.power)
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> float:
        return round(self._total, 3)
