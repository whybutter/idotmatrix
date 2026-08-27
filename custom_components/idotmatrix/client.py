"""BLE connection management for the iDotMatrix panel.

All connections go through HA's Bluetooth stack: the BLEDevice comes from
`bluetooth.async_ble_device_from_address`, so HA transparently routes the
GATT connection through whichever adapter or active proxy currently sees the
panel. This module never touches a local hci adapter directly.

Design points:
- A single asyncio lock serializes all writes; the panel is a single-session
  device and interleaved commands corrupt its state.
- Every write is followed by a settle delay (COMMAND_SETTLE_SECONDS) — the
  panel silently drops a command that arrives while it is still processing
  the previous one.
- The connection is dropped after IDLE_DISCONNECT_SECONDS of inactivity so
  we don't permanently occupy one of the proxy's limited connection slots.
"""
from __future__ import annotations

import asyncio
import logging

from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant, callback

from . import protocol
from .const import COMMAND_SETTLE_SECONDS, IDLE_DISCONNECT_SECONDS, WRITE_CHAR_UUID

_LOGGER = logging.getLogger(__name__)


class IdotMatrixError(Exception):
    """Raised when the panel can't be reached or a write fails."""


class IdotMatrixClient:
    def __init__(self, hass: HomeAssistant, address: str) -> None:
        self._hass = hass
        self._address = address
        self._client: BleakClientWithServiceCache | None = None
        self._lock = asyncio.Lock()
        self._idle_handle: asyncio.TimerHandle | None = None

    @property
    def address(self) -> str:
        return self._address

    # -- high-level commands --

    async def turn_on(self) -> None:
        await self._write(protocol.screen_power(True))

    async def turn_off(self) -> None:
        await self._write(protocol.screen_power(False))

    async def set_brightness_pct(self, pct: int) -> None:
        await self._write(protocol.brightness(pct))

    async def set_flip(self, flipped: bool) -> None:
        await self._write(protocol.flip(flipped))

    async def toggle_freeze(self) -> None:
        await self._write(protocol.toggle_freeze())

    async def set_speed(self, value: int) -> None:
        await self._write(protocol.speed(value))

    async def reset(self) -> None:
        await self._write(*protocol.reset_sequence())

    async def upload_image(self, rgb_bytes: bytes) -> None:
        # DIY mode must be active for the panel to accept pixel data.
        await self._write(
            protocol.diy_mode(True), *protocol.build_image_upload(rgb_bytes)
        )

    # -- connection plumbing --

    async def _write(self, *frames: bytes) -> None:
        async with self._lock:
            self._cancel_idle_timer()
            try:
                client = await self._ensure_connected()
                for frame in frames:
                    # bleak fragments per negotiated MTU internally for
                    # write-without-response payloads larger than mtu-3.
                    await client.write_gatt_char(WRITE_CHAR_UUID, frame, response=False)
                    await asyncio.sleep(COMMAND_SETTLE_SECONDS)
            except (BleakError, TimeoutError) as err:
                raise IdotMatrixError(f"Write to {self._address} failed: {err}") from err
            finally:
                self._schedule_idle_disconnect()

    async def _ensure_connected(self) -> BleakClientWithServiceCache:
        if self._client is not None and self._client.is_connected:
            return self._client

        ble_device = bluetooth.async_ble_device_from_address(
            self._hass, self._address, connectable=True
        )
        if ble_device is None:
            raise IdotMatrixError(
                f"No adapter or active proxy currently sees {self._address}; "
                "check the panel is powered and in range of an active BLE proxy"
            )
        try:
            self._client = await establish_connection(
                BleakClientWithServiceCache, ble_device, self._address
            )
        except (BleakError, TimeoutError) as err:
            raise IdotMatrixError(
                f"Failed to connect to {self._address}: {err}"
            ) from err
        return self._client

    @callback
    def _schedule_idle_disconnect(self) -> None:
        self._cancel_idle_timer()
        self._idle_handle = self._hass.loop.call_later(
            IDLE_DISCONNECT_SECONDS,
            lambda: self._hass.async_create_task(self.disconnect()),
        )

    @callback
    def _cancel_idle_timer(self) -> None:
        if self._idle_handle is not None:
            self._idle_handle.cancel()
            self._idle_handle = None

    async def disconnect(self) -> None:
        async with self._lock:
            self._cancel_idle_timer()
            if self._client is not None:
                try:
                    await self._client.disconnect()
                except BleakError as err:
                    _LOGGER.debug("Error disconnecting from %s: %s", self._address, err)
                self._client = None
