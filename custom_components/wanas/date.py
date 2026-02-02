from typing import Callable, Optional
from datetime import date

from homeassistant.components.date import DateEntity
from .const import DOMAIN
from .entity import WanasEntity
from .coordinator import WanasCoordinator
from .model_v2 import DATE_TYPES


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: WanasCoordinator = data["coordinator"]

    entities = [
        WanasDate(coordinator, key, icon_lambda)
        for key, icon_lambda in DATE_TYPES
    ]
    async_add_entities(entities)


class WanasDate(WanasEntity, DateEntity):
    def __init__(
        self,
        coordinator,
        key: str,
        icon_lambda: Optional[Callable[[date | None], str]],
    ):
        super().__init__(coordinator, key)
        self._icon_lambda = icon_lambda

    @property
    def icon(self) -> str | None:
        val = super().native_value
        return self._icon_lambda(None if val is None else val)

    @property
    def native_value(self) -> date | None:
        return super().native_value

    async def async_set_value(self, value: date) -> None:
        await self.coordinator.async_write_register(self._key, value)
        await self.coordinator.async_refresh()
