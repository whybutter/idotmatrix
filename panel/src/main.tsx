import { StrictMode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { App } from "./App";
import { HassContext } from "./hass-context";
import { CSS } from "./styles";
import type { Hass, PanelConfig } from "./types";

/**
 * Home Assistant custom panel custom element.
 *
 * HA sets these PROPERTIES on the instance: `hass`, `narrow`, `panel`, `route`.
 * `hass` changes frequently — each set triggers a React re-render.
 */
class IDotMatrixPanel extends HTMLElement {
  private _hass: Hass | null = null;
  private _narrow = false;
  private _panel: any = null;
  private _route: any = null;
  private _root: Root | null = null;

  connectedCallback() {
    if (this._root) return;

    const shadow = this.attachShadow({ mode: "open" });

    const style = document.createElement("style");
    style.textContent = CSS;
    shadow.appendChild(style);

    const mount = document.createElement("div");
    mount.style.height = "100%";
    shadow.appendChild(mount);

    this._root = createRoot(mount);
    this.render();
  }

  disconnectedCallback() {
    // Defer unmount to avoid React warning if HA re-attaches synchronously.
    const root = this._root;
    this._root = null;
    if (root) {
      Promise.resolve().then(() => root.unmount());
    }
  }

  set hass(value: Hass) {
    this._hass = value;
    this.render();
  }
  get hass(): Hass | null {
    return this._hass;
  }

  set narrow(value: boolean) {
    this._narrow = value;
  }
  get narrow() {
    return this._narrow;
  }

  set panel(value: PanelConfig) {
    this._panel = value;
  }
  get panel() {
    return this._panel;
  }

  set route(value: any) {
    this._route = value;
  }
  get route() {
    return this._route;
  }

  private render() {
    if (!this._root || !this._hass) return;
    this._root.render(
      <StrictMode>
        <HassContext.Provider value={this._hass}>
          <App />
        </HassContext.Provider>
      </StrictMode>
    );
  }
}

if (!customElements.get("idotmatrix-panel")) {
  customElements.define("idotmatrix-panel", IDotMatrixPanel);
}

export {};
