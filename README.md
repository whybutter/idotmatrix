# iDotMatrix Home Assistant Integration

Control an iDotMatrix RGB LED panel from Home Assistant over BLE, without any
dedicated bridge hardware or custom firmware.

## How it works

This is a standard HA custom integration (`bleak` + HA's `bluetooth`
component). It resolves the panel's `BLEDevice` via
`homeassistant.components.bluetooth.async_ble_device_from_address()`, which
transparently routes the GATT connection through whichever adapter or active
Bluetooth proxy currently sees the panel — a local adapter, or a remote
ESPHome-API-compatible proxy (e.g. an ESPHome `bluetooth_proxy` with
`active: true`, or a WBRG1-style proxy). No firmware changes are needed on
any proxy device; this is the same mechanism `ha-tuya-ble` uses for Tuya BLE
thermometers.

## Requirements

- Home Assistant with at least one Bluetooth adapter or **active** BLE proxy
  in range of the panel (`bluetooth_proxy` + `active: true` in ESPHome, or an
  equivalent GATT-capable proxy).
- The panel must be powered on and advertising (device name prefix `IDM-`).

## Install

Copy `custom_components/idotmatrix/` into your HA `config/custom_components/`
directory (or install via HACS as a custom repository once published), then
restart HA. The panel should be auto-discovered; otherwise add it manually
via Settings → Devices & Services → Add Integration → iDotMatrix.

## What it exposes

- A `light` entity: on/off + brightness (5-100%, mapped to HA's 0-255 range).
- Entity services on that light: `idotmatrix.flip`, `idotmatrix.freeze`,
  `idotmatrix.reset`, `idotmatrix.set_speed`, `idotmatrix.upload_image`.

## Status

**Untested against real hardware** — protocol was reverse-engineered from the
archived `derkalle4/python3-idotmatrix-library` (no maintainer, but code
available) and ported to this integration without a physical panel to
validate against. Before trusting it:

1. Confirm the panel is discovered (`IDM-*`) and the config flow completes.
2. Validate `turn_on` / `turn_off` / brightness first (cheapest commands).
3. Validate `flip`, `set_speed`, `freeze`, `reset`.
4. Validate `upload_image` last (most complex framing, chunked by both the
   4096-byte protocol-level chunking and the BLE-layer MTU).

## Not ported (out of scope for MVP)

- `text.py` equivalent (render text to bitmap + zlib compress before sending).
- `clock.py`, `chronograph.py`, `scoreboard.py`, `graffiti.py`, `musicSync.py`.

## Credits

Protocol reverse-engineered by the `derkalle4/python3-idotmatrix-library`
community (archived 2026-06-05).
