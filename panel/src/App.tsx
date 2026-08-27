import { useEffect, useMemo, useState } from "react";
import { useHass } from "./hass-context";
import { discoverDevices, getBrightnessPct, isAvailable, isLightOn } from "./idot";
import type { IDotDevice } from "./types";
import {
  IconAlbum,
  IconBrightness,
  IconDevice,
  IconGif,
  IconImage,
  IconPower,
  IconScore,
  IconSpinner,
  IconTimer,
} from "./icons";
import { ScoreboardModal, TimersModal, UploadModal } from "./modals";
import { InlineColor, InlineModes, InlineText } from "./InlineControls";
import { useBusyAction } from "./useBusyAction";
import { Gallery } from "./Gallery";
import { Albums } from "./Albums";

type View = "home" | "gallery" | "albums";

type ModalKey = "upload" | "scoreboard" | "timers" | null;

interface Tile {
  key: string;
  label: string;
  icon: React.ReactNode;
  modal?: ModalKey;
  view?: View;
  soon?: boolean;
}

// Grid holds actions that need an expanded view (Upload), navigation to the
// Gallery, plus the not-yet-built stubs. Everything common is inline above.
const TILES: Tile[] = [
  { key: "upload", label: "Upload image", icon: <IconImage size={22} />, modal: "upload" },
  { key: "gallery", label: "Galería", icon: <IconGif size={22} />, view: "gallery" },
  { key: "albums", label: "Álbumes", icon: <IconAlbum size={22} />, view: "albums" },
  { key: "score", label: "Marcador", icon: <IconScore size={22} />, modal: "scoreboard" },
  { key: "timers", label: "Temporizadores", icon: <IconTimer size={22} />, modal: "timers" },
];

// Deterministic pixel-art "city skyline at sunset" for the hero preview.
const HERO_COLS = 22;
const HERO_ROWS = 11;
function heroPixels(): string[] {
  const grid: string[] = [];
  const heights = [3, 5, 4, 7, 6, 8, 5, 9, 6, 4, 7, 5, 8, 6, 9, 5, 7, 4, 6, 5, 3, 4];
  for (let y = 0; y < HERO_ROWS; y++) {
    for (let x = 0; x < HERO_COLS; x++) {
      const rowFromBottom = HERO_ROWS - 1 - y;
      const h = heights[x % heights.length];
      if (rowFromBottom < h) {
        const lit = (x * 7 + y * 3) % 5 === 0;
        grid.push(lit ? "#ffd166" : "#243044");
      } else {
        const t = y / HERO_ROWS;
        if (t < 0.35) grid.push("#20304f");
        else if (t < 0.55) grid.push("#7a3d8f");
        else grid.push("#e8663d");
      }
    }
  }
  return grid;
}

