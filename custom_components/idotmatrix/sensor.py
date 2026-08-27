"""Diagnostic sensors from the panel's auto-pushed device-info notification.

On connect the panel sends `09 00 01 80 <fw_major> <fw_minor> <sub> <type> <flag>`
on fa03; the client parses it (protocol.parse_device_info) into firmware and
panel type. Note firmware over BLE is only major.minor — the app shows a fuller
string it fetches from a cloud API, which we don't use.
"""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
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
    async_add_entities(
        [
            IdotMatrixInfoSensor(*args, "firmware", "Firmware", "mdi:chip"),
            IdotMatrixInfoSensor(*args, "panel_type", "Panel type", "mdi:grid"),
        ]
    )


class IdotMatrixInfoSensor(IdotMatrixEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, client, availability, device_name: str, key: str, name: str, icon: str
    ) -> None:
        super().__init__(client, availability, device_name, key)
        self._key = key
        self._attr_name = name
        self._attr_icon = icon

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            self._client.add_device_info_listener(self.async_write_ha_state)
        )

    @property
    def native_value(self):
        info = self._client.device_info
        return info.get(self._key) if info else None