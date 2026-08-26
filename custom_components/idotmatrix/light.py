"""Panel power + brightness as a light entity, plus the upload_image service."""
from __future__ import annotations

import io
from typing import Any

import voluptuous as vol

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IdotMatrixConfigEntry
from .const import (
    ATTR_FILE_PATH,
    ATTR_SIZE,
    DEFAULT_PANEL_SIZE,
    MAX_BRIGHTNESS_PCT,
    MIN_BRIGHTNESS_PCT,
    PANEL_SIZES,
    SERVICE_UPLOAD_IMAGE,
)
from .entity import IdotMatrixEntity


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
        png_bytes = await self.hass.async_add_executor_job(
            _prepare_png, file_path, size
        )
        await self._run(self._client.upload_image(png_bytes))


def _prepare_png(file_path: str, size: int) -> bytes:
    """Normalize any input image to an exact-size RGB PNG (blocking; run in executor)."""
    from PIL import Image

    with Image.open(file_path) as img:
        img = img.convert("RGB")
        if img.size != (size, size):
            img = img.resize((size, size), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
