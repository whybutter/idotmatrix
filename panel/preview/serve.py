#!/usr/bin/env python3
"""Standalone preview server for the iDotMatrix sidebar panel.

Runs the real panel bundle against a mocked `hass` object so the UI can be
developed, reviewed, and screenshotted without a Home Assistant instance or the
physical panel. Serves:

  /                                     preview.html (mock hass + panel mount)
  /idotmatrix-panel.js                  the built bundle (dist/ preferred)
  /mock-data.json                       gallery/albums/catalog mock payloads
  /api/idotmatrix/catalog/img/<s>/<ref> catalog thumbnails from ASSETS_DIR

Usage:
  ASSETS_DIR=/path/to/idotmatrix-catalog/assets python3 serve.py [port]

ASSETS_DIR should point at a snapshot of the app catalog laid out as
`<size>px/<category>/<image|animation>/<id>.<png|gif>` (the layout of the
whybutter/idotmatrix-catalog repo). Without it, the catalog tab shows empty
groups and the gallery falls back to generated placeholder art.
"""
from __future__ import annotations

import base64
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent
ASSETS = Path(os.environ.get("ASSETS_DIR", "")) if os.environ.get("ASSETS_DIR") else None
SIZE = "32px"
CATEGORIES = ["daily", "holiday", "emoji", "creative", "business"]
PER_GROUP = 60


def _bundle_path() -> Path:
    for p in (HERE.parent / "dist" / "idotmatrix-panel.js",
              HERE.parent.parent / "custom_components" / "idotmatrix" / "frontend" / "idotmatrix-panel.js"):
        if p.exists():
            return p
    raise SystemExit("No built bundle found — run `pnpm build` in panel/ first")


def _list_assets(category: str, kind: str) -> list[Path]:
    if not ASSETS:
        return []
    d = ASSETS / SIZE / category / kind
    return sorted(d.glob("*")) if d.is_dir() else []


def _placeholder_png() -> bytes:
    """1x1 grey PNG for when no asset snapshot is available."""
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGBgAAAABQAB"
        "pfZFQAAAAABJRU5ErkJggg=="
    )


def build_mock_data() -> dict:
    # Gallery: a few real stills + one GIF, embedded as base64 (matches the
    # integration's storage format, which keeps the original file bytes).
    gallery = []
    picks: list[tuple[str, Path]] = []
    for cat, kind, n in (("daily", "image", 2), ("emoji", "image", 1), ("daily", "animation", 1)):
        picks += [(kind, p) for p in _list_assets(cat, kind)[3:3 + n]]
    names = ["Cat", "Hamster", "Skull", "Dancer"]
    for i, (kind, path) in enumerate(picks):
        raw = path.read_bytes()
        gallery.append({
            "id": f"g{i}",
            "name": names[i] if i < len(names) else path.stem[:8],
            "image_data": base64.b64encode(raw).decode(),
            "mime": "image/gif" if kind == "animation" else "image/png",
            "size": 32,
            "is_gif": kind == "animation",
            "created": "2026-09-01T12:00:00+00:00",
        })

    groups, items = [], {}
    for cat in CATEGORIES:
        for kind, label in (("image", "Images"), ("animation", "Animated")):
            gid = f"{'img' if kind == 'image' else 'ani'}_{cat}"
            groups.append({"id": gid, "name": f"{label} · {cat.capitalize()}"})
            items[gid] = [
                {"ref": f"{cat}/{kind}/{p.name}", "name": p.stem[:10], "is_gif": kind == "animation"}
                for p in _list_assets(cat, kind)[:PER_GROUP]
            ]

    return {
        "gallery": gallery,
        "albums": [{"id": "a1", "name": "Album 1",
                    "item_ids": [g["id"] for g in gallery], "interval": 10}],
        "catalog": {
            "sources": [{"id": "heaton", "name": "App catalog"},
                        {"id": "openmoji", "name": "OpenMoji"},
                        {"id": "poke", "name": "Pokémon"}],
            "groups": {"heaton": groups, "openmoji": [], "poke": []},
            "items": items,
            "totals": {gid: len(v) for gid, v in items.items()},
        },
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _send(self, body: bytes, ctype: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = unquote(self.path.split("?")[0])
        if path == "/":
            self._send((HERE / "preview.html").read_bytes(), "text/html; charset=utf-8")
        elif path == "/idotmatrix-panel.js":
            self._send(_bundle_path().read_bytes(), "application/javascript")
        elif path == "/mock-data.json":
            self._send(json.dumps(build_mock_data()).encode(), "application/json")
        elif path.startswith("/api/idotmatrix/catalog/img/"):
            ref = path.split("/api/idotmatrix/catalog/img/", 1)[1]
            ref = ref.split("/", 1)[1] if "/" in ref else ref  # drop source id
            f = (ASSETS / SIZE / ref) if ASSETS else None
            if f and f.is_file() and ASSETS in f.resolve().parents:
                ctype = "image/gif" if f.suffix == ".gif" else "image/png"
                self._send(f.read_bytes(), ctype)
            else:
                self._send(_placeholder_png(), "image/png")
        else:
            self._send(b"not found", "text/plain", 404)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8123
    print(f"Preview on http://localhost:{port}  (assets: {ASSETS or 'none — placeholders'})")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
