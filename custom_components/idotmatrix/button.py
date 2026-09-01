"""Action buttons: reset, chronograph, countdown, send-text, mic rhythm.

Note: there is deliberately no Freeze button. Disassembling the official app
showed it has no freeze command at all — the community `04 00 03 00` frame
freezes but the firmware never unfreezes from it (only a content-wiping reset
does). The app's way to hold a static display is to upload a still image, so
that's what we expose instead.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IdotMatrixConfigEntry
from .const import CHRONOGRAPH_ACTIONS, COUNTDOWN_ACTIONS
from .entity import IdotMatrixEntity
from .light import _render_text_bitmaps


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IdotMatrixConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = entry.runtime_data
    c, av, name, st = data.client, data.availability, data.device_name, data.state

    entities: list[ButtonEntity] = [IdotMatrixResetButton(c, av, name)]

    # Chronograph
    for key, action in (("start", "start"), ("pause", "pause"), ("reset", "reset")):
        entities.append(
            IdotMatrixActionButton(
                c, av, name, f"chrono_{key}", f"Chronograph {key}", "mdi:timer",
                lambda cl, a=action: cl.chronograph(CHRONOGRAPH_ACTIONS[a]),
            )
        )
    # Countdown start/stop (uses stored minutes/seconds)
    entities.append(
        IdotMatrixActionButton(
            c, av, name, "countdown_start", "Countdown start", "mdi:timer-play",
            lambda cl: cl.countdown(
                COUNTDOWN_ACTIONS["start"], st.countdown_minutes, st.countdown_seconds
            ),
        )
    )
    entities.append(
        IdotMatrixActionButton(
            c, av, name, "countdown_stop", "Countdown stop", "mdi:timer-off",
            lambda cl: cl.countdown(COUNTDOWN_ACTIONS["stop"], 0, 0),
        )
    )
    # Show the stored on-device album (carousel) without re-uploading it —
    # the way back to the album after clock/text/any other mode.
    entities.append(
        IdotMatrixActionButton(
            c, av, name, "show_album", "Show album", "mdi:view-carousel",
            lambda cl: cl.show_album(),
        )
    )
    # Send text (renders the Message text entity's stored value)
    entities.append(IdotMatrixSendTextButton(c, av, name, st, hass))

    async_add_entities(entities)


class IdotMatrixResetButton(IdotMatrixEntity, ButtonEntity):
    _attr_name = "Reset"
    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, client, availability, device_name: str) -> None:
        super().__init__(client, availability, device_name, "reset")

    async def async_press(self) -> None:
        await self._run(self._client.reset())


class IdotMatrixActionButton(IdotMatrixEntity, ButtonEntity):
    """Generic button that runs a client coroutine."""

    def __init__(
        self,
        client,
        availability,
        device_name: str,
        key: str,
        name: str,
        icon: str,
        action: Callable[[object], Awaitable[None]],
    ) -> None:
        super().__init__(client, availability, device_name, key)
        self._attr_name = name
        self._attr_icon = icon
        self._action = action

    async def async_press(self) -> None:
        await self._run(self._action(self._client))


class IdotMatrixSendTextButton(IdotMatrixEntity, ButtonEntity):
    _attr_name = "Send text"
    _attr_icon = "mdi:send"

    def __init__(self, client, availability, device_name: str, state, hass) -> None:
        super().__init__(client, availability, device_name, "send_text")
        self._state = state
        self._hass = hass

    async def async_press(self) -> None:
        text = self._state.text_message
        if not text:
            return
        bitmaps = await self._hass.async_add_executor_job(_render_text_bitmaps, text)
        # marquee, white, default speed
        await self._run(
            self._client.send_text(bitmaps, 1, 95, 0, (255, 255, 255), 0, (0, 0, 0))
        )
