"""The iDotMatrix LED panel integration."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .availability import IdotMatrixAvailability
from .client import IdotMatrixClient
from .const import (
    CONF_GAMMA,
    CONF_PREFERRED_PROXY,
    CONF_WB_BLUE,
    CONF_WB_GREEN,
    CONF_WB_RED,
    DEFAULT_GAMMA,
    DEFAULT_MIC_SENSITIVITY,
    DEFAULT_WB_BLUE,
    DEFAULT_WB_GREEN,
    DEFAULT_WB_RED,
    CONF_MEDIA_PLAYER,
    CONF_MEDIA_REACTION,
    DOMAIN,
    PROXY_AUTO,
    REACTION_NONE,
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
    mic_style: int = 1  # "Dancing guy"; valid mic styles are 1-4
    mic_sensitivity: int = DEFAULT_MIC_SENSITIVITY


@dataclass
class IdotMatrixData:
    client: IdotMatrixClient
    availability: IdotMatrixAvailability
    device_name: str
    # Colour correction for this panel: (gamma, wb_red, wb_green, wb_blue).
    # See CONF_GAMMA / CONF_WB_RED in const.py. The entry reloads on an options
    # change, so this is always the current value.
    correction: tuple[float, float, float, float] = (
        DEFAULT_GAMMA,
        DEFAULT_WB_RED,
        DEFAULT_WB_GREEN,
        DEFAULT_WB_BLUE,
    )
    state: IdotMatrixState = field(default_factory=IdotMatrixState)
    # Optional media-player reaction (album art / mic dance while playing).
    media_reactor: object | None = None


IdotMatrixConfigEntry = ConfigEntry[IdotMatrixData]


CARD_URL = f"/{DOMAIN}/idotmatrix-card.js"
SCOREBOARD_CARD_URL = f"/{DOMAIN}/idotmatrix-scoreboard-card.js"
PANEL_URL = f"/{DOMAIN}/idotmatrix-panel.js"


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Serve + register the card/panel and gallery WS commands (once)."""
    if hass.data.get(f"{DOMAIN}_frontend"):
        return
    hass.data[f"{DOMAIN}_frontend"] = True

    from .gallery import async_register as async_register_gallery

    async_register_gallery(hass)

    from .albums import async_register as async_register_albums

    async_register_albums(hass)

    from .catalog import async_register as async_register_catalog

    async_register_catalog(hass)
    # Cache-busting: the static routes are served without a Cache-Control header,
    # so browsers (and the HA frontend service worker) will happily keep serving a
    # previously fetched bundle after an update — the panel then still shows the
    # OLD JS until a manual hard refresh. Appending the integration version to the
    # *referenced* URL changes it on every release, which forces a real fetch.
    # The static ROUTES stay at the bare paths; query strings don't affect routing.
    version = (await async_get_integration(hass, DOMAIN)).version or "dev"
    card_url = f"{CARD_URL}?v={version}"
    scoreboard_url = f"{SCOREBOARD_CARD_URL}?v={version}"
    panel_url = f"{PANEL_URL}?v={version}"

    fdir = os.path.join(os.path.dirname(__file__), "frontend")
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(CARD_URL, os.path.join(fdir, "idotmatrix-card.js"), False),
            StaticPathConfig(
                SCOREBOARD_CARD_URL,
                os.path.join(fdir, "idotmatrix-scoreboard-card.js"),
                False,
            ),
            StaticPathConfig(PANEL_URL, os.path.join(fdir, "idotmatrix-panel.js"), False),
        ]
    )
    from homeassistant.components.frontend import add_extra_js_url

    add_extra_js_url(hass, card_url)
    add_extra_js_url(hass, scoreboard_url)

    from homeassistant.components import panel_custom

    try:
        await panel_custom.async_register_panel(
            hass,
            frontend_url_path=DOMAIN,
            webcomponent_name="idotmatrix-panel",
            js_url=panel_url,
            sidebar_title="iDotMatrix",
            sidebar_icon="mdi:view-grid-plus",
            require_admin=False,
            config={},
            embed_iframe=False,
        )
    except ValueError:
        # Already registered (e.g. a second config entry) — fine.
        pass


async def async_setup_entry(hass: HomeAssistant, entry: IdotMatrixConfigEntry) -> bool:
    await _async_register_frontend(hass)
    address: str = entry.data[CONF_ADDRESS]
    preferred = entry.options.get(CONF_PREFERRED_PROXY, PROXY_AUTO)
    preferred_source = None if preferred == PROXY_AUTO else preferred
    availability = IdotMatrixAvailability(hass, address)
    client = IdotMatrixClient(hass, address, preferred_source=preferred_source)
    # Stay "available" while we hold a connection (the panel stops advertising
    # when connected, which would otherwise flip the entity to unavailable).
    client.set_connection_listener(availability.async_set_connected)
    entry.runtime_data = IdotMatrixData(
        client=client,
        availability=availability,
        device_name=entry.title,
        correction=(
            entry.options.get(CONF_GAMMA, DEFAULT_GAMMA),
            entry.options.get(CONF_WB_RED, DEFAULT_WB_RED),
            entry.options.get(CONF_WB_GREEN, DEFAULT_WB_GREEN),
            entry.options.get(CONF_WB_BLUE, DEFAULT_WB_BLUE),
        ),
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    reaction = entry.options.get(CONF_MEDIA_REACTION, REACTION_NONE)
    media_entity = entry.options.get(CONF_MEDIA_PLAYER)
    if reaction != REACTION_NONE and media_entity:
        from .media_react import MediaReactor

        reactor = MediaReactor(hass, entry.runtime_data, media_entity, reaction)
        reactor.start()
        entry.runtime_data.media_reactor = reactor

    entry.async_on_unload(entry.add_update_listener(_async_reload_on_options))
    return True


async def _async_reload_on_options(
    hass: HomeAssistant, entry: IdotMatrixConfigEntry
) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: IdotMatrixConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        if (mgr := hass.data.get(f"{DOMAIN}_slideshow")) is not None:
            mgr.clear_state(entry.entry_id)
        if (reactor := entry.runtime_data.media_reactor) is not None:
            reactor.stop()
        entry.runtime_data.availability.async_stop()
        await entry.runtime_data.client.disconnect()
    return unloaded
