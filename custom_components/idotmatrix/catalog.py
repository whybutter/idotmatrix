"""Online pixel-art catalog — browse a public emoji/art source and pull images
to the panel / gallery / albums. Uses OpenMoji (open-source emojis, CC-BY-SA);
everything is proxied through HA (metadata + images fetched server-side) so the
frontend never hits an external CDN (avoids HA's CSP and CORS).
"""
from __future__ import annotations

import logging

import voluptuous as vol
from aiohttp import web

from homeassistant.components import websocket_api
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

META_URL = "https://cdn.jsdelivr.net/npm/openmoji@15.0.0/data/openmoji.json"
IMG_URL = "https://cdn.jsdelivr.net/gh/hfg-gmuend/openmoji@master/color/72x72/{hex}.png"
# Human labels for OpenMoji's top-level groups (the ones worth showing).
GROUPS = {
    "smileys-emotion": "Caritas y emociones",
    "people-body": "Personas",
    "animals-nature": "Animales y naturaleza",
    "food-drink": "Comida y bebida",
    "travel-places": "Viajes y lugares",
    "activities": "Actividades",
    "objects": "Objetos",
    "symbols": "Símbolos",
    "flags": "Banderas",
}


class Catalog:
    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._meta: list[dict] | None = None
        self._img: dict[str, bytes] = {}

    async def meta(self) -> list[dict]:
        if self._meta is None:
            session = async_get_clientsession(self._hass)
            async with session.get(META_URL) as r:
                r.raise_for_status()
                self._meta = await r.json(content_type=None)
        return self._meta

    async def list_group(self, group: str, limit: int, offset: int) -> dict:
        meta = await self.meta()
        items = [m for m in meta if m.get("group") == group]
        page = items[offset : offset + limit]
        return {
            "items": [
                {"hexcode": m["hexcode"], "name": m.get("annotation", "")} for m in page
            ],
            "total": len(items),
        }

    async def image(self, hexcode: str) -> bytes | None:
        if hexcode in self._img:
            return self._img[hexcode]
        session = async_get_clientsession(self._hass)
        try:
            async with session.get(IMG_URL.format(hex=hexcode)) as r:
                if r.status != 200:
                    return None
                data = await r.read()
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("catalog image fetch failed: %s", err)
            return None
        self._img[hexcode] = data
        return data


class CatalogImageView(HomeAssistantView):
    """Serves catalog images same-origin (no auth — public art) so the frontend
    grid can use them directly as <img src>."""

    url = "/api/idotmatrix/catalog/img/{hexcode}"
    name = "api:idotmatrix:catalog:img"
    requires_auth = False

    def __init__(self, catalog: Catalog) -> None:
        self._catalog = catalog

    async def get(self, request: web.Request, hexcode: str) -> web.Response:
        if not hexcode or any(c not in "0123456789ABCDEFabcdef-" for c in hexcode):
            return web.Response(status=400)
        data = await self._catalog.image(hexcode.upper())
        if data is None:
            return web.Response(status=404)
        return web.Response(
            body=data,
            content_type="image/png",
            headers={"Cache-Control": "public, max-age=86400"},
        )


@callback
def async_register(hass: HomeAssistant) -> None:
    catalog = Catalog(hass)
    hass.data[f"{DOMAIN}_catalog"] = catalog
    hass.http.register_view(CatalogImageView(catalog))

    @websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/catalog/groups"})
    @websocket_api.async_response
    async def ws_groups(hass, connection, msg):
        connection.send_result(
            msg["id"],
            {"groups": [{"id": k, "name": v} for k, v in GROUPS.items()]},
        )

    @websocket_api.websocket_command(
        {
            vol.Required("type"): f"{DOMAIN}/catalog/list",
            vol.Required("group"): str,
            vol.Optional("limit", default=60): int,
            vol.Optional("offset", default=0): int,
        }
    )
    @websocket_api.async_response
    async def ws_list(hass, connection, msg):
        try:
            result = await catalog.list_group(
                msg["group"], msg["limit"], msg["offset"]
            )
        except Exception as err:  # noqa: BLE001
            connection.send_error(msg["id"], "catalog_error", str(err))
            return
        connection.send_result(msg["id"], result)

    websocket_api.async_register_command(hass, ws_groups)
    websocket_api.async_register_command(hass, ws_list)
