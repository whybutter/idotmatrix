# iDotMatrix Panel (Home Assistant custom panel)

A polished, app-inspired sidebar **panel** (full page) for the `idotmatrix` LED-panel
integration. React + Vite + TypeScript, built into a single self-contained JS file.

## Build

```bash
pnpm install
pnpm build   # -> dist/idotmatrix-panel.js  (single IIFE bundle, React inlined)
```

## Install in Home Assistant

1. Copy `dist/idotmatrix-panel.js` into `config/www/` (e.g. `config/www/idotmatrix-panel.js`).
2. Register the panel in `configuration.yaml`:

   ```yaml
   panel_custom:
     - name: idotmatrix-panel        # must match the custom element tag
       sidebar_title: iDotMatrix
       sidebar_icon: mdi:grid
       module_url: /local/idotmatrix-panel.js
       embed_iframe: false
   ```

3. Restart HA. The panel mounts `<idotmatrix-panel>` and receives `hass`, `narrow`,
   `panel`, `route` as element properties.

## Iteration 1 — wired vs stubbed

**Wired (functional):** Color, Text, Upload image (16/32/64, base64), Clock, Effect,
On/Off toggle, brightness slider, device discovery + multi-device switcher.

**Stubbed ("Próximamente"):** Graffiti, GIF gallery, Scoreboard, Timers, Albums.
