/**
 * iDotMatrix control card — a self-contained custom Lovelace card (no build step).
 *
 * Config:
 *   type: custom:idotmatrix-card
 *   entity: light.<your idotmatrix light>   # the panel's light entity
 *
 * Everything is driven through the integration's services targeting that light
 * entity, so the card only needs the one entity. Image/GIF are read from the
 * user's PC in the browser and sent as base64 (no /config/www).
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

  getCardSize() { return 8; }

  _call(domain, service, data = {}) {
    return this._hass.callService(domain, service, {
      entity_id: this._config.entity, ...data,
    });
  }

  _hexToRgb(hex) {
    const n = parseInt(hex.slice(1), 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }

  async _upload(service, file) {
    const size = Number(this._sizeSel.value) || 32;
    const buf = await file.arrayBuffer();
    let bin = "";
    const bytes = new Uint8Array(buf);
    for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
    const b64 = btoa(bin);
    this._status(`Enviando ${file.name}…`);
    try {
      await this._call("idotmatrix", service, { image_data: b64, size });
      this._status(`✓ ${file.name} enviado`);
    } catch (e) {
      this._status(`✗ ${e.message || e}`);
    }
  }

  _status(msg) { if (this._statusEl) this._statusEl.textContent = msg; }

  _build() {
    this._built = true;
    const card = document.createElement("ha-card");
    card.header = this._config.title || "iDotMatrix";
    const c = document.createElement("div");
    c.style.padding = "8px 16px 16px";
    card.appendChild(c);

    const section = (title) => {
      const h = document.createElement("div");
      h.textContent = title;
      h.style.cssText = "font-weight:600;margin:14px 0 6px;opacity:.7;font-size:.9em";
      c.appendChild(h);
    };
    const row = () => {
      const r = document.createElement("div");
      r.style.cssText = "display:flex;gap:8px;flex-wrap:wrap;align-items:center";
      c.appendChild(r);
      return r;
    };
    const btn = (label, onClick) => {
      const b = document.createElement("mwc-button");
      b.outlined = true;
      b.label = label;
      b.addEventListener("click", onClick);
      return b;
    };

    // --- Power + brightness + color ---
    section("Pantalla");
    const r1 = row();
    this._powerBtn = btn("On/Off", () => {
      const on = this._hass.states[this._config.entity]?.state === "on";
      this._call("light", on ? "turn_off" : "turn_on");
    });
    r1.appendChild(this._powerBtn);

    const color = document.createElement("input");
    color.type = "color";
    color.value = "#ff0000";
    color.title = "Color de pantalla completa";
    color.style.cssText = "width:48px;height:36px;border:none;background:none;cursor:pointer";
    color.addEventListener("change", () =>
      this._call("light", "turn_on", { rgb_color: this._hexToRgb(color.value) }));
    r1.appendChild(color);

    const bright = document.createElement("input");
    bright.type = "range"; bright.min = 5; bright.max = 100; bright.value = 80;
    bright.title = "Brillo";
    bright.style.flex = "1";
    bright.addEventListener("change", () =>
      this._call("light", "turn_on", { brightness_pct: Number(bright.value) }));
    r1.appendChild(bright);

    // --- Modes ---
    section("Modos");
    const modeRow = row();
    this._clockSel = this._dropdown("Reloj", CLOCK_STYLES.map((n, i) => [n, i]), (v) =>
      this._call("idotmatrix", "show_clock", { style: Number(v) }));
    this._effectSel = this._dropdown("Efecto", EFFECT_STYLES.map((n, i) => [n, i]), (v) =>
      this._call("idotmatrix", "show_effect", { style: Number(v) }));
    this._micSel = this._dropdown("Mic", Object.entries(MIC_STYLES), (v) =>
      this._call("idotmatrix", "mic_rhythm", { style: Number(v), sensitivity: 50 }));
    modeRow.appendChild(this._clockSel);
    modeRow.appendChild(this._effectSel);
    modeRow.appendChild(this._micSel);

    // --- Text ---
    section("Texto");
    const textRow = row();
    const text = document.createElement("input");
    text.type = "text";
    text.placeholder = "Mensaje…";
    text.style.cssText = "flex:1;padding:8px;border-radius:8px;border:1px solid var(--divider-color)";
    textRow.appendChild(text);
    textRow.appendChild(btn("Enviar", () => {
      if (text.value) this._call("idotmatrix", "send_text", { text: text.value });
    }));

    // --- Image / GIF from PC ---
    section("Imagen / GIF (desde tu PC)");
    const upRow = row();
    this._sizeSel = document.createElement("select");
    for (const s of [16, 32, 64]) {
      const o = document.createElement("option");
      o.value = s; o.textContent = `${s}×${s}`;
      if (s === 32) o.selected = true;
      this._sizeSel.appendChild(o);
    }
    this._sizeSel.style.cssText = "padding:6px;border-radius:8px";
    upRow.appendChild(this._sizeSel);

    const imgInput = document.createElement("input");
    imgInput.type = "file"; imgInput.accept = "image/*"; imgInput.style.display = "none";
    imgInput.addEventListener("change", (e) => {
      if (e.target.files[0]) this._upload("upload_image", e.target.files[0]);
      imgInput.value = "";
    });
    const gifInput = document.createElement("input");
    gifInput.type = "file"; gifInput.accept = "image/gif"; gifInput.style.display = "none";
    gifInput.addEventListener("change", (e) => {
      if (e.target.files[0]) this._upload("upload_gif", e.target.files[0]);
      gifInput.value = "";
    });
    c.appendChild(imgInput);
    c.appendChild(gifInput);
    upRow.appendChild(btn("Subir imagen", () => imgInput.click()));
    upRow.appendChild(btn("Subir GIF", () => gifInput.click()));

    // --- Timers ---
    section("Cronómetro / Cuenta regresiva");
    const chronoRow = row();
    chronoRow.appendChild(btn("▶ Crono", () =>
      this._call("idotmatrix", "chronograph", { action: "start" })));
    chronoRow.appendChild(btn("⏸", () =>
      this._call("idotmatrix", "chronograph", { action: "pause" })));
    chronoRow.appendChild(btn("⟲", () =>
      this._call("idotmatrix", "chronograph", { action: "reset" })));
    const cdRow = row();
    const min = this._num("min", 0, 59, 5);
    const sec = this._num("seg", 0, 59, 0);
    cdRow.appendChild(min); cdRow.appendChild(sec);
    cdRow.appendChild(btn("Iniciar", () =>
      this._call("idotmatrix", "countdown", {
        action: "start", minutes: Number(min.value), seconds: Number(sec.value),
      })));
    cdRow.appendChild(btn("Detener", () =>
      this._call("idotmatrix", "countdown", { action: "stop" })));

    // --- status line ---
    this._statusEl = document.createElement("div");
    this._statusEl.style.cssText = "margin-top:12px;font-size:.85em;opacity:.7;min-height:1.2em";
    c.appendChild(this._statusEl);

    this.innerHTML = "";
    this.appendChild(card);
  }

  _dropdown(label, entries, onChange) {
    const wrap = document.createElement("select");
    wrap.style.cssText = "padding:8px;border-radius:8px";
    const ph = document.createElement("option");
    ph.textContent = label; ph.disabled = true; ph.selected = true;
    wrap.appendChild(ph);
    for (const [name, val] of entries) {
      const o = document.createElement("option");
      o.value = val; o.textContent = name;
      wrap.appendChild(o);
    }
    wrap.addEventListener("change", () => onChange(wrap.value));
    return wrap;
  }

  _num(label, min, max, def) {
    const i = document.createElement("input");
    i.type = "number"; i.min = min; i.max = max; i.value = def;
    i.title = label;
    i.style.cssText = "width:60px;padding:8px;border-radius:8px;border:1px solid var(--divider-color)";
    return i;
  }

  _refresh() {
    const st = this._hass?.states[this._config.entity];
    if (st && this._powerBtn) {
      this._powerBtn.label = st.state === "on" ? "Apagar" : "Encender";
    }
  }
}

customElements.define("idotmatrix-card", IdotMatrixCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "idotmatrix-card",
  name: "iDotMatrix Card",
  description: "Control panel for an iDotMatrix LED display",
});
console.info("%c iDotMatrix-Card ", "background:#6d28d9;color:#fff");
