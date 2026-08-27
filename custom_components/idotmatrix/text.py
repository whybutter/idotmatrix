"""A text entity holding the message to show; the 'Send text' button (button.py)
renders and sends it. Kept separate so typing doesn't fire a BLE write on every
keystroke."""
from __future__ import annotations

from homeassistant.components.text import TextEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IdotMatrixConfigEntry
from .const import MAX_TEXT_LEN
from .entity import IdotMatrixEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IdotMatrixConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = entry.runtime_data
    async_add_entities(
        [IdotMatrixMessageText(data.client, data.availability, data.device_name, data.state)]
    )


class IdotMatrixMessageText(IdotMatrixEntity, TextEntity):
    _attr_name = "Message"
    _attr_icon = "mdi:message-text"
    _attr_native_max = MAX_TEXT_LEN
    _attr_mode = "text"

    def __init__(self, client, availability, device_name: str, state) -> None:
        super().__init__(client, availability, device_name, "message")
        self._state = state
        self._attr_native_value = state.text_message

    async def async_set_value(self, value: str) -> None:
        self._state.text_message = value
        self._attr_native_value = value
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        # Editable regardless of BLE link; only sending needs the panel.
        return True
