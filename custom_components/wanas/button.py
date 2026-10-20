from typing import Awaitable, Callable, Optional

from homeassistant.components.button import ButtonEntity

from .const import DOMAIN
from .entity import WanasEntity
from .coordinator import WanasCoordinator
from .model_v2 import BUTTON_TYPES


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: WanasCoordinator = data["coordinator"]

    entities = [
        WanasButton(coordinator, key, icon_lambda, press)
        for key, icon_lambda, press in BUTTON_TYPES
    ]
    async_add_entities(entities)


class WanasButton(WanasEntity, ButtonEntity):
    def __init__(
        self,
        coordinator: WanasCoordinator,
        key: str,
        icon_lambda: Optional[Callable[[None], str]],
        press: Callable[[WanasCoordinator], Awaitable[None]],
    ):
        super().__init__(coordinator, key)
        self._icon_lambda = icon_lambda
        self._press = press

    @property
    def icon(self) -> str | None:
        return self._icon_lambda(None) if self._icon_lambda else None

    async def async_press(self) -> None:
        await self._press(self.coordinator)
