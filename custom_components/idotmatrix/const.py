"""Constants for the iDotMatrix integration."""
from __future__ import annotations

DOMAIN = "idotmatrix"

# BLE identifiers, from the community reverse engineering of the official app
# (derkalle4/python3-idotmatrix-library and its maintained forks).
LOCAL_NAME_PREFIX = "IDM-"
WRITE_CHAR_UUID = "0000fa02-0000-1000-8000-00805f9b34fb"
READ_CHAR_UUID = "0000fa03-0000-1000-8000-00805f9b34fb"

# The panel needs a moment to process each command before it can accept the
# next write-without-response (empirical, confirmed by the maintained forks).
COMMAND_SETTLE_SECONDS = 0.5

# Drop the BLE connection after this much idle time. An ESPHome-style active
# proxy has a small number of concurrent connection slots; holding one open
# forever would starve other BLE devices (e.g. Tuya thermometers) behind the
# same proxy.
IDLE_DISCONNECT_SECONDS = 20.0

# Brightness is 5-100% on the device; HA light entities use 0-255.
MIN_BRIGHTNESS_PCT = 5
MAX_BRIGHTNESS_PCT = 100

SERVICE_UPLOAD_IMAGE = "upload_image"
ATTR_FILE_PATH = "file_path"
ATTR_SIZE = "size"

PANEL_SIZES = (16, 32, 64)
DEFAULT_PANEL_SIZE = 32
