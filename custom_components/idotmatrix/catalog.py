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
        "smileys-emotion": "Smileys & emotion",
        "people-body": "People",
        "animals-nature": "Animals & nature",
        "food-drink": "Food & drink",
        "travel-places": "Travel & places",
        "activities": "Activities",
        "objects": "Objects",
        "symbols": "Symbols",
        "flags": "Flags",
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
        ("gen5", "Gen 5 · Unova", 494, 649),
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


# --------------------------------------------------------------------------- #
# Heaton — the official iDotMatrix app's own cloud catalog                     #
#                                                                              #
# Reverse-engineered from the APK and validated live. One signed+encrypted     #
# endpoint lists assets; file_path is a direct CDN URL we proxy. Images live   #
# under category_name="iPixels" (tab-agnostic); animations under "<tab>_IDM".  #
# All secrets are baked into the app (no login/token). Personal-use interop     #
# with a device the user owns.                                                 #
# --------------------------------------------------------------------------- #
class HeatonSource(CatalogSource):
    id = "heaton"
    name = "App catalog"

    API_URL = "https://manage.heaton.com.cn/api/rm/getMaterialUnderCategory"
    APP_KEY = "Jy47rzJAgKMfrcc92PamyyukQqB7wmFu"
    IV = b"0000000000000000"
    # (group id, label, category_name, type, is_gif). Both images and animations
    # are categorised by tab as "<tab>_IDM"; the key is label="ALL" (label
    # "Product_" only returns the flat generic bucket). 5 tabs × {image, gif}.
    GROUPS = [
        ("img_daily", "Images · Daily", "日常_IDM", "图片", False),
        ("img_holiday", "Images · Holidays", "节日_IDM", "图片", False),
        ("img_emoji", "Images · Emoji", "表情_IDM", "图片", False),
        ("img_creative", "Images · Creative", "创意_IDM", "图片", False),
        ("img_business", "Images · Business", "商业_IDM", "图片", False),
        ("ani_daily", "Animated · Daily", "日常_IDM", "动画", True),
        ("ani_holiday", "Animated · Holidays", "节日_IDM", "动画", True),
        ("ani_emoji", "Animated · Emoji", "表情_IDM", "动画", True),
        ("ani_creative", "Animated · Creative", "创意_IDM", "动画", True),
        ("ani_business", "Animated · Business", "商业_IDM", "动画", True),
    ]
    # The catalog is authored per asset-size; 32×32 has the richest set. We list
    # at 32 and resize on send to whatever size the user picks.
    LIST_SIZE = 32

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(hass)
        self._img: dict[str, tuple[bytes, str]] = {}

    # --- app crypto (md5 sign + AES-256-CBC body/response) ---
    @staticmethod
    def _java_url_encode(s: str) -> str:
        out = []
        for b in s.encode("utf-8"):
            c = chr(b)
            if c.isascii() and (c.isalnum() or c in ".*-_"):
                out.append(c)
            elif c == " ":
                out.append("+")
            else:
                out.append("%%%02X" % b)
        enc = "".join(out)
        return enc.replace("%26", "&").replace("%3D", "=").replace("%3F", "?")

    @classmethod
    def _sorted_query(cls, params: dict) -> str:
        return "&".join(f"{k}={params[k]}" for k in sorted(params))

    def _sign(self, params: dict, random: str, timestamp: str) -> str:
        import hashlib

        signed = {**params, "random": random, "timestamp": timestamp,
                  "app_key": self.APP_KEY}
        return hashlib.md5(
            self._java_url_encode(self._sorted_query(signed)).encode("utf-8")
        ).hexdigest().lower()

    def _aes(self):
        from cryptography.hazmat.primitives.ciphers import (
            Cipher,
            algorithms,
            modes,
        )

        return Cipher(algorithms.AES(self.APP_KEY.encode("ascii")), modes.CBC(self.IV))

    def _encrypt(self, plain: str) -> str:
        import base64

        from cryptography.hazmat.primitives import padding

        padder = padding.PKCS7(128).padder()
        data = padder.update(plain.encode("utf-8")) + padder.finalize()
        enc = self._aes().encryptor()
        return base64.b64encode(enc.update(data) + enc.finalize()).decode("ascii")

    def _decrypt(self, b64: str) -> str:
        import base64

        from cryptography.hazmat.primitives import padding

        dec = self._aes().decryptor()
        raw = dec.update(base64.b64decode(b64)) + dec.finalize()
        unpadder = padding.PKCS7(128).unpadder()
        return (unpadder.update(raw) + unpadder.finalize()).decode("utf-8")

    async def _query(self, category_name: str, mtype: str, page: int, count: int) -> dict:
        import random as _random
        import string
        import time

        params = {
            "appid": "140",
            "sort": "1",
            "page": str(page),
            "count": str(count),
            "category_name": category_name,
            "type": mtype,
            "width": str(self.LIST_SIZE),
            "height": str(self.LIST_SIZE),
            "label": "ALL",
            "filter_tags": "ALL",
            "file_lang": "none,cn",
        }
        rnd = "".join(_random.choices(string.ascii_letters + string.digits, k=8))
        ts = str(int(time.time() * 1000))
        sign = self._sign(params, rnd, ts)
        body = self._encrypt(self._java_url_encode(self._sorted_query(params)))
        url = f"{self.API_URL}?sign={sign}&timestamp={ts}&random={rnd}"
        session = async_get_clientsession(self._hass)
        async with session.post(
            url,
            data=body,
            headers={"Content-Type": "text/plain; charset=utf-8"},
        ) as r:
            r.raise_for_status()
            text = await r.text()
        import json

        payload = json.loads(self._decrypt(text.strip()))
        return payload.get("data") or {}

    async def groups(self) -> list[dict]:
        return [{"id": g[0], "name": g[1]} for g in self.GROUPS]

    async def list_group(self, group: str, limit: int, offset: int) -> dict:
        import base64

        g = next((x for x in self.GROUPS if x[0] == group), None)
        if g is None:
            return {"items": [], "total": 0}
        _, _, category_name, mtype, is_gif = g
        page = offset // limit + 1
        data = await self._query(category_name, mtype, page, limit)
        items = []
        for rec in data.get("records", []):
            path = rec.get("file_path") or ""
            if not path:
                continue
            ref = base64.urlsafe_b64encode(path.encode("utf-8")).decode("ascii").rstrip("=")
            items.append(
                {
                    "ref": ref,
                    "name": rec.get("label") or "",
                    "is_gif": is_gif or rec.get("format") == "gif",
                }
            )
        return {"items": items, "total": int(data.get("totalCount", 0))}

    async def image(self, ref: str) -> tuple[bytes, str] | None:
        import base64

        if ref in self._img:
            return self._img[ref]
        try:
            pad = "=" * (-len(ref) % 4)
            url = base64.urlsafe_b64decode(ref + pad).decode("utf-8")
        except Exception:  # noqa: BLE001
            return None
        if not url.startswith("http"):
            return None
        session = async_get_clientsession(self._hass)
        try:
            async with session.get(
                url, headers={"User-Agent": "okhttp/5.1.0", "Connection": "close"}
            ) as r:
                if r.status != 200:
                    return None
                text = await r.text()
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("heaton image fetch failed: %s", err)
            return None
        data = self._decode_asset(text)
        if data is None:
            return None
        # Sniff the real type (the CDN doesn't set a useful extension).
        if data[:4] == b"GIF8":
            ctype = "image/gif"
        elif data[:8] == b"\x89PNG\r\n\x1a\n":
            ctype = "image/png"
        elif data[:2] == b"\xff\xd8":
            ctype = "image/jpeg"
        else:
            ctype = "image/png"
        result = (data, ctype)
        self._img[ref] = result
        return result

    @staticmethod
    def _decode_asset(text: str) -> bytes | None:
        """The CDN's /download/<id> returns an obfuscated TEXT envelope, not raw
        image bytes (the app's DecryptHelper.getDecryptedFile). Decode: strip a
        32-char nonce off each end, '+'→space, URL-decode (UTF-8), reverse the
        whole string, trim CR/LF, then standard Base64-decode → the real PNG/GIF.
        No auth is involved; this is pure client-side obfuscation."""
        import base64
        import urllib.parse

        if len(text) <= 64:
            return None
        s = text[32 : len(text) - 32].replace("+", " ")
        s = urllib.parse.unquote(s, encoding="utf-8", errors="replace")
        s = s[::-1].strip().replace("\r", "").replace("\n", "")
        try:
            return base64.b64decode(s)
        except Exception:  # noqa: BLE001
            return None


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
        # Allow hex (openmoji), digits (poke) and base64url refs (heaton file_path).
        if not ref or any(
            not (c.isalnum() or c in "._-~") for c in ref
        ):
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
    for cls in (HeatonSource, OpenMojiSource, PokeSource):
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
