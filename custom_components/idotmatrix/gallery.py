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
            "name": name or "untitled",
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

    async def async_delete(self, item_ids: list[str]) -> int:
        """Delete one or many items in a SINGLE store write.

        Bulk matters because every save rewrites the whole store, base64 image
        data included — deleting N items one at a time is N full rewrites.
        Returns how many items actually existed and were removed.
        """
        items = await self._load()
        drop = set(item_ids)
        kept = [i for i in items if i["id"] not in drop]
        removed = len(items) - len(kept)
        if removed:
            self._items = kept
            await self._store.async_save({"items": self._items})
        return removed


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
        #
        # item_id (single) is still accepted so a panel left cached in a browser
        # from an older release keeps working.
        {
            vol.Required("type"): f"{DOMAIN}/gallery/delete",
            vol.Optional("item_id"): str,
            vol.Optional("item_ids"): [str],
        }
    )
    @websocket_api.async_response
    async def ws_delete(hass, connection, msg):
        ids = list(msg.get("item_ids") or [])
        if (single := msg.get("item_id")) is not None:
            ids.append(single)
        if not ids:
            connection.send_error(
                msg["id"], "invalid_format", "item_id or item_ids is required"
            )
            return
        removed = await store.async_delete(ids)
        connection.send_result(msg["id"], {"success": True, "removed": removed})

    websocket_api.async_register_command(hass, ws_list)
    websocket_api.async_register_command(hass, ws_add)
    websocket_api.async_register_command(hass, ws_delete)
