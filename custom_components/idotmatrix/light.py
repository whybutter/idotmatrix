"""Panel power + brightness as a light entity, plus the bulk/mode services."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IdotMatrixConfigEntry
from .const import (
    ATTR_ACTION,
    ATTR_BG_COLOR,
    ATTR_COLOR_MODE,
    ATTR_COLORS,
    ATTR_COUNT1,
    ATTR_COUNT2,
    ATTR_FILE_PATH,
    ATTR_HOUR24,
    ATTR_MINUTES,
    ATTR_MODE,
    ATTR_RGB_COLOR,
    ATTR_SECONDS,
    ATTR_SHOW_DATE,
    ATTR_SIZE,
    ATTR_SPEED,
    ATTR_STYLE,
    ATTR_TEXT,
    CHRONOGRAPH_ACTIONS,
    CLOCK_STYLES,
    COUNTDOWN_ACTIONS,
    DEFAULT_EFFECT_COLORS,
    DEFAULT_GIF_FRAME_MS,
    DEFAULT_PANEL_SIZE,
    DEFAULT_TEXT_SPEED,
    EFFECT_STYLES,
    MAX_BRIGHTNESS_PCT,
    MAX_GIF_FRAMES,
    MAX_TEXT_LEN,
    MIN_BRIGHTNESS_PCT,
    PANEL_SIZES,
    SERVICE_CHRONOGRAPH,
    SERVICE_COUNTDOWN,
    SERVICE_FULLSCREEN_COLOR,
    SERVICE_SCOREBOARD,
    SERVICE_SEND_TEXT,
    SERVICE_SHOW_CLOCK,
    SERVICE_SHOW_EFFECT,
    SERVICE_UPLOAD_GIF,
    SERVICE_UPLOAD_IMAGE,
    TEXT_COLOR_MODES,
    TEXT_MODES,
)
from .entity import IdotMatrixEntity

_RGB = vol.All(
    vol.ExactSequence([vol.All(int, vol.Range(0, 255))] * 3), vol.Coerce(tuple)
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IdotMatrixConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = entry.runtime_data
    async_add_entities(
        [IdotMatrixLight(data.client, data.availability, data.device_name)]
    )

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_UPLOAD_IMAGE,
        {
            vol.Required(ATTR_FILE_PATH): cv.string,
            vol.Optional(ATTR_SIZE, default=DEFAULT_PANEL_SIZE): vol.All(
                vol.Coerce(int), vol.In(PANEL_SIZES)
            ),
        },
        "async_upload_image",
    )
    platform.async_register_entity_service(
        SERVICE_UPLOAD_GIF,
        {
            vol.Required(ATTR_FILE_PATH): cv.string,
            vol.Optional(ATTR_SIZE, default=DEFAULT_PANEL_SIZE): vol.All(
                vol.Coerce(int), vol.In(PANEL_SIZES)
            ),
        },
        "async_upload_gif",
    )
    platform.async_register_entity_service(
        SERVICE_SEND_TEXT,
        {
            vol.Required(ATTR_TEXT): vol.All(cv.string, vol.Length(min=1, max=MAX_TEXT_LEN)),
            vol.Optional(ATTR_MODE, default="marquee"): vol.Any(
                vol.In(TEXT_MODES), vol.All(int, vol.Range(0, 8))
            ),
            vol.Optional(ATTR_SPEED, default=DEFAULT_TEXT_SPEED): vol.All(
                int, vol.Range(0, 255)
            ),
            vol.Optional(ATTR_COLOR_MODE, default="white"): vol.Any(
                vol.In(TEXT_COLOR_MODES), vol.All(int, vol.Range(0, 5))
            ),
            vol.Optional(ATTR_RGB_COLOR, default=(255, 255, 255)): _RGB,
            vol.Optional(ATTR_BG_COLOR): _RGB,
        },
        "async_send_text",
    )
    platform.async_register_entity_service(
        SERVICE_FULLSCREEN_COLOR,
        {vol.Required(ATTR_RGB_COLOR): _RGB},
        "async_fullscreen_color",
    )
    platform.async_register_entity_service(
        SERVICE_SHOW_CLOCK,
        {
            # Accept either a named style ("color") or the raw 0-7 int.
            vol.Optional(ATTR_STYLE, default="rgb_swipe_outline"): vol.Any(
                vol.In(CLOCK_STYLES), vol.All(int, vol.Range(0, 7))
            ),
            vol.Optional(ATTR_SHOW_DATE, default=True): cv.boolean,
            vol.Optional(ATTR_HOUR24, default=True): cv.boolean,
            vol.Optional(ATTR_RGB_COLOR, default=(255, 255, 255)): _RGB,
        },
        "async_show_clock",
    )
    platform.async_register_entity_service(
        SERVICE_SHOW_EFFECT,
        {
            vol.Optional(ATTR_STYLE, default="horizontal_rainbow"): vol.Any(
                vol.In(EFFECT_STYLES), vol.All(int, vol.Range(0, 6))
            ),
            # Colors optional: a sensible RGB palette is used if omitted, so the
            # effect can be fired by just picking a style.
            vol.Optional(ATTR_COLORS, default=DEFAULT_EFFECT_COLORS): vol.All(
                [_RGB], vol.Length(min=2, max=7)
            ),
        },
        "async_show_effect",
    )
    platform.async_register_entity_service(
        SERVICE_CHRONOGRAPH,
        {vol.Required(ATTR_ACTION): vol.In(list(CHRONOGRAPH_ACTIONS))},
        "async_chronograph",
    )
    platform.async_register_entity_service(
        SERVICE_COUNTDOWN,
        {
            vol.Required(ATTR_ACTION): vol.In(list(COUNTDOWN_ACTIONS)),
            vol.Optional(ATTR_MINUTES, default=0): vol.All(int, vol.Range(0, 59)),
            vol.Optional(ATTR_SECONDS, default=0): vol.All(int, vol.Range(0, 59)),
        },
        "async_countdown",
    )
    platform.async_register_entity_service(
        SERVICE_SCOREBOARD,
        {
            vol.Required(ATTR_COUNT1): vol.All(int, vol.Range(0, 999)),
            vol.Required(ATTR_COUNT2): vol.All(int, vol.Range(0, 999)),
        },
        "async_scoreboard",
    )


class IdotMatrixLight(IdotMatrixEntity, LightEntity):
    _attr_name = None  # takes the device name
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_assumed_state = True  # panel state can't be read back

    def __init__(self, client, availability, device_name: str) -> None:
        super().__init__(client, availability, device_name, "light")

    async def async_turn_on(self, **kwargs: Any) -> None:
        if (ha_brightness := kwargs.get(ATTR_BRIGHTNESS)) is not None:
            pct = max(
                MIN_BRIGHTNESS_PCT,
                min(MAX_BRIGHTNESS_PCT, round(ha_brightness / 255 * 100)),
            )
            await self._run(self._client.set_brightness_pct(pct))
            self._attr_brightness = ha_brightness
        await self._run(self._client.turn_on())
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._run(self._client.turn_off())
        self._attr_is_on = False
        self.async_write_ha_state()

    async def async_upload_image(self, file_path: str, size: int) -> None:
        if not self.hass.config.is_allowed_path(file_path):
            raise HomeAssistantError(
                f"{file_path} is not in an allowed directory; add it to "
                "homeassistant.allowlist_external_dirs"
            )
        pixel_bytes = await self.hass.async_add_executor_job(
            _prepare_pixels, file_path, size
        )
        await self._run(self._client.upload_image(pixel_bytes))

    async def async_upload_gif(self, file_path: str, size: int) -> None:
        if not self.hass.config.is_allowed_path(file_path):
            raise HomeAssistantError(
                f"{file_path} is not in an allowed directory; add it to "
                "homeassistant.allowlist_external_dirs"
            )
        gif_bytes = await self.hass.async_add_executor_job(
            _prepare_gif, file_path, size
        )
        await self._run(self._client.upload_gif(gif_bytes))

    async def async_send_text(
        self,
        text: str,
        mode: int | str,
        speed: int,
        color_mode: int | str,
        rgb_color: tuple[int, int, int],
        bg_color: tuple[int, int, int] | None = None,
    ) -> None:
        mode_int = TEXT_MODES.get(mode, mode) if isinstance(mode, str) else mode
        cmode_int = (
            TEXT_COLOR_MODES.get(color_mode, color_mode)
            if isinstance(color_mode, str)
            else color_mode
        )
        bg_mode = 0 if bg_color is None else 1
        bitmaps = await self.hass.async_add_executor_job(_render_text_bitmaps, text)
        await self._run(
            self._client.send_text(
                bitmaps,
                mode_int,
                speed,
                cmode_int,
                tuple(rgb_color),
                bg_mode,
                tuple(bg_color) if bg_color else (0, 0, 0),
            )
        )

    async def async_fullscreen_color(self, rgb_color: tuple[int, int, int]) -> None:
        await self._run(self._client.fullscreen_color(*rgb_color))

    async def async_show_clock(
        self,
        style: int | str,
        show_date: bool,
        hour24: bool,
        rgb_color: tuple[int, int, int],
    ) -> None:
        style_int = CLOCK_STYLES.get(style, style) if isinstance(style, str) else style
        await self._run(
            self._client.show_clock(style_int, show_date, hour24, *rgb_color)
        )

    async def async_show_effect(
        self, style: int | str, colors: list[tuple[int, int, int]]
    ) -> None:
        style_int = (
            EFFECT_STYLES.get(style, style) if isinstance(style, str) else style
        )
        await self._run(self._client.show_effect(style_int, colors))

    async def async_chronograph(self, action: str) -> None:
        await self._run(self._client.chronograph(CHRONOGRAPH_ACTIONS[action]))

    async def async_countdown(self, action: str, minutes: int, seconds: int) -> None:
        await self._run(
            self._client.countdown(COUNTDOWN_ACTIONS[action], minutes, seconds)
        )

    async def async_scoreboard(self, count1: int, count2: int) -> None:
        await self._run(self._client.scoreboard(count1, count2))


def _prepare_pixels(file_path: str, size: int) -> bytes:
    """Normalize any input image to the panel's raw pixel bytes (blocking; run
    in executor).

    The bulk image-upload path wants raw R,G,B pixel data, row-major (not an
    encoded file). Confirmed by disassembling the official app: the photo
    upload path (BGRUtils.bitmap2RGB) emits R,G,B, matching the maintained
    fork's img.tobytes(). (The G,R,B order in LedView.getColorData belongs to
    the separate interactive-draw screen, not this path.)
    """
    from PIL import Image, ImageOps

    with Image.open(file_path) as img:
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
        if img.size != (size, size):
            img = img.resize((size, size), Image.LANCZOS)
        return img.tobytes()


def _prepare_gif(file_path: str, size: int) -> bytes:
    """Normalize any GIF (or animated image) to an encoded GIF sized to the
    panel (blocking; run in executor).

    The GIF upload path takes an ENCODED .gif byte stream, not raw pixels. We
    re-encode: resize every frame to size×size (NEAREST to preserve pixel art),
    cap the frame count, and re-save. optimize=True is required — the panel's
    transfer fails on an unoptimized GIF (per the maintained fork).
    """
    from PIL import Image, ImageSequence

    with Image.open(file_path) as img:
        frames: list = []
        durations: list[int] = []
        for frame in ImageSequence.Iterator(img):
            rgb = frame.convert("RGB")
            if rgb.size != (size, size):
                rgb = rgb.resize((size, size), Image.NEAREST)
            frames.append(rgb)
            durations.append(int(frame.info.get("duration", DEFAULT_GIF_FRAME_MS)))
            if len(frames) >= MAX_GIF_FRAMES:
                break

    if not frames:
        raise ValueError("no frames found in GIF")

    import io

    buf = io.BytesIO()
    frames[0].save(
        buf,
        format="GIF",
        save_all=True,
        optimize=True,
        append_images=frames[1:],
        loop=0,
        duration=durations,
        disposal=2,
    )
    return buf.getvalue()


# 16-wide x 32-tall glyph cell (matches the panel's 32px height). The separator
# in protocol.text is 0x05 for this cell size.
_TEXT_CELL_W = 16
_TEXT_CELL_H = 32


def _render_text_bitmaps(text: str) -> bytes:
    """Render each character to a 16x32 monochrome bitmap (blocking; executor).

    Packing (per 8none1 / the maintained fork): row-major, 2 bytes per row,
    bit x set from x%8 (LSB-first). Each glyph is prefixed with the 4-byte
    separator. Font: Pillow's scalable default (no bundled font needed).
    """
    from PIL import Image, ImageDraw, ImageFont

    try:
        font = ImageFont.load_default(size=28)
    except TypeError:
        # Older Pillow: default font isn't scalable; fall back to a common TTF.
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 24)
        except OSError:
            font = ImageFont.load_default()

    from .protocol import TEXT_SEPARATOR

    stream = bytearray()
    for char in text:
        img = Image.new("1", (_TEXT_CELL_W, _TEXT_CELL_H), 0)
        draw = ImageDraw.Draw(img)
        _, _, w, h = draw.textbbox((0, 0), char, font=font)
        draw.text(
            ((_TEXT_CELL_W - w) // 2, (_TEXT_CELL_H - h) // 2), char, fill=1, font=font
        )
        bitmap = bytearray()
        for y in range(_TEXT_CELL_H):
            byte = 0
            for x in range(_TEXT_CELL_W):
                if x % 8 == 0:
                    byte = 0
                byte |= (img.getpixel((x, y)) & 1) << (x % 8)
                if x % 8 == 7 or x == _TEXT_CELL_W - 1:
                    bitmap.append(byte)
        stream += TEXT_SEPARATOR + bitmap
    return bytes(stream)
