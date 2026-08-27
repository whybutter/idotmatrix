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
    """Enter/exit DIY draw mode. Must be enabled before uploading pixel data
    (from the app decompile via the maintained fork: modes 2/3 exist but are
    unknown)."""
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


def effect(style: int, colors: list[tuple[int, int, int]]) -> bytes:
    """Built-in animated background. style 0-6; 2-7 RGB colors."""
    if not 0 <= style <= 6:
        raise ValueError("effect style must be 0-6")
    if not 2 <= len(colors) <= 7:
        raise ValueError("effect needs 2-7 colors")
    body = bytearray([0x06 + len(colors), 0x00, 0x03, 0x02, style % 256, 0x90, len(colors)])
    for r, g, b in colors:
        body += bytes([r % 256, g % 256, b % 256])
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


def mic_rhythm(style: int, sensitivity: int) -> bytes:
    """On-device microphone reactive visualizer (BleProtocolN.sendMicCommand1).
    One frame carries both the style (mode index) and sensitivity (0-100);
    re-send to change either live."""
    if not 0 <= style <= 255:
        raise ValueError("mic style must be 0-255")
    if not 0 <= sensitivity <= 100:
        raise ValueError("mic sensitivity must be 0-100")
    return bytes([0x06, 0x00, 0x0B, 0x80, style, sensitivity])


def parse_device_info(frame: bytes) -> dict | None:
    """Parse the panel's auto-pushed device-info notification.

    Frame: 09 00 01 80 <fw_major> <fw_minor> <sub> <panel_type> <flag>
    (from MainActivity's fa03 notify handler). Firmware over BLE is only
    major.minor; the app's fuller version string comes from a cloud API.
    """
    if len(frame) < 9 or frame[2] != 0x01 or frame[3] != 0x80:
        return None
    return {
        "firmware": f"{frame[4]}.{frame[5]:02d}",
        "panel_type": frame[7],
    }
