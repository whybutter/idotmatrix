"""BLE client for the iDotMatrix panel, routed through HA's Bluetooth stack.

Deliberately does NOT talk to a local hci0 adapter directly. Getting the
BLEDevice via homeassistant.components.bluetooth means HA transparently picks
whichever adapter/proxy has the best connection to the panel right now -
local adapter or a remote active ESPHome-API-compatible proxy (e.g. the WBRG1
gateway, see vault "Reutilizar Gateway Zigbee TYZB1.md") - exactly like
ha-tuya-ble does for BLE thermometers. No firmware changes needed on any proxy.
"""
from __future__ import annotations

import asyncio
import logging

from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

from . import protocol
from .const import READ_CHAR_UUID, WRITE_CHAR_UUID

_LOGGER = logging.getLogger(__name__)


class IdotMatrixError(Exception):
    """Raised when the panel can't be reached or a write fails."""


class IdotMatrixClient:
    """Thin wrapper: resolve device via HA, connect, write protocol frames."""

    def __init__(self, hass: HomeAssistant, address: str) -> None:
        self._hass = hass
        self._address = address
        self._client: BleakClientWithServiceCache | None = None

    @property
    def address(self) -> str:
        return self._address

    async def _ensure_connected(self) -> BleakClientWithServiceCache:
        if self._client is not None and self._client.is_connected:
            return self._client

        ble_device = bluetooth.async_ble_device_from_address(
            self._hass, self._address, connectable=True
        )
        if ble_device is None:
            raise IdotMatrixError(
                f"No active proxy or adapter currently sees {self._address} - "
                "confirm the panel is powered and in range of an active BLE proxy"
            )

        try:
            self._client = await establish_connection(
                BleakClientWithServiceCache, ble_device, self._address
            )
        except (BleakError, TimeoutError) as err:
            raise IdotMatrixError(f"Failed to connect to {self._address}: {err}") from err

        return self._client

    async def disconnect(self) -> None:
        if self._client is not None:
            await self._client.disconnect()
            self._client = None

    async def _write_raw(self, data: bytes) -> None:
        client = await self._ensure_connected()
        # bleak chunks internally per the negotiated MTU when write-without-response
        # is used with data larger than mtu_size - 3, so a single call is enough.
        try:
            await client.write_gatt_char(WRITE_CHAR_UUID, data, response=False)
        except (BleakError, TimeoutError) as err:
            raise IdotMatrixError(f"Write failed: {err}") from err
        # Empirically required (per Toon-nooT/idotmatrix-api-client, an actively
        # maintained sibling port of this protocol): the panel needs a moment to
        # process a command before it can accept the next write-without-response.
        # Without this, back-to-back commands (e.g. toggling freeze twice) can
        # silently drop the second write.
        await asyncio.sleep(0.5)

    async def turn_on(self) -> None:
        await self._write_raw(protocol.cmd_screen_power(True))

    async def turn_off(self) -> None:
        await self._write_raw(protocol.cmd_screen_power(False))

    async def set_brightness_pct(self, pct: int) -> None:
        await self._write_raw(protocol.cmd_brightness(pct))

    async def flip(self, flipped: bool) -> None:
        await self._write_raw(protocol.cmd_flip(flipped))

    async def toggle_freeze(self) -> None:
        await self._write_raw(protocol.cmd_toggle_freeze())

    async def set_speed(self, speed: int) -> None:
        await self._write_raw(protocol.cmd_speed(speed))

    async def reset(self) -> None:
        for packet in protocol.cmd_reset():
            await self._write_raw(packet)

    async def upload_image(self, png_bytes: bytes) -> None:
        plan = protocol.build_image_upload(png_bytes)
        for packet in plan.packets:
            await self._write_raw(packet)

    async def read_status(self) -> bytes:
        client = await self._ensure_connected()
        try:
            return bytes(await client.read_gatt_char(READ_CHAR_UUID))
        except (BleakError, TimeoutError) as err:
            raise IdotMatrixError(f"Read failed: {err}") from err
