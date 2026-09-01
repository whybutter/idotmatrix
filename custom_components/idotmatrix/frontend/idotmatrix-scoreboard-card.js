/**
 * iDotMatrix Scoreboard card — a big, touch-friendly live scoreboard.
 *
 * Config:
 *   type: custom:idotmatrix-scoreboard-card
 *   entity: light.<your idotmatrix light>
 *   home: "Home"        # optional labels
 *   away: "Away"
 *
 * Both counts travel in every frame, so any change sends {count1, count2}
 * (debounced). Values clamp 0-999.
 */
const STYLES = `
  .sb { padding: 4px 12px 16px; }
  .teams { display: grid; grid-template-columns: 1fr auto 1fr; gap: 8px; align-items: center; }
  .team { display: flex; flex-direction: column; align-items: center; gap: 8px; }
  .name { font-weight: 700; text-transform: uppercase; letter-spacing: .05em;
          font-size: .8rem; color: var(--secondary-text-color); }
  .score { font-variant-numeric: tabular-nums; font-weight: 800; line-height: 1;
           font-size: clamp(48px, 16vw, 96px); color: var(--primary-text-color); }
  .home .score { color: var(--info-color, #2196f3); }
  .away .score { color: var(--error-color, #f44336); }
  .colon { font-size: clamp(32px, 8vw, 56px); font-weight: 800;
           color: var(--secondary-text-color); }
  .btns { display: flex; gap: 8px; }
  button.sbb { appearance: none; border: none; cursor: pointer; font: inherit;
    font-weight: 800; font-size: 1.4rem; width: 56px; height: 56px;
    border-radius: 16px; color: var(--text-primary-color, #fff);
    background: var(--primary-color); transition: filter .12s, transform .05s; }
  button.sbb.minus { background: var(--secondary-background-color);
    color: var(--primary-text-color); border: 1px solid var(--divider-color); }
  button.sbb:hover { filter: brightness(1.1); }
  button.sbb:active { transform: scale(.94); }
  .foot { display: flex; justify-content: center; gap: 10px; margin-top: 16px; }
  button.reset { appearance: none; cursor: pointer; font: inherit; font-weight: 600;
    padding: 9px 16px; border-radius: 12px; background: var(--secondary-background-color);
    color: var(--primary-text-color); border: 1px solid var(--divider-color); }
  .status { text-align: center; margin-top: 8px; font-size: .8rem;
    min-height: 1.1em; color: var(--secondary-text-color); }
`;

class IdotMatrixScoreboardCard extends HTMLElement {
  setConfig(config) {
    if (!config.entity) throw new Error("Set 'entity' to your iDotMatrix light");
    this._config = config;
    this._c1 = 0;
    this._c2 = 0;
    this._built = false;
    this._timer = null;
  }
  set hass(hass) { this._hass = hass; if (!this._built) this._build(); this._refresh(); }
  getCardSize() { return 5; }

  _clamp(v) { return Math.max(0, Math.min(999, v)); }

  _send() {
    if (this._timer) clearTimeout(this._timer);
    this._status("Sending…");
    this._timer = setTimeout(async () => {
      try {
        await this._hass.callService("idotmatrix", "scoreboard", {
          entity_id: this._config.entity, count1: this._c1, count2: this._c2,
        });
        this._status("");
      } catch (e) { this._status("✗ " + (e.message || e)); }
    }, 350);
  }
  _status(m) { if (this._statusEl) this._statusEl.textContent = m; }

  _bump(which, delta) {
    if (which === 1) this._c1 = this._clamp(this._c1 + delta);
    else this._c2 = this._clamp(this._c2 + delta);
    this._render();
    this._send();
  }
  _reset() { this._c1 = 0; this._c2 = 0; this._render(); this._send(); }

  _team(cls, name, which) {
    const t = document.createElement("div");
    t.className = "team " + cls;
    const n = document.createElement("div");
    n.className = "name"; n.textContent = name;
    const s = document.createElement("div");
    s.className = "score"; s.textContent = "0";
    const plus = document.createElement("button");
    plus.className = "sbb"; plus.textContent = "+";
    plus.addEventListener("click", () => this._bump(which, 1));
    const minus = document.createElement("button");
    minus.className = "sbb minus"; minus.textContent = "−";
    minus.addEventListener("click", () => this._bump(which, -1));
    const btns = document.createElement("div");
    btns.className = "btns"; btns.appendChild(minus); btns.appendChild(plus);
    t.appendChild(n); t.appendChild(s); t.appendChild(btns);
    if (which === 1) this._score1 = s; else this._score2 = s;
    return t;
  }

  _render() {
    if (this._score1) this._score1.textContent = String(this._c1);
    if (this._score2) this._score2.textContent = String(this._c2);
  }

  _build() {
    this._built = true;
    const card = document.createElement("ha-card");
    card.header = this._config.title || "Scoreboard";
    const style = document.createElement("style");
    style.textContent = STYLES;
    card.appendChild(style);
    const wrap = document.createElement("div");
    wrap.className = "sb";
    const teams = document.createElement("div");
    teams.className = "teams";
    teams.appendChild(this._team("home", this._config.home || "Home", 1));
    const colon = document.createElement("div");
    colon.className = "colon"; colon.textContent = ":";
    teams.appendChild(colon);
    teams.appendChild(this._team("away", this._config.away || "Away", 2));
    wrap.appendChild(teams);

    const foot = document.createElement("div");
    foot.className = "foot";
    const reset = document.createElement("button");
    reset.className = "reset"; reset.textContent = "Reiniciar 0 : 0";
    reset.addEventListener("click", () => this._reset());
    foot.appendChild(reset);
    wrap.appendChild(foot);

    this._statusEl = document.createElement("div");
    this._statusEl.className = "status";
    wrap.appendChild(this._statusEl);

    card.appendChild(wrap);
    this.innerHTML = "";
    this.appendChild(card);
    this._render();
  }

  _refresh() {}
}

customElements.define("idotmatrix-scoreboard-card", IdotMatrixScoreboardCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "idotmatrix-scoreboard-card",
  name: "iDotMatrix Scoreboard",
  description: "A big touch-friendly scoreboard for an iDotMatrix panel",
});
