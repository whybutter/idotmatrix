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
    st = data.state
    async_add_entities(
        [
            IdotMatrixSpeedNumber(*args),
            IdotMatrixScreenTimeNumber(*args),
            IdotMatrixScoreNumber(*args, st, 1),
            IdotMatrixScoreNumber(*args, st, 2),
            IdotMatrixCountdownNumber(*args, st, "minutes"),
            IdotMatrixCountdownNumber(*args, st, "seconds"),
            IdotMatrixMicNumber(*args, st, "sensitivity"),
            IdotMatrixMicNumber(*args, st, "style"),
        ]
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


class IdotMatrixScoreNumber(IdotMatrixEntity, NumberEntity):
    """One scoreboard counter. Both counters travel in every frame, so setting
    one re-sends both from shared state."""

    _attr_icon = "mdi:scoreboard"
    _attr_native_min_value = 0
    _attr_native_max_value = 999
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_assumed_state = True

    def __init__(self, client, availability, device_name: str, state, which: int) -> None:
        super().__init__(client, availability, device_name, f"score{which}")
        self._state = state
        self._which = which
        self._attr_name = f"Score {which}"
        self._attr_native_value = 0

    async def async_set_native_value(self, value: float) -> None:
        if self._which == 1:
            self._state.score1 = int(value)
        else:
            self._state.score2 = int(value)
        await self._run(
            self._client.scoreboard(self._state.score1, self._state.score2)
        )
        self._attr_native_value = value
        self.async_write_ha_state()


class IdotMatrixCountdownNumber(IdotMatrixEntity, NumberEntity):
    """Countdown minutes/seconds — stored only; the Countdown start button sends
    them (button.py)."""

    _attr_icon = "mdi:timer-sand"
    _attr_native_min_value = 0
    _attr_native_max_value = 59
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_assumed_state = True

    def __init__(self, client, availability, device_name: str, state, field: str) -> None:
        super().__init__(client, availability, device_name, f"countdown_{field}")
        self._state = state
        self._field = field
        self._attr_name = f"Countdown {field}"
        self._attr_native_value = 0

    async def async_set_native_value(self, value: float) -> None:
        setattr(self._state, f"countdown_{self._field}", int(value))
        self._attr_native_value = value
        self.async_write_ha_state()


class IdotMatrixMicNumber(IdotMatrixEntity, NumberEntity):
    """Mic-rhythm style/sensitivity — stored only; the 'Start mic rhythm' button
    applies them (button.py)."""

    _attr_mode = NumberMode.SLIDER
    _attr_assumed_state = True

    def __init__(self, client, availability, device_name: str, state, field: str) -> None:
        super().__init__(client, availability, device_name, f"mic_{field}")
        self._state = state
        self._field = field
        if field == "sensitivity":
            self._attr_name = "Mic sensitivity"
            self._attr_icon = "mdi:microphone"
            self._attr_native_min_value = 0
            self._attr_native_max_value = 100
            self._attr_native_value = state.mic_sensitivity
        else:
            self._attr_name = "Mic style"
            self._attr_icon = "mdi:animation"
            self._attr_native_min_value = 0
            self._attr_native_max_value = 20
            self._attr_mode = NumberMode.BOX
            self._attr_native_value = state.mic_style
        self._attr_native_step = 1

    async def async_set_native_value(self, value: float) -> None:
        setattr(self._state, f"mic_{self._field}", int(value))
        self._attr_native_value = value
        self.async_write_ha_state()
