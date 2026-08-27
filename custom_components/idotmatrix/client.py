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
from homeassistant.util import dt as dt_util

from . import protocol
from .const import (
    BULK_WRITE_PACE_SECONDS,
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
        self._notifications: asyncio.Queue[bytes] = asyncio.Queue()
        self._last_notification: bytes | None = None

    @property
    def address(self) -> str:
        return self._address

    @property
    def last_notification(self) -> bytes | None:
        """Most recent bytes the panel sent on the notify characteristic."""
        return self._last_notification

    def _on_notify(self, _char, data: bytearray) -> None:
        """fa03 notification handler. The panel signals transfer readiness here
        (e.g. 05 00 01 00 01 = ready for next block) and answers queries; we log
        every frame and queue it for anyone awaiting an ack/response."""
        frame = bytes(data)
        self._last_notification = frame
        _LOGGER.debug("notify from %s: %s", self._address, frame.hex())
        self._notifications.put_nowait(frame)

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

    async def set_eco(
        self,
        enabled: bool,
        start_h: int,
        start_m: int,
        end_h: int,
        end_m: int,
        eco_brightness: int,
    ) -> None:
        await self._write(
            protocol.eco(enabled, start_h, start_m, end_h, end_m, eco_brightness)
        )

    async def set_screen_on_time(self, value: int) -> None:
        await self._write(protocol.screen_on_time(value))

    async def upload_image(self, pixel_bytes: bytes) -> None:
        """Upload a still image.

        `pixel_bytes` must already be raw R,G,B (see light._prepare_pixels). The
        bulk path is different from the short commands: enter DIY mode, then send
        per-4K-block framing with write-with-response and an ack round-trip on
        the notify characteristic after each block. Sending it blind — or without
        response — leaves the panel black.
        """
        blocks = protocol.build_image_upload(pixel_bytes)
        await self._send_bulk(blocks, enter_diy=True, label="Image")

    async def upload_gif(self, gif_bytes: bytes) -> None:
        """Upload an animated GIF (encoded .gif bytes, not raw pixels).

        Same block+ack transport as image, but with the GIF's own 16-byte
        headers (CRC32) and no DIY-mode enable (that's the still-image path).
        """
        blocks = protocol.build_gif_upload(gif_bytes)
        await self._send_bulk(blocks, enter_diy=False, label="GIF")

    async def send_text(
        self,
        bitmaps: bytes,
        mode: int,
        speed: int,
        color_mode: int,
        color: tuple[int, int, int],
        bg_mode: int,
        bg_color: tuple[int, int, int],
    ) -> None:
        """Send rendered text. Unlike image/GIF, text is a single stream
        (header+metadata+bitmaps) written write-without-response and fragmented
        by MTU underneath — no 4K blocks, no ack."""
        payload = protocol.build_text_packet(
            bitmaps, mode, speed, color_mode, color, bg_mode, bg_color
        )
        await self._write(payload)

    async def _send_bulk(
        self, blocks: list[bytes], *, enter_diy: bool, label: str
    ) -> None:
        async with self._lock:
            self._cancel_idle_timer()
            try:
                client = await self._ensure_connected()
                if enter_diy:
                    # response=False like the other short commands (all of which
                    # work over the proxy); with-response risks GATT error 133.
                    await client.write_gatt_char(
                        WRITE_CHAR_UUID, protocol.diy_mode(True), response=False
                    )
                    await asyncio.sleep(COMMAND_SETTLE_SECONDS)
                sub = self._image_subchunk_size(client)
                _LOGGER.debug(
                    "%s upload: %d block(s), sub-chunk %d, mtu %s, enter_diy=%s",
                    label,
                    len(blocks),
                    sub,
                    getattr(client, "mtu_size", "?"),
                    enter_diy,
                )
                # Clear any stale notifications before the transfer.
                while not self._notifications.empty():
                    self._notifications.get_nowait()
                for n, block in enumerate(blocks, 1):
                    await self._write_block(client, block, sub)
                    _LOGGER.debug("%s block %d/%d written", label, n, len(blocks))
                    if n < len(blocks):
                        await self._wait_for_block_ack()
            except (BleakError, TimeoutError) as err:
                raise IdotMatrixError(
                    f"{label} upload to {self._address} failed: {err}"
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
        """Write one 4K bulk block, split into paced BLE sub-writes.

        Confirmed against the official app's own BLE log: writes to fa02 are
        write-WITHOUT-response (write-with-response gives GATT error 133 over
        the WBRG1 proxy), MTU 517, and the app paces sub-writes ~20ms apart.
        Without the pacing the proxy silently drops packets and the panel stays
        black; the delay is the flow control.
        """
        for i in range(0, len(block), sub):
            await client.write_gatt_char(
                WRITE_CHAR_UUID, block[i : i + sub], response=False
            )
            await asyncio.sleep(BULK_WRITE_PACE_SECONDS)

    async def _wait_for_block_ack(self) -> None:
        """Between 4K blocks the panel notifies readiness (05 00 01 00 01) on
        fa03. Best-effort: wait briefly for any notification, else continue."""
        try:
            await asyncio.wait_for(self._notifications.get(), timeout=2.0)
        except (TimeoutError, asyncio.TimeoutError):
            _LOGGER.debug("No block ack notification; continuing")

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
        # The panel needs notifications enabled on fa03 to accept a bulk
        # transfer (the official app subscribes before uploading) and uses them
        # to answer queries. Subscribe once per connection; best-effort.
        try:
            await self._client.start_notify(READ_CHAR_UUID, self._on_notify)
        except (BleakError, TimeoutError) as err:
            _LOGGER.debug("Could not subscribe to notifications: %s", err)
        await self._sync_time(self._client)
        return self._client

    async def _sync_time(self, client: BleakClientWithServiceCache) -> None:
        """Push the current local time on connect so on-device clock/schedule
        features are accurate. Best-effort — never fail the connection over it."""
        try:
            await client.write_gatt_char(
                WRITE_CHAR_UUID, protocol.set_time(dt_util.now()), response=False
            )
            await asyncio.sleep(COMMAND_SETTLE_SECONDS)
        except (BleakError, TimeoutError) as err:
            _LOGGER.debug("Time sync on connect skipped: %s", err)

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
