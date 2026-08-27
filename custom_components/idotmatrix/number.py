"""Animation speed as a number entity.

Kept as a diagnostic-ish config entity: per the maintained fork this command
is not referenced by the official app and likely only affects animated modes,
so it's disabled by default to avoid suggesting a control that may do nothing
on a static image.
"""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
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
        [IdotMatrixSpeedNumber(*args), IdotMatrixScreenTimeNumber(*args)]
    )


class IdotMatrixSpeedNumber(IdotMatrixEntity, NumberEntity):
    _attr_name = "Animation speed"
    _attr_icon = "mdi:speedometer"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False
    _attr_native_min_value = 0
    _attr_native_max_value = 255
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER
    _attr_assumed_state = True

    def __init__(self, client, availability, device_name: str) -> None:
        super().__init__(client, availability, device_name, "speed")

    async def async_set_native_value(self, value: float) -> None:
        await self._run(self._client.set_speed(int(value)))
        self._attr_native_value = value
        self.async_write_ha_state()


class IdotMatrixScreenTimeNumber(IdotMatrixEntity, NumberEntity):
    """Auto screen-off timeout (cmd 0x0f). Value is a device-defined unit; 0
    typically means 'always on'. Set-only — the panel's current value can't be
    read back without notify parsing, hence assumed_state."""

    _attr_name = "Screen-on time"
    _attr_icon = "mdi:monitor-off"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 0
    _attr_native_max_value = 255
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_assumed_state = True

    def __init__(self, client, availability, device_name: str) -> None:
        super().__init__(client, availability, device_name, "screen_on_time")

    async def async_set_native_value(self, value: float) -> None:
        await self._run(self._client.set_screen_on_time(int(value)))
        self._attr_native_value = value
        self.async_write_ha_state()
