"""Panel power + brightness as a light entity, plus the upload_image service."""
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
    ATTR_COLORS,
    ATTR_COUNT1,
    ATTR_COUNT2,
    ATTR_FILE_PATH,
    ATTR_HOUR24,
    ATTR_MINUTES,
    ATTR_RGB_COLOR,
    ATTR_SECONDS,
    ATTR_SHOW_DATE,
    ATTR_SIZE,
    ATTR_STYLE,
    CHRONOGRAPH_ACTIONS,
    COUNTDOWN_ACTIONS,
    DEFAULT_PANEL_SIZE,
    MAX_BRIGHTNESS_PCT,
    MIN_BRIGHTNESS_PCT,
    PANEL_SIZES,
    SERVICE_CHRONOGRAPH,
    SERVICE_COUNTDOWN,
    SERVICE_FULLSCREEN_COLOR,
    SERVICE_SCOREBOARD,
    SERVICE_SHOW_CLOCK,
    SERVICE_SHOW_EFFECT,
    SERVICE_UPLOAD_IMAGE,
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
        SERVICE_FULLSCREEN_COLOR,
        {vol.Required(ATTR_RGB_COLOR): _RGB},
        "async_fullscreen_color",
    )
    platform.async_register_entity_service(
        SERVICE_SHOW_CLOCK,
        {
            vol.Optional(ATTR_STYLE, default=0): vol.All(int, vol.Range(0, 7)),
            vol.Optional(ATTR_SHOW_DATE, default=True): cv.boolean,
            vol.Optional(ATTR_HOUR24, default=True): cv.boolean,
            vol.Optional(ATTR_RGB_COLOR, default=(255, 255, 255)): _RGB,
        },
        "async_show_clock",
    )
    platform.async_register_entity_service(
        SERVICE_SHOW_EFFECT,
        {
            vol.Required(ATTR_STYLE): vol.All(int, vol.Range(0, 6)),
            vol.Required(ATTR_COLORS): vol.All([_RGB], vol.Length(min=2, max=7)),
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

    async def async_fullscreen_color(self, rgb_color: tuple[int, int, int]) -> None:
        await self._run(self._client.fullscreen_color(*rgb_color))

    async def async_show_clock(
        self,
        style: int,
        show_date: bool,
        hour24: bool,
        rgb_color: tuple[int, int, int],
    ) -> None:
        await self._run(
            self._client.show_clock(style, show_date, hour24, *rgb_color)
        )

    async def async_show_effect(
        self, style: int, colors: list[tuple[int, int, int]]
    ) -> None:
        await self._run(self._client.show_effect(style, colors))

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

    The panel's DIY upload wants raw pixel data in G,R,B order (not R,G,B, and
    not an encoded file) — confirmed by disassembling the official app's
    LedView.getColorData, which stores green, then red, then blue per pixel.
    Sending R,G,B leaves the panel blank/wrong.
    """
    from PIL import Image, ImageOps

    with Image.open(file_path) as img:
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
        if img.size != (size, size):
            img = img.resize((size, size), Image.LANCZOS)
        r, g, b = img.split()
        return Image.merge("RGB", (g, r, b)).tobytes()
