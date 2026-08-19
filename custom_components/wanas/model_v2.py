from __future__ import annotations

import asyncio
from typing import Callable, Any, Optional, TYPE_CHECKING
from dataclasses import dataclass, field
from copy import deepcopy
from datetime import date, time

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.const import UnitOfTime, UnitOfTemperature, UnitOfVolumeFlowRate
from homeassistant.components.number import NumberMode
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.exceptions import HomeAssistantError

if TYPE_CHECKING:
    from .coordinator import WanasCoordinator
from .const import DOMAIN
from .register import Register
from .modbus_helper import group_registers

import logging
_LOGGER = logging.getLogger(__name__)

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
    if v < 63066:  # positive temps
        return round(v / 10.0, 1)
    # negative temps
    y = 65536 - v
    return round(-y / 10.0, 1)


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


def week_schedule_minutes_to_time(v: int) -> time:
    if not isinstance(v, int) or not (0 <= v < 1440):
        raise ValueError(f"Invalid schedule minute value: {v}")
    return time(v // 60, v % 60)


def week_schedule_time_to_minutes(t: time) -> int:
    return t.hour * 60 + t.minute


# ----------------------------------------------------------------------
# Converters used in the registers list with workarounds
# there is no way to tell if the external sensor is connected or not
# in the (SERVICE_MENU_BINARY_BIT_TYPES)
# ----------------------------------------------------------------------
def ext_sensor_co2th_co2_identity(v: int) -> int | None:
    # my machine returns 0 when its not connected
    # 0 is unrealistic so it should be fine
    if(v == 0):
        return None
    return v


def ext_sensor_co2th_humidity_identity(v: int) -> int | None:
    # my machine returns 63982 when its not connected - why this value?
    if(v == 63982):
        return None
    return round(v / 10.0, 1)


def ext_sensor_th_humidity_identity(v: int) -> float | None:
    # my machine returns 65535(uint16 max) when its not connected
    if(v == 65535):
        return None
    return round(v / 10.0, 1)


def ext_sensor_co2th_and_th_temp_from_raw(v: int) -> float | None:
    # my machine returns 65036(which is -50,0 c) when its not connected
    if(v == 65036):
        return None
    return temp_from_raw(v)


# ----------------------------------------------------------------------
# Helper weekly schedule functions
# ----------------------------------------------------------------------
ZONE_MIN_STEP = 15
DAY_END = 24 * 60

def adjust_schedule(zones, zone_num, new_start, new_end):
    """
    zones:
        dict[int, ScheduleZone]
    zone_num:
        1..5
    new_start/new_end:
        minutes
    Returns:
        adjusted_zone_nums
        adjusted_zone_values
    adjusted_zones: [
        zone_number
        ...
    ]
    adjusted_zone_values: [
        time
        ...
    ]
    """

    # build start table
    starts = {
        z: week_schedule_time_to_minutes(zones[z].start)
        for z in range(1, 6)
    }

    # apply requested edit
    if zone_num > 1:
        starts[zone_num] = new_start
    if zone_num < 5:
        starts[zone_num + 1] = new_end

    # expand left if needed
    for z in range(zone_num - 1, 0, -1):
        if starts[z + 1] - starts[z] >= ZONE_MIN_STEP:
            continue
        starts[z] = starts[z + 1] - ZONE_MIN_STEP
    starts[1] = 0

    # expand right if needed
    for z in range(zone_num + 1, 6):
        previous_end = starts[z]
        next_start = DAY_END if z == 5 else starts[z + 1]
        if next_start - previous_end >= ZONE_MIN_STEP:
            continue
        if z < 5:
            starts[z + 1] = previous_end + ZONE_MIN_STEP

    # clamp from right
    starts[5] = min(starts[5], DAY_END - ZONE_MIN_STEP)

    # clamp backwards
    for z in range(4, 0, -1):
        max_start = starts[z + 1] - ZONE_MIN_STEP
        if starts[z] > max_start:
            starts[z] = max_start
    starts[1] = 0

    # build returns
    adjusted_zone_nums = []
    adjusted_zone_values = []
    for z in range(2, 6):
        old = week_schedule_time_to_minutes(zones[z].start)
        new = starts[z]
        if old != new:
            adjusted_zone_nums.append(z)
            adjusted_zone_values.append(week_schedule_minutes_to_time(new))

    return adjusted_zone_nums, adjusted_zone_values


def _get_coordinator_for_device(hass: HomeAssistant, call: ServiceCall) -> WanasCoordinator:
    """Get the coordinator for the targeted Wanas device."""

    device_ids = call.data.get("device_id")
    if not device_ids:
        raise HomeAssistantError(
            "A Wanas device must be specified as the target."
        )

    if isinstance(device_ids, str):
        device_id = device_ids
    elif len(device_ids) == 1:
        device_id = device_ids[0]
    else:
        raise HomeAssistantError(
            "Exactly one Wanas device must be targeted."
        )

    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        raise HomeAssistantError(
            f"Unknown Wanas device: {device_id}"
        )

    entry_id = device.config_entry_id
    if entry_id is None:
        raise HomeAssistantError(
            f"Wanas device {device_id} has no config entry."
        )

    data = hass.data.get(DOMAIN, {}).get(entry_id)
    if data is None:
        raise HomeAssistantError(
            f"Wanas config entry {entry_id} is not loaded."
        )
    try:
        return data["coordinator"]
    except KeyError as err:
        raise HomeAssistantError(
            f"No coordinator found for Wanas device {device_id}."
        ) from err

async def async_model_register_services(hass: HomeAssistant):
    async def async_update_weekly_schedule_zone(call: ServiceCall):
        coordinator = _get_coordinator_for_device(hass, call)
        async with coordinator.locked():
            # important: call these modbus writes under one lock
            # to prevent day change by periodic updates between the calls

            day = int(call.data["day"])
            zone = int(call.data["zone"])
            # optional fields
            def optional_int(value):
                return None if value is None else int(value)
            start = optional_int(call.data.get("start"))
            end = optional_int(call.data.get("end"))
            speed = optional_int(call.data.get("speed"))
            temp = optional_int(call.data.get("temp"))

            adjusted_zone_nums: list[int] = []
            adjusted_zone_values: list[int] = []
            single_writes: dict[str, int] = {}
            if start is not None and end is not None:
                if zone == 1:
                    boundary_reg = REGISTERS_BY_KEY["zone2_start"]
                    step = boundary_reg.write_value_step
                    min_start = boundary_reg.min - step
                    max_end = boundary_reg.max - step
                else:
                    boundary_reg = REGISTERS_BY_KEY[f"zone{zone}_start"]
                    step = boundary_reg.write_value_step
                    min_start = boundary_reg.min
                    max_end = boundary_reg.max
                start = max(min(start, max_end - step), min_start)
                end = min(max(end, start + step), max_end)

                if coordinator.data is None:
                    raise HomeAssistantError(
                        "update_weekly_schedule_zone: coordinator data is not available"
                    )
                if day not in coordinator.data.weekly_schedule:
                    raise HomeAssistantError(
                        f"update_weekly_schedule_zone: day {day} "
                        "is not available in the weekly schedule"
                    )

                adjusted_zone_nums, adjusted_zone_values = adjust_schedule(
                    zones=coordinator.data.weekly_schedule[day],
                    zone_num=zone,
                    new_start=start,
                    new_end=end,
                )
            if speed is not None:
                single_writes[f"zone{zone}_fan_speed"] = speed
            if temp is not None:
                single_writes[f"zone{zone}_temperature"] = temp

            # nothing to do?
            if not adjusted_zone_nums and not single_writes:
                return

            await coordinator._async_write_register("weekly_schedule_day", day)
            # check
            for attempt in range(5):  # 5 retries
                regs = await coordinator._async_read_register_block(address=8, count=1)
                if regs[0] == day:
                    break
                await asyncio.sleep(0.05 + attempt * 0.03)
            else:
                raise UpdateFailed(f"Failed to switch weekly schedule day to {day}")

            # write zones
            if adjusted_zone_nums:
                await coordinator._async_write_registers(
                    [f"zone{num}_start" for num in adjusted_zone_nums],
                    adjusted_zone_values,
                )

            # write speed / temp
            for reg_name, value in single_writes.items():
                await coordinator._async_write_register(reg_name, value)

            # refresh
            coordinator.async_set_updated_data(deepcopy(coordinator.data))
            coordinator.do_modbus_full_update = True
            hass.async_create_task(coordinator.async_refresh())


    hass.services.async_register(
        DOMAIN,
        "update_weekly_schedule_zone",
        async_update_weekly_schedule_zone,
    )


def _parse_schedule_day(raw: dict[int,int]) -> dict[int, ScheduleZone]:
    zones: dict[int, ScheduleZone] = {}
    for i in range(5):  # 5 zones
        zones[i + 1] = ScheduleZone(
            start=week_schedule_minutes_to_time(raw.get(9 + i)) if i > 0 else time(hour=0, minute=0),
            speed=raw.get(14 + i),
            comfort_temp=raw.get(19 + i),
        )
    return zones


async def _async_fetch_weekly_schedule(coordinator: "WanasCoordinator") -> dict[int, dict[int, ScheduleZone]]:
    schedule: dict[int, dict[int, ScheduleZone]] = {}
    try:
        for day in range(7):
            # set day (register 8)
            await coordinator._async_write_register("weekly_schedule_day", day)
            # check
            for attempt in range(5):  # 5 retries
                regs = await coordinator._async_read_register_block(address=8, count=1)
                if regs[0] == day:
                    break
                await asyncio.sleep(0.05 + attempt * 0.03)
            else:
                raise UpdateFailed(f"Failed to switch weekly schedule day to {day}")

            # read registers 8-23
            start_address = 8
            raw_list = await coordinator._async_read_register_block(address=start_address, count=16)
            raw = {
                start_address + i: value
                for i, value in enumerate(raw_list)
            }
            schedule[day] = _parse_schedule_day(raw)
    finally:  # restore controller to current weekday
        try:
            today = (date.today().weekday() + 1) % 7  # convert python -> wanas day numeration
            await coordinator._async_write_register("weekly_schedule_day", today)
        except Exception:
            _LOGGER.warning("Failed to restore weekly_schedule_day", exc_info=True)
    return schedule


async def _async_fetch_complex_registers(coordinator: "WanasCoordinator", full_update: bool) -> dict[str, Any]:
    weekly_schedule = None
    if full_update:
        weekly_schedule = await _async_fetch_weekly_schedule(coordinator)
    else:
        weekly_schedule = (
            coordinator.data.weekly_schedule
            if coordinator.data is not None
            else {}
        )

    return { "weekly_schedule": weekly_schedule }


def _set_complex_register_data(data: WanasData, reg: Register, name: str, value: Any):
    if 10 <= reg.address <= 23:  # weekly schedule
        if data.weekly_schedule_day not in data.weekly_schedule:
            data.weekly_schedule[data.weekly_schedule_day] = {}
            for zone_id in range(1, 6):
                data.weekly_schedule[data.weekly_schedule_day][zone_id] = ScheduleZone(
                    start = time(hour=0, minute=0) if zone_id == 1 else None,
                    speed = None,
                    comfort_temp = None,
                )

        day_data = data.weekly_schedule[data.weekly_schedule_day]
        if 10 <= reg.address <= 13:  # zone start times
            zone = reg.address - 8  # its correct, there is no first zone start - as its always 00:00
            day_data[zone].start = value
        elif 14 <= reg.address <= 18:  # zone fan speeds
            zone = reg.address - 13
            day_data[zone].speed = value
        elif 19 <= reg.address <= 23:  # zone temperatures
            zone = reg.address - 18
            day_data[zone].comfort_temp = value
    else:
        raise ValueError(f"Unhandled complex register[{reg.address}: {name}] data write")

# ----------------------------------------------------------------------
# Make sure to match 'key' param of register list, WanasData data class
# and the entity definitions
# ----------------------------------------------------------------------

@dataclass
class ScheduleZone:
    start: time | None = None
    speed: int | None = None
    comfort_temp: float | None = None


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
    weekly_schedule_day: int
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
    extsen_th_humidity_livingroom: float
    extsen_th_humidity_bathroom1: float
    extsen_th_humidity_bathroom2: float
    extsen_co2th_co2_dayzone: int
    extsen_co2th_co2_nightzone: int
    extsen_co2th_humidity_dayzone: int
    extsen_co2th_humidity_nightzone: int
    extsen_th_temp_livingroom: float
    extsen_th_temp_bathroom1: float
    extsen_th_temp_bathroom2: float
    extsen_co2th_temp_dayzone: float
    extsen_co2th_temp_nightzone: float
    zone_damper_mode: bool
    frost_protection: bool
    primary_heater: bool
    zone_damper: bool
    service_menu: int
    manual_fan_speed: int
    manual_comfort_temp: int
    weekly_schedule: dict[int, dict[int, ScheduleZone]] = field(default_factory=dict)  # key: day 0-6, key: zone 1-5


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
        # read-write manual feature control
        Register(
            8,
            "weekly_schedule_day",
            identity,
            min=0,
            max=6,
            writable=True,
            write_converter=lambda v: int(v),
        ),
        Register(
            10,
            "zone2_start",
            week_schedule_minutes_to_time,
            min=15,
            max=1395,
            writable=True,
            write_value_step=15,
            write_converter=week_schedule_time_to_minutes,
            is_complex=True,
        ),
        Register(
            11,
            "zone3_start",
            week_schedule_minutes_to_time,
            min=30,
            max=1410,
            writable=True,
            write_value_step=15,
            write_converter=week_schedule_time_to_minutes,
            is_complex=True,
        ),
        Register(
            12,
            "zone4_start",
            week_schedule_minutes_to_time,
            min=45,
            max=1425,
            writable=True,
            write_value_step=15,
            write_converter=week_schedule_time_to_minutes,
            is_complex=True,
        ),
        Register(
            13,
            "zone5_start",
            week_schedule_minutes_to_time,
            min=60,
            max=1440,
            writable=True,
            write_value_step=15,
            write_converter=week_schedule_time_to_minutes,
            is_complex=True,
        ),
        Register(
            14,
            "zone1_fan_speed",
            identity,
            min=0,
            max=3,
            writable=True,
            write_converter=lambda v: int(v),
            is_complex=True,
        ),
        Register(
            15,
            "zone2_fan_speed",
            identity,
            min=0,
            max=3,
            writable=True,
            write_converter=lambda v: int(v),
            is_complex=True,
        ),
        Register(
            16,
            "zone3_fan_speed",
            identity,
            min=0,
            max=3,
            writable=True,
            write_converter=lambda v: int(v),
            is_complex=True,
        ),
        Register(
            17,
            "zone4_fan_speed",
            identity,
            min=0,
            max=3,
            writable=True,
            write_converter=lambda v: int(v),
            is_complex=True,
        ),
        Register(
            18,
            "zone5_fan_speed",
            identity,
            min=0,
            max=3,
            writable=True,
            write_converter=lambda v: int(v),
            is_complex=True,
        ),
        Register(
            19,
            "zone1_temperature",
            identity,
            min=10,
            max=30,
            writable=True,
            write_converter=lambda v: int(v),
            is_complex=True,
        ),
        Register(
            20,
            "zone2_temperature",
            identity,
            min=10,
            max=30,
            writable=True,
            write_converter=lambda v: int(v),
            is_complex=True,
        ),
        Register(
            21,
            "zone3_temperature",
            identity,
            min=10,
            max=30,
            writable=True,
            write_converter=lambda v: int(v),
            is_complex=True,
        ),
        Register(
            22,
            "zone4_temperature",
            identity,
            min=10,
            max=30,
            writable=True,
            write_converter=lambda v: int(v),
            is_complex=True,
        ),
        Register(
            23,
            "zone5_temperature",
            identity,
            min=10,
            max=30,
            writable=True,
            write_converter=lambda v: int(v),
            is_complex=True,
        ),
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
        # readonly current feature state
        Register(55, "extsen_th_humidity_livingroom", ext_sensor_th_humidity_identity, min=0, max=1000),
        Register(56, "extsen_th_humidity_bathroom1", ext_sensor_th_humidity_identity, min=0, max=1000),
        Register(57, "extsen_th_humidity_bathroom2", ext_sensor_th_humidity_identity, min=0, max=1000),
        Register(58, "extsen_co2th_co2_dayzone", ext_sensor_co2th_co2_identity, min=0, max=9999),
        Register(59, "extsen_co2th_co2_nightzone", ext_sensor_co2th_co2_identity, min=0, max=9999),
        Register(60, "extsen_co2th_humidity_dayzone", ext_sensor_co2th_humidity_identity, min=0, max=100),
        Register(61, "extsen_co2th_humidity_nightzone", ext_sensor_co2th_humidity_identity, min=0, max=100),
        Register(65, "extsen_th_temp_livingroom", ext_sensor_co2th_and_th_temp_from_raw, min=0, max=65535),
        Register(66, "extsen_th_temp_bathroom1", ext_sensor_co2th_and_th_temp_from_raw, min=0, max=65535),
        Register(67, "extsen_th_temp_bathroom2", ext_sensor_co2th_and_th_temp_from_raw, min=0, max=65535),
        Register(68, "extsen_co2th_temp_dayzone", ext_sensor_co2th_and_th_temp_from_raw, min=0, max=65535),
        Register(69, "extsen_co2th_temp_nightzone", ext_sensor_co2th_and_th_temp_from_raw, min=0, max=65535),
        # read-write manual feature control
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
GROUPED_REGISTERS = group_registers(REGISTERS, include_complex_regs=True)
GROUPED_REGISTERS_NO_COMPLEX = group_registers(REGISTERS, include_complex_regs=False)

# HASS entity definitions

SENSOR_TYPES = [
    # key, unit, device_class, state_class, icon_lambda
    (
        "supply_airflow",
        UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        SensorDeviceClass.VOLUME_FLOW_RATE,
        SensorStateClass.MEASUREMENT,
        lambda x: "mdi:fan",
    ),
    (
        "extract_airflow",
        UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        SensorDeviceClass.VOLUME_FLOW_RATE,
        SensorStateClass.MEASUREMENT,
        lambda x: "mdi:fan",
    ),
    (
        "supply_fan_speed",
        None,
        None,
        SensorStateClass.MEASUREMENT,
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
        None,
        SensorStateClass.MEASUREMENT,
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
        SensorDeviceClass.TEMPERATURE,
        SensorStateClass.MEASUREMENT,
        lambda x: "mdi:thermometer",
    ),
    (
        "exhaust_temp",
        UnitOfTemperature.CELSIUS,
        SensorDeviceClass.TEMPERATURE,
        SensorStateClass.MEASUREMENT,
        lambda x: "mdi:thermometer",
    ),
    (
        "supply_temp",
        UnitOfTemperature.CELSIUS,
        SensorDeviceClass.TEMPERATURE,
        SensorStateClass.MEASUREMENT,
        lambda x: "mdi:thermometer",
    ),
    (
        "extract_temp",
        UnitOfTemperature.CELSIUS,
        SensorDeviceClass.TEMPERATURE,
        SensorStateClass.MEASUREMENT,
        lambda x: "mdi:thermometer",
    ),
    (
        "extra_temp",
        UnitOfTemperature.CELSIUS,
        SensorDeviceClass.TEMPERATURE,
        SensorStateClass.MEASUREMENT,
        lambda x: "mdi:thermometer",
    ),
    (
        "extsen_th_humidity_livingroom",
        "%",
        SensorDeviceClass.HUMIDITY,
        SensorStateClass.MEASUREMENT,
        lambda x: "mdi:water-percent",
    ),
    (
        "extsen_th_humidity_bathroom1",
        "%",
        SensorDeviceClass.HUMIDITY,
        SensorStateClass.MEASUREMENT,
        lambda x: "mdi:water-percent",
    ),
    (
        "extsen_th_humidity_bathroom2",
        "%",
        SensorDeviceClass.HUMIDITY,
        SensorStateClass.MEASUREMENT,
        lambda x: "mdi:water-percent",
    ),
    (
        "extsen_co2th_co2_dayzone",
        "ppm",
        SensorDeviceClass.CO2,
        SensorStateClass.MEASUREMENT,
        lambda x: "mdi:molecule-co2",
    ),
    (
        "extsen_co2th_co2_nightzone",
        "ppm",
        SensorDeviceClass.CO2,
        SensorStateClass.MEASUREMENT,
        lambda x: "mdi:molecule-co2",
    ),
    (
        "extsen_co2th_humidity_dayzone",
        "%",
        SensorDeviceClass.HUMIDITY,
        SensorStateClass.MEASUREMENT,
        lambda x: "mdi:water-percent",
    ),
    (
        "extsen_co2th_humidity_nightzone",
        "%",
        SensorDeviceClass.HUMIDITY,
        SensorStateClass.MEASUREMENT,
        lambda x: "mdi:water-percent",
    ),
    (
        "extsen_th_temp_livingroom",
        UnitOfTemperature.CELSIUS,
        SensorDeviceClass.TEMPERATURE,
        SensorStateClass.MEASUREMENT,
        lambda x: "mdi:thermometer",
    ),
    (
        "extsen_th_temp_bathroom1",
        UnitOfTemperature.CELSIUS,
        SensorDeviceClass.TEMPERATURE,
        SensorStateClass.MEASUREMENT,
        lambda x: "mdi:thermometer",
    ),
    (
        "extsen_th_temp_bathroom2",
        UnitOfTemperature.CELSIUS,
        SensorDeviceClass.TEMPERATURE,
        SensorStateClass.MEASUREMENT,
        lambda x: "mdi:thermometer",
    ),
    (
        "extsen_co2th_temp_dayzone",
        UnitOfTemperature.CELSIUS,
        SensorDeviceClass.TEMPERATURE,
        SensorStateClass.MEASUREMENT,
        lambda x: "mdi:thermometer",
    ),
    (
        "extsen_co2th_temp_nightzone",
        UnitOfTemperature.CELSIUS,
        SensorDeviceClass.TEMPERATURE,
        SensorStateClass.MEASUREMENT,
        lambda x: "mdi:thermometer",
    ),
]

DIAGNOSTIC_SENSOR_TYPES = [
    # key, unit, device_class, state_class, icon_lambda
    (
        "weekly_schedule_day",
        None,
        None,
        None,
        lambda x: "mdi:calendar-search",
    ),
]

FILTER_SENSOR_TYPES = [
    # key, unit, device_class, state_class, icon_lambda
    (
        "filter_wear_status",
        UnitOfTime.DAYS,
        SensorDeviceClass.DURATION,
        SensorStateClass.MEASUREMENT,
        lambda x: "mdi:alert-circle" if x == 0 else "mdi:air-filter",
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
