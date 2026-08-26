"""Constants for the iDotMatrix integration."""
from __future__ import annotations

DOMAIN = "idotmatrix"

# BLE identifiers, extracted from the archived derkalle4/python3-idotmatrix-library
# (see vault note "iDotMatrix ESP32 Bridge.md" for full protocol notes).
LOCAL_NAME_PREFIX = "IDM-"
WRITE_CHAR_UUID = "0000fa02-0000-1000-8000-00805f9b34fb"
READ_CHAR_UUID = "0000fa03-0000-1000-8000-00805f9b34fb"

# Conservative fallback chunk size if the negotiated MTU can't be read.
DEFAULT_CHUNK_SIZE = 180

# Brightness is 5-100% on the device; HA light entities use 0-255.
MIN_BRIGHTNESS_PCT = 5
MAX_BRIGHTNESS_PCT = 100

CONF_ADDRESS = "address"

SERVICE_FLIP = "flip"
SERVICE_FREEZE = "freeze"
SERVICE_UNFREEZE = "unfreeze"
SERVICE_RESET = "reset"
SERVICE_UPLOAD_IMAGE = "upload_image"
SERVICE_SET_SPEED = "set_speed"

ATTR_FLIPPED = "flipped"
ATTR_FILE_PATH = "file_path"
ATTR_SPEED = "speed"

PANEL_SIZE_OPTIONS = (16, 32)
DEFAULT_PANEL_SIZE = 32
CONF_PANEL_SIZE = "panel_size"
