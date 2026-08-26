"""Stateless actions as buttons: freeze toggle and reset.

Freeze is a button rather than a switch on purpose: the panel only exposes a
toggle command and its state can't be read back, so a switch would lie about
which state the panel is in.
"""
from __future__ import annotations

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
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
    args = (data.client, data.availability, data.device_name)
    async_add_entities([IdotMatrixFreezeButton(*args), IdotMatrixResetButton(*args)])


class IdotMatrixFreezeButton(IdotMatrixEntity, ButtonEntity):
    _attr_name = "Toggle freeze"
    _attr_icon = "mdi:snowflake"

    def __init__(self, client, availability, device_name: str) -> None:
        super().__init__(client, availability, device_name, "freeze")

    async def async_press(self) -> None:
        await self._run(self._client.toggle_freeze())


class IdotMatrixResetButton(IdotMatrixEntity, ButtonEntity):
    _attr_name = "Reset"
    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, client, availability, device_name: str) -> None:
        super().__init__(client, availability, device_name, "reset")

    async def async_press(self) -> None:
        await self._run(self._client.reset())
