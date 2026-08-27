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
SERVICE_FULLSCREEN_COLOR = "fullscreen_color"
SERVICE_SHOW_CLOCK = "show_clock"
SERVICE_SHOW_EFFECT = "show_effect"
SERVICE_CHRONOGRAPH = "chronograph"
SERVICE_COUNTDOWN = "countdown"
SERVICE_SCOREBOARD = "scoreboard"

ATTR_FILE_PATH = "file_path"
ATTR_SIZE = "size"
ATTR_RGB_COLOR = "rgb_color"
ATTR_STYLE = "style"
ATTR_SHOW_DATE = "show_date"
ATTR_HOUR24 = "hour24"
ATTR_COLORS = "colors"
ATTR_ACTION = "action"
ATTR_MINUTES = "minutes"
ATTR_SECONDS = "seconds"
ATTR_COUNT1 = "count1"
ATTR_COUNT2 = "count2"

# Chronograph/countdown action label -> mode byte.
CHRONOGRAPH_ACTIONS = {"reset": 0, "start": 1, "pause": 2, "resume": 3}
COUNTDOWN_ACTIONS = {"stop": 0, "start": 1, "pause": 2, "restart": 3}

PANEL_SIZES = (16, 32, 64)
DEFAULT_PANEL_SIZE = 32
