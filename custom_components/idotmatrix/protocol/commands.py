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


def toggle_freeze() -> bytes:
    """Single fixed toggle command — the panel keeps the state, we can't read it."""
    return bytes([0x04, 0x00, 0x03, 0x00])


def speed(value: int) -> bytes:
    """Animation/scroll speed. Not referenced by the official app per the
    maintained fork; likely only affects animated modes (text/clock/effects)."""
    if not 0 <= value <= 255:
        raise ValueError("speed must be 0-255")
    return bytes([0x05, 0x00, 0x03, 0x01, value])


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


def reset_sequence() -> tuple[bytes, ...]:
    """General 'fix the panel' reset.

    The maintained fork sends only the first frame (credited to 8none1); the
    original archived library followed it with a brightness reset to 80%. We
    keep both — a fixed brightness afterwards is deterministic and harmless.
    """
    return (bytes([0x04, 0x00, 0x03, 0x80]), brightness(80))
