from __future__ import annotations

import logging
from typing import Any
import re

from homeassistant.helpers.typing import ConfigType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP

from .const import (
    DOMAIN,
    CONF_DISCOVERY_MODE,
    CONF_DEVICE_TYPE,
    CONF_MAC,
    MODE_AUTO,
    MODE_MANUAL,
    CONF_SLAVE,
    CONF_SCAN_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_SLAVE,
    DEFAULT_SCAN_INTERVAL,
    PLATFORMS,
)
from .coordinator import WanasCoordinator
from .model_v2 import REGISTERS, async_model_register_services
from .frontend import WanasCardRegistration

from homeassistant.helpers import config_validation as cv
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Wanas integration."""

    # register card
    cards = WanasCardRegistration(hass)
    await cards.async_register()
    # store it so async_unload() can clean it up.
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["cards"] = cards

    # register services
    await async_model_register_services(hass)

    return True


async def async_unload(hass: HomeAssistant, config: ConfigEntry) -> bool:
    """Unload the Wanas integration."""

    cards = hass.data.get(DOMAIN, {}).pop("cards", None)
    if cards is not None:
        await cards.async_unregister()

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Wanas from a config entry."""
    host = entry.data.get(CONF_HOST, "")
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)
    slave = entry.data.get(CONF_SLAVE, DEFAULT_SLAVE)
    net_update_interval = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    mac = entry.data.get(CONF_MAC, "")
    device_model = entry.data.get(CONF_DEVICE_TYPE, "")

    def normalize_device_id(raw_id: str) -> str:
        raw_id = raw_id.lower()
        # allow a-z, 0-9, and underscore _
        normalized = re.sub(r"[^a-z0-9_]", "", raw_id)
        return normalized

    raw_device_id = (
        f"{mac}{slave}"
        if entry.data[CONF_DISCOVERY_MODE] == MODE_AUTO
        else f"{host}{port}{slave}"
    )
    device_id = normalize_device_id(raw_device_id)

    # device registry entry - do it early
    # ie. before 'async_forward_entry_setups - PLATFORMS'
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, device_id)},
        manufacturer="Wanas",
        model=device_model,
        name=f"Wanas ({device_id})",
    )

    hass_entity_prefix = f"{DOMAIN}_{device_id}"

    coordinator = WanasCoordinator(hass, entry, device, hass_entity_prefix)

    # store early
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "net_update_interval": net_update_interval,
    }

    # forward to platforms (entities will be unavailable until first successful update)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # start background refresh – will retry forever if disconnected
    await coordinator.async_refresh()

    # register shutdown hook
    async def async_handle_stop_event(event):
        await coordinator.stop()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_handle_stop_event)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Wanas integration."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    data = hass.data[DOMAIN].pop(entry.entry_id)
    coordinator: WanasCoordinator = data["coordinator"]
    await coordinator.stop()

    return unload_ok
