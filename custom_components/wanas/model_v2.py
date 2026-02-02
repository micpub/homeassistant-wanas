from __future__ import annotations

from typing import Callable, Any, Optional
from dataclasses import dataclass
from datetime import date, time

from homeassistant.const import UnitOfTime, UnitOfTemperature, UnitOfVolumeFlowRate
from homeassistant.components.number import NumberMode
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass

from .register import Register
from .modbus_helper import group_registers


# ----------------------------------------------------------------------
# Converters used in the registers list
# ----------------------------------------------------------------------
def identity(v: int) -> int:
    return v


def bool_from_int(v: int) -> bool:
    return bool(v)


def temp_from_raw(v: int) -> float | None:
    if v == 63066:  # special value: sensor error
        return None
    elif v < 63066:
        return round(v / 10.0, 1)
    elif v > 63066:
        delta = (65535 - v) / 10.0
        return round(-0.1 - delta, 1)
    return None


def int_to_date(value: int) -> date:
    year = (value & 0x7F) + 2000  # 7 bits -> year
    month = (value >> 7) & 0x0F  # 4 bits -> month
    day = (value >> 11) & 0x1F  # 5 bits -> day
    return date(year, month, day)


def date_to_int(d: date) -> int:
    year = d.year - 2000
    month = d.month
    day = d.day
    return (day << 11) | (month << 7) | year


def int_to_time(value: int) -> time:
    minute = value & 0xFF  # 8 bits -> minute
    hour = (value >> 8) & 0xFF  # 8 bits -> hour
    return time(hour, minute)


def time_to_int(t: time) -> int:
    return (t.hour << 8) | t.minute


# ----------------------------------------------------------------------
# Make sure to match 'key' param of register list, WanasData data class
# and the entity definitions
# ----------------------------------------------------------------------
@dataclass
class WanasData:
    supply_airflow: int
    extract_airflow: int
    supply_fan_speed: int
    extract_fan_speed: int
    outdoor_temp: float
    exhaust_temp: float
    supply_temp: float
    extract_temp: float
    extra_temp: float
    ghe: bool
    summer_bypass: bool
    humidifier: bool
    heater: bool
    cooler: bool
    vacation: bool
    filter_wear_status: int
    error_status: int
    ghe_mode: bool
    summer_bypass_mode: bool
    humidifier_mode: bool
    heater_mode: int
    cooler_mode: int
    vacation_mode: int
    fireplace_mode: int
    party_mode: int
    device_date: date
    device_time: time
    speed1_airflow: int
    speed2_airflow: int
    speed3_airflow: int
    zone_damper_mode: bool
    frost_protection: bool
    primary_heater: bool
    zone_damper: bool
    service_menu: int
    manual_fan_speed: int
    manual_comfort_temp: int


