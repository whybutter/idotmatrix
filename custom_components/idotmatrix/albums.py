"""Albums = DEVICE-side slideshow. Gallery items are grouped into an album and
flashed into the panel's persistent asset memory in one go; the panel then
carousels them itself. No HA timer, no re-upload flash, and it survives HA
restarts and BLE disconnects.

Every asset is uploaded through the GIF agreement (stills as single-frame GIFs)
and encoded to last the album's interval — see SlideshowManager.play and
light._prepare_still_as_gif for the hardware reasons behind both.
"""
from __future__ import annotations

import asyncio
import base64
import logging
import time

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY = f"{DOMAIN}_albums"
STORAGE_VERSION = 1
MIN_INTERVAL = 3
DEFAULT_INTERVAL = 10


class AlbumStore:
    def __init__(self, hass: HomeAssistant) -> None:
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._albums: list[dict] | None = None
        self._seq = 0

    async def _load(self) -> list[dict]:
        if self._albums is None:
            data = await self._store.async_load() or {}
            self._albums = data.get("albums", [])
        return self._albums

    async def async_list(self) -> list[dict]:
        return list(await self._load())

    async def async_save(self, album: dict) -> dict:
        albums = await self._load()
        if not album.get("id"):
            self._seq += 1
            album = {**album, "id": f"{int(time.time())}-{self._seq}"}
            albums.insert(0, album)
        else:
            for i, a in enumerate(albums):
                if a["id"] == album["id"]:
                    albums[i] = {**a, **album}
                    break
            else:
                albums.insert(0, album)
        await self._store.async_save({"albums": albums})
        return album

    async def async_delete(self, album_id: str) -> None:
        albums = await self._load()
        self._albums = [a for a in albums if a["id"] != album_id]
        await self._store.async_save({"albums": self._albums})


