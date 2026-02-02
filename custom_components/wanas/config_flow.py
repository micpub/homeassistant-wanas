from __future__ import annotations

from typing import Any

import voluptuous as vol
import re

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    DOMAIN,
    CONF_DEVICE_TYPE,
    SUPPORTED_DEVICE_LIST,
    CONF_DISCOVERY_MODE,
    CONF_MAC,
    CONF_SLAVE,
    CONF_SCAN_INTERVAL,
    MODE_AUTO,
    MODE_MANUAL,
    DEFAULT_PORT,
    DEFAULT_SLAVE,
    DEFAULT_SCAN_INTERVAL,
)

# MAC validator
MAC_REGEX = re.compile(r"^([0-9a-f]{2}[:-]?){5}[0-9a-f]{2}$", re.IGNORECASE)


def validate_mac_address(value: Any) -> str:
    """Validate and normalize MAC address."""
    if not isinstance(value, str):
        raise vol.Invalid("error_invalid_mac", params={"value": value})

    # Handle common formats (with/without separators)
    mac = value.strip().upper().replace("-", ":")

    if not mac:
        raise vol.Invalid("error_empty_mac")

    if len(mac.replace(":", "")) != 12:
        raise vol.Invalid("error_mac_length", params={"value": value})

    if not MAC_REGEX.match(mac):
        raise vol.Invalid("error_invalid_mac_format", params={"mac": value})

    return mac  # Return normalized colon format


class WanasConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Wanas."""

    VERSION = 1

    def __init__(self):
        self.discovered_mac: str | None = None  # Only for UX pre-fill

    async def async_step_dhcp(self, discovery_info: DhcpServiceInfo) -> FlowResult:
        """Handle DHCP discovery."""
        mac = discovery_info.macaddress.upper().replace("-", ":")
        await self.async_set_unique_id(mac)
        self._abort_if_unique_id_configured()

        # Go directly to auto form with pre-filled MAC
        self.discovered_mac = mac
        return await self.async_step_auto()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manual entry point (Add Integration → Wanas)"""
        return await self.async_step_init(user_input)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1: Choose discovery mode"""
        if user_input is not None:
            # Jump to conditional step based on mode
            if user_input[CONF_DISCOVERY_MODE] == MODE_AUTO:
                return await self.async_step_auto()
            return await self.async_step_manual()

        schema = vol.Schema(
            {
                vol.Required(CONF_DISCOVERY_MODE, default=MODE_AUTO): SelectSelector(
                    config=SelectSelectorConfig(
                        options=[MODE_AUTO, MODE_MANUAL],
                        mode=SelectSelectorMode.LIST,
                        translation_key=CONF_DISCOVERY_MODE,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
        )

    async def async_step_auto(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2A: Automatic IP - via MAC address."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                mac = validate_mac_address(user_input[CONF_MAC])
                slave = int(user_input.get(CONF_SLAVE, DEFAULT_SLAVE))

                config_data = {
                    CONF_DISCOVERY_MODE: MODE_AUTO,
                    CONF_DEVICE_TYPE: user_input[CONF_DEVICE_TYPE],
                    CONF_MAC: mac,
                    CONF_PORT: DEFAULT_PORT,
                    CONF_SLAVE: slave,
                    CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                }
                unique_id = f"{mac}_{slave}"
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Wanas ({mac}_{slave})",
                    data=config_data,
                )
            except vol.Invalid as err:
                errors[CONF_MAC] = str(err)

        mac_description = (  ########################display this? in the mac?
            f"Discovered device: {self.discovered_mac}"
            if self.discovered_mac
            else "Enter MAC (e.g. AA:BB:CC:11:22:33)"
        )
        # Cannot validate mac here - use only simple string length
        schema = vol.Schema(
            {
                vol.Required(CONF_DEVICE_TYPE, default=SUPPORTED_DEVICE_LIST[0]): SelectSelector(
                    config=SelectSelectorConfig(
                        options=SUPPORTED_DEVICE_LIST,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
                vol.Required(CONF_MAC, default=self.discovered_mac or ""): vol.All(
                    cv.string,
                    vol.Length(min=12, max=17),
                ),
                vol.Required(CONF_SLAVE, default=DEFAULT_SLAVE): NumberSelector(
                    config=NumberSelectorConfig(
                        min=1,
                        max=24,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
            }
        )

        return self.async_show_form(
            step_id="auto",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2B: Manual mode: IP - static."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                host = cv.string(user_input[CONF_HOST]).strip()
                port = cv.port(user_input.get(CONF_PORT, DEFAULT_PORT))
                slave = int(user_input.get(CONF_SLAVE, DEFAULT_SLAVE))

                config_data = {
                    CONF_DISCOVERY_MODE: MODE_MANUAL,
                    CONF_DEVICE_TYPE: user_input[CONF_DEVICE_TYPE],
                    CONF_HOST: host,
                    CONF_PORT: port,
                    CONF_SLAVE: slave,
                    CONF_SCAN_INTERVAL: int(
                        user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
                    ),
                }

                # Unique ID based on host/port/slave
                unique_id = f"{host}_{port}_{slave}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Wanas ({host}_{port}_{slave})",
                    data=config_data,
                )
            except vol.Invalid as exc:
                errors["base"] = str(exc)

        schema = vol.Schema(
            {
                vol.Required(CONF_DEVICE_TYPE, default=SUPPORTED_DEVICE_LIST[0]): SelectSelector(
                    config=SelectSelectorConfig(
                        options=SUPPORTED_DEVICE_LIST,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
                vol.Required(CONF_HOST, default=""): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.Coerce(int),
                vol.Required(CONF_SLAVE, default=DEFAULT_SLAVE): NumberSelector(
                    config=NumberSelectorConfig(
                        min=1,
                        max=24,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
            }
        )

        return self.async_show_form(
            step_id="manual",
            data_schema=schema,
            errors=errors,
        )
