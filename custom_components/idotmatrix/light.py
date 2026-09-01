"""Panel power + brightness as a light entity, plus the bulk/mode services."""
from __future__ import annotations

from functools import lru_cache
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
    ATTR_ECO_BRIGHTNESS,
    ATTR_ENABLED,
    ATTR_END_TIME,
    ATTR_FILE_PATH,
    ATTR_HOUR24,
    ATTR_IMAGE_DATA,
    ATTR_MINUTES,
    ATTR_MODE,
    ATTR_RGB_COLOR,
    ATTR_SECONDS,
    ATTR_SHOW_DATE,
    ATTR_SIZE,
    ATTR_SPEED,
    ATTR_START_TIME,
    ATTR_STYLE,
    ATTR_TEXT,
    ATTR_SENSITIVITY,
    CHRONOGRAPH_ACTIONS,
    CLOCK_STYLES,
    COUNTDOWN_ACTIONS,
    DEFAULT_EFFECT_COLORS,
    DEFAULT_GIF_FRAME_MS,
    DEFAULT_MIC_SENSITIVITY,
    DEFAULT_PANEL_SIZE,
    DEFAULT_TEXT_SPEED,
    EFFECT_STYLES,
    MAX_ALBUM_ASSET_BYTES,
    MAX_BRIGHTNESS_PCT,
    MAX_GIF_FRAMES,
    MAX_TEXT_LEN,
    MIN_BRIGHTNESS_PCT,
    PANEL_SIZES,
    SERVICE_CHRONOGRAPH,
    SERVICE_COUNTDOWN,
    SERVICE_FULLSCREEN_COLOR,
    SERVICE_MIC_RHYTHM,
    SERVICE_SCOREBOARD,
    SERVICE_SEND_TEXT,
    SERVICE_SET_ECO,
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


# (gamma, wb_red, wb_green, wb_blue) for the panel's colour correction.
Correction = tuple[float, float, float, float]

NO_CORRECTION: Correction = (1.0, 1.0, 1.0, 1.0)


@lru_cache(maxsize=8)
def _correction_lut(correction: Correction) -> tuple[int, ...]:
    """768-entry per-channel LUT: sRGB in, panel-ready bytes out.

    Two corrections, in this order, because they live in different spaces:

    1. Gamma — `255 * (v/255) ** gamma` — converts the sRGB-encoded source into
       the near-linear space the panel's PWM actually works in. See CONF_GAMMA.
    2. White balance — a per-channel gain applied to that LINEAR value, because
       the panel's blue LEDs emit far more light per unit than its red ones.
       See CONF_WB_RED and friends.

    Cached: otherwise this is rebuilt for every frame of every GIF.
    """
    gamma, *gains = correction
    return tuple(
        min(255, round(255 * ((i / 255) ** gamma) * gain))
        for gain in gains
        for i in range(256)
    )


def _is_identity(correction: Correction) -> bool:
    return all(abs(v - 1.0) < 1e-3 for v in correction)


def _apply_correction(img, correction: Correction):
    """Colour-correct an RGB image for the panel. Identity is a no-op."""
    if _is_identity(correction):
        return img
    return img.point(_correction_lut(correction))


