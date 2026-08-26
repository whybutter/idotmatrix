"""Pure byte-protocol helpers for the iDotMatrix BLE panel.

Ported from the archived `derkalle4/python3-idotmatrix-library` (common.py /
image.py), as reverse-engineered and documented 2026-08-13 in the vault note
"iDotMatrix ESP32 Bridge.md". No BLE I/O here on purpose — keep this module
pure/testable, the actual GATT write happens in ble.py.

Generic command framing: [len_lsb, len_msb, opcode, subopcode/flag, ...payload]
where len is the total packet length (little-endian, includes the length
bytes themselves).
"""
from __future__ import annotations

from dataclasses import dataclass


def cmd_toggle_freeze() -> bytes:
    """Documented as a single fixed toggle command (no on/off parameter)."""
    return bytes([0x04, 0x00, 0x03, 0x00])


def cmd_screen_power(on: bool) -> bytes:
    return bytes([0x05, 0x00, 0x07, 0x01, 0x01 if on else 0x00])


def cmd_flip(flipped: bool) -> bytes:
    return bytes([0x05, 0x00, 0x06, 0x80, 0x01 if flipped else 0x00])


def cmd_brightness(pct: int) -> bytes:
    if not 5 <= pct <= 100:
        raise ValueError("brightness must be 5-100")
    return bytes([0x05, 0x00, 0x04, 0x80, pct])


def cmd_speed(speed: int) -> bytes:
    if not 0 <= speed <= 255:
        raise ValueError("speed must be 0-255")
    return bytes([0x05, 0x00, 0x03, 0x01, speed])


def cmd_set_time(dt) -> bytes:
    """dt: a datetime-like object with year/month/day/hour/minute/second/weekday()."""
    yy = dt.year % 100
    weekday = dt.isoweekday()  # library uses weekday+1, ISO Monday=1..Sunday=7
    return bytes(
        [
            0x0B,
            0x00,
            0x01,
            0x80,
            yy,
            dt.month,
            dt.day,
            weekday,
            dt.hour,
            dt.minute,
            dt.second,
        ]
    )


def cmd_reset() -> list[bytes]:
    """Reset is two writes: a generic reset, then brightness fixed to 80%."""
    return [bytes([0x04, 0x00, 0x03, 0x80]), bytes([0x05, 0x00, 0x04, 0x80, 0x50])]


@dataclass
class ImageUploadPlan:
    """Sequence of raw packets to write to the panel, in order."""

    packets: list[bytes]


def build_image_upload(png_bytes: bytes) -> ImageUploadPlan:
    """Build the packet sequence for uploading a PNG (16x16 or 32x32) image.

    Framing (from image.py, _createPayloads()):
      idk_bytes(int16 LE) + [0, 0, 2 if i>0 else 0] + png_total_len(int32 LE) + chunk(<=4096 bytes)
    one packet per 4096-byte chunk of the PNG. idk_bytes = len(png_data) + num_chunks,
    as int16 LE. This is written as-is to the write characteristic; BLE-layer
    fragmentation by negotiated MTU happens underneath in ble.py, independent
    of this 4096-byte chunking.
    """
    chunk_size = 4096
    total_len = len(png_bytes)
    chunks = [png_bytes[i : i + chunk_size] for i in range(0, total_len, chunk_size)] or [b""]
    num_chunks = len(chunks)
    idk_bytes = (total_len + num_chunks) & 0xFFFF

    packets: list[bytes] = []
    for i, chunk in enumerate(chunks):
        flag = 2 if i > 0 else 0
        header = (
            idk_bytes.to_bytes(2, "little")
            + bytes([0, 0, flag])
            + total_len.to_bytes(4, "little")
        )
        packets.append(header + chunk)
    return ImageUploadPlan(packets=packets)
