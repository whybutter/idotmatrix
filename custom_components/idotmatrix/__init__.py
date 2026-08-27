"""The iDotMatrix LED panel integration."""
from __future__ import annotations

from dataclasses import dataclass, field

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant

from .availability import IdotMatrixAvailability
from .client import IdotMatrixClient
from .const import (
    CONF_PREFERRED_PROXY,
    DEFAULT_MIC_SENSITIVITY,
    PROXY_AUTO,
)

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TEXT,
]


@dataclass
class IdotMatrixState:
    """Shared UI state for entities that must remember values and re-send them
    together (the panel takes whole frames, not deltas)."""

    text_message: str = ""
    score1: int = 0
    score2: int = 0
    countdown_minutes: int = 0
    countdown_seconds: int = 0
    mic_style: int = 0
    mic_sensitivity: int = DEFAULT_MIC_SENSITIVITY


@dataclass
class IdotMatrixData:
    client: IdotMatrixClient
    availability: IdotMatrixAvailability
    device_name: str
    state: IdotMatrixState = field(default_factory=IdotMatrixState)


IdotMatrixConfigEntry = ConfigEntry[IdotMatrixData]


async def async_setup_entry(hass: HomeAssistant, entry: IdotMatrixConfigEntry) -> bool:
    address: str = entry.data[CONF_ADDRESS]
    preferred = entry.options.get(CONF_PREFERRED_PROXY, PROXY_AUTO)
    preferred_source = None if preferred == PROXY_AUTO else preferred
    entry.runtime_data = IdotMatrixData(
        client=IdotMatrixClient(hass, address, preferred_source=preferred_source),
        availability=IdotMatrixAvailability(hass, address),
        device_name=entry.title,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_on_options))
    return True


async def _async_reload_on_options(
    hass: HomeAssistant, entry: IdotMatrixConfigEntry
) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: IdotMatrixConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        entry.runtime_data.availability.async_stop()
        await entry.runtime_data.client.disconnect()
    return unloaded
