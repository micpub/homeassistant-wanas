from typing import Callable, Optional
from datetime import time

from homeassistant.components.time import TimeEntity

from .const import DOMAIN
from .entity import WanasEntity
from .coordinator import WanasCoordinator
from .model_v2 import TIME_TYPES


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: WanasCoordinator = data["coordinator"]

    entities = [
        WanasTime(coordinator, key, icon_lambda)
        for key, icon_lambda in TIME_TYPES
    ]
    async_add_entities(entities)


class WanasTime(WanasEntity, TimeEntity):
    def __init__(
        self,
        coordinator,
        key: str,
        icon_lambda: Optional[Callable[[time | None], str]],
    ):
        super().__init__(coordinator, key)
        self._icon_lambda = icon_lambda

    @property
    def icon(self) -> str | None:
        val = super().native_value
        return self._icon_lambda(None if val is None else val)

    @property
    def native_value(self) -> time | None:
        return super().native_value

    async def async_set_value(self, value: time) -> None:
        await self.coordinator.async_write_register(self._key, value)
        await self.coordinator.async_refresh()
