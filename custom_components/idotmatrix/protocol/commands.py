"""Byte builders for the panel's simple commands.

Generic framing: [len_lsb, len_msb, opcode, subopcode/flag, ...payload]
where len is the total packet length (little-endian, includes the two
length bytes themselves).

All commands below are validated against real hardware or byte-identical to
the maintained forks; anything speculative stays out of this module.
"""
from __future__ import annotations

from datetime import datetime


def screen_power(on: bool) -> bytes:
    return bytes([0x05, 0x00, 0x07, 0x01, 0x01 if on else 0x00])


def brightness(pct: int) -> bytes:
    if not 5 <= pct <= 100:
        raise ValueError("brightness must be 5-100")
    return bytes([0x05, 0x00, 0x04, 0x80, pct])


def flip(flipped: bool) -> bytes:
    return bytes([0x05, 0x00, 0x06, 0x80, 0x01 if flipped else 0x00])


def speed(value: int) -> bytes:
    """Animation/scroll speed. Not referenced by the official app per the
    maintained fork; likely only affects animated modes (text/clock/effects)."""
    if not 0 <= value <= 255:
        raise ValueError("speed must be 0-255")
    return bytes([0x05, 0x00, 0x03, 0x01, value])


def diy_mode(enable: bool) -> bytes:
    """Enter/exit DIY draw mode. Must be enabled before uploading pixel data.

    Full mode set (the app's DiyImageFun enum, named by dallanwagz/idotmatrix-ha):
    0=quit without saving, 1=enter and clear, 2=quit but keep showing the current
    still, 3=enter without clearing. We use 0/1 today.
    """
    return bytes([0x05, 0x00, 0x04, 0x01, 0x01 if enable else 0x00])


def set_time(dt: datetime) -> bytes:
    return bytes(
        [
            0x0B,
            0x00,
            0x01,
            0x80,
            dt.year % 100,
            dt.month,
            dt.day,
            dt.isoweekday(),
            dt.hour,
            dt.minute,
            dt.second,
        ]
    )


def reset() -> bytes:
    """General 'fix the panel' reset.

    Confirmed by disassembling the official app (BleProtocolN.restDevice): a
    single frame, no brightness follow-up. Wipes content back to defaults.
    """
    return bytes([0x04, 0x00, 0x03, 0x80])


# --- native display modes (short commands; byte-identical across two repos) ---


def fullscreen_color(r: int, g: int, b: int) -> bytes:
    """Fill the whole panel with one solid RGB color."""
    for v in (r, g, b):
        if not 0 <= v <= 255:
            raise ValueError("color components must be 0-255")
    return bytes([0x07, 0x00, 0x02, 0x02, r, g, b])


def clock(style: int, show_date: bool, hour24: bool, r: int, g: int, b: int) -> bytes:
    """Show the on-device clock. style 0-7; flags packed into one byte."""
    if not 0 <= style <= 7:
        raise ValueError("clock style must be 0-7")
    flags = style | (0x80 if show_date else 0) | (0x40 if hour24 else 0)
    return bytes([0x08, 0x00, 0x06, 0x01, flags, r % 256, g % 256, b % 256])


def effect(style: int, colors: list[tuple[int, int, int]], speed: int = 90) -> bytes:
    """Built-in animated background ("MutilColor"). style 0-6; 2-7 RGB colors;
    speed 0-100 (the app's lightning-bolt slider).

    Frame per the app's MutilColorAgreement, hardware-confirmed on a 32x32 by
    dallanwagz/idotmatrix-ha (device acks 05 00 03 02 01): a NORMAL little-endian
    total length (7 + 3*n_colors) — the old "0x06 + n_colors" first byte copied
    from the maintained fork was wrong — and full-range 0-255 RGB. Channel
    value 1 is reserved by the firmware and remapped to 0, matching the app.
    """
    if not 0 <= style <= 6:
        raise ValueError("effect style must be 0-6")
    if not 2 <= len(colors) <= 7:
        raise ValueError("effect needs 2-7 colors")
    if not 0 <= speed <= 100:
        raise ValueError("effect speed must be 0-100")
    total = 7 + 3 * len(colors)
    body = bytearray([total & 0xFF, (total >> 8) & 0xFF, 0x03, 0x02, style, speed, len(colors)])
    for color in colors:
        body += bytes(0 if v % 256 == 1 else v % 256 for v in color)
    return bytes(body)


