from typing import Callable, Optional

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime, UnitOfTemperature, UnitOfVolumeFlowRate, EntityCategory

from .const import DOMAIN
from .entity import WanasEntity
from .coordinator import WanasCoordinator
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
