"""Reset action as a button.

Note: there is deliberately no Freeze button. Disassembling the official app
showed it has no freeze command at all — the community `04 00 03 00` frame
freezes but the firmware never unfreezes from it (only a content-wiping reset
does). The app's way to hold a static display is to upload a still image
(the upload_image service), so that's what we expose instead.
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
    async_add_entities(
        [IdotMatrixResetButton(data.client, data.availability, data.device_name)]
    )


class IdotMatrixResetButton(IdotMatrixEntity, ButtonEntity):
    _attr_name = "Reset"
    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, client, availability, device_name: str) -> None:
        super().__init__(client, availability, device_name, "reset")

    async def async_press(self) -> None:
        await self._run(self._client.reset())