def chronograph(mode: int) -> bytes:
    """Stopwatch. mode: 0=reset+show, 1=start, 2=pause, 3=resume."""
    if not 0 <= mode <= 3:
        raise ValueError("chronograph mode must be 0-3")
    return bytes([0x05, 0x00, 0x09, 0x80, mode])


def countdown(mode: int, minutes: int, seconds: int) -> bytes:
    """Timer. mode: 0=disable, 1=start, 2=pause, 3=restart. minutes/seconds 0-59."""
    if not 0 <= mode <= 3:
        raise ValueError("countdown mode must be 0-3")
    if not 0 <= minutes <= 59 or not 0 <= seconds <= 59:
        raise ValueError("countdown minutes/seconds must be 0-59")
    return bytes([0x07, 0x00, 0x08, 0x80, mode, minutes, seconds])


def scoreboard(count1: int, count2: int) -> bytes:
    """Two counters, each 0-999 (clamped; higher risks a device overflow)."""
    c1 = max(0, min(999, count1))
    c2 = max(0, min(999, count2))
    return bytes(
        [0x08, 0x00, 0x0A, 0x80, c1 & 0xFF, (c1 >> 8) & 0xFF, c2 & 0xFF, (c2 >> 8) & 0xFF]
    )


def eco(
    enabled: bool,
    start_h: int,
    start_m: int,
    end_h: int,
    end_m: int,
    eco_brightness: int,
) -> bytes:
    """Energy-saving auto-dim window: between start and end the panel drops to
    eco_brightness. Times 0-23h / 0-59m; brightness 0-255."""
    for h in (start_h, end_h):
        if not 0 <= h <= 23:
            raise ValueError("hours must be 0-23")
    for m in (start_m, end_m):
        if not 0 <= m <= 59:
            raise ValueError("minutes must be 0-59")
    if not 0 <= eco_brightness <= 255:
        raise ValueError("eco brightness must be 0-255")
    return bytes(
        [
            0x0A,
            0x00,
            0x02,
            0x80,
            1 if enabled else 0,
            start_h,
            start_m,
            end_h,
            end_m,
            eco_brightness,
        ]
    )


def screen_on_time(value: int) -> bytes:
    """Auto screen-off timeout (cmd 0x0f, from the app disassembly). Value is a
    device-defined unit (0-255)."""
    if not 0 <= value <= 255:
        raise ValueError("screen-on-time value must be 0-255")
    return bytes([0x05, 0x00, 0x0F, 0x80, value])


def delete_all_assets() -> bytes:
    """Wipe the panel's stored asset album. The on-device album is write-only
    (no per-slot delete), so replacing it = delete-all then re-flash in order.
    Confirmed byte-exact from the app (Agreement.deleteDeviceMaterial)."""
    return bytes(
        [0x11, 0x00, 0x02, 0x01, 0x0C, 0x00, 0x01, 0x02, 0x03, 0x04,
         0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B]
    )


# Carousel interval: the device's ConvertTime maps a key to seconds. Only these
# intervals are representable; the panel auto-rotates stored assets at this rate.
_INTERVAL_KEY_SECONDS = {1: 10, 2: 30, 3: 60, 4: 300}


def convert_time(key: int) -> int:
    """seconds for a time-sign key (1->10,2->30,3->60,4->300, else->5; 12->none)."""
    return _INTERVAL_KEY_SECONDS.get(key, 5)


