"""Pure protocol layer for the iDotMatrix BLE panel.

No Home Assistant or BLE imports here on purpose: everything in this package
takes plain values and returns `bytes` ready to write to the panel's write
characteristic. Knowledge source: the community reverse engineering of the
official app (derkalle4/python3-idotmatrix-library, archived, and its
maintained fork Toon-nooT/idotmatrix-api-client) — byte tables cross-checked
against both.
"""
from .commands import (
    brightness,
    diy_mode,
    flip,
    reset,
    screen_power,
    set_time,
    speed,
)
from .image import build_image_upload

__all__ = [
    "brightness",
    "build_image_upload",
    "diy_mode",
    "flip",
    "reset",
    "screen_power",
    "set_time",
    "speed",
]