def _correct_rgb(
    rgb: tuple[int, int, int], correction: Correction
) -> tuple[int, int, int]:
    """Colour-correct a single colour, so a colour the user picks lands on the
    panel the same way that colour would inside an uploaded image. Without this
    the picker and the image pipeline disagree, and solid colours come out
    washed out and blue."""
    if _is_identity(correction):
        return tuple(rgb)
    lut = _correction_lut(correction)
    return tuple(lut[256 * ch + max(0, min(255, int(v)))] for ch, v in enumerate(rgb))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IdotMatrixConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = entry.runtime_data
    async_add_entities(
        [
            IdotMatrixLight(
                data.client, data.availability, data.device_name, data.correction
            )
        ]
    )

    platform = entity_platform.async_get_current_platform()
    _upload_schema = {
        vol.Optional(ATTR_FILE_PATH): cv.string,
        vol.Optional(ATTR_IMAGE_DATA): cv.string,
        vol.Optional(ATTR_SIZE, default=DEFAULT_PANEL_SIZE): vol.All(
            vol.Coerce(int), vol.In(PANEL_SIZES)
        ),
    }
    platform.async_register_entity_service(
        SERVICE_UPLOAD_IMAGE, _upload_schema, "async_upload_image"
    )
    platform.async_register_entity_service(
        SERVICE_UPLOAD_GIF, _upload_schema, "async_upload_gif"
    )
    platform.async_register_entity_service(
        SERVICE_SEND_TEXT,
        {
            vol.Required(ATTR_TEXT): vol.All(cv.string, vol.Length(min=1, max=MAX_TEXT_LEN)),
            vol.Optional(ATTR_MODE, default="marquee"): vol.Any(
                vol.In(TEXT_MODES), vol.All(int, vol.Range(0, 8))
            ),
            vol.Optional(ATTR_SPEED, default=DEFAULT_TEXT_SPEED): vol.All(
                int, vol.Range(0, 100)
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
                vol.In(CLOCK_STYLES), vol.All(vol.Coerce(int), vol.Range(0, 7))
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
                vol.In(EFFECT_STYLES), vol.All(vol.Coerce(int), vol.Range(0, 6))
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
    platform.async_register_entity_service(
        SERVICE_MIC_RHYTHM,
        {
            vol.Optional(ATTR_STYLE, default=0): vol.All(int, vol.Range(0, 255)),
            vol.Optional(ATTR_SENSITIVITY, default=DEFAULT_MIC_SENSITIVITY): vol.All(
                int, vol.Range(0, 100)
            ),
        },
        "async_mic_rhythm",
    )
    platform.async_register_entity_service(
        SERVICE_SET_ECO,
        {
            vol.Required(ATTR_ENABLED): cv.boolean,
            vol.Required(ATTR_START_TIME): cv.time,
            vol.Required(ATTR_END_TIME): cv.time,
            vol.Optional(ATTR_ECO_BRIGHTNESS, default=10): vol.All(
                int, vol.Range(0, 100)
            ),
        },
        "async_set_eco",
    )


class IdotMatrixLight(IdotMatrixEntity, LightEntity):
    """The panel as a light: power + brightness, and setting an RGB color fills
    the whole panel with that solid color (the fullscreen-color command)."""

    _attr_name = None  # takes the device name
    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_assumed_state = True  # panel state can't be read back

    def __init__(
        self,
        client,
        availability,
        device_name: str,
        correction: Correction = NO_CORRECTION,
    ) -> None:
        super().__init__(client, availability, device_name, "light")
        self._correction = correction
        self._attr_rgb_color = (255, 255, 255)
        self._attr_brightness = 255

    async def async_turn_on(self, **kwargs: Any) -> None:
        if (ha_brightness := kwargs.get(ATTR_BRIGHTNESS)) is not None:
            pct = max(
                MIN_BRIGHTNESS_PCT,
                min(MAX_BRIGHTNESS_PCT, round(ha_brightness / 255 * 100)),
            )
            await self._run(self._client.set_brightness_pct(pct))
            self._attr_brightness = ha_brightness
        if (rgb := kwargs.get("rgb_color")) is not None:
            # Correct what goes on the wire, but keep the colour the user asked
            # for in HA state, so the UI still shows their pick.
            await self._run(
                self._client.fullscreen_color(*_correct_rgb(rgb, self._correction))
            )
            self._attr_rgb_color = rgb
        else:
            await self._run(self._client.turn_on())
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._run(self._client.turn_off())
        self._attr_is_on = False
        self.async_write_ha_state()

    async def async_upload_image(
        self, size: int, file_path: str | None = None, image_data: str | None = None
    ) -> None:
        raw = await self._resolve_source(file_path, image_data)
        pixel_bytes = await self.hass.async_add_executor_job(
            _prepare_pixels, raw, size, (0, 0, 0), self._correction
        )
        await self._run(self._client.upload_image(pixel_bytes))

    async def async_upload_gif(
        self, size: int, file_path: str | None = None, image_data: str | None = None
    ) -> None:
        raw = await self._resolve_source(file_path, image_data)
        gif_bytes = await self.hass.async_add_executor_job(
            _prepare_gif, raw, size, (0, 0, 0), self._correction
        )
        await self._run(self._client.upload_gif(gif_bytes))

    async def _resolve_source(
        self, file_path: str | None, image_data: str | None
    ) -> bytes:
        """Return the raw file bytes from either base64 data (from the frontend
        card/panel — a file picked on the user's PC) or a local file path."""
        if image_data:
            import base64

            try:
                return base64.b64decode(image_data)
            except (ValueError, TypeError) as err:
                raise HomeAssistantError(f"Invalid image_data: {err}") from err
        if not file_path:
            raise HomeAssistantError("Provide either file_path or image_data")
        if not self.hass.config.is_allowed_path(file_path):
            raise HomeAssistantError(
                f"{file_path} is not in an allowed directory; add it to "
                "homeassistant.allowlist_external_dirs"
            )
        return await self.hass.async_add_executor_job(_read_file, file_path)

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
                _correct_rgb(rgb_color, self._correction),
                bg_mode,
                _correct_rgb(bg_color, self._correction) if bg_color else (0, 0, 0),
            )
        )

    async def async_fullscreen_color(self, rgb_color: tuple[int, int, int]) -> None:
        await self._run(
            self._client.fullscreen_color(*_correct_rgb(rgb_color, self._correction))
        )

    async def async_show_clock(
        self,
        style: int | str,
        show_date: bool,
        hour24: bool,
        rgb_color: tuple[int, int, int],
    ) -> None:
        style_int = CLOCK_STYLES.get(style, style) if isinstance(style, str) else style
        await self._run(
            self._client.show_clock(
                style_int, show_date, hour24, *_correct_rgb(rgb_color, self._correction)
            )
        )

    async def async_show_effect(
        self, style: int | str, colors: list[tuple[int, int, int]]
    ) -> None:
        style_int = (
            EFFECT_STYLES.get(style, style) if isinstance(style, str) else style
        )
        await self._run(
            self._client.show_effect(
                style_int, [_correct_rgb(c, self._correction) for c in colors]
            )
        )

    async def async_chronograph(self, action: str) -> None:
        await self._run(self._client.chronograph(CHRONOGRAPH_ACTIONS[action]))

    async def async_countdown(self, action: str, minutes: int, seconds: int) -> None:
        await self._run(
            self._client.countdown(COUNTDOWN_ACTIONS[action], minutes, seconds)
        )

    async def async_scoreboard(self, count1: int, count2: int) -> None:
        await self._run(self._client.scoreboard(count1, count2))

    async def async_mic_rhythm(self, style: int, sensitivity: int) -> None:
        await self._run(self._client.mic_rhythm(style, sensitivity))

    async def async_set_eco(
        self, enabled: bool, start_time, end_time, eco_brightness: int
    ) -> None:
        await self._run(
            self._client.set_eco(
                enabled,
                start_time.hour,
                start_time.minute,
                end_time.hour,
                end_time.minute,
                eco_brightness,
            )
        )


def _read_file(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def _alpha_bbox(img):
    """Bounding box of the artwork (alpha > threshold), or the whole frame if
    the image is fully opaque. None only if fully transparent."""
    alpha = img.getchannel("A")
    if alpha.getextrema()[0] >= 255:  # fully opaque — don't trim photos
        return (0, 0, img.width, img.height)
    return alpha.point(lambda a: 255 if a > 16 else 0).getbbox()


def _fit_rgb(img, size, background, pixel_art, crop_box=None, square_side=None):
    """Fit an RGBA image into a size×size RGB frame for the panel.

    The panel is tiny, so wasted margin matters: many sources (emoji, sprites)
    embed the artwork in a large transparent canvas. We (1) crop to the artwork
    box, (2) pad to a centered square so aspect ratio is preserved (no
    stretching), (3) composite over an opaque background so transparency/shadows
    blend into it instead of becoming garbage, and (4) scale to the panel.

    crop_box / square_side can be supplied so every frame of an animation shares
    the same crop and scale (otherwise per-frame trimming would destroy motion).
    """
    from PIL import Image

    img = img.convert("RGBA")
    if crop_box is None:
        crop_box = _alpha_bbox(img)
    if crop_box:
        img = img.crop(crop_box)
    w, h = img.size
    side = square_side or max(w, h, 1)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(img, ((side - w) // 2, (side - h) // 2))
    canvas = Image.new("RGBA", (side, side), (*background, 255))
    canvas.alpha_composite(square)
    rgb = canvas.convert("RGB")
    if rgb.size != (size, size):
        rgb = rgb.resize((size, size), Image.NEAREST if pixel_art else Image.LANCZOS)
    return rgb


def _prepare_pixels(
    raw: bytes,
    size: int,
    background: tuple[int, int, int] = (0, 0, 0),
    correction: Correction = NO_CORRECTION,
) -> bytes:
    """Normalize any input image (raw file bytes) to the panel's raw pixel bytes
    (blocking; run in executor).

    The bulk image-upload path wants raw R,G,B pixel data, row-major (not an
    encoded file). Confirmed by disassembling the official app: the photo
    upload path (BGRUtils.bitmap2RGB) emits R,G,B, matching the maintained
    fork's img.tobytes(). (The G,R,B order in LedView.getColorData belongs to
    the separate interactive-draw screen, not this path.)
    """
    import io

    from PIL import Image, ImageOps

    with Image.open(io.BytesIO(raw)) as img:
        img = ImageOps.exif_transpose(img).convert("RGBA")
        if img.getchannel("A").getextrema()[0] >= 255:
            # Fully opaque (a photo): center-crop to square so it fills the panel
            # without distortion or letterbox bars.
            rgb = ImageOps.fit(
                img.convert("RGB"), (size, size), Image.LANCZOS, centering=(0.5, 0.5)
            )
        else:
            # Transparent art (emoji, icons): trim the margin, pad to square, and
            # flatten onto the background so it fills the panel.
            rgb = _fit_rgb(img, size, background, pixel_art=False)
        return _apply_correction(rgb, correction).tobytes()


def _prepare_still_as_gif(
    raw: bytes,
    size: int,
    dwell_seconds: int,
    background: tuple[int, int, int] = (0, 0, 0),
    correction: Correction = NO_CORRECTION,
) -> bytes:
    """Normalize a still image into a single-frame encoded GIF, for album use.

    Why not the raw-pixel asset path (protocol.build_asset_upload, type 0x02)?
    The panel keeps stills and animations in two separate material banks, and
    when both are non-empty the carousel plays ONLY the GIF bank — the stills
    are stored (they finish-ack fine) but never displayed. Verified on hardware
    in both orders: stills-then-GIFs and GIFs-then-stills each played only the
    GIFs; either type alone plays correctly. So an album sends everything
    through the GIF agreement, which makes album playback independent of the
    mix of stills and animations it happens to contain.

    `dwell_seconds` is how long the slide should stay up, and it is NOT
    optional: the panel advances the carousel after one full GIF loop and
    ignores the header's interval time-sign for this, so the loop duration IS
    the slide duration. A still left at PIL's default ~100ms loop is skipped by
    the carousel entirely (measured: zero appearances over 90s) — which is what
    made album stills look like they had failed to upload.

    The cost of the GIF route is its 256-colour palette. At 32x32 that is ~1024
    pixels against an adaptive 256-colour palette: measured mean channel error
    2.2/255 on a photo — invisible on the LED panel.
    """
    import io

    pixels = _prepare_pixels(raw, size, background, correction)

    from PIL import Image

    frame = Image.frombytes("RGB", (size, size), pixels)
    buf = io.BytesIO()
    # One frame held for the whole dwell. GIF stores the delay in centiseconds
    # (max 65535cs ≈ 655s), comfortably above the longest carousel interval.
    # optimize=True matches the animated path — the panel's transfer fails on an
    # unoptimized GIF.
    frame.convert("P", palette=Image.ADAPTIVE, colors=256).save(
        buf,
        format="GIF",
        optimize=True,
        duration=max(1, int(dwell_seconds)) * 1000,
        loop=0,
    )
    return buf.getvalue()


def _prepare_gif(
    raw: bytes,
    size: int,
    background: tuple[int, int, int] = (0, 0, 0),
    correction: Correction = NO_CORRECTION,
    dwell_seconds: int = 0,
) -> bytes:
    """Normalize any GIF (raw file bytes) to an encoded GIF sized to the panel
    (blocking; run in executor).

    The GIF upload path takes an ENCODED .gif byte stream, not raw pixels. We
    re-encode: trim (using ONE bounding box shared across all frames so motion
    is preserved), flatten onto a background, and resize every frame to
    size×size, capping the frame count. optimize=True is required — the panel's
    transfer fails on an unoptimized GIF (per the maintained fork). The shared
    trim + background composite fixes sprites that otherwise showed with
    mis-cropped backgrounds or leftover shadows.

    `dwell_seconds` > 0 (album use) repeats the whole frame sequence until it
    covers that long. The panel plays exactly ONE pass through a GIF's frames
    and then advances the carousel — it ignores both the header's interval
    time-sign and the GIF's own loop count — so physically repeating the frames
    is the only way to make an animated slide honour the album interval.
    """
    import io

    from PIL import Image, ImageSequence

    with Image.open(io.BytesIO(raw)) as img:
        raw_frames: list = []
        durations: list[int] = []
        union = None
        for frame in ImageSequence.Iterator(img):
            rgba = frame.convert("RGBA")
            raw_frames.append(rgba)
            durations.append(int(frame.info.get("duration", DEFAULT_GIF_FRAME_MS)))
            bb = _alpha_bbox(rgba)
            if bb:
                union = (
                    bb
                    if union is None
                    else (
                        min(union[0], bb[0]),
                        min(union[1], bb[1]),
                        max(union[2], bb[2]),
                        max(union[3], bb[3]),
                    )
                )
            if len(raw_frames) >= MAX_GIF_FRAMES:
                break

        if not raw_frames:
            raise ValueError("no frames found in GIF")
        if union is None:
            union = (0, 0, raw_frames[0].width, raw_frames[0].height)
        side = max(union[2] - union[0], union[3] - union[1], 1)
        frames = [
            _apply_correction(
                _fit_rgb(f, size, background, True, crop_box=union, square_side=side),
                correction,
            )
            for f in raw_frames
        ]

    if not frames:
        raise ValueError("no frames found in GIF")

    import io

    from PIL import Image

    # Quantise every frame against ONE palette built from the WHOLE animation,
    # and write that palette as the GIF's global colour table.
    #
    # Left to itself, PIL derives the global colour table from the first frame
    # and gives every later frame its own local colour table. The panel renders
    # against the GLOBAL table and ignores the local ones, so an animation whose
    # first frame is unrepresentative comes out wrong — and one that opens on a
    # blank/black frame (a fade-in) yields a 2-4 colour global table and plays
    # entirely BLACK on the panel while decoding perfectly in any GIF viewer.
    # That was the "corrupt" burger animation in the catalog; nothing was wrong
    # with the file.
    #
    # Passing `palette=` forces the shared table into the header and drops the
    # per-frame tables entirely, which also makes the file ~25-45% smaller —
    # welcome against the album storage budget.
    strip = Image.new("RGB", (size, size * len(frames)))
    for i, f in enumerate(frames):
        strip.paste(f, (0, i * size))
    palette = strip.quantize(colors=256, method=Image.MEDIANCUT)
    global_palette = palette.palette.tobytes()
    paletted = []
    for f in frames:
        # dither=NONE: these are pixel-art sprites on a 32x32 panel, where
        # dithering reads as noise rather than as extra colour depth.
        q = f.quantize(palette=palette, dither=Image.Dither.NONE)
        # A transparency index inherited from the source breaks PIL's writer and
        # means nothing here — every frame is already composited onto background.
        q.info.pop("transparency", None)
        q.info.pop("background", None)
        paletted.append(q)

    def _encode(frames_, durations_) -> bytes:
        buf = io.BytesIO()
        frames_[0].save(
            buf,
            format="GIF",
            save_all=True,
            optimize=True,
            append_images=frames_[1:],
            loop=0,
            duration=durations_,
            disposal=2,
            palette=global_palette,
        )
        return buf.getvalue()

    encoded = _encode(paletted, durations)
    if dwell_seconds <= 0:
        return encoded

    loop_ms = sum(durations) or 1
    # Repeat whole loops only — a partial pass would cut the animation off
    # mid-motion. Round to the nearest loop so a 3.5s animation on a 5s
    # interval stays at one pass instead of doubling to 7s.
    repeats = max(1, round(dwell_seconds * 1000 / loop_ms))
    # ...but never past the per-asset size ceiling, or a long animation on a long
    # interval would balloon into an asset big enough to push the album out of the
    # panel's storage — which silently drops slides (the exact failure this whole
    # path exists to avoid). Size scales ~linearly with the repeat count.
    repeats = min(repeats, max(1, MAX_ALBUM_ASSET_BYTES // max(1, len(encoded))))
    if repeats <= 1:
        return encoded
    return _encode(paletted * repeats, durations * repeats)


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