def seconds_to_time_key(seconds: int) -> int:
    """Nearest device-supported interval key for a desired seconds value."""
    if seconds <= 7:
        return 0  # -> 5s (any non-1..4 key)
    if seconds <= 20:
        return 1  # 10s
    if seconds <= 45:
        return 2  # 30s
    if seconds <= 150:
        return 3  # 60s
    return 4  # 300s


def enter_asset_view() -> bytes:
    """Switch the panel to its stored-asset (album/carousel) view.

    The app sends this on the Device Material tab (PatternFragment); it makes the
    panel show and cycle whatever assets are stored, without re-uploading them.
    Cross-confirmed by dallanwagz/idotmatrix-ha as the carousel-start command.
    """
    return bytes([0x04, 0x00, 0x0A, 0x01])


def request_device_info() -> bytes:
    """Query LED type / device info (BleProtocolN.getLedType). The panel answers
    on fa03 with the same 09 00 01 80 ... frame it auto-pushes on connect."""
    return bytes([0x04, 0x00, 0x01, 0x80])


def rhythm_stop() -> bytes:
    """Stop the phone-audio rhythm visualizer (BleProtocolN.sendStopMicRhythm).
    Cross-confirmed by both the ESP32 emulator project and dallanwagz."""
    return bytes([0x06, 0x00, 0x00, 0x02, 0x00, 0x00])


# Streamed phone-audio spectrum frames: a constant 5-byte prefix followed by 16
# column heights = 8 band magnitudes mirrored left-right (symmetric bars). Sent
# raw at ~12 fps, no envelope/CRC. Wire-captured golden frame (dallanwagz):
# 2100010202 0a05040202040202 0202040202 0405 0a from bands [a,5,4,2,2,4,2,2].
RHYTHM_PREFIX = bytes([0x21, 0x00, 0x01, 0x02, 0x02])


def rhythm_frame(bands: list[int]) -> bytes:
    """One streamed spectrum frame from 8 band magnitudes (0-~31)."""
    b = [max(0, min(255, int(v))) for v in bands][:8]
    b += [0] * (8 - len(b))
    return RHYTHM_PREFIX + bytes(b + b[::-1])


def mic_rhythm(style: int, sensitivity: int) -> bytes:
    """On-device microphone reactive visualizer (BleProtocolN.sendMicCommand1).
    One frame carries both the style (mode index) and sensitivity (0-100);
    re-send to change either live."""
    if not 0 <= style <= 255:
        raise ValueError("mic style must be 0-255")
    if not 0 <= sensitivity <= 100:
        raise ValueError("mic sensitivity must be 0-100")
    return bytes([0x06, 0x00, 0x0B, 0x80, style, sensitivity])


# panel_type ("ledType") -> pixel dimensions, from the app's AppData.setLedType
# (via dallanwagz/idotmatrix-ha). Marco's panel reports type 3 = 32x32.
PANEL_TYPE_SIZES = {
    1: (16, 16),
    2: (8, 32),
    3: (32, 32),
    4: (64, 64),
    6: (24, 48),
    7: (16, 32),
    11: (16, 64),
}


def parse_device_info(frame: bytes) -> dict | None:
    """Parse the panel's auto-pushed device-info notification.

    Frame: 09 00 01 80 <fw_major> <fw_minor> <sub> <panel_type> <flag>
    (from MainActivity's fa03 notify handler). Firmware over BLE is only
    major.minor; the app's fuller version string comes from a cloud API.
    """
    if len(frame) < 9 or frame[2] != 0x01 or frame[3] != 0x80:
        return None
    panel_type = frame[7]
    size = PANEL_TYPE_SIZES.get(panel_type)
    return {
        "firmware": f"{frame[4]}.{frame[5]:02d}",
        "panel_type": panel_type,
        "panel_size": f"{size[0]}x{size[1]}" if size else None,
    }
