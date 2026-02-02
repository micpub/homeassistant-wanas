from typing import Optional

from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN
from .coordinator import WanasCoordinator


class WanasEntity(CoordinatorEntity[WanasCoordinator]):
    """Base entity for all Wanas entities."""

    def __init__(
        self,
        coordinator: WanasCoordinator,
        key: str,
        data_key: Optional[str] = None,
    ):
        super().__init__(coordinator)
        self._key = key
        self._data_key = data_key if data_key is not None else key
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{coordinator.hass_entity_prefix}_{key}"
        self._attr_device_info = {
            "identifiers": coordinator.device_entry.identifiers,
            "manufacturer": coordinator.device_entry.manufacturer,
            "name": coordinator.device_entry.name,
        }

    @property
    def available(self) -> bool:
        """Return True if coordinator has data."""
        return super().available and self.coordinator.data is not None

    @property
    def native_value(self):
        """Return the value from coordinator data."""
        if self.coordinator.data is None:
            return None
        return getattr(self.coordinator.data, self._data_key, None)

    @property
    def translation_key(self) -> str:
        return self._key
