"""Flip (180° rotation) as a switch — we send an explicit on/off state."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IdotMatrixConfigEntry
from .entity import IdotMatrixEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IdotMatrixConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = entry.runtime_data
    async_add_entities(
        [IdotMatrixFlipSwitch(data.client, data.availability, data.device_name)]
    )


class IdotMatrixFlipSwitch(IdotMatrixEntity, SwitchEntity):
    _attr_name = "Flip display"
    _attr_icon = "mdi:flip-vertical"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_assumed_state = True  # panel state can't be read back

    def __init__(self, client, availability, device_name: str) -> None:
        super().__init__(client, availability, device_name, "flip")

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._run(self._client.set_flip(True))
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._run(self._client.set_flip(False))
        self._attr_is_on = False
        self.async_write_ha_state()
