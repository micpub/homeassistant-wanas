from typing import Callable, Optional

from homeassistant.components.switch import SwitchEntity, SwitchDeviceClass

from .const import DOMAIN
from .entity import WanasEntity
from .coordinator import WanasCoordinator
from .model_v2 import SWITCH_TYPES


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: WanasCoordinator = data["coordinator"]

    entities = [
        WanasSwitch(coordinator, key, icon_lambda)
        for key, icon_lambda in SWITCH_TYPES
    ]
    async_add_entities(entities)


class WanasSwitch(WanasEntity, SwitchEntity):
    def __init__(
        self,
        coordinator,
        key: str,
        icon_lambda: Optional[Callable[[bool | None], str]],
    ):
        super().__init__(coordinator, key)
        self._attr_device_class = SwitchDeviceClass.SWITCH
        self._icon_lambda = icon_lambda

    @property
    def icon(self) -> str | None:
        val = super().native_value
        return self._icon_lambda(None if val is None else val)

    @property
    def is_on(self) -> bool | None:
        val = super().native_value
        return bool(val) if val is not None else None

    async def async_turn_on(self, **kwargs):
        await self.coordinator.async_write_register(self._key, True)
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs):
        await self.coordinator.async_write_register(self._key, False)
        await self.coordinator.async_refresh()