class SlideshowManager:
    """Device-side album playback. Instead of an HA timer re-uploading (which
    flashes), we flash the whole album into the panel's asset memory once and
    let the DEVICE carousel it (interval baked per-asset). No flash, persists,
    survives HA disconnects."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._playing: dict[str, str] = {}  # entry_id -> album_id

    def is_playing(self, entry_id: str) -> str | None:
        return self._playing.get(entry_id)

    def _client_for(self, entity_id: str):
        ent = er.async_get(self._hass).async_get(entity_id)
        if not ent or not ent.config_entry_id:
            return None, None
        entry = self._hass.config_entries.async_get_entry(ent.config_entry_id)
        if not entry or not getattr(entry, "runtime_data", None):
            return None, None
        return entry.entry_id, entry.runtime_data.client

    async def play(self, entity_id: str, album: dict, gallery_items: dict) -> None:
        from . import protocol
        from .light import _prepare_gif, _prepare_still_as_gif

        entry_id, client = self._client_for(entity_id)
        if client is None:
            raise ValueError("device not found for entity")
        entry = self._hass.config_entries.async_get_entry(entry_id)
        correction = entry.runtime_data.correction
        items = [
            gallery_items[i] for i in album.get("item_ids", []) if i in gallery_items
        ]
        if not items:
            raise ValueError("album has no (existing) images")
        time_key = protocol.seconds_to_time_key(
            int(album.get("interval", DEFAULT_INTERVAL))
        )
        # The panel only supports a few discrete intervals, so the dwell an asset
        # is encoded for has to be the one the device actually rounded to. The
        # carousel advances after ONE pass through a GIF's frames (it ignores
        # both the header time-sign and the GIF loop count), so this dwell is what
        # gives every slide — still or animated — the interval the user asked for.
        dwell = protocol.convert_time(time_key)
        # EVERY album asset goes through the GIF agreement — stills as
        # single-frame GIFs. The panel keeps stills (asset type 0x02) and
        # animations (0x01) in separate banks and carousels only the GIF bank
        # when both are populated, so a mixed album silently dropped its stills.
        # See _prepare_still_as_gif for the hardware evidence.
        block_lists: list[list[bytes]] = []
        for index, item in enumerate(items):
            raw = base64.b64decode(item["image_data"])
            size = int(item.get("size", 32))
            if item.get("is_gif"):
                gif = await self._hass.async_add_executor_job(
                    _prepare_gif, raw, size, (0, 0, 0), correction, dwell
                )
            else:
                gif = await self._hass.async_add_executor_job(
                    _prepare_still_as_gif, raw, size, dwell, (0, 0, 0), correction
                )
            # byte[15] = album slot index (0-based), NOT 0xFF.
            block_lists.append(protocol.build_gif_upload(gif, index, time_key))
        await client.save_album(block_lists)
        self._playing[entry_id] = album["id"]

    async def stop(self, entity_id: str) -> None:
        entry_id, client = self._client_for(entity_id)
        if client is not None:
            await client.clear_album()
        if entry_id:
            self._playing.pop(entry_id, None)

    def clear_state(self, entry_id: str) -> None:
        """Drop tracking without touching the device (used on unload — the
        device keeps its stored album on purpose)."""
        self._playing.pop(entry_id, None)


@callback
def async_register(hass: HomeAssistant) -> None:
    store = AlbumStore(hass)
    manager = SlideshowManager(hass)
    hass.data[f"{DOMAIN}_albums"] = store
    hass.data[f"{DOMAIN}_slideshow"] = manager

    @websocket_api.websocket_command(
        {
            vol.Required("type"): f"{DOMAIN}/albums/list",
            vol.Optional("entity_id"): str,
        }
    )
    @websocket_api.async_response
    async def ws_list(hass, connection, msg):
        albums = await store.async_list()
        playing_album_id = None
        if (entity_id := msg.get("entity_id")):
            ent = er.async_get(hass).async_get(entity_id)
            if ent and ent.config_entry_id:
                playing_album_id = manager.is_playing(ent.config_entry_id)
        connection.send_result(
            msg["id"], {"albums": albums, "playing_album_id": playing_album_id}
        )

    @websocket_api.websocket_command(
        {
            vol.Required("type"): f"{DOMAIN}/albums/save",
            vol.Optional("album_id"): str,
            vol.Required("name"): str,
            vol.Required("item_ids"): [str],
            vol.Optional("interval", default=DEFAULT_INTERVAL): int,
        }
    )
    @websocket_api.async_response
    async def ws_save(hass, connection, msg):
        album = await store.async_save(
            {
                "id": msg.get("album_id"),
                "name": msg["name"],
                "item_ids": msg["item_ids"],
                "interval": msg["interval"],
            }
        )
        connection.send_result(msg["id"], {"album": album})

    @websocket_api.websocket_command(
        {vol.Required("type"): f"{DOMAIN}/albums/delete", vol.Required("album_id"): str}
    )
    @websocket_api.async_response
    async def ws_delete(hass, connection, msg):
        await store.async_delete(msg["album_id"])
        connection.send_result(msg["id"], {"success": True})

    @websocket_api.websocket_command(
        {
            vol.Required("type"): f"{DOMAIN}/albums/play",
            vol.Required("album_id"): str,
            vol.Required("entity_id"): str,
        }
    )
    @websocket_api.async_response
    async def ws_play(hass, connection, msg):
        albums = await store.async_list()
        album = next((a for a in albums if a["id"] == msg["album_id"]), None)
        gstore = hass.data.get(f"{DOMAIN}_gallery")
        if album is None or gstore is None:
            connection.send_error(msg["id"], "not_found", "album/gallery missing")
            return
        gmap = {i["id"]: i for i in await gstore.async_list()}
        try:
            await manager.play(msg["entity_id"], album, gmap)
        except ValueError as err:
            connection.send_error(msg["id"], "cannot_play", str(err))
            return
        connection.send_result(msg["id"], {"playing": album["id"]})

    @websocket_api.websocket_command(
        {vol.Required("type"): f"{DOMAIN}/albums/stop", vol.Required("entity_id"): str}
    )
    @websocket_api.async_response
    async def ws_stop(hass, connection, msg):
        try:
            await manager.stop(msg["entity_id"])
        except (ValueError, Exception) as err:  # noqa: BLE001
            connection.send_error(msg["id"], "cannot_stop", str(err))
            return
        connection.send_result(msg["id"], {"success": True})

    for cmd in (ws_list, ws_save, ws_delete, ws_play, ws_stop):
        websocket_api.async_register_command(hass, cmd)
