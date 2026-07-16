from typing import Callable, Optional

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime, UnitOfTemperature, UnitOfVolumeFlowRate

from .const import DOMAIN
from .entity import WanasEntity
from .coordinator import WanasCoordinator
from .model_v2 import (
    SENSOR_TYPES,
    FILTER_SENSOR_TYPES,
)


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: WanasCoordinator = data["coordinator"]

    entities = [
        WanasSensor(coordinator, key, unit, device_class, icon_lambda)
        for key, unit, device_class, icon_lambda in SENSOR_TYPES
    ]
    entities += [
        WanasFilterSensor(
            coordinator, key, unit, device_class, state_class, icon_lambda
        )
        for key, unit, device_class, state_class, icon_lambda in FILTER_SENSOR_TYPES
    ]

    async_add_entities(entities)


class WanasSensor(WanasEntity, SensorEntity):
    def __init__(
        self,
        coordinator,
        key: str,
        unit,
        device_class,
        icon_lambda: Optional[Callable[[str | int | float | None], str]],
    ):
        super().__init__(coordinator, key)
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
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