REGISTERS: list[Register] = sorted(
    [
        # readonly current airflow
        Register(0, "supply_airflow", identity, min=0, max=1600),
        Register(1, "extract_airflow", identity, min=0, max=1600),
        # readonly current fan speeds
        Register(2, "supply_fan_speed", identity, min=0, max=3),
        Register(3, "extract_fan_speed", identity, min=0, max=3),
        # readonly current temperature - main sensors
        Register(4, "outdoor_temp", temp_from_raw, min=0, max=65535),
        Register(5, "exhaust_temp", temp_from_raw, min=0, max=65535),
        Register(6, "supply_temp", temp_from_raw, min=0, max=65535),
        Register(7, "extract_temp", temp_from_raw, min=0, max=65535),
        # readonly current temperature - optional extra sensor
        Register(29, "extra_temp", temp_from_raw, min=0, max=65535),
        # readonly current feature state
        Register(30, "ghe", bool_from_int, min=0, max=1),
        Register(31, "summer_bypass", bool_from_int, min=0, max=1),
        Register(32, "humidifier", bool_from_int, min=0, max=1),
        Register(33, "heater", bool_from_int, min=0, max=1),
        Register(34, "cooler", bool_from_int, min=0, max=1),
        Register(35, "vacation", bool_from_int, min=0, max=1),
        # readonly current filter wear level
        Register(36, "filter_wear_status", identity, min=0, max=252),
        # readonly error state
        Register(37, "error_status", identity, min=0, max=65535),  # error set in bits
        # read-write manual feature control
        Register(
            38,
            "ghe_mode",
            bool_from_int,
            min=0,
            max=1,
            writable=True,
            write_converter=lambda v: int(v),
        ),
        Register(
            39,
            "summer_bypass_mode",
            bool_from_int,
            min=0,
            max=1,
            writable=True,
            write_converter=lambda v: int(v),
        ),
        Register(
            40,
            "humidifier_mode",
            bool_from_int,
            min=0,
            max=1,
            writable=True,
            write_converter=lambda v: int(v),
        ),
        Register(
            41,
            "heater_mode",
            identity,
            min=0,
            max=180,
            writable=True,
            write_converter=lambda v: int(v),
        ),
        Register(
            42,
            "cooler_mode",
            identity,
            min=0,
            max=180,
            writable=True,
            write_converter=lambda v: int(v),
        ),
        Register(
            43,
            "vacation_mode",
            identity,
            min=0,
            max=30,
            writable=True,
            write_converter=lambda v: int(v),
        ),
        Register(
            44,
            "fireplace_mode",
            identity,
            min=0,
            max=180,
            writable=True,
            write_value_step=180, # step 180  ie. 0 or 180 but it reports every second
            write_converter=lambda v: int(v),
        ),
        Register(
            45,
            "party_mode",
            identity,
            min=0,
            max=720,
            writable=True,
            write_value_step=15,
            write_converter=lambda v: int(v),
        ),
        # date and time are set in bits
        Register(
            50,
            "device_date",
            int_to_date,
            min=0,
            max=65535,
            writable=True,
            write_converter=date_to_int,
        ),
        Register(
            51,
            "device_time",
            int_to_time,
            min=0,
            max=65535,
            writable=True,
            write_converter=time_to_int,
        ),
        Register(
            52,
            "speed1_airflow",
            identity,
            min=10,
            max=1600,
            writable=True,
            write_value_step=10,
            write_converter=lambda v: int(v),
        ),
        Register(
            53,
            "speed2_airflow",
            identity,
            min=10,
            max=1600,
            writable=True,
            write_value_step=10,
            write_converter=lambda v: int(v),
        ),
        Register(
            54,
            "speed3_airflow",
            identity,
            min=10,
            max=1600,
            writable=True,
            write_value_step=10,
            write_converter=lambda v: int(v),
        ),
        Register(
            62,
            "zone_damper_mode",
            bool_from_int,
            min=0,
            max=1,
            writable=True,
            write_converter=lambda v: int(v),
        ),
        # readonly current feature state
        Register(63, "frost_protection", bool_from_int, min=0, max=1),
        Register(64, "primary_heater", bool_from_int, min=0, max=1),
        Register(70, "zone_damper", bool_from_int, min=0, max=1),
        # readonly service menu values (bits)
        Register(71, "service_menu", identity, min=0, max=65535),
        # read-write manual feature control
        Register(
            72,
            "manual_fan_speed",
            identity,
            min=0,
            max=3,
            writable=True,
            write_converter=lambda v: int(v),
        ),
        Register(
            73,
            "manual_comfort_temp",
            identity,
            min=10,
            max=30,
            writable=True,
            write_converter=lambda v: int(v),
        ),
    ],
    key=lambda x: x.address,
)

# Safety checks - check duplicate address / key (names)
addresses = [reg.address for reg in REGISTERS]
if len(addresses) != len(set(addresses)):
    raise ValueError("Duplicate register addresses found in REGISTERS!")

keys = [reg.name for reg in REGISTERS]
if len(keys) != len(set(keys)):
    raise ValueError("Duplicate register keys found in REGISTERS!")

# Helper dicts to access Register
REGISTERS_BY_ADDRESS = {reg.address: reg for reg in REGISTERS}
REGISTERS_BY_KEY = {reg.name: reg for reg in REGISTERS}

# Calc groups of registers - optimization to read more modbus registers at once
GROUPED_REGISTERS = group_registers(REGISTERS)


# HASS entity definitions

