"""DIY-image upload framing for the iDotMatrix panel.

Source of truth: the official Android app's `sendDIYImageData` (BleProtocolN.java),
as decompiled/ported by the maintained fork (Toon-nooT/idotmatrix-api-client).

The payload is RAW pixel bytes (width * height * 3), NOT an encoded PNG/GIF
file. Pixel order is R,G,B per pixel (see light._prepare_pixels — the app's
photo-upload path BGRUtils.bitmap2RGB emits R,G,B). It is split into 4096-byte
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


import binascii

ASSET_HEADER_SIZE = 16
ASSET_TYPE = 0xFF  # "download whole album" path passes index -1 -> 0xFF


def build_asset_upload(pixel_bytes: bytes, time_key: int) -> list[bytes]:
    """Build a PERSISTENT still-image asset (stored in device memory, carousels,
    no DIY-mode blank/flash). 16-byte header per 4K chunk (byte-exact from the
    app's ImageAgreement.sendImageData):

        [0:2]  (len(chunk)+16) int16 LE
        [2]    0x02   (still-asset marker; GIF=0x01, text=0x03)
        [3]    0x00
        [4]    0x00 first / 0x02 continuation
        [5:9]  total pixel length int32 LE (w*h*3)
        [9:13] CRC32(all pixels) int32 LE
        [13:15]interval time-sign, int16 BE (ConvertTime(time_key))
        [15]   type = 0xFF

    Delivered via the same block+ack transport as image/GIF (no DIY enable).
    """
    from .commands import convert_time

    total_len = len(pixel_bytes)
    crc = binascii.crc32(pixel_bytes) & 0xFFFFFFFF
    time_sign = 0 if time_key == 12 else convert_time(time_key)
    chunks = [
        pixel_bytes[i : i + PROTOCOL_CHUNK_SIZE]
        for i in range(0, total_len, PROTOCOL_CHUNK_SIZE)
    ] or [b""]

    packets: list[bytes] = []
    for i, chunk in enumerate(chunks):
        header = bytearray(ASSET_HEADER_SIZE)
        header[0:2] = (len(chunk) + ASSET_HEADER_SIZE).to_bytes(2, "little")
        header[2] = 0x02
        header[3] = 0x00
        header[4] = 0x02 if i > 0 else 0x00
        header[5:9] = total_len.to_bytes(4, "little")
        header[9:13] = crc.to_bytes(4, "little")
        header[13:15] = time_sign.to_bytes(2, "big")
        header[15] = ASSET_TYPE
        packets.append(bytes(header) + chunk)
    return packets


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
