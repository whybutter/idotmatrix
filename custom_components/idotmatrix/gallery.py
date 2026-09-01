"""Personal image/GIF gallery for the panel — stored in HA and browsed from the
custom panel. Sending a stored item to the panel is done frontend-side via the
existing upload_image/upload_gif services (the item's base64 is in the list),
so this module only handles storage + list/add/delete over the WebSocket API.
"""
from __future__ import annotations

import time

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store

from .const import DOMAIN

STORAGE_KEY = f"{DOMAIN}_gallery"
STORAGE_VERSION = 1
MAX_ITEMS = 100


class GalleryStore:
    def __init__(self, hass: HomeAssistant) -> None:
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._items: list[dict] | None = None
        self._seq = 0

    async def _load(self) -> list[dict]:
        if self._items is None:
            data = await self._store.async_load() or {}
            self._items = data.get("items", [])
        return self._items

    async def async_list(self) -> list[dict]:
        return list(await self._load())

    async def async_add(
        self, name: str, image_data: str, size: int, is_gif: bool, mime: str
    ) -> dict:
        items = await self._load()
        self._seq += 1
        item = {
            "id": f"{int(time.time())}-{self._seq}",
            "name": name or "sin nombre",
            "image_data": image_data,
            "mime": mime or ("image/gif" if is_gif else "image/png"),
            "size": size,
            "is_gif": is_gif,
            "created": time.time(),
        }
        items.insert(0, item)
        del items[MAX_ITEMS:]
        await self._store.async_save({"items": items})
        return item

    async def async_delete(self, item_id: str) -> None:
        items = await self._load()
        self._items = [i for i in items if i["id"] != item_id]
        await self._store.async_save({"items": self._items})


@callback
def async_register(hass: HomeAssistant) -> None:
    """Register the gallery WebSocket commands (once)."""
    store = GalleryStore(hass)
    hass.data[f"{DOMAIN}_gallery"] = store

    @websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/gallery/list"})
    @websocket_api.async_response
    async def ws_list(hass, connection, msg):
        connection.send_result(msg["id"], {"items": await store.async_list()})

    @websocket_api.websocket_command(
        {
            vol.Required("type"): f"{DOMAIN}/gallery/add",
            vol.Required("name"): str,
            vol.Required("image_data"): str,
            vol.Required("size"): int,
            vol.Optional("is_gif", default=False): bool,
            vol.Optional("mime", default=""): str,
        }
    )
    @websocket_api.async_response
    async def ws_add(hass, connection, msg):
        item = await store.async_add(
            msg["name"], msg["image_data"], msg["size"], msg["is_gif"], msg["mime"]
        )
        connection.send_result(msg["id"], {"item": item})

    @websocket_api.websocket_command(
        # NOT "id": that key is HA's own websocket message identifier (an int),
        # so declaring it as a str both fails validation ("expected str ... Got
        # 242") and would shadow the message id we need for send_result.
        {vol.Required("type"): f"{DOMAIN}/gallery/delete", vol.Required("item_id"): str}
    )
    @websocket_api.async_response
    async def ws_delete(hass, connection, msg):
        await store.async_delete(msg["item_id"])
        connection.send_result(msg["id"], {"success": True})

    websocket_api.async_register_command(hass, ws_list)
    websocket_api.async_register_command(hass, ws_add)
    websocket_api.async_register_command(hass, ws_delete)
