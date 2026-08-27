"""DIY-image upload framing for the iDotMatrix panel.

Source of truth: the official Android app's `sendDIYImageData` (BleProtocolN.java),
as decompiled/ported by the maintained fork (Toon-nooT/idotmatrix-api-client).

The payload is RAW RGB pixel bytes (width * height * 3), NOT an encoded
PNG/GIF file. It is split into 4096-byte chunks, each wrapped with a 9-byte
header:

    [len(chunk) + 9 as int16 LE] + [0, 0, flag] + [total_len as int32 LE]

where flag is 0 for the first chunk and 2 for every continuation chunk.
Each wrapped packet is written to the write characteristic; BLE-layer MTU
fragmentation happens underneath and is a separate concern.

Note: the archived original library used a different scheme (PNG bytes with a
`len + chunk_count` marker). Tested against real hardware 2026-08-26, that
scheme does nothing on Marco's panel — the app-decompile scheme here is the
correct one. DIY mode must be enabled first (commands.diy_mode).
"""
from __future__ import annotations

PROTOCOL_CHUNK_SIZE = 4096
HEADER_SIZE = 9


def build_image_upload(rgb_bytes: bytes) -> list[bytes]:
    total_len = len(rgb_bytes)
    chunks = [
        rgb_bytes[i : i + PROTOCOL_CHUNK_SIZE]
        for i in range(0, total_len, PROTOCOL_CHUNK_SIZE)
    ] or [b""]

    packets: list[bytes] = []
    for i, chunk in enumerate(chunks):
        header = (
            (len(chunk) + HEADER_SIZE).to_bytes(2, "little")
            + bytes([0, 0, 2 if i > 0 else 0])
            + total_len.to_bytes(4, "little")
        )
        packets.append(header + chunk)
    return packets
