"""GIF (animation) upload framing for the iDotMatrix panel.

Source: the official app's GifAgreement (sendImageData), as ported by the
maintained fork (Toon-nooT/idotmatrix-api-client gif.py).

Unlike the still-image path, the payload here is an ENCODED GIF file (the whole
.gif byte stream), not raw pixels. It is split into 4096-byte chunks, each
wrapped with a 16-byte header:

    [0:2]  = (len(chunk) + 16) as int16 LE   (per-block length)
    [2]    = 1        (fixed)
    [3]    = 0        (fixed)
    [4]    = 0 for the first block, 2 for continuation blocks
    [5:9]  = total GIF length as int32 LE
    [9:13] = CRC32 of the whole GIF as int32 LE
    [13:15]= 0,0 for gif_type 12 (no time signature)
    [15]   = gif_type

We use gif_type = 12 ("no time signature") like the app's single-GIF send.
Delivery is the same block+ack transport as image upload (write-with-response,
per-block ack); no DIY-mode enable (that's the still-image path only).
"""
from __future__ import annotations

import binascii

PROTOCOL_CHUNK_SIZE = 4096
HEADER_SIZE = 16
GIF_TYPE_NO_TIME_SIGNATURE = 12


def build_gif_upload(gif_bytes: bytes, gif_type: int = GIF_TYPE_NO_TIME_SIGNATURE) -> list[bytes]:
    if not gif_bytes:
        raise ValueError("gif_bytes cannot be empty")

    total_len = len(gif_bytes)
    # java.util.zip.CRC32 == standard CRC-32 == binascii.crc32 (unsigned).
    crc = binascii.crc32(gif_bytes) & 0xFFFFFFFF

    chunks = [
        gif_bytes[i : i + PROTOCOL_CHUNK_SIZE]
        for i in range(0, total_len, PROTOCOL_CHUNK_SIZE)
    ]

    packets: list[bytes] = []
    for i, chunk in enumerate(chunks):
        header = bytearray(HEADER_SIZE)
        header[0:2] = (len(chunk) + HEADER_SIZE).to_bytes(2, "little")
        header[2] = 1
        header[3] = 0
        header[4] = 2 if i > 0 else 0
        header[5:9] = total_len.to_bytes(4, "little")
        header[9:13] = crc.to_bytes(4, "little")
        header[13] = 0
        header[14] = 0
        header[15] = gif_type & 0xFF
        packets.append(bytes(header) + chunk)
    return packets
