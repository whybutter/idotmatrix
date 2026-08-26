"""The iDotMatrix LED panel integration."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant

from .availability import IdotMatrixAvailability
from .client import IdotMatrixClient

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SWITCH,
]


@dataclass
class IdotMatrixData:
    client: IdotMatrixClient
    availability: IdotMatrixAvailability
    device_name: str


IdotMatrixConfigEntry = ConfigEntry[IdotMatrixData]


async def async_setup_entry(hass: HomeAssistant, entry: IdotMatrixConfigEntry) -> bool:
    address: str = entry.data[CONF_ADDRESS]
    entry.runtime_data = IdotMatrixData(
        client=IdotMatrixClient(hass, address),
        availability=IdotMatrixAvailability(hass, address),
        device_name=entry.title,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: IdotMatrixConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        entry.runtime_data.availability.async_stop()
        await entry.runtime_data.client.disconnect()
    return unloaded
