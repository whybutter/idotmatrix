"""Image-upload framing for the iDotMatrix panel.

From the reverse-engineered image.py (_createPayloads) of the original
library: the PNG is split into 4096-byte chunks, each wrapped as

    total_marker(int16 LE) + [0, 0, flag] + png_total_len(int32 LE) + chunk

where flag is 0 for the first chunk and 2 for every following chunk, and
total_marker = len(png_data) + number_of_chunks. Each wrapped packet is
written as-is to the write characteristic; BLE-layer MTU fragmentation
happens underneath and is a separate concern.
"""
from __future__ import annotations

PROTOCOL_CHUNK_SIZE = 4096


def build_image_upload(png_bytes: bytes) -> list[bytes]:
    total_len = len(png_bytes)
    chunks = [
        png_bytes[i : i + PROTOCOL_CHUNK_SIZE]
        for i in range(0, total_len, PROTOCOL_CHUNK_SIZE)
    ] or [b""]
    total_marker = (total_len + len(chunks)) & 0xFFFF

    packets: list[bytes] = []
    for i, chunk in enumerate(chunks):
        header = (
            total_marker.to_bytes(2, "little")
            + bytes([0, 0, 2 if i > 0 else 0])
            + total_len.to_bytes(4, "little")
        )
        packets.append(header + chunk)
    return packets
