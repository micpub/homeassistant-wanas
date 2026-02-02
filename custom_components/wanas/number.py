from typing import Callable, Optional

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import UnitOfTemperature

from .const import DOMAIN
from .entity import WanasEntity
from .coordinator import WanasCoordinator
from .register import Register
from .model_v2 import NUMBER_TYPES, REGISTERS_BY_KEY


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: WanasCoordinator = data["coordinator"]

    entities = [
        WanasNumber(coordinator, key, mode, unit, icon_lambda)
        for key, mode, unit, icon_lambda in NUMBER_TYPES
    ]
    async_add_entities(entities)


class WanasNumber(WanasEntity, NumberEntity):
    def __init__(
        self,
        coordinator: WanasCoordinator,
        key: str,
        mode,
        unit,
        icon_lambda: Optional[Callable[[int | float | None], str]],
    ):
        super().__init__(coordinator, key)
        self._attr_native_unit_of_measurement = unit
        self._attr_mode = mode
        register_info = REGISTERS_BY_KEY[key]
        self._attr_native_min_value = register_info.min
        self._attr_native_max_value = register_info.max
        self._attr_native_step = register_info.write_value_step
        self._icon_lambda = icon_lambda

    @property
    def native_value(self) -> float | int | None:
        return super().native_value

    @property
    def icon(self) -> str | None:
        val = super().native_value
        return self._icon_lambda(None if val is None else val)

    async def async_set_native_value(self, value: float) -> None:
        """Write value to device."""
        await self.coordinator.async_write_register(self._key, value)
        await self.coordinator.async_refresh()
