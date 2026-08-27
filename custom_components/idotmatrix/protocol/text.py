"""Text rendering + framing for the iDotMatrix panel.

Source: 8none1/idotmatrix's protocol notes and the maintained fork's text.py.

A text message is: a 16-byte transport header + a 14-byte metadata block +
one monochrome bitmap per character. Each character bitmap is preceded by a
4-byte separator. The whole thing is written as a single MTU-fragmented
stream (write-without-response) — NOT the 4K-block+ack transport that
image/GIF use.

Layout:

  header (16B):
    [0:2]   total length (header+packet) int16 LE
    [2]     3   (fixed)
    [3:5]   0,0 (fixed)
    [5:9]   len(packet) int32 LE
    [9:13]  CRC32(packet) int32 LE
    [13:15] 0,0 (fixed)
    [15]    12  (fixed)

  packet = metadata (14B) + bitmaps
  metadata (14B):
    [0:2]   number of characters int16 LE
    [2]     0
    [3]     1
    [4]     text_mode (0-8)
    [5]     speed
    [6]     text_color_mode (0-5)
    [7:10]  text RGB
    [10]    bg_mode (0/1)
    [11:14] bg RGB

  bitmaps: for each char, SEPARATOR + glyph, where the glyph for a 16x32 cell
  is 64 bytes (row-major, 2 bytes/row, bit x set from x%8, LSB-first).

The glyph rendering (needs Pillow) lives in the entity layer; this module is
pure byte assembly.
"""
from __future__ import annotations

import zlib

# 16x32 cell -> separator 0x05; an 8x16 cell would use 0x02 (16-tall panels).
SEPARATOR = b"\x05\xff\xff\xff"


def build_text_packet(
    bitmaps: bytes,
    text_mode: int,
    speed: int,
    color_mode: int,
    color: tuple[int, int, int],
    bg_mode: int,
    bg_color: tuple[int, int, int],
) -> bytes:
    num_chars = bitmaps.count(SEPARATOR)

    metadata = bytearray(
        [0, 0, 0, 1, text_mode, speed, color_mode, *color, bg_mode, *bg_color]
    )
    metadata[0:2] = num_chars.to_bytes(2, "little")

    packet = bytes(metadata) + bitmaps

    header = bytearray(16)
    header[2] = 3
    header[15] = 12
    header[0:2] = (len(packet) + len(header)).to_bytes(2, "little")
    header[5:9] = len(packet).to_bytes(4, "little")
    header[9:13] = (zlib.crc32(packet) & 0xFFFFFFFF).to_bytes(4, "little")

    return bytes(header) + packet
