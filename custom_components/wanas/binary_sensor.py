from typing import Callable, Optional

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.const import EntityCategory

from .const import DOMAIN
from .entity import WanasEntity
from .coordinator import WanasCoordinator
from .model_v2 import (
    BINARY_TYPES,
    CONNECTION_BINARY_TYPES,
    ERROR_BINARY_BIT_TYPES,
    SERVICE_MENU_BINARY_BIT_TYPES,
)


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: WanasCoordinator = data["coordinator"]

    entities = [
        WanasBinarySensor(coordinator, key, icon_lambda)
        for key, icon_lambda in BINARY_TYPES
    ]
    entities += [
        WanasConnectionStatusSensor(coordinator, key, icon_lambda)
        for key, icon_lambda in CONNECTION_BINARY_TYPES
    ]

    entities += [
        WanasErrorSensor(coordinator, key, bit, data_key, unit, icon_lambda)
        for key, bit, data_key, unit, icon_lambda in ERROR_BINARY_BIT_TYPES
    ]
    entities += [
        WanasServiceMenuSensor(coordinator, key, bit, data_key, unit, icon_lambda)
        for key, bit, data_key, unit, icon_lambda in SERVICE_MENU_BINARY_BIT_TYPES
    ]

    async_add_entities(entities)


class WanasBinarySensor(WanasEntity, BinarySensorEntity):
    def __init__(
        self,
        coordinator: WanasCoordinator,
        key: str,
        icon_lambda: Optional[Callable[[bool | None], str]],
    ):
        super().__init__(coordinator, key)
        self._icon_lambda = icon_lambda

    @property
    def is_on(self) -> bool | None:
        val = super().native_value
        return bool(val) if val is not None else None

    @property
    def icon(self) -> str | None:
        return self._icon_lambda(self.is_on)


class WanasConnectionStatusSensor(WanasEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(
        self,
        coordinator: WanasCoordinator,
        key: str,
        icon_lambda: Optional[Callable[[bool | None], str]],
    ):
        super().__init__(coordinator, key)
        self._icon_lambda = icon_lambda

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.connection.connected

    @property
    def icon(self) -> str | None:
        return self._icon_lambda(self.is_on)

    @property
    def extra_state_attributes(self):
        connection = self.coordinator.connection
        return {
            (
                "connected to:" f"{connection.host}:{connection.port}"
                if connection.connected
                else "" "status"
            ): connection.status,
            "last_error": connection.last_error,
            "reconnect_attempts": connection.reconnect_attempts,
        }

    @property
    def available(self) -> bool:
        return True  # Always show status


class WanasErrorSensor(WanasEntity, BinarySensorEntity):
    def __init__(
        self,
        coordinator,
        key: str,
        bit: int,
        data_key: str,
        unit,
        icon_lambda: Optional[Callable[[bool | None], str]],
    ):
        super().__init__(coordinator, key, data_key)
        self._attr_native_unit_of_measurement = unit
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_entity_registry_visible_default = False
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM
        self._icon_lambda = icon_lambda
        self._bit = bit

    @property
    def is_on(self) -> bool | None:
        """Return True if the monitored bit is set."""
        val = super().native_value
        return bool(val & (1 << self._bit)) if val is not None else None

    @property
    def icon(self) -> str | None:
        return self._icon_lambda(self.is_on)


class WanasServiceMenuSensor(WanasEntity, BinarySensorEntity):
    def __init__(
        self,
        coordinator,
        key: str,
        bit: int,
        data_key: str,
        unit,
        icon_lambda: Optional[Callable[[bool | None], str]],
    ):
        super().__init__(coordinator, key, data_key)
        self._attr_native_unit_of_measurement = unit
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_entity_registry_visible_default = False
        self._icon_lambda = icon_lambda
        self._bit = bit

    @property
    def is_on(self) -> bool | None:
        """Return True if the monitored bit is set."""
        val = super().native_value
        return bool(val & (1 << self._bit)) if val is not None else None

    @property
    def icon(self) -> str | None:
        return self._icon_lambda(self.is_on)
