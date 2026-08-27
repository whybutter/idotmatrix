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
