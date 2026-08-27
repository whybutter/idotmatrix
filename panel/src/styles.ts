// All panel CSS as a string, injected into the shadow root at mount time.
// HA-native styling: leans on Home Assistant theme variables so it blends into
// both dark and light themes. The only bespoke touch is the small pixel-LED hero.

export const CSS = `
:host {
  /* Fallbacks map to sensible defaults when HA vars are absent (e.g. standalone). */
  --idot-card-bg: var(--card-background-color, #1c1c1c);
  --idot-bg: var(--primary-background-color, var(--lovelace-background, #111111));
  --idot-radius: var(--ha-card-border-radius, 12px);
  --idot-border: var(--divider-color, rgba(127,127,127,0.2));
  --idot-text: var(--primary-text-color, #e1e1e1);
  --idot-text-dim: var(--secondary-text-color, #9b9b9b);
  --idot-accent: var(--primary-color, #03a9f4);
  --idot-shadow: var(--ha-card-box-shadow, 0 2px 6px rgba(0,0,0,0.15));
  --idot-hover: color-mix(in srgb, var(--idot-text) 6%, transparent);
}

* { box-sizing: border-box; }

.idot-root {
  font-family: var(--paper-font-body1_-_font-family, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif);
  color: var(--idot-text);
  background: var(--idot-bg);
  min-height: 100%;
  width: 100%;
  padding: 16px;
  overflow-y: auto;
}

.idot-shell {
  max-width: 900px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* Shared card surface */
.idot-card {
  background: var(--idot-card-bg);
  border: 1px solid var(--idot-border);
  border-radius: var(--idot-radius);
  box-shadow: var(--idot-shadow);
}

/* ---------- Header ---------- */
.idot-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  padding: 14px 18px;
}
.idot-title-block { display: flex; align-items: center; gap: 12px; min-width: 0; }
.idot-logo {
  width: 36px; height: 36px; border-radius: 8px; flex: none;
  background: var(--idot-accent);
  display: grid; grid-template-columns: repeat(4,1fr); grid-template-rows: repeat(4,1fr);
  gap: 2px; padding: 5px;
}
.idot-logo span { border-radius: 1px; background: rgba(255,255,255,0.9); }
.idot-logo span:nth-child(2n) { background: rgba(255,255,255,0.4); }
.idot-title { font-size: 1.2rem; font-weight: 600; line-height: 1.1; }
.idot-subtitle { font-size: 0.8rem; color: var(--idot-text-dim); margin-top: 1px; }

.idot-header-controls { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }

/* Power toggle */
.idot-power {
  display: inline-flex; align-items: center; gap: 10px;
  cursor: pointer; user-select: none;
}
.idot-power-label { font-size: .78rem; color: var(--idot-text-dim); font-weight: 600; letter-spacing: .4px; }
.idot-switch {
  width: 42px; height: 24px; border-radius: 999px; position: relative;
  background: var(--idot-border); transition: background .2s ease; flex: none;
}
.idot-switch.on { background: var(--idot-accent); }
.idot-switch .knob {
  position: absolute; top: 3px; left: 3px; width: 18px; height: 18px; border-radius: 50%;
  background: #fff; transition: transform .2s ease; box-shadow: 0 1px 2px rgba(0,0,0,.3);
}
.idot-switch.on .knob { transform: translateX(18px); }

/* Brightness */
.idot-bright { display: flex; align-items: center; gap: 8px; min-width: 190px; }
.idot-bright svg { flex: none; opacity: .7; }
.idot-slider {
  -webkit-appearance: none; appearance: none; height: 4px; border-radius: 999px;
  background: var(--idot-border); outline: none; flex: 1; cursor: pointer;
}
.idot-slider::-webkit-slider-thumb {
  -webkit-appearance: none; appearance: none; width: 16px; height: 16px; border-radius: 50%;
  background: var(--idot-accent); cursor: pointer;
}
.idot-slider::-moz-range-thumb {
  width: 16px; height: 16px; border: none; border-radius: 50%; background: var(--idot-accent); cursor: pointer;
}
.idot-slider:disabled { opacity: .5; }
.idot-bright-val { font-size: .78rem; color: var(--idot-text-dim); width: 34px; text-align: right; font-variant-numeric: tabular-nums; }

/* ---------- Hero (kept: small pixel-LED preview) ---------- */
.idot-hero {
  display: flex; flex-direction: column; align-items: center; gap: 8px;
  padding: 16px;
}
.idot-hero-panel {
  --cell: 9px;
  display: grid; gap: 1px; padding: 10px;
  border-radius: 8px; background: #050308;
  box-shadow: inset 0 0 0 2px rgba(255,255,255,.05);
}
.idot-hero-panel .px { width: var(--cell); height: var(--cell); border-radius: 1px; }
.idot-hero-caption {
  font-size: .8rem; color: var(--idot-text-dim); letter-spacing: .5px;
}

/* ---------- Status row ---------- */
.idot-status-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.idot-status-card {
  padding: 14px 16px; display: flex; align-items: center; gap: 12px;
}
.idot-status-icon {
  width: 38px; height: 38px; border-radius: 10px; flex: none;
  display: grid; place-items: center;
  background: var(--idot-hover); color: var(--idot-text-dim);
}
.idot-status-title { font-weight: 600; font-size: .92rem; }
.idot-status-sub { font-size: .76rem; color: var(--idot-text-dim); margin-top: 1px; }
.idot-dot { width: 9px; height: 9px; border-radius: 50%; background: #4caf50; }
.idot-dot.off { background: var(--idot-text-dim); opacity: .5; }
.idot-status-card.power-card { cursor: pointer; }
.idot-status-card.power-card:hover { background: var(--idot-hover); }
.idot-status-card.power-card .idot-status-icon.on { color: var(--idot-accent); }

.idot-device-select {
  margin-left: auto; background: var(--idot-bg); color: var(--idot-text);
  border: 1px solid var(--idot-border); border-radius: 8px; padding: 6px 8px; font-size: .8rem;
}

/* ---------- Inline control sections ---------- */
.idot-section { padding: 16px 18px; }
.idot-section-head {
  display: flex; align-items: center; gap: 10px; margin-bottom: 14px;
}
.idot-section-icon {
  width: 30px; height: 30px; border-radius: 8px; flex: none; display: grid; place-items: center;
  background: color-mix(in srgb, var(--idot-accent) 14%, transparent); color: var(--idot-accent);
}
.idot-section-title { font-size: .98rem; font-weight: 600; }

/* Inline color: swatch row + picker + apply-on-tap */
.idot-inline-color { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.idot-inline-color .idot-swatch { width: 34px; height: 34px; border-radius: 9px; }
.idot-inline-color .idot-swatch.active { border-color: var(--idot-text); }
.idot-inline-color .idot-color-input { width: 44px; height: 44px; border-radius: 10px; padding: 3px; }

/* Inline text: input + send button on one row */
.idot-inline-text { display: flex; gap: 10px; align-items: stretch; }
.idot-inline-text .idot-input { flex: 1; }
.idot-inline-send {
  border: none; border-radius: 8px; padding: 0 18px; cursor: pointer; flex: none;
  font-weight: 600; font-size: .92rem; color: #fff; background: var(--idot-accent);
  display: inline-flex; align-items: center; gap: 7px;
}
.idot-inline-send:hover { filter: brightness(1.08); }
.idot-inline-send:disabled { opacity: .5; cursor: not-allowed; }

/* Inline quick-mode row: label + select + go button, repeated */
.idot-quick-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.idot-quick { display: flex; flex-direction: column; gap: 8px; }
.idot-quick-label { font-size: .8rem; color: var(--idot-text-dim); font-weight: 600; }
.idot-quick-row { display: flex; gap: 8px; }
.idot-quick-row .idot-select { flex: 1; padding: 9px 10px; font-size: .88rem; }
.idot-quick-go {
  border: 1px solid var(--idot-accent); background: transparent; color: var(--idot-accent);
  border-radius: 8px; padding: 0 14px; cursor: pointer; font-weight: 600; font-size: .85rem; flex: none;
}
.idot-quick-go:hover { background: color-mix(in srgb, var(--idot-accent) 14%, transparent); }
.idot-quick-go:disabled { opacity: .5; cursor: not-allowed; }

/* ---------- Compact grid (remaining tiles: upload + stubs) ---------- */
.idot-grid {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px;
}
.idot-tile {
  display: flex; align-items: center; gap: 12px;
  padding: 14px 14px; min-height: 64px;
  background: var(--idot-card-bg);
  border: 1px solid var(--idot-border); border-radius: var(--idot-radius);
  box-shadow: var(--idot-shadow);
  cursor: pointer;
  transition: border-color .12s ease, background .12s ease;
}
.idot-tile:hover { border-color: var(--idot-accent); background: var(--idot-hover); }
.idot-tile.soon { cursor: default; opacity: .55; }
.idot-tile.soon:hover { border-color: var(--idot-border); background: var(--idot-card-bg); }
.idot-tile-icon {
  width: 36px; height: 36px; border-radius: 9px; flex: none; display: grid; place-items: center;
  background: color-mix(in srgb, var(--idot-accent) 14%, transparent);
  color: var(--idot-accent);
}
.idot-tile-body { min-width: 0; display: flex; flex-direction: column; }
.idot-tile-label { font-size: .9rem; font-weight: 600; line-height: 1.15; }
.idot-soon-badge {
  font-size: .64rem; font-weight: 600; color: var(--idot-text-dim); margin-top: 2px;
}

/* ---------- Modal ---------- */
.idot-modal-backdrop {
  position: fixed; inset: 0; background: rgba(0,0,0,.5); backdrop-filter: blur(2px);
  display: grid; place-items: center; z-index: 1000; padding: 20px;
  animation: idot-fade .12s ease;
}
@keyframes idot-fade { from { opacity: 0; } to { opacity: 1; } }
.idot-modal {
  width: min(460px, 100%); max-height: 90vh; overflow-y: auto;
  background: var(--idot-card-bg);
  border: 1px solid var(--idot-border); border-radius: var(--idot-radius);
  box-shadow: 0 8px 30px rgba(0,0,0,.4); padding: 20px;
  animation: idot-pop .14s ease;
}
@keyframes idot-pop { from { transform: translateY(8px); opacity: 0; } to { transform: none; opacity: 1; } }
.idot-modal-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.idot-modal-title { font-size: 1.1rem; font-weight: 600; }
.idot-modal-close {
  width: 32px; height: 32px; border-radius: 8px; border: 1px solid var(--idot-border);
  background: transparent; color: var(--idot-text); cursor: pointer; font-size: 1.1rem;
  display: grid; place-items: center;
}
.idot-modal-close:hover { background: var(--idot-hover); }

.idot-field { margin-bottom: 16px; }
.idot-field label { display: block; font-size: .8rem; color: var(--idot-text-dim); margin-bottom: 6px; font-weight: 600; }
.idot-input, .idot-select, .idot-textarea {
  width: 100%; background: var(--idot-bg); color: var(--idot-text);
  border: 1px solid var(--idot-border); border-radius: 8px; padding: 10px 12px;
  font-size: .95rem; font-family: inherit;
}
.idot-input:focus, .idot-select:focus, .idot-textarea:focus { outline: none; border-color: var(--idot-accent); }
.idot-textarea { resize: vertical; min-height: 84px; }

.idot-color-row { display: flex; align-items: center; gap: 12px; }
.idot-color-input {
  width: 56px; height: 56px; border: 1px solid var(--idot-border); border-radius: 10px;
  background: none; cursor: pointer; padding: 4px;
}
.idot-swatches { display: flex; gap: 7px; flex-wrap: wrap; }
.idot-swatch { width: 28px; height: 28px; border-radius: 7px; cursor: pointer; border: 2px solid transparent; }
.idot-swatch:hover { border-color: var(--idot-text); }

.idot-size-toggle { display: flex; gap: 8px; }
.idot-size-btn {
  flex: 1; padding: 10px; border-radius: 8px; border: 1px solid var(--idot-border);
  background: var(--idot-bg); color: var(--idot-text); cursor: pointer; font-weight: 600; font-size: .9rem;
}
.idot-size-btn.active { background: var(--idot-accent); border-color: transparent; color: #fff; }

.idot-checkbox-row { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.idot-checkbox-row input { width: 18px; height: 18px; accent-color: var(--idot-accent); }
.idot-checkbox-row label { margin: 0; color: var(--idot-text); }

.idot-btn {
  width: 100%; border: none; border-radius: 8px; padding: 12px; cursor: pointer;
  font-size: .98rem; font-weight: 600; color: #fff; background: var(--idot-accent);
  transition: filter .1s ease, transform .1s ease;
}
.idot-btn:hover { filter: brightness(1.08); }
.idot-btn:active { transform: scale(.99); }
.idot-btn:disabled { opacity: .5; cursor: not-allowed; }

.idot-file-drop {
  border: 2px dashed var(--idot-border); border-radius: 8px; padding: 20px;
  text-align: center; color: var(--idot-text-dim); cursor: pointer; transition: border-color .12s;
}
.idot-file-drop:hover { border-color: var(--idot-accent); }
.idot-preview-img {
  max-width: 100%; max-height: 170px; border-radius: 8px; margin-top: 12px;
  image-rendering: pixelated; border: 1px solid var(--idot-border);
}

.idot-toast {
  position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
  background: var(--idot-card-bg); color: var(--idot-text);
  border: 1px solid var(--idot-border); border-radius: 8px; padding: 11px 18px;
  box-shadow: 0 6px 24px rgba(0,0,0,.35); z-index: 1100; font-size: .9rem;
  animation: idot-pop .16s ease;
}
.idot-toast.err { border-color: var(--error-color, #db4437); }

.idot-empty {
  text-align: center; padding: 60px 20px; color: var(--idot-text-dim);
}
.idot-empty h2 { color: var(--idot-text); margin-bottom: 8px; }

.idot-hint { font-size: .78rem; color: var(--idot-text-dim); margin-top: -6px; margin-bottom: 14px; }

/* Responsive: 4 cols wide -> 3 -> 2 narrow */
@media (max-width: 720px) {
  .idot-grid { grid-template-columns: repeat(3, 1fr); }
}
@media (max-width: 560px) {
  .idot-root { padding: 12px; }
  .idot-grid { grid-template-columns: repeat(2, 1fr); }
  .idot-status-row { grid-template-columns: 1fr; }
  .idot-header-controls { width: 100%; justify-content: space-between; }
  .idot-bright { min-width: 0; flex: 1; }
  .idot-quick-grid { grid-template-columns: 1fr; }
}
`;