export function App() {
  const hass = useHass();
  const [devices, setDevices] = useState<IDotDevice[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [view, setView] = useState<View>("home");
  const [modal, setModal] = useState<ModalKey>(null);
  const [toast, setToast] = useState<{ msg: string; err: boolean } | null>(null);
  const hero = useMemo(() => heroPixels(), []);

  useEffect(() => {
    let alive = true;
    discoverDevices(hass).then((d) => {
      if (!alive) return;
      setDevices(d);
      if (d.length && !selected) setSelected(d[0].lightEntityId);
    });
    return () => {
      alive = false;
    };
    // Discovery runs once on mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const notify = (msg: string, err = false) => {
    setToast({ msg, err });
    window.setTimeout(() => setToast(null), 2600);
  };

  const power = useBusyAction((m) => notify("Power failed: " + m, true));
  const bright = useBusyAction((m) => notify("Brightness failed: " + m, true));

  const device = devices?.find((d) => d.lightEntityId === selected) ?? null;
  const entityId = device?.lightEntityId ?? "";
  const available = device ? isAvailable(hass, entityId) : false;
  // "missing" (no state at all) vs "unavailable" — both hide controls, but we
  // word the placeholder slightly differently.
  const entityMissing = device ? !hass.states[entityId] : false;
  const on = device ? isLightOn(hass, entityId) : false;
  const brightness = device ? getBrightnessPct(hass, entityId) : 0;

  const togglePower = () => {
    if (!device || power.busy) return;
    power.run(() =>
      hass.callService("light", on ? "turn_off" : "turn_on", { entity_id: entityId })
    );
  };

  const setBrightness = (pct: number) => {
    if (!device) return;
    bright.run(() =>
      hass.callService("light", "turn_on", { entity_id: entityId, brightness_pct: pct })
    );
  };

  if (devices === null) {
    return (
      <div className="idot-root">
        <div className="idot-empty">
          <h2>Loading…</h2>
          <p>Discovering iDotMatrix devices.</p>
        </div>
      </div>
    );
  }

  if (devices.length === 0) {
    return (
      <div className="idot-root">
        <div className="idot-empty">
          <h2>No iDotMatrix device found</h2>
          <p>
            No entity from the <code>idotmatrix</code> integration was found. Make sure the
            integration is set up and the panel light entity exists.
          </p>
        </div>
      </div>
    );
  }

  const closeModal = () => setModal(null);

  return (
    <div className="idot-root">
      <div className="idot-shell">
        {/* Header */}
        <header className="idot-card idot-header">
          <div className="idot-title-block">
            <div className="idot-logo" aria-hidden>
              {Array.from({ length: 16 }).map((_, i) => (
                <span key={i} />
              ))}
            </div>
            <div>
              <div className="idot-title">iDotMatrix</div>
              <div className="idot-subtitle">{device?.name ?? "LED Panel"}</div>
            </div>
          </div>

          {available && (
            <div className="idot-header-controls">
              <div className="idot-bright" title="Brightness">
                <IconBrightness />
                <input
                  type="range"
                  className="idot-slider"
                  min={1}
                  max={100}
                  value={brightness || 1}
                  disabled={!on}
                  onChange={(e) => setBrightness(+e.target.value)}
                />
                <span className="idot-bright-val">
                  {bright.busy ? (
                    <IconSpinner size={13} />
                  ) : on ? (
                    brightness + "%"
                  ) : (
                    "—"
                  )}
                </span>
              </div>

              <div
                className={"idot-power" + (power.busy ? " busy" : "")}
                onClick={togglePower}
                role="button"
                tabIndex={0}
              >
                <span className="idot-power-label">{on ? "ON" : "OFF"}</span>
                {power.busy ? (
                  <span className="idot-power-spin">
                    <IconSpinner size={22} />
                  </span>
                ) : (
                  <span className={"idot-switch" + (on ? " on" : "")}>
                    <span className="knob" />
                  </span>
                )}
              </div>
            </div>
          )}
        </header>

        {/* Tabs */}
        <div className="idot-tabs" role="tablist">
          <button
            className={"idot-tab" + (view === "home" ? " active" : "")}
            onClick={() => setView("home")}
            role="tab"
            aria-selected={view === "home"}
          >
            Inicio
          </button>
          <button
            className={"idot-tab" + (view === "gallery" ? " active" : "")}
            onClick={() => setView("gallery")}
            role="tab"
            aria-selected={view === "gallery"}
          >
            Galería
          </button>
          <button
            className={"idot-tab" + (view === "albums" ? " active" : "")}
            onClick={() => setView("albums")}
            role="tab"
            aria-selected={view === "albums"}
          >
            Álbumes
          </button>
        </div>

        {/* Device switcher stays visible so the user can pick a device even
            while a panel is connecting. */}
        {devices.length > 1 && (
          <div className="idot-card idot-status-card">
            <div className="idot-status-icon">
              <IconDevice />
            </div>
            <div>
              <div className="idot-status-title">Device</div>
              <div className="idot-status-sub">{device?.name}</div>
            </div>
            <select
              className="idot-device-select"
              value={selected ?? ""}
              onChange={(e) => setSelected(e.target.value)}
            >
              {devices.map((d) => (
                <option key={d.lightEntityId} value={d.lightEntityId}>
                  {d.name}
                </option>
              ))}
            </select>
          </div>
        )}

        {view === "gallery" || view === "albums" ? (
          device ? (
            view === "gallery" ? (
              <Gallery device={device} notify={notify} />
            ) : (
              <Albums device={device} available={available} notify={notify} />
            )
          ) : (
            <div className="idot-card idot-connecting">
              <div className="idot-connecting-title">Sin dispositivo</div>
              <div className="idot-connecting-sub">
                No se encontró ningún panel iDotMatrix.
              </div>
            </div>
          )
        ) : !available ? (
          /* Gate: only show the full control surface once the panel is reachable. */
          <div className="idot-card idot-connecting">
            {entityMissing ? (
              <>
                <div className="idot-connecting-title">Panel no disponible</div>
                <div className="idot-connecting-sub">
                  Esperando a que el panel esté disponible en Home Assistant…
                </div>
              </>
            ) : (
              <>
                <IconSpinner size={34} />
                <div className="idot-connecting-title">Conectando con el panel…</div>
                <div className="idot-connecting-sub">Esto puede tardar unos segundos (BLE).</div>
              </>
            )}
          </div>
        ) : (
          <>
            {/* Hero preview (compact, centered) */}
            <div className="idot-card idot-hero">
              <div
                className="idot-hero-panel"
                style={{ gridTemplateColumns: `repeat(${HERO_COLS}, var(--cell))` }}
              >
                {hero.map((c, i) => (
                  <div key={i} className="px" style={{ background: on ? c : "#12161d" }} />
                ))}
              </div>
              <div className="idot-hero-caption">iDotMatrix</div>
            </div>

            {/* Status row */}
            <div className="idot-status-row">
              <div className="idot-card idot-status-card">
                <div className="idot-status-icon">
                  <IconDevice />
                </div>
                <div>
                  <div className="idot-status-title">Device connection</div>
                  <div className="idot-status-sub">{device?.name}</div>
                </div>
                <span className="idot-dot" style={{ marginLeft: "auto" }} />
              </div>

              <div
                className={"idot-card idot-status-card power-card" + (power.busy ? " busy" : "")}
                onClick={togglePower}
                role="button"
                tabIndex={0}
              >
                <div className={"idot-status-icon" + (power.busy ? " busy" : on ? " on" : "")}>
                  {power.busy ? <IconSpinner size={22} /> : <IconPower />}
                </div>
                <div>
                  <div className="idot-status-title">
                    {power.busy ? "…" : on ? "ON" : "OFF"}
                  </div>
                  <div className="idot-status-sub">
                    {power.busy ? "Working…" : `Tap to turn ${on ? "off" : "on"}`}
                  </div>
                </div>
                <span className={"idot-dot" + (on ? "" : " off")} style={{ marginLeft: "auto" }} />
              </div>
            </div>

            {/* Inline quick controls */}
            {device && <InlineColor device={device} notify={notify} />}
            {device && <InlineText device={device} notify={notify} />}
            {device && <InlineModes device={device} notify={notify} />}

            {/* Remaining tiles: Upload (modal) + coming-soon stubs */}
            <div className="idot-grid">
              {TILES.map((t) => (
                <div
                  key={t.key}
                  className={"idot-tile" + (t.soon ? " soon" : "")}
                  onClick={() => {
                    if (t.soon) return;
                    if (t.view) setView(t.view);
                    else if (t.modal) setModal(t.modal);
                  }}
                  role="button"
                  tabIndex={t.soon ? -1 : 0}
                >
                  <div className="idot-tile-icon">{t.icon}</div>
                  <div className="idot-tile-body">
                    <div className="idot-tile-label">{t.label}</div>
                    {t.soon && <div className="idot-soon-badge">Próximamente</div>}
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      {/* Upload modal (needs file picker + size + preview) */}
      {device && modal === "upload" && (
        <UploadModal device={device} onClose={closeModal} notify={notify} />
      )}
      {device && modal === "scoreboard" && (
        <ScoreboardModal
          device={device}
          available={available}
          onClose={closeModal}
          notify={notify}
        />
      )}
      {device && modal === "timers" && (
        <TimersModal
          device={device}
          available={available}
          onClose={closeModal}
          notify={notify}
        />
      )}

      {toast && <div className={"idot-toast" + (toast.err ? " err" : "")}>{toast.msg}</div>}
    </div>
  );
}
