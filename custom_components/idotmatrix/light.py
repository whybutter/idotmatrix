"""iDotMatrix panel exposed as an HA light entity (on/off + brightness)."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .ble import IdotMatrixClient, IdotMatrixError
from .const import DOMAIN, MAX_BRIGHTNESS_PCT, MIN_BRIGHTNESS_PCT

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    client: IdotMatrixClient = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([IdotMatrixLight(client, entry)])


def _pct_to_brightness(pct: int) -> int:
    return round(pct / 100 * 255)


def _brightness_to_pct(brightness: int) -> int:
    pct = round(brightness / 255 * 100)
    return max(MIN_BRIGHTNESS_PCT, min(MAX_BRIGHTNESS_PCT, pct))


class IdotMatrixLight(LightEntity):
    """Represents the panel's power + brightness. Everything else (flip,
    upload_image, freeze, reset, set_speed) is exposed as an entity service,
    see __init__.py / services.yaml."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_should_poll = False

    def __init__(self, client: IdotMatrixClient, entry: ConfigEntry) -> None:
        self._client = client
        self._attr_unique_id = entry.data[CONF_ADDRESS]
        self._attr_is_on: bool | None = None
        self._attr_brightness: int | None = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data[CONF_ADDRESS])},
            name="iDotMatrix Panel",
            manufacturer="iDotMatrix",
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        try:
            if (brightness := kwargs.get("brightness")) is not None:
                await self._client.set_brightness_pct(_brightness_to_pct(brightness))
                self._attr_brightness = brightness
            await self._client.turn_on()
        except IdotMatrixError as err:
            raise HomeAssistantError(str(err)) from err
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        try:
            await self._client.turn_off()
        except IdotMatrixError as err:
            raise HomeAssistantError(str(err)) from err
        self._attr_is_on = False
        self.async_write_ha_state()

    # -- entity services (registered in __init__.py) --

    async def async_flip(self, flipped: bool) -> None:
        try:
            await self._client.flip(flipped)
        except IdotMatrixError as err:
            raise HomeAssistantError(str(err)) from err

    async def async_toggle_freeze(self) -> None:
        try:
            await self._client.toggle_freeze()
        except IdotMatrixError as err:
            raise HomeAssistantError(str(err)) from err

    async def async_reset(self) -> None:
        try:
            await self._client.reset()
        except IdotMatrixError as err:
            raise HomeAssistantError(str(err)) from err

    async def async_set_speed(self, speed: int) -> None:
        try:
            await self._client.set_speed(speed)
        except IdotMatrixError as err:
            raise HomeAssistantError(str(err)) from err

    async def async_upload_image_service(self, file_path: str) -> None:
        if not self.hass.config.is_allowed_path(file_path):
            raise HomeAssistantError(f"{file_path} is not in an allowed HA path")
        try:
            png_bytes = await self.hass.async_add_executor_job(_read_file, file_path)
            await self._client.upload_image(png_bytes)
        except IdotMatrixError as err:
            raise HomeAssistantError(str(err)) from err


def _read_file(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()
