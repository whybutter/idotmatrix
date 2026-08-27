"""Constants for the iDotMatrix integration."""
from __future__ import annotations

DOMAIN = "idotmatrix"

CONF_PREFERRED_PROXY = "preferred_proxy"
# Sentinel option value meaning "let HA pick the best proxy by signal".
PROXY_AUTO = "auto"

# BLE identifiers, from the community reverse engineering of the official app
# (derkalle4/python3-idotmatrix-library and its maintained forks).
LOCAL_NAME_PREFIX = "IDM-"
WRITE_CHAR_UUID = "0000fa02-0000-1000-8000-00805f9b34fb"
READ_CHAR_UUID = "0000fa03-0000-1000-8000-00805f9b34fb"

# The panel needs a moment to process each command before it can accept the
# next write-without-response (empirical, confirmed by the maintained forks).
COMMAND_SETTLE_SECONDS = 0.5

# Drop the BLE connection after this much idle time. Reconnecting (not the
# transfer) is the slow part, so a long timeout keeps the panel responsive by
# reusing one connection across a whole usage session. An ESPHome-style proxy
# has few connectable slots, so we still release it after prolonged idle rather
# than holding one forever.
IDLE_DISCONNECT_SECONDS = 600.0

# Pacing between BLE sub-writes during a bulk (image/GIF) transfer. Bulk data
# is sent write-WITHOUT-response (write-with-response gives GATT error 133 over
# the WBRG1 proxy); without a small gap the proxy silently drops the rapid
# packets and the panel stays black. This delay is the flow control instead.
BULK_WRITE_PACE_SECONDS = 0.02

# Brightness is 5-100% on the device; HA light entities use 0-255.
MIN_BRIGHTNESS_PCT = 5
MAX_BRIGHTNESS_PCT = 100

SERVICE_UPLOAD_IMAGE = "upload_image"
SERVICE_UPLOAD_GIF = "upload_gif"
SERVICE_SEND_TEXT = "send_text"
SERVICE_SET_ECO = "set_eco_mode"
SERVICE_MIC_RHYTHM = "mic_rhythm"
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
ATTR_TEXT = "text"
ATTR_ENABLED = "enabled"
ATTR_START_TIME = "start_time"
ATTR_END_TIME = "end_time"
ATTR_ECO_BRIGHTNESS = "eco_brightness"
ATTR_MODE = "mode"
ATTR_SPEED = "speed"
ATTR_COLOR_MODE = "color_mode"
ATTR_BG_COLOR = "bg_color"

# Named text scroll/animation modes -> byte.
TEXT_MODES = {
    "replace": 0,
    "marquee": 1,
    "reversed_marquee": 2,
    "rising": 3,
    "lowering": 4,
    "blinking": 5,
    "fading": 6,
    "tetris": 7,
    "filling": 8,
}
# Named text color modes -> byte.
TEXT_COLOR_MODES = {
    "white": 0,
    "rgb": 1,
    "rainbow_1": 2,
    "rainbow_2": 3,
    "rainbow_3": 4,
    "rainbow_4": 5,
}
DEFAULT_TEXT_SPEED = 95
MAX_TEXT_LEN = 500

ATTR_SENSITIVITY = "sensitivity"
DEFAULT_MIC_SENSITIVITY = 50

# Friendly dropdown labels -> style byte (shown in the UI selects).
CLOCK_STYLE_LABELS = {
    "RGB swipe outline": 0,
    "Christmas tree": 1,
    "Checkers": 2,
    "Color": 3,
    "Hourglass": 4,
    "Alarm clock": 5,
    "Outlines": 6,
    "RGB corners": 7,
}
EFFECT_STYLE_LABELS = {
    "Horizontal rainbow": 0,
    "Random colored pixels": 1,
    "Random white pixels": 2,
    "Vertical rainbow": 3,
    "Diagonal-right rainbow": 4,
    "Diagonal-left rainbow": 5,
    "Random colored pixels (alt)": 6,
}
# Mic visualizer styles Marco identified on the panel (1-4). More may exist.
MIC_STYLE_LABELS = {
    "Dancing guy": 1,
    "Heart": 2,
    "Gummy bear": 3,
    "Eyes and mouth": 4,
}

# Chronograph/countdown action label -> mode byte.
CHRONOGRAPH_ACTIONS = {"reset": 0, "start": 1, "pause": 2, "resume": 3}
COUNTDOWN_ACTIONS = {"stop": 0, "start": 1, "pause": 2, "restart": 3}

# Named clock/effect styles -> style byte, so the UI shows labels not numbers.
CLOCK_STYLES = {
    "rgb_swipe_outline": 0,
    "christmas_tree": 1,
    "checkers": 2,
    "color": 3,
    "hourglass": 4,
    "alarm_clock": 5,
    "outlines": 6,
    "rgb_corners": 7,
}
EFFECT_STYLES = {
    "horizontal_rainbow": 0,
    "random_colored_pixels": 1,
    "random_white_pixels": 2,
    "vertical_rainbow": 3,
    "diagonal_right_rainbow": 4,
    "diagonal_left_rainbow": 5,
    "random_colored_pixels_alt": 6,
}
# Sensible default palette so an effect can be fired with just a style.
DEFAULT_EFFECT_COLORS = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]

PANEL_SIZES = (16, 32, 64)
DEFAULT_PANEL_SIZE = 32

# Frame budget for GIF uploads (too many frames destabilize the transfer).
MAX_GIF_FRAMES = 64
DEFAULT_GIF_FRAME_MS = 200
