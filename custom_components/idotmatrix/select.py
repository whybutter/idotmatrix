"""Clock and effect style selectors.

Picking a style immediately shows that mode on the panel, so these double as
one-tap "show clock / show effect" controls on the device page.
"""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IdotMatrixConfigEntry
from .const import CLOCK_STYLES, DEFAULT_EFFECT_COLORS, EFFECT_STYLES
from .entity import IdotMatrixEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IdotMatrixConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = entry.runtime_data
    args = (data.client, data.availability, data.device_name)
    async_add_entities([IdotMatrixClockSelect(*args), IdotMatrixEffectSelect(*args)])


class IdotMatrixClockSelect(IdotMatrixEntity, SelectEntity):
    _attr_name = "Clock style"
    _attr_icon = "mdi:clock-digital"
    _attr_options = list(CLOCK_STYLES)

    def __init__(self, client, availability, device_name: str) -> None:
        super().__init__(client, availability, device_name, "clock_style")
        self._attr_current_option = None

    async def async_select_option(self, option: str) -> None:
        await self._run(
            self._client.show_clock(CLOCK_STYLES[option], True, True, 255, 255, 255)
        )
        self._attr_current_option = option
        self.async_write_ha_state()


class IdotMatrixEffectSelect(IdotMatrixEntity, SelectEntity):
    _attr_name = "Effect"
    _attr_icon = "mdi:animation-play"
    _attr_options = list(EFFECT_STYLES)

    def __init__(self, client, availability, device_name: str) -> None:
        super().__init__(client, availability, device_name, "effect_style")
        self._attr_current_option = None

    async def async_select_option(self, option: str) -> None:
        await self._run(
            self._client.show_effect(EFFECT_STYLES[option], DEFAULT_EFFECT_COLORS)
        )
        self._attr_current_option = option
        self.async_write_ha_state()
