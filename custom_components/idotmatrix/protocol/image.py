"""DIY-image upload framing for the iDotMatrix panel.

Source of truth: the official Android app's `sendDIYImageData` (BleProtocolN.java),
as decompiled/ported by the maintained fork (Toon-nooT/idotmatrix-api-client).

The payload is RAW pixel bytes (width * height * 3), NOT an encoded PNG/GIF
file. Pixel order is G,R,B per pixel (see light._prepare_pixels — confirmed by
disassembling the app's LedView.getColorData). It is split into 4096-byte
chunks, each wrapped with a 9-byte header:

    [len(chunk) + 9 as int16 LE] + [0, 0, flag] + [total_len as int32 LE]

where flag is 0 for the first chunk and 2 for every continuation chunk, and
total_len is the raw pixel byte count (w*h*3). No CRC/trailer (that's GIF-only).

Delivery (see client.upload_image): DIY mode enabled first (commands.diy_mode),
then each block written write-with-response with a notify-characteristic ack
read between blocks. The archived original library's PNG-based scheme does
nothing on real hardware; this app-decompile scheme is the correct one.
"""
from __future__ import annotations

PROTOCOL_CHUNK_SIZE = 4096
HEADER_SIZE = 9


def build_image_upload(pixel_bytes: bytes) -> list[bytes]:
    total_len = len(pixel_bytes)
    chunks = [
        pixel_bytes[i : i + PROTOCOL_CHUNK_SIZE]
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
