// All panel CSS as a string, injected into the shadow root at mount time.
// Dark purple / pixel-art LED aesthetic, layered on top of HA theme vars.

export const CSS = `
:host {
  --idot-bg: #0e0b1e;
  --idot-bg-2: #16112e;
  --idot-surface: #1c1640;
  --idot-surface-2: #241a52;
  --idot-tile: #201743;
  --idot-tile-hover: #2c2060;
  --idot-accent: #7c4dff;
  --idot-accent-2: #b388ff;
  --idot-accent-glow: rgba(124, 77, 255, 0.45);
  --idot-text: #f2eefe;
  --idot-text-dim: #a99fce;
  --idot-border: rgba(179, 136, 255, 0.16);
  --idot-good: #38d39f;
  --idot-radius: 20px;
  --idot-radius-sm: 14px;
}

* { box-sizing: border-box; }

.idot-root {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  color: var(--idot-text);
  background:
    radial-gradient(1200px 600px at 20% -5%, rgba(124,77,255,0.22), transparent 60%),
    radial-gradient(900px 500px at 100% 0%, rgba(179,136,255,0.14), transparent 55%),
    linear-gradient(180deg, var(--idot-bg-2), var(--idot-bg));
  min-height: 100%;
  width: 100%;
  padding: 20px;
  overflow-y: auto;
}

.idot-shell {
  max-width: 1080px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

/* ---------- Header ---------- */
.idot-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  background: linear-gradient(135deg, var(--idot-surface), var(--idot-bg-2));
  border: 1px solid var(--idot-border);
  border-radius: var(--idot-radius);
  padding: 16px 20px;
  box-shadow: 0 8px 30px rgba(0,0,0,0.35);
}
.idot-title-block { display: flex; align-items: center; gap: 14px; min-width: 0; }
.idot-logo {
  width: 44px; height: 44px; border-radius: 12px; flex: none;
  background: linear-gradient(135deg, #7c4dff, #b388ff);
  display: grid; grid-template-columns: repeat(4,1fr); grid-template-rows: repeat(4,1fr);
  gap: 2px; padding: 6px; box-shadow: 0 0 18px var(--idot-accent-glow);
}
.idot-logo span { border-radius: 2px; background: rgba(255,255,255,0.85); }
.idot-logo span:nth-child(2n) { background: rgba(255,255,255,0.35); }
.idot-title { font-size: 1.35rem; font-weight: 700; letter-spacing: 0.3px; line-height: 1.1; }
.idot-subtitle { font-size: 0.82rem; color: var(--idot-text-dim); margin-top: 2px; }

.idot-header-controls { display: flex; align-items: center; gap: 18px; flex-wrap: wrap; }

/* Power toggle */
.idot-power {
  display: inline-flex; align-items: center; gap: 10px;
  background: var(--idot-tile); border: 1px solid var(--idot-border);
  border-radius: 999px; padding: 6px 8px 6px 16px; cursor: pointer;
  transition: background .15s ease;
}
.idot-power:hover { background: var(--idot-tile-hover); }
.idot-power-label { font-size: .8rem; color: var(--idot-text-dim); font-weight: 600; letter-spacing: .5px; }
.idot-switch {
  width: 46px; height: 26px; border-radius: 999px; position: relative;
  background: #3a2f63; transition: background .2s ease; flex: none;
}
.idot-switch.on { background: linear-gradient(135deg, #7c4dff, #b388ff); box-shadow: 0 0 12px var(--idot-accent-glow); }
.idot-switch .knob {
  position: absolute; top: 3px; left: 3px; width: 20px; height: 20px; border-radius: 50%;
  background: #fff; transition: transform .2s ease;
}
.idot-switch.on .knob { transform: translateX(20px); }

/* Brightness */
.idot-bright { display: flex; align-items: center; gap: 10px; min-width: 210px; }
.idot-bright svg { flex: none; opacity: .8; }
.idot-slider {
  -webkit-appearance: none; appearance: none; height: 8px; border-radius: 999px;
  background: linear-gradient(90deg, var(--idot-accent), var(--idot-accent-2));
  outline: none; flex: 1; cursor: pointer;
}
.idot-slider::-webkit-slider-thumb {
  -webkit-appearance: none; appearance: none; width: 20px; height: 20px; border-radius: 50%;
  background: #fff; box-shadow: 0 0 0 4px rgba(124,77,255,.35); cursor: pointer;
}
.idot-slider::-moz-range-thumb {
  width: 20px; height: 20px; border: none; border-radius: 50%; background: #fff;
  box-shadow: 0 0 0 4px rgba(124,77,255,.35); cursor: pointer;
}
.idot-bright-val { font-size: .8rem; color: var(--idot-text-dim); width: 38px; text-align: right; font-variant-numeric: tabular-nums; }

/* ---------- Hero ---------- */
.idot-hero {
  position: relative; border-radius: var(--idot-radius); overflow: hidden;
  border: 1px solid var(--idot-border);
  background: linear-gradient(160deg, #2a1f57, #140f2c);
  min-height: 190px; display: flex; align-items: center; justify-content: center;
  box-shadow: inset 0 0 60px rgba(124,77,255,.15), 0 10px 30px rgba(0,0,0,.4);
}
.idot-hero-panel {
  --cell: 12px;
  display: grid; gap: 2px; padding: 14px;
  border-radius: 12px; background: #050308;
  box-shadow: 0 0 40px var(--idot-accent-glow), inset 0 0 0 3px #241a52;
}
.idot-hero-panel .px { width: var(--cell); height: var(--cell); border-radius: 2px; }
.idot-hero-caption {
  position: absolute; bottom: 12px; left: 0; right: 0; text-align: center;
  font-family: Georgia, "Times New Roman", serif; font-style: italic;
  font-size: 1.2rem; letter-spacing: 1px; text-shadow: 0 2px 12px rgba(0,0,0,.6);
  color: #efe9ff;
}

/* ---------- Status row ---------- */
.idot-status-row { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.idot-status-card {
  background: linear-gradient(135deg, var(--idot-surface), var(--idot-bg-2));
  border: 1px solid var(--idot-border); border-radius: var(--idot-radius);
  padding: 18px 20px; display: flex; align-items: center; gap: 14px;
}
.idot-status-icon {
  width: 46px; height: 46px; border-radius: 12px; flex: none;
  display: grid; place-items: center; background: var(--idot-tile);
  border: 1px solid var(--idot-border);
}
.idot-status-title { font-weight: 700; font-size: .98rem; }
.idot-status-sub { font-size: .78rem; color: var(--idot-text-dim); margin-top: 2px; }
.idot-dot { width: 10px; height: 10px; border-radius: 50%; background: var(--idot-good); box-shadow: 0 0 8px var(--idot-good); }
.idot-dot.off { background: #6b6389; box-shadow: none; }
.idot-status-card.power-card { cursor: pointer; justify-content: space-between; }
.idot-status-card.power-card:hover { background: linear-gradient(135deg, var(--idot-surface-2), var(--idot-surface)); }

/* device switcher select */
.idot-device-select {
  margin-left: auto; background: var(--idot-tile); color: var(--idot-text);
  border: 1px solid var(--idot-border); border-radius: 10px; padding: 6px 10px; font-size: .82rem;
}

/* ---------- Grid ---------- */
.idot-grid {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px;
}
.idot-tile {
  position: relative; aspect-ratio: 1 / 1;
  background:
    linear-gradient(160deg, var(--idot-tile), var(--idot-bg-2));
  border: 1px solid var(--idot-border); border-radius: var(--idot-radius);
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 12px; cursor: pointer; overflow: hidden; padding: 12px;
  transition: transform .12s ease, box-shadow .15s ease, border-color .15s ease;
}
.idot-tile::before {
  content: ""; position: absolute; inset: 0; opacity: .5;
  background-image:
    linear-gradient(rgba(179,136,255,.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(179,136,255,.06) 1px, transparent 1px);
  background-size: 14px 14px; pointer-events: none;
}
.idot-tile:hover {
  transform: translateY(-3px);
  border-color: var(--idot-accent);
  box-shadow: 0 12px 26px rgba(0,0,0,.4), 0 0 0 1px var(--idot-accent-glow);
}
.idot-tile:hover .idot-tile-icon { box-shadow: 0 0 22px var(--idot-accent-glow); }
.idot-tile.soon { cursor: default; opacity: .62; }
.idot-tile.soon:hover { transform: none; border-color: var(--idot-border); box-shadow: none; }
.idot-tile-icon {
  width: 58px; height: 58px; border-radius: 16px; display: grid; place-items: center;
  background: linear-gradient(140deg, rgba(124,77,255,.28), rgba(179,136,255,.1));
  border: 1px solid var(--idot-border); color: var(--idot-accent-2);
  transition: box-shadow .15s ease; z-index: 1;
}
.idot-tile-label { font-size: .92rem; font-weight: 600; text-align: center; z-index: 1; }
.idot-soon-badge {
  position: absolute; top: 8px; right: 8px; font-size: .62rem; font-weight: 700;
  text-transform: uppercase; letter-spacing: .5px; color: var(--idot-accent-2);
  background: rgba(124,77,255,.16); border: 1px solid var(--idot-border);
  padding: 3px 7px; border-radius: 999px; z-index: 2;
}

/* ---------- Modal ---------- */
.idot-modal-backdrop {
  position: fixed; inset: 0; background: rgba(6,4,16,.66); backdrop-filter: blur(4px);
  display: grid; place-items: center; z-index: 1000; padding: 20px;
  animation: idot-fade .15s ease;
}
@keyframes idot-fade { from { opacity: 0; } to { opacity: 1; } }
.idot-modal {
  width: min(480px, 100%); max-height: 90vh; overflow-y: auto;
  background: linear-gradient(180deg, var(--idot-surface), var(--idot-bg-2));
  border: 1px solid var(--idot-border); border-radius: var(--idot-radius);
  box-shadow: 0 24px 60px rgba(0,0,0,.55); padding: 22px;
  animation: idot-pop .16s cubic-bezier(.2,.9,.3,1.2);
}
@keyframes idot-pop { from { transform: translateY(10px) scale(.98); opacity: 0; } to { transform: none; opacity: 1; } }
.idot-modal-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.idot-modal-title { font-size: 1.15rem; font-weight: 700; }
.idot-modal-close {
  width: 34px; height: 34px; border-radius: 10px; border: 1px solid var(--idot-border);
  background: var(--idot-tile); color: var(--idot-text); cursor: pointer; font-size: 1.1rem;
  display: grid; place-items: center;
}
.idot-modal-close:hover { background: var(--idot-tile-hover); }

.idot-field { margin-bottom: 16px; }
.idot-field label { display: block; font-size: .8rem; color: var(--idot-text-dim); margin-bottom: 7px; font-weight: 600; }
.idot-input, .idot-select, .idot-textarea {
  width: 100%; background: var(--idot-bg); color: var(--idot-text);
  border: 1px solid var(--idot-border); border-radius: 12px; padding: 12px 14px;
  font-size: .95rem; font-family: inherit;
}
.idot-input:focus, .idot-select:focus, .idot-textarea:focus { outline: none; border-color: var(--idot-accent); }
.idot-textarea { resize: vertical; min-height: 90px; }

.idot-color-row { display: flex; align-items: center; gap: 14px; }
.idot-color-input {
  width: 64px; height: 64px; border: 1px solid var(--idot-border); border-radius: 14px;
  background: none; cursor: pointer; padding: 4px;
}
.idot-swatches { display: flex; gap: 8px; flex-wrap: wrap; }
.idot-swatch { width: 30px; height: 30px; border-radius: 8px; cursor: pointer; border: 2px solid transparent; }
.idot-swatch:hover { border-color: #fff; }

.idot-size-toggle { display: flex; gap: 8px; }
.idot-size-btn {
  flex: 1; padding: 10px; border-radius: 12px; border: 1px solid var(--idot-border);
  background: var(--idot-tile); color: var(--idot-text); cursor: pointer; font-weight: 600; font-size: .9rem;
}
.idot-size-btn.active { background: linear-gradient(135deg, var(--idot-accent), var(--idot-accent-2)); border-color: transparent; }

.idot-checkbox-row { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.idot-checkbox-row input { width: 18px; height: 18px; accent-color: var(--idot-accent); }
.idot-checkbox-row label { margin: 0; color: var(--idot-text); }

.idot-btn {
  width: 100%; border: none; border-radius: 14px; padding: 14px; cursor: pointer;
  font-size: 1rem; font-weight: 700; color: #fff;
  background: linear-gradient(120deg, #7c4dff, #b388ff, #7c4dff);
  background-size: 200% 100%; box-shadow: 0 8px 22px var(--idot-accent-glow);
  transition: background-position .3s ease, transform .1s ease;
}
.idot-btn:hover { background-position: 100% 0; }
.idot-btn:active { transform: scale(.985); }
.idot-btn:disabled { opacity: .5; cursor: not-allowed; box-shadow: none; }

.idot-file-drop {
  border: 2px dashed var(--idot-border); border-radius: 14px; padding: 22px;
  text-align: center; color: var(--idot-text-dim); cursor: pointer; transition: border-color .15s;
}
.idot-file-drop:hover { border-color: var(--idot-accent); }
.idot-preview-img {
  max-width: 100%; max-height: 180px; border-radius: 10px; margin-top: 12px;
  image-rendering: pixelated; border: 1px solid var(--idot-border);
}

.idot-toast {
  position: fixed; bottom: 22px; left: 50%; transform: translateX(-50%);
  background: var(--idot-surface-2); color: var(--idot-text);
  border: 1px solid var(--idot-border); border-radius: 12px; padding: 12px 20px;
  box-shadow: 0 10px 30px rgba(0,0,0,.5); z-index: 1100; font-size: .9rem;
  animation: idot-pop .18s ease;
}
.idot-toast.err { border-color: #ff5c7c; }

.idot-empty {
  text-align: center; padding: 60px 20px; color: var(--idot-text-dim);
}
.idot-empty h2 { color: var(--idot-text); margin-bottom: 8px; }

.idot-hint { font-size: .78rem; color: var(--idot-text-dim); margin-top: -6px; margin-bottom: 14px; }

/* Responsive */
@media (max-width: 640px) {
  .idot-root { padding: 14px; }
  .idot-grid { grid-template-columns: repeat(2, 1fr); gap: 12px; }
  .idot-status-row { grid-template-columns: 1fr; }
  .idot-header-controls { width: 100%; justify-content: space-between; }
  .idot-bright { min-width: 0; flex: 1; }
}
@media (max-width: 380px) {
  .idot-grid { grid-template-columns: repeat(2, 1fr); }
}
`;
