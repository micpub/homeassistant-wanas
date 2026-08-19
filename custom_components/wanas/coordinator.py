from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import logging
from dataclasses import dataclass
from datetime import timedelta, datetime
from typing import Any, Callable, Dict, Awaitable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import (
    HomeAssistant,
    CALLBACK_TYPE,
)
from homeassistant.helpers.network import get_url
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.device_registry import DeviceEntry
from pymodbus.client import AsyncModbusTcpClient
from pymodbus import ModbusException

from .register import Register
from .model_v2 import (
    WanasData,
    REGISTERS,
    GROUPED_REGISTERS_NO_COMPLEX,
    REGISTERS_BY_KEY,
    _async_fetch_complex_registers,
    _set_complex_register_data,
)
from .const import (
    CONF_DISCOVERY_MODE,
    CONF_MAC,
    MODE_AUTO,
    MODE_MANUAL,
    CONF_SLAVE,
    CONF_SCAN_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_SLAVE,
    DEFAULT_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class ModbusConnection:
    """Manages the Modbus TCP client and host switching."""

    def __init__(self, initial_host: str, port: int, slave: int) -> None:
        self.host = initial_host
        self.port = port
        self.slave = slave
        self.last_error: str | None = None
        self.reconnect_attempts: int = 0
        self._client: AsyncModbusTcpClient | None = None

    @property
    def client(self) -> AsyncModbusTcpClient:
        if self._client is None:
            self._client = AsyncModbusTcpClient(
                host=self.host,
                port=self.port,
                reconnect_delay=1,
                reconnect_delay_max=300,
                retries=10,
                timeout=5,
            )
        return self._client

    @property
    def connected(self) -> bool:
        return self._client is not None and self._client.connected

    @property
    def status(self) -> str:
        if self.connected:
            return "Connected"
        if self.last_error:
            return f"Disconnected – {self.last_error}"
        return "Reconnecting"

    async def switch_host(self, new_host: str) -> bool:
        if new_host == self.host and self.connected:
            return True

        old_host = self.host
        self.host = new_host
        self.last_error = None
        self.reconnect_attempts = 0
        self.close()

        _LOGGER.info(
            "Gateway IP changed: %s → %s – reconnecting...", old_host, new_host
        )
        return (
            await self.client.connect()
        )  # access client via property - will create object

    def close(self) -> None:
        """Close and reset the underlying Modbus client."""
        if self._client is not None:
            self._client.close()
            self._client = None


class GatewayDiscoveryManager:
    """Handles persistent UDP discovery and identity tracking."""

    DISCOVERY_PORT = 48899
    TRIGGERS = [b"www.waveshare.com"]
    BROADCAST_INTERVAL = timedelta(seconds=30)

    def __init__(
        self,
        hass: HomeAssistant,
        wanted_mac: str,
        on_found: Callable[[str], Awaitable[None]],
    ):
        self.hass = hass
        self.wanted_mac = wanted_mac.strip().upper()
        self.on_found = on_found

        self._transport: asyncio.DatagramTransport | None = None
        self._send_broadcast_cancel: CALLBACK_TYPE | None = None
        self._starting: bool = False

    def _parse_packet(self, data: bytes, src_ip: str) -> Dict[str, str | None]:
        # received packet: b'192.168.99.141,D4AD20BF7D70,'
        text = data.decode("utf-8", errors="ignore").strip()
        parts = text.split(",")
        ip = parts[0] if len(parts) > 0 and parts[0] else src_ip
        mac = parts[1].upper() if len(parts) > 1 and parts[1] else None

        # normalize MAC by inserting colons every 2 chars:
        if mac and len(mac) == 12:
            mac = ":".join(mac[i : i + 2] for i in range(0, 12, 2))

        return {
            "ip": ip,
            "mac": mac,
        }

    async def _send_broadcast_once(self) -> None:
        if not self.is_active():
            return

        addr = "255.255.255.255"
        try:
            for t in self.TRIGGERS:
                _LOGGER.debug(
                    f"GatewayDiscoveryManager: sending '{t}' to {addr}:{self.DISCOVERY_PORT}"
                )
                self._transport.sendto(t, (addr, self.DISCOVERY_PORT))
        except Exception as e:
            _LOGGER.debug("Failed to send discovery broadcast: %s", e)

    async def _handle_discovered(self, gateway_info):
        await self.stop()
        await self.on_found(gateway_info["ip"])

    async def start(self) -> None:
        if self._transport is not None or self._starting:
            _LOGGER.debug("Gateway discovery already running or starting")
            return

        self._starting = True

        class DiscoveryProtocol(asyncio.DatagramProtocol):
            def __init__(self, outer: GatewayDiscoveryManager):
                self.outer = outer

            def connection_made(self, transport):
                self.transport = transport
                sock = transport.get_extra_info("socket")
                local_port = sock.getsockname()[1]
                _LOGGER.debug(
                    f"Gateway discovery started, listening on UDP port {local_port}"
                )

            def datagram_received(self, data: bytes, addr):
                src_ip, _ = addr
                gateway_info = self.outer._parse_packet(data, src_ip)
                _LOGGER.debug(
                    f"gateway listener: received packet from {src_ip}: {data}"
                )

                if self.outer.wanted_mac != gateway_info["mac"]:
                    return

                # now that the gateway is found - call the callback
                _LOGGER.debug(
                    "Target gateway found at %s (MAC=%s)",
                    gateway_info["ip"],
                    gateway_info["mac"],
                )
                self.outer.hass.async_create_task(
                    self.outer._handle_discovered(gateway_info)
                )

        try:
            # Bind to local port 0 for ephemeral port assigned by OS
            (
                self._transport,
                _,
            ) = await asyncio.get_running_loop().create_datagram_endpoint(
                lambda: DiscoveryProtocol(self),
                local_addr=("0.0.0.0", 0),
                allow_broadcast=True,
            )

            # start broadcast loop
            async def send_broadcast(event_time: datetime) -> None:
                await self._send_broadcast_once()

            if self._send_broadcast_cancel is not None:
                self._send_broadcast_cancel()
                self._send_broadcast_cancel = None

            # schedule next
            self._send_broadcast_cancel = async_track_time_interval(
                self.hass,
                send_broadcast,
                self.BROADCAST_INTERVAL,
            )
            # call immediately
            await self._send_broadcast_once()
        except Exception as e:
            _LOGGER.warning("Failed to start gateway discovery: %s", e)
            if self._transport:
                self._transport.close()
                self._transport = None
        finally:
            self._starting = False

    async def stop(self) -> None:
        # cancel broadcast loop if scheduled
        if self._send_broadcast_cancel is not None:
            self._send_broadcast_cancel()
            self._send_broadcast_cancel = None

        if self._transport:
            self._transport.close()
            self._transport = None

    def is_active(self) -> bool:
        return self._transport is not None and not self._transport.is_closing()


class WanasCoordinator(DataUpdateCoordinator[WanasData]):
    """Fetch data and manage Modbus TCP connection."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device: DeviceEntry,
        hass_entity_prefix: str,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="Wanas",
            update_interval=timedelta(
                seconds=entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self._entry = entry
        self._lock = asyncio.Lock()
        self._retry_cancel: CALLBACK_TYPE | None = None
        self._stopped = False
        self.device_entry = device
        self.hass_entity_prefix = hass_entity_prefix

        self._cancel_full_update_timer: CALLBACK_TYPE | None = async_track_time_interval(
            hass,
            self._mark_modbus_full_update,
            timedelta(seconds=30),
        )
        self.do_modbus_full_update = True

        # in auto mode on first run theres no CONF_HOST so need 'default' ip here - its never really used
        self.connection = ModbusConnection(
            initial_host=entry.data.get(CONF_HOST, "127.0.0.1"),
            port=entry.data.get(CONF_PORT, DEFAULT_PORT),
            slave=entry.data.get(CONF_SLAVE, DEFAULT_SLAVE),
        )

        # discovery manager (only for AUTO mode)
        self.gateway_discovery: GatewayDiscoveryManager | None = None

        # automatic ip discovery
        if entry.data[CONF_DISCOVERY_MODE] == MODE_AUTO:
            self.gateway_discovery = GatewayDiscoveryManager(
                hass=hass,
                wanted_mac=entry.data[CONF_MAC],
                on_found=self._on_gateway_discovered,
            )
            hass.async_create_task(self.gateway_discovery.start())

    async def _mark_modbus_full_update(self, event_time: datetime) -> None:
        async with self._lock:
            self.do_modbus_full_update = True

    @asynccontextmanager
    async def locked(self):
        """Run a block of Modbus operations under the coordinator lock."""
        async with self._lock:
            yield

    async def _async_write_register(self, name: str, value: Any) -> None:
        if self._stopped:
            raise UpdateFailed("Coordinator stopped")

        if not await self._ensure_connected():
            raise UpdateFailed("Cannot write: Modbus not connected")

        reg = REGISTERS_BY_KEY.get(name, None)
        if not reg or not reg.writable:
            raise ValueError(f"Register {name} is not writable")
        raw = reg.write_converter(value) if reg.write_converter else value
        try:
            result = await self.connection.client.write_register(
                address=reg.address, value=raw, device_id=self.connection.slave
            )
        except ModbusException as err:
            raise UpdateFailed(
                f"Modbus write failed (addr={reg.address}, value={raw}, error: {err})"
            ) from err
        if result.isError():
            raise UpdateFailed(
                f"Modbus error (addr={reg.address}, value={raw}, error: {result})"
            )

        if self.data is not None:
            if not reg.is_complex:
                setattr(self.data, name, value)
            else:
                _set_complex_register_data(self.data, reg, name, value)

    async def async_write_register(self, name: str, value: Any) -> None:
        async with self._lock:
            await self._async_write_register(name, value)

    async def _async_write_registers(self, names: list[str], values: list[Any]) -> None:
        if self._stopped:
            raise UpdateFailed("Coordinator stopped")

        if not await self._ensure_connected():
            raise UpdateFailed("Cannot write: Modbus not connected")

        if len(names) == 0:
            raise UpdateFailed("Cannot write registers: register list empty - nothing to write")
        if len(names) != len(values):
            raise UpdateFailed("Cannot write registers: register list len is not the same as values")
        start_reg = REGISTERS_BY_KEY.get(names[0])
        expected = start_reg.address
        for name in names:
            reg = REGISTERS_BY_KEY.get(name, None)
            if reg.address != expected:
                raise UpdateFailed("Cannot write registers: registers must be contiguous")
            expected += 1

        raw_values: list[int] = []
        for index, name in enumerate(names):
            reg = REGISTERS_BY_KEY.get(name, None)
            if not reg or not reg.writable:
                raise ValueError(f"Register {name} is not writable")
            raw_values.append(
                reg.write_converter(values[index]) if reg.write_converter else values[index])

        try:
            result = await self.connection.client.write_registers(
                address=start_reg.address, values=raw_values, device_id=self.connection.slave
            )
        except ModbusException as err:
            raise UpdateFailed(
                f"Modbus write failed (addr={start_reg.address}, values={raw_values}, error: {err})"
            ) from err
        if result.isError():
            raise UpdateFailed(
                f"Modbus error (addr={start_reg.address}, values={raw_values}, error: {result})"
            )

        if self.data is not None:
            for index, name in enumerate(names):
                reg = REGISTERS_BY_KEY.get(name, None)
                if not reg.is_complex:
                    setattr(self.data, name, values[index])
                else:
                    _set_complex_register_data(self.data, reg, name, values[index])

    async def async_write_registers(self, names: list[str], values: list[Any]) -> None:
        async with self._lock:
            await self._async_write_registers(names, values)

    async def _async_read_register_block(self, address: int, count: int) -> list[int]:
        try:
            _LOGGER.debug(
                "Reading block %d-%d (%d regs)", address, address + count - 1, count
            )
            resp = await self.connection.client.read_holding_registers(
                address=address, count=count, device_id=self.connection.slave
            )
            _LOGGER.debug(
                "Modbus response for %d-%d: isError=%s, registers=%s",
                address,
                address + count - 1,
                resp.isError(),
                resp.registers,
            )
            if resp.isError():
                raise UpdateFailed(
                    f"Modbus read error (addr={address}, count={count}, error: {resp})"
                )
            return resp.registers
        except ModbusException as err:
            self.connection.close()
            self.connection.last_error = str(err)
            raise UpdateFailed(
                f"Modbus read failed (addr={address}, count={count}, error: {err})"
            ) from err

    async def _async_update_data(self) -> WanasData:
        async with self._lock:
            if self._stopped:
                raise UpdateFailed("Coordinator stopped")

            if not await self._ensure_connected():
                raise UpdateFailed(
                    f"Device is not connected: {self.connection.last_error or 'Unknown error'}"
                )

            raw_values: dict[int, int] = {}
            try:
                for start, count, block in GROUPED_REGISTERS_NO_COMPLEX:
                    registers = await self._async_read_register_block(address=start, count=count)
                    for reg, val in zip(block, registers):
                        raw_values[reg.address] = val

                # get complex model specific registers ie. weekly schedule
                extra_params = await _async_fetch_complex_registers(self, self.do_modbus_full_update)

                self.do_modbus_full_update = False

                return self._build_data(raw_values, extra_params)
            except Exception as err:
                raise UpdateFailed(f"Unexpected update error: {err}") from err

    def _build_data(self, raw: dict[int, int], extra_params: dict[str, Any]) -> WanasData:
        kwargs = {}
        for reg in REGISTERS:
            raw_val = raw.get(reg.address)
            if raw_val is not None:
                try:
                    kwargs[reg.name] = reg.converter(raw_val)
                except Exception as e:
                    _LOGGER.warning(
                        "Failed to convert %s (raw=%s): %s", reg.name, raw_val, e
                    )
        kwargs.update(extra_params)
        return WanasData(**kwargs)

    async def _on_gateway_discovered(self, ip: str) -> None:
        """Called when discovery finds the gateway."""
        async with self._lock:
            if self._stopped:
                return

            if await self.connection.switch_host(ip):
                _LOGGER.debug("Successfully connected to discovered gateway at %s", ip)
                # update config entry so future restarts know the IP
                self.hass.config_entries.async_update_entry(
                    self._entry,
                    data={**self._entry.data, CONF_HOST: ip},
                )

                self.do_modbus_full_update = True
                self.hass.async_create_task(self.async_request_refresh())
            else:
                _LOGGER.warning("Failed to connect to discovered IP %s", ip)

    def _schedule_manual_retry(self, exc: Exception) -> bool:
        self.connection.last_error = str(exc)
        self.connection.reconnect_attempts += 1
        _LOGGER.warning(
            "Gateway reconnect failed (attempt %d): %s",
            self.connection.reconnect_attempts,
            exc,
        )

        delay = min(60, 5 * (2 ** min(self.connection.reconnect_attempts - 1, 4)))
        _LOGGER.debug("Scheduling reconnect retry in %s seconds", delay)

        async def force_refresh(event_time: datetime) -> None:
            await self.async_request_refresh()

        self._retry_cancel = async_call_later(
            self.hass,
            delay,
            force_refresh,
        )
        return False

    async def _ensure_connected(self) -> bool:
        """Ensure we're connected. Returns True if ready to read/write."""
        if self._stopped:
            return False

        # cancel any pending retry
        if self._retry_cancel is not None:
            self._retry_cancel()
            self._retry_cancel = None

        # if already connected return success
        if self.connection.connected:
            # in AUTO mode: if we got here with old IP, stop discovery
            if self.gateway_discovery and self.gateway_discovery.is_active():
                await self.gateway_discovery.stop()
            return True

        # AUTO mode: gateway_discovery handles reconnects
        if self._entry.data[CONF_DISCOVERY_MODE] == MODE_AUTO:
            if self.gateway_discovery and not self.gateway_discovery.is_active():
                self.hass.async_create_task(self.gateway_discovery.start())
            return False

        # MANUAL mode: try direct reconnect with backoff
        _LOGGER.debug("Gateway not connected – attempting to connect")

        try:
            await self.connection.client.connect()
        except Exception as exc:
            return self._schedule_manual_retry(exc)

        if not self.connection.connected:
            return self._schedule_manual_retry(
                Exception("connect() returned but client is not connected")
            )

        self.connection.last_error = None
        self.connection.reconnect_attempts = 0
        return True

    async def stop(self) -> None:
        async with self._lock:
            self._stopped = True

            if self.gateway_discovery:
                await self.gateway_discovery.stop()

            # cancel any pending retry
            if self._retry_cancel is not None:
                self._retry_cancel()
                self._retry_cancel = None

            if self._cancel_full_update_timer is not None:
                self._cancel_full_update_timer()
                self._cancel_full_update_timer = None

            self.connection.close()
