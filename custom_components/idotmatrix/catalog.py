"""Online pixel-art catalog — browse public art sources and pull images to the
panel / gallery / albums.

Multi-source: each source implements groups()/list_group()/image(). Everything is
proxied through HA (metadata + images fetched server-side) so the frontend never
hits an external CDN directly (avoids HA's CSP/CORS) and GIF/PNG bytes are cached.

Sources:
  * openmoji — open-source emojis (CC BY-SA 4.0), still PNGs.
  * poke     — Pokémon "Showdown" sprites (animated GIFs). Pixel art, animated.
               Pokémon © Nintendo/Game Freak — personal/hobby use only.
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


class CatalogSource:
    """Base class for a catalog source."""

    id: str = ""
    name: str = ""

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass

    async def groups(self) -> list[dict]:
        """[{id, name}] — the browseable categories for this source."""
        raise NotImplementedError

    async def list_group(self, group: str, limit: int, offset: int) -> dict:
        """{items: [{ref, name, is_gif}], total}."""
        raise NotImplementedError

    async def image(self, ref: str) -> tuple[bytes, str] | None:
        """(bytes, content_type) for one item, or None."""
        raise NotImplementedError


# --------------------------------------------------------------------------- #
# OpenMoji — still emoji PNGs                                                  #
# --------------------------------------------------------------------------- #
class OpenMojiSource(CatalogSource):
    id = "openmoji"
    name = "OpenMoji"

    META_URL = "https://cdn.jsdelivr.net/npm/openmoji@15.0.0/data/openmoji.json"
    IMG_URL = "https://cdn.jsdelivr.net/gh/hfg-gmuend/openmoji@master/color/72x72/{hex}.png"
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

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(hass)
        self._meta: list[dict] | None = None
        self._img: dict[str, bytes] = {}

    async def _get_meta(self) -> list[dict]:
        if self._meta is None:
            session = async_get_clientsession(self._hass)
            async with session.get(self.META_URL) as r:
                r.raise_for_status()
                self._meta = await r.json(content_type=None)
        return self._meta

    async def groups(self) -> list[dict]:
        return [{"id": k, "name": v} for k, v in self.GROUPS.items()]

    async def list_group(self, group: str, limit: int, offset: int) -> dict:
        meta = await self._get_meta()
        items = [m for m in meta if m.get("group") == group]
        page = items[offset : offset + limit]
        return {
            "items": [
                {
                    "ref": m["hexcode"],
                    "name": m.get("annotation", ""),
                    "is_gif": False,
                }
                for m in page
            ],
            "total": len(items),
        }

    async def image(self, ref: str) -> tuple[bytes, str] | None:
        if not ref or any(c not in "0123456789ABCDEFabcdef-" for c in ref):
            return None
        ref = ref.upper()
        if ref in self._img:
            return self._img[ref], "image/png"
        session = async_get_clientsession(self._hass)
        try:
            async with session.get(self.IMG_URL.format(hex=ref)) as r:
                if r.status != 200:
                    return None
                data = await r.read()
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("openmoji image fetch failed: %s", err)
            return None
        self._img[ref] = data
        return data, "image/png"


# --------------------------------------------------------------------------- #
# PokéAPI — animated "Showdown" sprite GIFs                                    #
# --------------------------------------------------------------------------- #
class PokeSource(CatalogSource):
    id = "poke"
    name = "Pokémon"

    LIST_URL = "https://pokeapi.co/api/v2/pokemon?limit=1302&offset=0"
    IMG_URL = (
        "https://cdn.jsdelivr.net/gh/PokeAPI/sprites@master/"
        "sprites/pokemon/other/showdown/{id}.gif"
    )
    # National-dex generation ranges (inclusive). Later gens have patchier
    # Showdown coverage but most early-gen sprites animate cleanly.
    GENERATIONS = [
        ("gen1", "Gen 1 · Kanto", 1, 151),
        ("gen2", "Gen 2 · Johto", 152, 251),
        ("gen3", "Gen 3 · Hoenn", 252, 386),
        ("gen4", "Gen 4 · Sinnoh", 387, 493),
        ("gen5", "Gen 5 · Teselia", 494, 649),
        ("gen6", "Gen 6 · Kalos", 650, 721),
        ("gen7", "Gen 7 · Alola", 722, 809),
        ("gen8", "Gen 8 · Galar", 810, 905),
        ("gen9", "Gen 9 · Paldea", 906, 1025),
    ]

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(hass)
        self._names: dict[int, str] | None = None  # id -> display name
        self._img: dict[str, bytes] = {}

    async def _get_names(self) -> dict[int, str]:
        if self._names is None:
            session = async_get_clientsession(self._hass)
            names: dict[int, str] = {}
            try:
                async with session.get(self.LIST_URL) as r:
                    r.raise_for_status()
                    data = await r.json(content_type=None)
                for entry in data.get("results", []):
                    # url: https://pokeapi.co/api/v2/pokemon/25/
                    parts = [p for p in entry["url"].split("/") if p]
                    try:
                        pid = int(parts[-1])
                    except ValueError:
                        continue
                    if pid <= 1025:
                        names[pid] = entry["name"].replace("-", " ").title()
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("pokeapi list fetch failed: %s", err)
            self._names = names
        return self._names

    async def groups(self) -> list[dict]:
        return [{"id": g[0], "name": g[1]} for g in self.GENERATIONS]

    async def list_group(self, group: str, limit: int, offset: int) -> dict:
        gen = next((g for g in self.GENERATIONS if g[0] == group), None)
        if gen is None:
            return {"items": [], "total": 0}
        _, _, lo, hi = gen
        names = await self._get_names()
        ids = list(range(lo, hi + 1))
        page = ids[offset : offset + limit]
        return {
            "items": [
                {
                    "ref": str(pid),
                    "name": names.get(pid, f"#{pid}"),
                    "is_gif": True,
                }
                for pid in page
            ],
            "total": len(ids),
        }

    async def image(self, ref: str) -> tuple[bytes, str] | None:
        if not ref.isdigit():
            return None
        if ref in self._img:
            return self._img[ref], "image/gif"
        session = async_get_clientsession(self._hass)
        try:
            async with session.get(self.IMG_URL.format(id=ref)) as r:
                if r.status != 200:
                    return None
                data = await r.read()
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("pokeapi image fetch failed: %s", err)
            return None
        self._img[ref] = data
        return data, "image/gif"


class CatalogImageView(HomeAssistantView):
    """Serves catalog images same-origin (no auth — public art) so the frontend
    grid can use them directly as <img src>."""

    url = "/api/idotmatrix/catalog/img/{source}/{ref}"
    name = "api:idotmatrix:catalog:img"
    requires_auth = False

    def __init__(self, sources: dict[str, CatalogSource]) -> None:
        self._sources = sources

    async def get(
        self, request: web.Request, source: str, ref: str
    ) -> web.Response:
        src = self._sources.get(source)
        if src is None:
            return web.Response(status=404)
        if not ref or any(c not in "0123456789ABCDEFabcdef._-" for c in ref):
            return web.Response(status=400)
        result = await src.image(ref)
        if result is None:
            return web.Response(status=404)
        data, ctype = result
        return web.Response(
            body=data,
            content_type=ctype,
            headers={"Cache-Control": "public, max-age=86400"},
        )


@callback
def async_register(hass: HomeAssistant) -> None:
    sources: dict[str, CatalogSource] = {}
    for cls in (OpenMojiSource, PokeSource):
        src = cls(hass)
        sources[src.id] = src
    hass.data[f"{DOMAIN}_catalog"] = sources
    hass.http.register_view(CatalogImageView(sources))

    @websocket_api.websocket_command(
        {vol.Required("type"): f"{DOMAIN}/catalog/sources"}
    )
    @websocket_api.async_response
    async def ws_sources(hass, connection, msg):
        connection.send_result(
            msg["id"],
            {"sources": [{"id": s.id, "name": s.name} for s in sources.values()]},
        )

    @websocket_api.websocket_command(
        {
            vol.Required("type"): f"{DOMAIN}/catalog/groups",
            vol.Optional("source", default="openmoji"): str,
        }
    )
    @websocket_api.async_response
    async def ws_groups(hass, connection, msg):
        src = sources.get(msg["source"])
        if src is None:
            connection.send_error(msg["id"], "unknown_source", msg["source"])
            return
        try:
            groups = await src.groups()
        except Exception as err:  # noqa: BLE001
            connection.send_error(msg["id"], "catalog_error", str(err))
            return
        connection.send_result(msg["id"], {"groups": groups})

    @websocket_api.websocket_command(
        {
            vol.Required("type"): f"{DOMAIN}/catalog/list",
            vol.Optional("source", default="openmoji"): str,
            vol.Required("group"): str,
            vol.Optional("limit", default=60): int,
            vol.Optional("offset", default=0): int,
        }
    )
    @websocket_api.async_response
    async def ws_list(hass, connection, msg):
        src = sources.get(msg["source"])
        if src is None:
            connection.send_error(msg["id"], "unknown_source", msg["source"])
            return
        try:
            result = await src.list_group(msg["group"], msg["limit"], msg["offset"])
        except Exception as err:  # noqa: BLE001
            connection.send_error(msg["id"], "catalog_error", str(err))
            return
        connection.send_result(msg["id"], result)

    for cmd in (ws_sources, ws_groups, ws_list):
        websocket_api.async_register_command(hass, cmd)
