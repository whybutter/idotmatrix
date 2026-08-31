# CLAUDE.md

Guidance for Claude/Cortex working in this repo. Read this first.

## What this is

A Home Assistant **custom integration** that controls an iDotMatrix RGB LED panel
over BLE — no bridge hardware, no custom firmware. It connects through HA's
`bluetooth` component (`async_ble_device_from_address`), so the GATT connection
routes transparently through any local adapter or **active** ESPHome-style BLE
proxy (the same mechanism `ha-tuya-ble` uses). On top of device control it ships a
Lovelace card, a scoreboard card, and a React sidebar **panel**.

Everything the panel/app can do was reverse-engineered from the official app's
APK and community projects, then verified against real hardware and the live
cloud API. The protocol is documented in **[`docs/`](./docs/)** — read those
before touching the BLE transport or the cloud catalog.

## Repo layout

- `custom_components/idotmatrix/` — the integration (the shippable artifact).
  - `client.py` — BLE connection + the paced/ack-gated upload transport.
  - `protocol/` — pure byte-builders (`commands.py`, `image.py`, `gif.py`, `text.py`). No I/O.
  - `light.py` — main light entity, device services, image/GIF preprocessing.
  - `{button,number,select,sensor,switch,text}.py` — entity platforms.
  - `availability.py`, `gallery.py`, `albums.py`, `catalog.py`, `config_flow.py`.
  - `frontend/` — **built** JS: `idotmatrix-card.js`, `idotmatrix-scoreboard-card.js`, `idotmatrix-panel.js`.
- `panel/` — React/Vite source for `idotmatrix-panel.js` (build output copied into `frontend/`).
- `docs/` — reverse-engineering reference (BLE protocol, cloud catalog, architecture).
- Companion repo **whybutter/idotmatrix-catalog** — preserved snapshot of the app's cloud art + the scraper.

## Non-obvious things that WILL bite you

These cost real debugging time. Don't "simplify" them away.

1. **BLE uploads: write-WITHOUT-response, paced, sub-chunked.** Over an ESPHome
   proxy a large `write-with-response` throws GATT error 133, and an un-paced
   burst of `write-without-response` is silently dropped — the panel just stays
   black. Uploads write ~180-byte sub-chunks ~20 ms apart, ack-gated on the `fa03`
   notify characteristic between 4 KB blocks. Write char = `fa02`, notify = `fa03`.
2. **The panel stops advertising while connected.** So `available = connected OR
   advertising` (see `availability.py`) — naive advertising-only availability
   flips entities to unavailable mid-use.
3. **Device-side albums:** the persistent-asset header's last byte is the **0-based
   album index** (NOT `0xFF`); assets are sent one at a time, each gated on the
   previous asset's finish-ack; there is **no "play album" command** — storing the
   assets *is* the trigger, and the panel auto-carousels. GIFs are multi-block and
   need a size-scaled finish-ack timeout. Three things cost real hardware time to
   find (all verified on the panel, see `docs/bluetooth-protocol.md` §21f):
   - **The finish/ready ack echoes the payload type**: `05 00 <type> 00 <01|03>`,
     where `<type>` is header byte 2 of the block sent (`01` GIF, `02` raw still).
     Derive the marker from the block; a hardcoded `05 00 01 00 03` silently
     times out on every still.
   - **Stills and GIFs live in separate banks and don't mix** — with both
     populated the carousel plays ONLY the GIF bank, and the stills are stored
     but never shown. So albums send *everything* through `build_gif_upload`,
     stills included (`light._prepare_still_as_gif`).
   - **Slide dwell = the GIF's total frame duration**, not the header interval.
     A still must therefore be encoded with `duration = interval`; left at PIL's
     default ~100ms the carousel skips it entirely. The GIF loop count is ignored,
     so making an animation fill an interval means physically repeating frames.
4. **Cloud catalog** (`catalog.py`, source `heaton`): requests need an md5 `sign` +
   AES-256-CBC body (keys hard-coded, no login); categorised content needs
   **`label="ALL"`** (not `Product_`); and downloaded assets are an **obfuscated
   text envelope**, not image bytes — decode = strip 32-char nonce each end,
   `+`→space, URL-decode, **reverse the string**, Base64-decode. Full spec in
   [`docs/cloud-catalog.md`](./docs/cloud-catalog.md).
5. **`freeze` does not exist** in the real app (a community myth); don't re-add it.

## Build & release

The integration is installed via HACS, which reads `custom_components/` from a
release **tag**. So every change ships as: bump `manifest.json` `version` → commit
→ push → create a GitHub release/pre-release on that tag.

- **Frontend panel:** edit `panel/src/`, then `cd panel && pnpm build`; copy
  `panel/dist/idotmatrix-panel.js` → `custom_components/idotmatrix/frontend/`. The
  Lovelace cards are hand-written vanilla JS directly in `frontend/` (no build).
  The panel is data-driven (sources/groups come over WebSocket), so adding a
  catalog source/category is a backend-only change.
- **No hardware or HA in this environment.** You cannot run the integration here.
  Verify protocol changes by byte-checking against `docs/` and, where possible,
  against the live cloud API (the catalog crypto is reproducible). BLE/device
  behavior must be confirmed by the user on real hardware — say so when you can't
  verify.
- **git push gotcha:** pushes go through the OneCLI proxy and need the CA + a
  connection header. `http.sslCAInfo` global config does not persist, so pass it
  inline:
  ```
  git -c http.sslCAInfo=/tmp/onecli-combined-ca.pem \
      -c http.extraHeader="x-onecli-connection-id: <whybutter-conn-id>" push
  ```
- **Never** `rm -rf custom_components` from inside a command that `cd`s into a
  working copy — it has clobbered the canonical source before. Sync explicitly.

## Deeper context

Full decision trail and byte-level detail live in the agent memory
`idotmatrix-ha-integration` and the project note
`second-brain/1 - Projects/iDotMatrix ESP32 Bridge.md`. The `docs/` folder is the
public, self-contained version of the protocol knowledge.
