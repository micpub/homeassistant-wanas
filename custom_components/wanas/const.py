from typing import Final

from homeassistant.const import Platform


DOMAIN: Final = "wanas"

CONF_DEVICE_TYPE: Final = "device_type"
SUPPORTED_DEVICE_LIST = [
    "Display V2"
]
CONF_DISCOVERY_MODE: Final = "discovery_mode"
CONF_MAC: Final = "mac"
# hass defines these in homeassistant.const
# CONF_HOST: Final = "host"
# CONF_PORT: Final = "port"
CONF_SLAVE: Final = "slave"
CONF_SCAN_INTERVAL: Final = "scan_interval"

DEFAULT_PORT: Final = 8899
DEFAULT_SLAVE: Final = 1
DEFAULT_SCAN_INTERVAL: Final = 5

MODE_AUTO: Final = "auto"
MODE_MANUAL: Final = "manual"

PLATFORMS = (
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.DATE,
    Platform.TIME,
)

URL_BASE = "/wanas"
WANAS_CARDS = [
    {"name": "Wanas Cards", "filename": "wanas-vent-card.js", "version": "0.1.2"}
]
