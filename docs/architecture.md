# Integration Architecture

How the pieces of this integration fit together. If you're extending it or
debugging, start here.

## Overview

A standard Home Assistant custom integration (config-entry only) that talks to an
iDotMatrix panel over BLE through HA's `bluetooth` component — so it works through
any local adapter or **active** ESPHome-style BLE proxy, with no firmware changes
on the panel or the proxy. On top of the device control it ships a custom Lovelace
card, a dedicated scoreboard card, and a full React sidebar **panel** (Explorar /
Galería / Álbumes / Marcador / Temporizadores).

## Python modules (`custom_components/idotmatrix/`)

| File | Responsibility |
|------|----------------|
| `__init__.py` | Entry setup/teardown; shared `IdotMatrixState`; registers the frontend (static JS paths, `add_extra_js_url`, `panel_custom`) and the gallery/albums/catalog WebSocket commands. |
| `client.py` | BLE connection manager. Selects the BLE device (optionally a preferred proxy), connects via `bleak_retry_connector`, subscribes to the `fa03` notify characteristic, and implements the paced write / per-block ack transport for image/GIF/album uploads. |
| `availability.py` | Availability tracking. Key subtlety: the panel **stops advertising while connected**, so `available = connected OR advertising` (otherwise entities flip to unavailable mid-use). |
| `protocol/` | Pure byte-builders (no I/O): `commands.py` (power, brightness, clock, effects, etc.), `image.py` (DIY + persistent-asset uploads), `gif.py`, `text.py`. |
| `light.py` | The main light entity + all the device services; image/GIF preprocessing (`_fit_rgb`, `_prepare_pixels`, `_prepare_gif`). |
| `button/number/select/sensor/switch/text.py` | Entity platforms exposing each feature on the device page. |
| `gallery.py` | User's saved-image gallery (HA `Store`), with `gallery/*` WebSocket commands. |
| `albums.py` | Device-side albums: builds asset blocks and flashes them into panel memory (`SlideshowManager`), plus `albums/*` WebSocket commands. |
| `catalog.py` | Online art sources (OpenMoji, PokéAPI, and the app's own **Heaton** cloud catalog). Source registry + image proxy + `catalog/*` WebSocket commands. See [cloud-catalog.md](./cloud-catalog.md). |

## Frontend (`custom_components/idotmatrix/frontend/`, built from `panel/`)

- `idotmatrix-card.js` — the main Lovelace card (vanilla JS web component).
- `idotmatrix-scoreboard-card.js` — a dedicated live scoreboard card.
- `idotmatrix-panel.js` — the React sidebar panel, built from `panel/src/` (Vite →
  single IIFE web-component bundle registered as `<idotmatrix-panel>`).

The panel is **data-driven**: it fetches the source/group lists over WebSocket, so
adding a catalog source or category is a backend-only change.

## Two things that are easy to get wrong

These cost real debugging time; they're documented in full in
[bluetooth-protocol.md](./bluetooth-protocol.md) §22 and inline in `client.py`.

1. **BLE writes must be write-*without*-response, paced, and sub-chunked.** Over an
   ESPHome proxy, a large `write-with-response` returns GATT error 133, and an
   un-paced burst of `write-without-response` is silently dropped — the panel just
   stays black. The image/GIF/album transport writes ~180-byte sub-chunks ~20 ms
   apart and waits for an ack on `fa03` between 4 KB blocks. The panel does not
   advertise while connected, which also breaks naive availability logic.

2. **Device-side albums need per-asset indexing and ack-gating.** The persistent
   asset header's last byte is the **0-based album index** (not `0xFF`); assets
   must be sent strictly one at a time, each gated on the previous asset's finish
   ack (`05 00 01 00 03`). There is no separate "play album" command — storing the
   assets *is* the display trigger, and the panel auto-carousels them.

## Image / GIF preprocessing

Small panels punish wasted margin, and many art sources embed the artwork inside a
large transparent canvas. `_fit_rgb` trims the transparent margin to the artwork's
bounding box, pads to a centered square (preserving aspect), composites onto an
opaque background, then scales to the panel size. For GIFs a **single** bounding
box is shared across all frames so motion is preserved (per-frame trimming would
re-center each frame and destroy the animation).

### Display gamma

The panel's PWM is roughly **linear** in the byte value, but source images are
sRGB-encoded. Sent through untouched, midtones land far too bright and everything
looks washed out and desaturated. Fully saturated primaries (0/255) are unaffected,
which is why a pure red heart looks right while a photo or a shaded sprite does not.

`_apply_gamma` applies `out = 255 * (in/255) ** gamma` to every still and GIF frame.
Measured on hardware with one source image (webcam, mean per-pixel max−min as
"saturation"):

| gamma | saturation | brightness |
|---|---|---|
| 1.0 (uncorrected) | 44 | 166 |
| 1.6 | 47 | 155 |
| **2.2 (default)** | **59** | **140** |
| 2.8 | 70 | 130 |

The source image measures 137 brightness, so 2.2 — the theoretically correct sRGB
value — is also the best empirical match. It is exposed as the `gamma` integration
option (1.0–3.0) for per-panel tuning.

Note this corrects the *transfer curve* only. The panel's white point is separately
blue-heavy (whites render slightly cyan); a per-channel white-balance gain would be
the next refinement.

### Album asset preparation

Album slides take a different path from one-off uploads (`albums.SlideshowManager.play`):
every asset is encoded as a **GIF** (stills as single-frame GIFs) because the panel
will not carousel stills and animations together, and each is encoded to last the
album's interval — a still gets `duration = interval`, an animation has its frame
sequence repeated to the nearest whole loop — because the carousel advances after one
pass through the frames. See `docs/bluetooth-protocol.md` §21f.
