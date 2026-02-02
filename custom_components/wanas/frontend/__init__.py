"""Frontend for Wanas Cards"""

import logging
import os
import pathlib

from packaging.version import parse

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later
from homeassistant.components.http import StaticPathConfig
from homeassistant.const import __version__

from ..const import WANAS_CARDS, URL_BASE

_LOGGER = logging.getLogger(__name__)


class WanasCardRegistration:
    def __init__(self, hass: HomeAssistant):
        self.hass = hass

    @property
    def lovelace_mode(self):
        ha_version = parse(__version__)
        if (ha_version.major >= 2026) or (
            (ha_version.major == 2025) and (ha_version.minor >= 2)
        ):
            return self.hass.data["lovelace"].mode
        else:
            return self.hass.data["lovelace"]["mode"]

    @property
    def lovelace_resources(self):
        ha_version = parse(__version__)
        if (ha_version.major >= 2026) or (
            (ha_version.major == 2025) and (ha_version.minor >= 2)
        ):
            return self.hass.data["lovelace"].resources
        else:
            return self.hass.data["lovelace"]["resources"]

    async def async_register(self):
        await self.async_register_wanas_path()
        if self.lovelace_mode == "storage":
            await self.async_wait_for_lovelace_resources()

    # install card
    async def async_register_wanas_path(self):
        """Register custom cards path if not already registered"""
        try:
            await self.hass.http.async_register_static_paths(
                [StaticPathConfig(URL_BASE, pathlib.Path(__file__).parent, False)]
            )
            _LOGGER.debug(
                "Registered Wanas path from %s", pathlib.Path(__file__).parent
            )
        except RuntimeError:
            _LOGGER.debug("Wanas static path already registered")

    async def async_wait_for_lovelace_resources(self) -> None:
        async def check_lovelace_resources_loaded(now):
            if self.lovelace_resources.loaded:
                await self.async_register_wanas_cards()
            else:
                _LOGGER.debug(
                    "Unable to install Wanas Cards because Lovelace resources not yet loaded. Trying again in 5 seconds"
                )
                async_call_later(self.hass, 5, check_lovelace_resources_loaded)

        await check_lovelace_resources_loaded(0)

    async def async_register_wanas_cards(self):
        _LOGGER.debug("Installing Lovelace resource for Wanas Cards")

        # Get resources already registered
        wanas_resources = [
            resource
            for resource in self.lovelace_resources.async_items()
            if resource["url"].startswith(URL_BASE)
        ]

        for card in WANAS_CARDS:
            url = f"{URL_BASE}/{card.get('filename')}"

            card_registered = False

            for res in wanas_resources:
                if self.get_resource_path(res["url"]) == url:
                    card_registered = True
                    # check version
                    if self.get_resource_version(res["url"]) != card.get("version"):

                        # Update card version
                        _LOGGER.debug(
                            "Updating %s to version %s",
                            card.get("name"),
                            card.get("version"),
                        )
                        await self.lovelace_resources.async_update_item(
                            res.get("id"),
                            {
                                "res_type": "module",
                                "url": url + "?v=" + card.get("version"),
                            },
                        )
                    else:
                        _LOGGER.debug(
                            "%s already registered as version %s",
                            card.get("name"),
                            card.get("version"),
                        )

            if not card_registered:
                _LOGGER.debug(
                    "Registering %s as version %s",
                    card.get("name"),
                    card.get("version"),
                )
                await self.lovelace_resources.async_create_item(
                    {"res_type": "module", "url": url + "?v=" + card.get("version")}
                )

    def get_resource_path(self, url: str):
        return url.split("?")[0]

    def get_resource_version(self, url: str):
        try:
            return url.split("?")[1].replace("v=", "")
        except Exception:
            return 0

    async def async_unregister(self):
        # Unload lovelace module resource
        if self.lovelace_mode == "storage":
            for card in WANAS_CARDS:
                url = f"{URL_BASE}/{card.get('filename')}"
                wanas_resources = [
                    resource
                    for resource in self.lovelace_resources.async_items()
                    if str(resource["url"]).startswith(url)
                ]

                for resource in wanas_resources:
                    await self.lovelace_resources.async_delete_item(resource.get("id"))