SENSOR_TYPES = [
    # key, unit, icon_lambda
    (
        "supply_airflow",
        UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        lambda x: "mdi:fan",
    ),
    (
        "extract_airflow",
        UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        lambda x: "mdi:fan",
    ),
    (
        "supply_fan_speed",
        None,
        lambda x: (
            "mdi:fan-off"
            if x is None or x == 0
            else (
                "mdi:fan-speed-1"
                if x == 1
                else (
                    "mdi:fan-speed-2"
                    if x == 2
                    else "mdi:fan-speed-3" if x == 3 else "mdi:fan-off"
                )
            )
        ),
    ),
    (
        "extract_fan_speed",
        None,
        lambda x: (
            "mdi:fan-off"
            if x is None or x == 0
            else (
                "mdi:fan-speed-1"
                if x == 1
                else (
                    "mdi:fan-speed-2"
                    if x == 2
                    else "mdi:fan-speed-3" if x == 3 else "mdi:fan-off"
                )
            )
        ),
    ),
    (
        "outdoor_temp",
        UnitOfTemperature.CELSIUS,
        lambda x: "mdi:thermometer",
    ),
    (
        "exhaust_temp",
        UnitOfTemperature.CELSIUS,
        lambda x: "mdi:thermometer",
    ),
    (
        "supply_temp",
        UnitOfTemperature.CELSIUS,
        lambda x: "mdi:thermometer",
    ),
    (
        "extract_temp",
        UnitOfTemperature.CELSIUS,
        lambda x: "mdi:thermometer",
    ),
    (
        "extra_temp",
        UnitOfTemperature.CELSIUS,
        lambda x: "mdi:thermometer",
    ),
]

FILTER_SENSOR_TYPES = [
    # key, unit, device_class, state_class, icon_lambda
    (
        "filter_wear_status",
        UnitOfTime.DAYS,
        SensorDeviceClass.DURATION,
        SensorStateClass.MEASUREMENT,
        lambda x: "mdi:air-filter",
    ),
]

SWITCH_TYPES = [
    # key, icon_lambda
    ("ghe_mode", lambda x: "mdi:waves-arrow-up"),
    ("summer_bypass_mode", lambda x: "mdi:arrow-decision"),
    (
        "humidifier_mode",
        lambda x: "mdi:air-humidifier" if x is True else "mdi:air-humidifier-off",
    ),
    ("zone_damper_mode", lambda x: "mdi:pipe-valve"),
]

NUMBER_TYPES = [
    # key, name, mode, unit, icon_lambda
    (
        "heater_mode",
        NumberMode.BOX,
        UnitOfTime.DAYS,
        lambda x: ("mdi:radiator-off" if x is None or x == 0 else "mdi:radiator"),
    ),
    (
        "cooler_mode",
        NumberMode.BOX,
        UnitOfTime.DAYS,
        lambda x: ("mdi:snowflake-off" if x is None or x == 0 else "mdi:snowflake"),
    ),
    (
        "vacation_mode",
        NumberMode.BOX,
        UnitOfTime.DAYS,
        lambda x: (
            "mdi:bag-suitcase-off" if x is None or x == 0 else "mdi:bag-suitcase"
        ),
    ),
    (
        "fireplace_mode",
        NumberMode.BOX,
        UnitOfTime.SECONDS,
        lambda x: ("mdi:fireplace-off" if x is None or x == 0 else "mdi:fireplace"),
    ),
    (
        "party_mode",
        NumberMode.BOX,
        UnitOfTime.MINUTES,
        lambda x: (
            "mdi:glass-cocktail-off" if x is None or x == 0 else "mdi:glass-cocktail"
        ),
    ),
    (
        "speed1_airflow",
        NumberMode.BOX,
        UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        lambda x: "mdi:fan-speed-1",
    ),
    (
        "speed2_airflow",
        NumberMode.BOX,
        UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        lambda x: "mdi:fan-speed-2",
    ),
    (
        "speed3_airflow",
        NumberMode.BOX,
        UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        lambda x: "mdi:fan-speed-3",
    ),
    (
        "manual_fan_speed",
        NumberMode.BOX,
        None,
        lambda x: (
            "mdi:fan-off"
            if x is None or x == 0
            else (
                "mdi:fan-speed-1"
                if x == 1
                else (
                    "mdi:fan-speed-2"
                    if x == 2
                    else "mdi:fan-speed-3" if x == 3 else "mdi:fan-off"
                )
            )
        ),
    ),
    (
        "manual_comfort_temp",
        NumberMode.BOX,
        UnitOfTemperature.CELSIUS,
        lambda x: "mdi:thermometer",
    ),
]

BINARY_TYPES = [
    # key, icon_lambda
    ("ghe", lambda x: "mdi:waves-arrow-up"),
    ("summer_bypass", lambda x: "mdi:arrow-decision"),
    (
        "humidifier",
        lambda x: "mdi:air-humidifier" if x is True else "mdi:air-humidifier-off",
    ),
    ("heater", lambda x: "mdi:radiator" if x is True else "mdi:radiator-off"),
    (
        "cooler",
        lambda x: "mdi:snowflake" if x is True else "mdi:snowflake-off",
    ),
    (
        "vacation",
        lambda x: "mdi:bag-suitcase" if x is True else "mdi:bag-suitcase-off",
    ),
    (
        "frost_protection",
        lambda x: "mdi:air-humidifier" if x is True else "mdi:air-humidifier-off",
    ),
    (
        "primary_heater",
        lambda x: "mdi:radiator" if x is True else "mdi:radiator-off",
    ),
    (
        "zone_damper",
        lambda x: "mdi:pipe-valve",
    ),
]

