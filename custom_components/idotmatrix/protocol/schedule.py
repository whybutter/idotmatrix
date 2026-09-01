"""Programs / Schedule byte builders — SPECULATIVE (not yet hardware-verified).

Unlike `commands.py` (verified-only by policy), this module encodes the
Programs/Schedule feature whose layout currently comes from ONE source: the
`piggei/IDotMatrix-ESP32-Emulator` protocol captures, where the official app was
used as an oracle against an ESP32 pretending to be a panel. We own a real device
and can drive it, but this exact framing has NOT been confirmed on our hardware
yet — treat every offset here as provisional until a real-panel capture confirms
it. Kept out of `commands.py` deliberately.

A "program" is a set of activities. Each activity shows a piece of content
(GIF / PNG image / text) during a daily time window on selected weekdays. The
transfer choreography (per the emulator):

  1. `program_switch(enabled, sound)`  ->  ACK `05 00 07 80 01`
  2. for each activity: send the activity packet, wait for its completion
     ACK `05 00 05 80 03` (NOT `01` — `01` makes the app/device error and stops).
  3. no explicit "end of list" command; the device commits after a short idle.

Source: https://github.com/piggei/IDotMatrix-ESP32-Emulator/blob/HEAD/PROTOCOL.md
"""
from __future__ import annotations

import binascii

# Activity / alarm weekday-flag byte (shared convention per the emulator).
_ENABLED = 0x01
_WEEKDAY_BIT = {
    "mon": 0x02, "tue": 0x04, "wed": 0x08, "thu": 0x10,
    "fri": 0x20, "sat": 0x40, "sun": 0x80,
}

# contentType values (LE uint16 in the activity header).
CONTENT_GIF = 0x01
CONTENT_IMAGE = 0x02  # PNG file bytes (16x16 8-bit observed)
CONTENT_TEXT = 0x03


def weekday_flags(days: list[str] | None, *, enabled: bool = True) -> int:
    """Build the flags byte: bit0=enabled, bit1=Mon .. bit7=Sun. An empty/None
    day list yields a one-shot (weekday bits zero)."""
    flags = _ENABLED if enabled else 0
    for d in days or []:
        key = d.strip().lower()[:3]
        if key not in _WEEKDAY_BIT:
            raise ValueError(f"unknown weekday {d!r}")
        flags |= _WEEKDAY_BIT[key]
    return flags


def program_switch(enabled: bool, sound: bool = False) -> bytes:
    """Global program state: `05 00 07 80 FLAGS` (bit0=enabled, bit1=sound)."""
    flags = (0x01 if enabled else 0) | (0x02 if sound else 0)
    return bytes([0x05, 0x00, 0x07, 0x80, flags])


def build_schedule_activity(
    index: int,
    flags: int,
    start_h: int,
    start_m: int,
    end_h: int,
    end_m: int,
    content_type: int,
    payload: bytes,
    media_id: int = 0,
) -> bytes:
    """One activity packet (24-byte header + payload).

    Header (LE multi-byte):
        0..1  total length (header+payload)
        2     0x05
        3     0x80
        4     activity index (0-based)
        5     flags (enabled + weekday bits, see weekday_flags)
        6..9  start hour, start minute, end hour, end minute
        10..11 contentType (uint16 LE)
        12..15 payload size (uint32 LE)
        16..19 CRC32 of payload (uint32 LE)
        20..21 reserved (0)
        22     mediaId
        23..   payload
    """
    if not 0 <= index <= 255:
        raise ValueError("activity index must be 0-255")
    for h in (start_h, end_h):
        if not 0 <= h <= 23:
            raise ValueError("hours must be 0-23")
    for m in (start_m, end_m):
        if not 0 <= m <= 59:
            raise ValueError("minutes must be 0-59")
    if not payload:
        raise ValueError("activity payload cannot be empty")

    crc = binascii.crc32(payload) & 0xFFFFFFFF
    header = bytearray(23)
    total = 23 + len(payload)
    header[0:2] = total.to_bytes(2, "little")
    header[2] = 0x05
    header[3] = 0x80
    header[4] = index
    header[5] = flags & 0xFF
    header[6] = start_h
    header[7] = start_m
    header[8] = end_h
    header[9] = end_m
    header[10:12] = (content_type & 0xFFFF).to_bytes(2, "little")
    header[12:16] = len(payload).to_bytes(4, "little")
    header[16:20] = crc.to_bytes(4, "little")
    header[20:22] = (0).to_bytes(2, "little")
    header[22] = media_id & 0xFF
    return bytes(header) + payload
