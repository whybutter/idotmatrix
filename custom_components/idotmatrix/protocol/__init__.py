"""Pure protocol layer for the iDotMatrix BLE panel.

No Home Assistant or BLE imports here on purpose: everything in this package
takes plain values and returns `bytes` ready to write to the panel's write
characteristic. Knowledge source: the community reverse engineering of the
official app (derkalle4/python3-idotmatrix-library, archived, and its
maintained fork Toon-nooT/idotmatrix-api-client) — byte tables cross-checked
against both, plus dallanwagz/idotmatrix-ha (independent RE of the same
hardware, golden-frame tested).
"""
from .commands import (
    PANEL_TYPE_SIZES,
    brightness,
    chronograph,
    clock,
    convert_time,
    countdown,
    delete_all_assets,
    diy_mode,
    eco,
    effect,
    enter_asset_view,
    flip,
    fullscreen_color,
    graffiti,
    mic_rhythm,
    parse_device_info,
    request_device_info,
    reset,
    rhythm_frame,
    rhythm_stop,
    scoreboard,
    screen_on_time,
    screen_power,
    seconds_to_time_key,
    set_time,
    speed,
)
from .gif import build_gif_upload
from .image import build_asset_upload, build_image_upload
from .text import SEPARATOR as TEXT_SEPARATOR, build_text_packet

__all__ = [
    "PANEL_TYPE_SIZES",
    "TEXT_SEPARATOR",
    "brightness",
    "build_asset_upload",
    "build_gif_upload",
    "build_image_upload",
    "delete_all_assets",
    "seconds_to_time_key",
    "build_text_packet",
    "chronograph",
    "clock",
    "convert_time",
    "countdown",
    "diy_mode",
    "eco",
    "effect",
    "enter_asset_view",
    "flip",
    "fullscreen_color",
    "graffiti",
    "mic_rhythm",
    "parse_device_info",
    "request_device_info",
    "reset",
    "rhythm_frame",
    "rhythm_stop",
    "scoreboard",
    "screen_on_time",
    "screen_power",
    "set_time",
    "speed",
]
