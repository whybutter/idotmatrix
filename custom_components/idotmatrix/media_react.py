"""React to a media player: show album art or dance to the beat while it plays.

Opt-in per panel via the integration options (a media_player entity + a reaction
mode). When the chosen player starts playing we either push the current track's
album art to the panel or start the on-device microphone visualizer; when it
stops we return the panel to its stored album (carousel). All of this is driven
here rather than by a user-authored automation so it's a single toggle.

Nothing here blocks or raises into HA's state machine — a failed BLE push is
logged and swallowed, since the panel being briefly unreachable must not break
media playback.
"""
from __future__ import annotations

import logging

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

from .const import REACTION_ALBUM_ART, REACTION_MIC_DANCE

_LOGGER = logging.getLogger(__name__)

# media_player states we treat as "audio is on".
_PLAYING = {"playing"}


class MediaReactor:
    """Bridges one media_player's play/stop to a panel reaction."""

    def __init__(
        self,
        hass: HomeAssistant,
        data,
        media_entity: str,
        reaction: str,
    ) -> None:
        self._hass = hass
        self._data = data
        self._media_entity = media_entity
        self._reaction = reaction
        self._unsub = None
        self._active = False

    @callback
    def start(self) -> None:
        self._unsub = async_track_state_change_event(
            self._hass, [self._media_entity], self._on_change
        )
        # Sync to the current state (e.g. music already playing at setup/reload).
        state = self._hass.states.get(self._media_entity)
        if state is not None and state.state in _PLAYING:
            self._hass.async_create_task(self._react_playing(state))

    @callback
    def stop(self) -> None:
        if self._unsub is not None:
            self._unsub()
            self._unsub = None

    @callback
    def _on_change(self, event: Event) -> None:
        new = event.data.get("new_state")
        old = event.data.get("old_state")
        now_playing = new is not None and new.state in _PLAYING
        was_playing = old is not None and old.state in _PLAYING
        if now_playing and not was_playing:
            self._active = True
            self._hass.async_create_task(self._react_playing(new))
        elif now_playing and was_playing and self._reaction == REACTION_ALBUM_ART:
            # Track changed while still playing — refresh the art if it moved.
            if self._art_url(new) != self._art_url(old):
                self._hass.async_create_task(self._react_playing(new))
        elif was_playing and not now_playing and self._active:
            self._active = False
            self._hass.async_create_task(self._react_stopped())

    @staticmethod
    def _art_url(state) -> str | None:
        if state is None:
            return None
        # entity_picture is a relative HA path (proxied art) or an absolute URL.
        return state.attributes.get("entity_picture")

    async def _react_playing(self, state) -> None:
        try:
            if self._reaction == REACTION_ALBUM_ART:
                url = self._art_url(state)
                if not url:
                    _LOGGER.debug("No album art for %s yet", self._media_entity)
                    return
                if url.startswith("/"):
                    base = self._hass.config.external_url or self._hass.config.internal_url
                    if not base:
                        # Fall back to the loopback the HTTP server always answers.
                        from homeassistant.helpers.network import NoURLAvailableError, get_url

                        try:
                            base = get_url(self._hass, prefer_external=False)
                        except NoURLAvailableError:
                            _LOGGER.debug("No HA URL to resolve album art path")
                            return
                    url = base.rstrip("/") + url
                await self._upload_art(url)
            elif self._reaction == REACTION_MIC_DANCE:
                st = self._data.state
                await self._data.client.mic_rhythm(st.mic_style, st.mic_sensitivity)
        except Exception as err:  # noqa: BLE001 — never break playback
            _LOGGER.warning("Panel reaction to %s failed: %s", self._media_entity, err)

    async def _react_stopped(self) -> None:
        try:
            await self._data.client.show_album()
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Panel revert after %s stopped failed: %s", self._media_entity, err)

    async def _upload_art(self, url: str) -> None:
        # Import here to avoid a light<->media_react import cycle at module load.
        from .light import _prepare_pixels

        from homeassistant.helpers.aiohttp_client import async_get_clientsession
        import aiohttp

        session = async_get_clientsession(self._hass)
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                resp.raise_for_status()
                raw = await resp.read()
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.warning("Couldn't fetch album art %s: %s", url, err)
            return
        if not raw:
            return
        pixels = await self._hass.async_add_executor_job(
            _prepare_pixels, raw, 32, (0, 0, 0), self._data.correction
        )
        await self._data.client.upload_image(pixels)