CONNECTION_BINARY_TYPES = [
    # key, icon_lambda
    (
        "connection_status",
        lambda x: "mdi:wifi" if x is True else "mdi:wifi-off",
    ),
]

ERROR_BINARY_BIT_TYPES = [
    # key, bit, data_key, unit, icon_lambda
    (
        "extract_fan_error",
        0,
        "error_status",
        None,
        lambda x: "mdi:alert-circle" if x is True else "mdi:checkbox-marked-circle",
    ),
    (
        "supply_fan_error",
        1,
        "error_status",
        None,
        lambda x: "mdi:alert-circle" if x is True else "mdi:checkbox-marked-circle",
    ),
    (
        "outdoor_temp_sensor_error",
        2,
        "error_status",
        None,
        lambda x: "mdi:alert-circle" if x is True else "mdi:checkbox-marked-circle",
    ),
    (
        "extract_temp_sensor_error",
        3,
        "error_status",
        None,
        lambda x: "mdi:alert-circle" if x is True else "mdi:checkbox-marked-circle",
    ),
    (
        "supply_temp_sensor_error",
        4,
        "error_status",
        None,
        lambda x: "mdi:alert-circle" if x is True else "mdi:checkbox-marked-circle",
    ),
    (
        "exhaust_temp_sensor_error",
        5,
        "error_status",
        None,
        lambda x: "mdi:alert-circle" if x is True else "mdi:checkbox-marked-circle",
    ),
    (
        "humidifier_temp_sensor_error",
        6,
        "error_status",
        None,
        lambda x: "mdi:alert-circle" if x is True else "mdi:checkbox-marked-circle",
    ),
    (
        "extra_outdoor_temp_sensor_error",
        7,
        "error_status",
        None,
        lambda x: "mdi:alert-circle" if x is True else "mdi:checkbox-marked-circle",
    ),
    (
        "extra_supply_temp_sensor_error",
        8,
        "error_status",
        None,
        lambda x: "mdi:alert-circle" if x is True else "mdi:checkbox-marked-circle",
    ),
    (
        "extract_air_pressure_sensor_error",
        9,
        "error_status",
        None,
        lambda x: "mdi:alert-circle" if x is True else "mdi:checkbox-marked-circle",
    ),
    (
        "supply_air_pressure_sensor_error",
        10,
        "error_status",
        None,
        lambda x: "mdi:alert-circle" if x is True else "mdi:checkbox-marked-circle",
    ),
    # bits 11-15 are not used yet
]

SERVICE_MENU_BINARY_BIT_TYPES = [
    # key, bit, data_key, unit, icon_lambda
    (
        "humidifier_func_enabled",
        0,
        "service_menu",
        None,
        lambda x: "mdi:account-question",
    ),
    (
        "xf_func_enabled",
        1,
        "service_menu",
        None,
        lambda x: "mdi:account-question",
    ),
    (
        "ghe_func_enabled",
        2,
        "service_menu",
        None,
        lambda x: "mdi:account-question",
    ),
    (
        "cooler_func_enabled",
        3,
        "service_menu",
        None,
        lambda x: "mdi:account-question",
    ),
    (
        "heater_func_enabled",
        4,
        "service_menu",
        None,
        lambda x: "mdi:account-question",
    ),
    (
        "zone_damper_func_enabled",
        5,
        "service_menu",
        None,
        lambda x: "mdi:account-question",
    ),
    (
        "extra_supply_temp_enabled",
        6,
        "service_menu",
        None,
        lambda x: "mdi:account-question",
    ),
    (
        "extra_outdoor_temp_enabled",
        7,
        "service_menu",
        None,
        lambda x: "mdi:account-question",
    ),
    # bits 8-15 havent figured out / are not used yet
]

DATE_TYPES = [
    # key, icon_lambda
    ("device_date", lambda x: "mdi:calendar-clock"),
]

TIME_TYPES = [
    # key, icon_lambda
    ("device_time", lambda x: "mdi:clock"),
]
