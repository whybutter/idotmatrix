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
from .const import (
    COMMAND_SETTLE_SECONDS,
    IDLE_DISCONNECT_SECONDS,
    READ_CHAR_UUID,
    WRITE_CHAR_UUID,
)

# Fallback BLE sub-chunk size for image data when the negotiated MTU can't be
# read. Matches the official app / maintained fork (509 bytes when a large MTU
# is negotiated).
IMAGE_SUBCHUNK_FALLBACK = 509

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

    async def set_speed(self, value: int) -> None:
        await self._write(protocol.speed(value))

    async def reset(self) -> None:
        await self._write(protocol.reset())

    # -- native display modes --

    async def fullscreen_color(self, r: int, g: int, b: int) -> None:
        await self._write(protocol.fullscreen_color(r, g, b))

    async def show_clock(
        self, style: int, show_date: bool, hour24: bool, r: int, g: int, b: int
    ) -> None:
        await self._write(protocol.clock(style, show_date, hour24, r, g, b))

    async def show_effect(self, style: int, colors: list[tuple[int, int, int]]) -> None:
        await self._write(protocol.effect(style, colors))

    async def chronograph(self, mode: int) -> None:
        await self._write(protocol.chronograph(mode))

    async def countdown(self, mode: int, minutes: int, seconds: int) -> None:
        await self._write(protocol.countdown(mode, minutes, seconds))

    async def scoreboard(self, count1: int, count2: int) -> None:
        await self._write(protocol.scoreboard(count1, count2))

    async def upload_image(self, pixel_bytes: bytes) -> None:
        """Upload a still image.

        `pixel_bytes` must already be in the panel's native G,R,B order
        (see light._prepare_pixels). The DIY image path is different from the
        short commands: it needs write-with-response, per-4K-block framing, and
        an ack round-trip on the notify characteristic after each block (the
        panel signals it's ready for the next block). Sending it blind — or
        without response — leaves the panel black.
        """
        blocks = protocol.build_image_upload(pixel_bytes)
        async with self._lock:
            self._cancel_idle_timer()
            try:
                client = await self._ensure_connected()
                # Enter DIY draw mode (short command, with response).
                await client.write_gatt_char(
                    WRITE_CHAR_UUID, protocol.diy_mode(True), response=True
                )
                await asyncio.sleep(COMMAND_SETTLE_SECONDS)
                sub = self._image_subchunk_size(client)
                for block in blocks:
                    await self._write_block(client, block, sub)
            except (BleakError, TimeoutError) as err:
                raise IdotMatrixError(
                    f"Image upload to {self._address} failed: {err}"
                ) from err
            finally:
                self._schedule_idle_disconnect()

    @staticmethod
    def _image_subchunk_size(client: BleakClientWithServiceCache) -> int:
        mtu = getattr(client, "mtu_size", 0) or 0
        return (mtu - 3) if mtu > 3 else IMAGE_SUBCHUNK_FALLBACK

    async def _write_block(
        self, client: BleakClientWithServiceCache, block: bytes, sub: int
    ) -> None:
        """Write one 4K DIY block, split into BLE sub-writes.

        All sub-writes are write-without-response except the last, which is
        write-with-response; then we read the notify characteristic once. That
        read is the block-level ack round-trip the panel needs before the next
        block (mirrors the maintained fork, which is known to work on real
        hardware). Best-effort: some stacks refuse the read, which is fine.
        """
        for i in range(0, len(block), sub):
            piece = block[i : i + sub]
            is_last = i + sub >= len(block)
            await client.write_gatt_char(WRITE_CHAR_UUID, piece, response=is_last)
        try:
            await client.read_gatt_char(READ_CHAR_UUID)
        except (BleakError, TimeoutError) as err:
            _LOGGER.debug("Image block ack read skipped: %s", err)

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
