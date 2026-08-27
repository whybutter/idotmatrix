/**
 * iDotMatrix control card — self-contained custom Lovelace card (no build step).
 *
 * Config:
 *   type: custom:idotmatrix-card
 *   entity: light.<your idotmatrix light>
 */
const CLOCK_STYLES = [
  "RGB swipe outline", "Christmas tree", "Checkers", "Color",
  "Hourglass", "Alarm clock", "Outlines", "RGB corners",
];
const EFFECT_STYLES = [
  "Horizontal rainbow", "Random colored pixels", "Random white pixels",
  "Vertical rainbow", "Diagonal-right rainbow", "Diagonal-left rainbow",
  "Random colored pixels (alt)",
];
const MIC_STYLES = { "Dancing guy": 1, "Heart": 2, "Gummy bear": 3, "Eyes and mouth": 4 };

const STYLES = `
  .wrap { padding: 4px 16px 18px; }
  .sec { font-size: .72rem; font-weight: 700; letter-spacing: .06em;
         text-transform: uppercase; color: var(--secondary-text-color);
         margin: 18px 0 8px; }
  .sec:first-child { margin-top: 6px; }
  .row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
  .grid3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
  button.idm {
    appearance: none; border: none; cursor: pointer; font: inherit;
    font-weight: 600; padding: 9px 14px; border-radius: 12px;
    background: var(--primary-color); color: var(--text-primary-color, #fff);
    transition: filter .15s, transform .05s; white-space: nowrap;
  }
  button.idm:hover { filter: brightness(1.1); }
  button.idm:active { transform: scale(.97); }
  button.idm.ghost {
    background: var(--secondary-background-color);
    color: var(--primary-text-color);
    border: 1px solid var(--divider-color);
  }
  button.idm.icon { padding: 9px 12px; min-width: 44px; }
  select.idm, input.idm {
    font: inherit; padding: 9px 10px; border-radius: 12px;
    border: 1px solid var(--divider-color);
    background: var(--card-background-color); color: var(--primary-text-color);
  }
  select.idm { width: 100%; }
  input.text { flex: 1; min-width: 140px; }
  input.num { width: 64px; }
  .color-wrap { position: relative; width: 44px; height: 44px; border-radius: 12px;
    overflow: hidden; border: 1px solid var(--divider-color); flex: 0 0 auto; }
  .color-wrap input { position: absolute; inset: -6px; width: 200%; height: 200%;
    border: none; padding: 0; cursor: pointer; }
  input[type=range].bright { flex: 1; min-width: 120px; accent-color: var(--primary-color); }
  .status { margin-top: 14px; font-size: .82rem; min-height: 1.2em;
    color: var(--secondary-text-color); }
  .grow { flex: 1; }
`;

class IdotMatrixCard extends HTMLElement {
  setConfig(config) {
    if (!config.entity) throw new Error("Set 'entity' to your iDotMatrix light");
    this._config = config;
    this._built = false;
  }
  set hass(hass) {
    this._hass = hass;
    if (!this._built) this._build();
    this._refresh();
  }
  getCardSize() { return 9; }

