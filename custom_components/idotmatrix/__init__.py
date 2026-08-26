"""The iDotMatrix LED panel integration."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv, entity_platform

from .ble import IdotMatrixClient, IdotMatrixError
from .const import (
    ATTR_FILE_PATH,
    ATTR_FLIPPED,
    ATTR_SPEED,
    DOMAIN,
    SERVICE_FLIP,
    SERVICE_FREEZE,
    SERVICE_RESET,
    SERVICE_SET_SPEED,
    SERVICE_UPLOAD_IMAGE,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    client = IdotMatrixClient(hass, entry.data[CONF_ADDRESS])
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _async_register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        client: IdotMatrixClient = hass.data[DOMAIN].pop(entry.entry_id)
        await client.disconnect()
    return unloaded


def _async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_FLIP):
        return  # already registered by a previous entry

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_FLIP, {vol.Required(ATTR_FLIPPED): cv.boolean}, "async_flip"
    )
    platform.async_register_entity_service(SERVICE_FREEZE, {}, "async_toggle_freeze")
    platform.async_register_entity_service(SERVICE_RESET, {}, "async_reset")
    platform.async_register_entity_service(
        SERVICE_SET_SPEED,
        {vol.Required(ATTR_SPEED): vol.All(vol.Coerce(int), vol.Range(min=0, max=255))},
        "async_set_speed",
    )
    platform.async_register_entity_service(
        SERVICE_UPLOAD_IMAGE,
        {vol.Required(ATTR_FILE_PATH): cv.string},
        "async_upload_image_service",
    )
