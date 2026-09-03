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
    VERSION_CHAR_UUID,
    WRITE_CHAR_UUID,
)

# BLE sub-chunk size for bulk (image/GIF) writes. The official app uses ~514
# (full MTU) because it connects DIRECTLY, but over an ESPHome-style proxy (the
# WBRG1 gateway) a large write-without-response can be silently dropped while
# still reporting success. A small, conservative chunk is far more reliable
# through the proxy, at the cost of more (paced) writes.
IMAGE_SUBCHUNK_MAX = 180

# Cap connection retries so a busy/unreachable panel fails with a clear error in
# reasonable time instead of the connector retrying for ~30s+.
CONNECT_MAX_ATTEMPTS = 3

# Total album size above which the panel was measured to start silently dropping
# stored assets (see save_album). 280 KB stored reliably; 300 KB did not.
ALBUM_TOTAL_WARN_BYTES = 280 * 1024

_LOGGER = logging.getLogger(__name__)


class IdotMatrixError(Exception):
    """Raised when the panel can't be reached or a write fails."""


class IdotMatrixClient:
    def __init__(
        self, hass: HomeAssistant, address: str, preferred_source: str | None = None
    ) -> None:
        self._hass = hass
        self._address = address
        # Adapter/proxy MAC to force connections through, or None for auto
        # (HA picks the best signal). See the preferred-proxy option.
        self._preferred_source = preferred_source
        self._client: BleakClientWithServiceCache | None = None
        self._lock = asyncio.Lock()
        self._idle_handle: asyncio.TimerHandle | None = None
        self._notifications: asyncio.Queue[bytes] = asyncio.Queue()
        self._last_notification: bytes | None = None
        self._device_info: dict | None = None
        self._device_info_listeners: list = []
        self._connection_listener = None

    def set_connection_listener(self, cb) -> None:
        """Called with True/False on connect/disconnect (feeds availability so
        we stay 'available' while connected — the panel stops advertising then)."""
        self._connection_listener = cb

    def _notify_connection(self, connected: bool) -> None:
        if self._connection_listener is not None:
            self._connection_listener(connected)

    @property
    def address(self) -> str:
        return self._address

    @property
    def last_notification(self) -> bytes | None:
        """Most recent bytes the panel sent on the notify characteristic."""
        return self._last_notification

    @property
    def device_info(self) -> dict | None:
        """Parsed device-info the panel auto-pushes on connect (firmware, type)."""
        return self._device_info

    def add_device_info_listener(self, cb) -> callable:
        self._device_info_listeners.append(cb)

        def _unsub() -> None:
            if cb in self._device_info_listeners:
                self._device_info_listeners.remove(cb)

        return _unsub

    def _on_notify(self, _char, data: bytearray) -> None:
        """fa03 notification handler. The panel signals transfer readiness here
        (e.g. 05 00 01 00 01 = ready for next block) and answers queries; we log
        every frame and queue it for anyone awaiting an ack/response."""
        frame = bytes(data)
        self._last_notification = frame
        _LOGGER.debug("notify from %s: %s", self._address, frame.hex())
        self._notifications.put_nowait(frame)
        if (info := protocol.parse_device_info(frame)) is not None:
            # Merge, don't replace: firmware_full comes from a separate GATT read.
            self._device_info = {**(self._device_info or {}), **info}
            for cb in list(self._device_info_listeners):
                cb()

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

    async def show_effect(
        self, style: int, colors: list[tuple[int, int, int]], speed: int = 90
    ) -> None:
        await self._write(protocol.effect(style, colors, speed))

    async def show_album(self) -> None:
        """Switch the panel to its stored-asset carousel without re-uploading."""
        await self._write(protocol.enter_asset_view())

    async def draw_pixels(
        self, frames: list[bytes], pace: float = BULK_WRITE_PACE_SECONDS
    ) -> None:
        """Stream pre-built graffiti frames, fast.

        Unlike _write, this paces at BULK_WRITE_PACE_SECONDS (20 ms) instead of
        the 0.5 s command settle — graffiti frames are tiny, unacked, and meant
        to appear as a live stroke; a half-second per frame would make drawing
        crawl. The pace matches what the maintained fork uses for pixel writes.
        """
        async with self._lock:
            self._cancel_idle_timer()
            try:
                client = await self._ensure_connected()
                for frame in frames:
                    await client.write_gatt_char(WRITE_CHAR_UUID, frame, response=False)
                    await asyncio.sleep(max(pace, BULK_WRITE_PACE_SECONDS))
            except (BleakError, TimeoutError) as err:
                raise IdotMatrixError(
                    f"Pixel draw on {self._address} failed: {err}"
                ) from err
            finally:
                self._schedule_idle_disconnect()

    async def stop_rhythm(self) -> None:
        await self._write(protocol.rhythm_stop())

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

    async def mic_rhythm(self, style: int, sensitivity: int) -> None:
        await self._write(protocol.mic_rhythm(style, sensitivity))

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

    async def save_album(self, block_lists: list[list[bytes]]) -> None:
        """Write a persistent on-device asset album: wipe, then flash each
        image's asset blocks in order. The device then carousels them itself
        (interval baked into each asset header) — no flash, survives HA
        disconnects. block_lists come from protocol.build_gif_upload (asset
        variant) — albums send stills through it too, as single-frame GIFs; see
        light._prepare_still_as_gif. No DIY-mode enable on this path.

        The gating is derived per asset from the block's own type byte, so this
        still transports raw-pixel assets (protocol.build_asset_upload,
        type 0x02) correctly if a caller ever mixes them in."""
        # The panel stores each asset then auto-carousels them — there is no
        # "commit"/"show album" command; storing IS the display trigger. But
        # assets must be sent STRICTLY one at a time, each gated on the previous
        # asset's finish-ack — sending them back-to-back makes the panel drop
        # them (confirmed from the app's onFinishSend chaining).
        total_bytes = sum(len(b) for blocks in block_lists for b in blocks)
        if total_bytes > ALBUM_TOTAL_WARN_BYTES:
            # Measured: ~280 KB of album content stores fine, ~300 KB starts
            # silently dropping assets — they finish-ack normally but never
            # appear in the carousel. Warn rather than refuse; the exact ceiling
            # is firmware/model dependent and this is only an observed threshold.
            _LOGGER.warning(
                "Album is %.0f KB across %d assets, above the ~%.0f KB the panel "
                "was measured to hold — the panel may silently drop slides. "
                "Use fewer or shorter animations if slides go missing.",
                total_bytes / 1024,
                len(block_lists),
                ALBUM_TOTAL_WARN_BYTES / 1024,
            )
        async with self._lock:
            self._cancel_idle_timer()
            try:
                client = await self._ensure_connected()
                sub = self._image_subchunk_size(client)
                await self._write_paced(client, protocol.delete_all_assets(), sub)
                await asyncio.sleep(COMMAND_SETTLE_SECONDS)
                while not self._notifications.empty():
                    self._notifications.get_nowait()
                for n, blocks in enumerate(block_lists, 1):
                    # The panel's acks ECHO the asset's payload-type byte
                    # (header[2]): a GIF asset (0x01) acks 05 00 01 00 0x, a raw
                    # still asset (0x02) acks 05 00 02 00 0x. Deriving the marker
                    # from the block we actually sent is what makes the gating
                    # work for every asset type — hardcoding the GIF marker made
                    # still assets burn their whole timeout on every upload.
                    asset_type = blocks[0][2]
                    ready = bytes([0x05, 0x00, asset_type, 0x00, 0x01])
                    finish = bytes([0x05, 0x00, asset_type, 0x00, 0x03])
                    for j, block in enumerate(blocks):
                        await self._write_block(client, block, sub)
                        # Between 4K blocks the panel signals readiness on fa03.
                        # Match the marker strictly: accepting *any* notification
                        # lets an unrelated frame (device-info, a command ack)
                        # satisfy one block's wait, desyncing the queue so a later
                        # block consumes the previous block's ack and the transfer
                        # runs ahead of the panel.
                        if j < len(blocks) - 1:
                            if not await self._wait_for_ack(ready, timeout=8.0):
                                _LOGGER.warning(
                                    "Album asset %d/%d: no ready-ack after block "
                                    "%d/%d — continuing, the panel may drop it",
                                    n,
                                    len(block_lists),
                                    j + 1,
                                    len(blocks),
                                )
                    # Gate on this asset's finish before starting the next. A big
                    # GIF is many blocks and the panel needs longer to store +
                    # CRC-check it, so scale the timeout with size.
                    finish_timeout = min(30.0, 5.0 + 1.5 * len(blocks))
                    got = await self._wait_for_ack(finish, timeout=finish_timeout)
                    if got:
                        _LOGGER.debug(
                            "Album asset %d/%d stored", n, len(block_lists)
                        )
                    else:
                        _LOGGER.warning(
                            "Album asset %d/%d (%d block(s)): no finish-ack within "
                            "%.0fs — the panel may not have stored it (large GIFs "
                            "are the usual cause)",
                            n,
                            len(block_lists),
                            len(blocks),
                            finish_timeout,
                        )
                    # Small settle so the panel is ready for the next asset.
                    await asyncio.sleep(COMMAND_SETTLE_SECONDS)
            except (BleakError, TimeoutError) as err:
                raise IdotMatrixError(
                    f"Album save to {self._address} failed: {err}"
                ) from err
            finally:
                self._schedule_idle_disconnect()

    async def clear_album(self) -> None:
        """Wipe the device asset album (stops the carousel)."""
        await self._write(protocol.delete_all_assets())

    async def _write_paced(self, client, data: bytes, sub: int) -> None:
        for i in range(0, len(data), sub):
            await client.write_gatt_char(
                WRITE_CHAR_UUID, data[i : i + sub], response=False
            )
            await asyncio.sleep(BULK_WRITE_PACE_SECONDS)

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

    def _select_ble_device(self):
        """Pick the BLEDevice to connect through.

        With a preferred proxy configured, use that specific scanner's device
        (bypassing HA's signal-based pick — useful when the strongest proxy is
        unreliable). Falls back to auto if the preferred proxy isn't currently
        seeing the panel.
        """
        if self._preferred_source:
            for dev in bluetooth.async_scanner_devices_by_address(
                self._hass, self._address, connectable=True
            ):
                if dev.scanner.source == self._preferred_source:
                    return dev.ble_device
            _LOGGER.debug(
                "Preferred proxy %s doesn't see %s right now; using best available",
                self._preferred_source,
                self._address,
            )
        return bluetooth.async_ble_device_from_address(
            self._hass, self._address, connectable=True
        )

    @staticmethod
    def _image_subchunk_size(client: BleakClientWithServiceCache) -> int:
        mtu = getattr(client, "mtu_size", 0) or 0
        usable = (mtu - 3) if mtu > 3 else IMAGE_SUBCHUNK_MAX
        return min(usable, IMAGE_SUBCHUNK_MAX)

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

    async def _wait_for_ack(self, marker: bytes, timeout: float = 4.0) -> bool:
        """Drain fa03 notifications until one starts with ``marker`` (ignoring
        unrelated frames like device-info), or the timeout elapses. Returns True
        if the marker was seen. Used to gate album asset transfers on the panel's
        per-block ready ack (05 00 01 00 01) and per-asset finish ack
        (05 00 01 00 03)."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                return False
            try:
                frame = await asyncio.wait_for(
                    self._notifications.get(), timeout=remaining
                )
            except (TimeoutError, asyncio.TimeoutError):
                return False
            if frame.startswith(marker):
                return True

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

        ble_device = self._select_ble_device()
        if ble_device is None:
            raise IdotMatrixError(
                f"No BLE proxy currently sees {self._address} — check the panel is "
                "powered and in range of an active proxy, and that the proxy "
                "(gateway) is online"
            )
        try:
            self._client = await establish_connection(
                BleakClientWithServiceCache,
                ble_device,
                self._address,
                max_attempts=CONNECT_MAX_ATTEMPTS,
            )
        except (BleakError, TimeoutError) as err:
            # Common causes: the official phone app holds the panel's single BLE
            # connection, or the proxy/gateway is flaky. Surface both.
            raise IdotMatrixError(
                f"Couldn't connect to the panel ({self._address}). It may be in "
                "use by the iDotMatrix phone app (close it), or its BLE proxy "
                f"may be unreachable. ({err})"
            ) from err

        # Over a weak/distant proxy the link can come up but GATT service
        # discovery is incomplete ("partial" connection) — the write
        # characteristic is then missing. Detect that and give an actionable
        # error instead of a cryptic "characteristic not found" mid-write.
        if self._client.services.get_characteristic(WRITE_CHAR_UUID) is None:
            try:
                await self._client.clear_cache()
            except (BleakError, AttributeError) as err:
                _LOGGER.debug("clear_cache failed: %s", err)
            await self._disconnect_locked()
            raise IdotMatrixError(
                f"Connected to {self._address} but couldn't read its services "
                "(weak BLE link — the proxy is too far). Pin a closer/stronger "
                "proxy in the integration options."
            )

        # The panel needs notifications enabled on fa03 to accept a bulk
        # transfer (the official app subscribes before uploading) and uses them
        # to answer queries. Subscribe once per connection; best-effort.
        try:
            await self._client.start_notify(READ_CHAR_UUID, self._on_notify)
        except (BleakError, TimeoutError) as err:
            _LOGGER.debug("Could not subscribe to notifications: %s", err)
        await self._read_firmware_version(self._client)
        await self._sync_time(self._client)
        self._notify_connection(True)
        return self._client

    async def _read_firmware_version(self, client: BleakClientWithServiceCache) -> None:
        """Read the firmware version string from its dedicated GATT characteristic
        (found by dallanwagz/idotmatrix-ha) — a fuller ASCII string than the
        major.minor in the auto-pushed device-info frame. Best-effort: older
        firmwares may not expose it, and it must never fail the connection."""
        if self._device_info and self._device_info.get("firmware_full"):
            return
        try:
            raw = await client.read_gatt_char(VERSION_CHAR_UUID)
        except (BleakError, TimeoutError, OSError) as err:
            _LOGGER.debug("No firmware-version characteristic: %s", err)
            return
        version = raw.decode("ascii", errors="replace").strip("\x00 \r\n")
        if not version:
            return
        self._device_info = {**(self._device_info or {}), "firmware_full": version}
        for cb in list(self._device_info_listeners):
            cb()

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
            await self._disconnect_locked()

    async def _disconnect_locked(self) -> None:
        """Tear down the connection. Caller must hold the lock."""
        self._cancel_idle_timer()
        if self._client is not None:
            try:
                await self._client.disconnect()
            except BleakError as err:
                _LOGGER.debug("Error disconnecting from %s: %s", self._address, err)
            self._client = None
        self._notify_connection(False)