  _call(domain, service, data = {}) {
    return this._hass.callService(domain, service, { entity_id: this._config.entity, ...data });
  }
  _hexToRgb(hex) {
    const n = parseInt(hex.slice(1), 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }
  _status(m) { if (this._statusEl) this._statusEl.textContent = m; }

  async _upload(service, file) {
    const size = Number(this._sizeSel.value) || 32;
    const bytes = new Uint8Array(await file.arrayBuffer());
    let bin = "";
    for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
    this._status(`Enviando ${file.name}…`);
    try {
      await this._call("idotmatrix", service, { image_data: btoa(bin), size });
      this._status(`✓ ${file.name} enviado`);
    } catch (e) { this._status(`✗ ${e.message || e}`); }
  }

  _btn(label, onClick, cls = "") {
    const b = document.createElement("button");
    b.className = "idm " + cls;
    b.textContent = label;
    b.addEventListener("click", onClick);
    return b;
  }
  _dropdown(label, entries, onChange) {
    const s = document.createElement("select");
    s.className = "idm";
    const ph = document.createElement("option");
    ph.textContent = label; ph.disabled = true; ph.selected = true;
    s.appendChild(ph);
    for (const [name, val] of entries) {
      const o = document.createElement("option");
      o.value = val; o.textContent = name; s.appendChild(o);
    }
    s.addEventListener("change", () => onChange(s.value));
    return s;
  }
  _num(def, min, max) {
    const i = document.createElement("input");
    i.className = "idm num"; i.type = "number"; i.min = min; i.max = max; i.value = def;
    return i;
  }

  _build() {
    this._built = true;
    const card = document.createElement("ha-card");
    card.header = this._config.title || "iDotMatrix";
    const style = document.createElement("style");
    style.textContent = STYLES;
    card.appendChild(style);
    const c = document.createElement("div");
    c.className = "wrap";
    card.appendChild(c);

    const sec = (t) => { const d = document.createElement("div"); d.className = "sec"; d.textContent = t; c.appendChild(d); };
    const row = (cls = "row") => { const r = document.createElement("div"); r.className = cls; c.appendChild(r); return r; };

    // Pantalla
    sec("Pantalla");
    const r1 = row();
    this._powerBtn = this._btn("On/Off", () => {
      const on = this._hass.states[this._config.entity]?.state === "on";
      this._call("light", on ? "turn_off" : "turn_on");
    });
    r1.appendChild(this._powerBtn);
    const cw = document.createElement("div");
    cw.className = "color-wrap";
    const color = document.createElement("input");
    color.type = "color"; color.value = "#ff0000"; color.title = "Color";
    color.addEventListener("change", () =>
      this._call("light", "turn_on", { rgb_color: this._hexToRgb(color.value) }));
    cw.appendChild(color); r1.appendChild(cw);
    const bright = document.createElement("input");
    bright.type = "range"; bright.className = "bright"; bright.min = 5; bright.max = 100; bright.value = 80;
    bright.title = "Brillo";
    bright.addEventListener("change", () =>
      this._call("light", "turn_on", { brightness_pct: Number(bright.value) }));
    r1.appendChild(bright);

    // Modos
    sec("Modos");
    const modes = row("grid3");
    modes.appendChild(this._dropdown("Reloj", CLOCK_STYLES.map((n, i) => [n, i]),
      (v) => this._call("idotmatrix", "show_clock", { style: Number(v) })));
    modes.appendChild(this._dropdown("Efecto", EFFECT_STYLES.map((n, i) => [n, i]),
      (v) => this._call("idotmatrix", "show_effect", { style: Number(v) })));
    modes.appendChild(this._dropdown("Mic", Object.entries(MIC_STYLES),
      (v) => this._call("idotmatrix", "mic_rhythm", { style: Number(v), sensitivity: 50 })));

    // Texto
    sec("Texto");
    const tr = row();
    const text = document.createElement("input");
    text.className = "idm text"; text.type = "text"; text.placeholder = "Mensaje…";
    tr.appendChild(text);
    tr.appendChild(this._btn("Enviar", () => {
      if (text.value) this._call("idotmatrix", "send_text", { text: text.value });
    }));

    // Imagen / GIF
    sec("Imagen / GIF (desde tu PC)");
    const ur = row();
    this._sizeSel = this._dropdown("Tamaño", [["16×16", 16], ["32×32", 32], ["64×64", 64]], () => {});
    this._sizeSel.style.width = "auto";
    this._sizeSel.value = 32;
    ur.appendChild(this._sizeSel);
    const imgInput = document.createElement("input");
    imgInput.type = "file"; imgInput.accept = "image/*"; imgInput.style.display = "none";
    imgInput.addEventListener("change", (e) => { if (e.target.files[0]) this._upload("upload_image", e.target.files[0]); e.target.value = ""; });
    const gifInput = document.createElement("input");
    gifInput.type = "file"; gifInput.accept = "image/gif"; gifInput.style.display = "none";
    gifInput.addEventListener("change", (e) => { if (e.target.files[0]) this._upload("upload_gif", e.target.files[0]); e.target.value = ""; });
    c.appendChild(imgInput); c.appendChild(gifInput);
    ur.appendChild(this._btn("📷 Subir imagen", () => imgInput.click()));
    ur.appendChild(this._btn("🎞 Subir GIF", () => gifInput.click(), "ghost"));

    // Timers
    sec("Cronómetro");
    const cr = row();
    cr.appendChild(this._btn("▶", () => this._call("idotmatrix", "chronograph", { action: "start" }), "icon"));
    cr.appendChild(this._btn("⏸", () => this._call("idotmatrix", "chronograph", { action: "pause" }), "icon ghost"));
    cr.appendChild(this._btn("⟲", () => this._call("idotmatrix", "chronograph", { action: "reset" }), "icon ghost"));

    sec("Cuenta regresiva");
    const cdr = row();
    const min = this._num(5, 0, 59), sec2 = this._num(0, 0, 59);
    cdr.appendChild(min); const colon = document.createElement("span"); colon.textContent = ":"; cdr.appendChild(colon); cdr.appendChild(sec2);
    cdr.appendChild(this._btn("Iniciar", () => this._call("idotmatrix", "countdown",
      { action: "start", minutes: Number(min.value), seconds: Number(sec2.value) })));
    cdr.appendChild(this._btn("Detener", () => this._call("idotmatrix", "countdown", { action: "stop" }), "ghost"));

    this._statusEl = document.createElement("div");
    this._statusEl.className = "status";
    c.appendChild(this._statusEl);

    this.innerHTML = "";
    this.appendChild(card);
  }

  _refresh() {
    const st = this._hass?.states[this._config.entity];
    if (st && this._powerBtn) this._powerBtn.textContent = st.state === "on" ? "Apagar" : "Encender";
  }
}

customElements.define("idotmatrix-card", IdotMatrixCard);
window.customCards = window.customCards || [];
window.customCards.push({ type: "idotmatrix-card", name: "iDotMatrix Card",
  description: "Control panel for an iDotMatrix LED display" });
console.info("%c iDotMatrix-Card ", "background:#6d28d9;color:#fff");
