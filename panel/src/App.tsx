import { useEffect, useMemo, useState } from "react";
import { useHass } from "./hass-context";
import { discoverDevices, getBrightnessPct, isLightOn } from "./idot";
import type { IDotDevice } from "./types";
import {
  IconAlbum,
  IconBrightness,
  IconDevice,
  IconGif,
  IconGraffiti,
  IconImage,
  IconPower,
  IconScore,
  IconTimer,
} from "./icons";
import { UploadModal } from "./modals";
import { InlineColor, InlineModes, InlineText } from "./InlineControls";

type ModalKey = "upload" | null;

interface Tile {
  key: string;
  label: string;
  icon: React.ReactNode;
  modal?: ModalKey;
  soon?: boolean;
}

// Grid holds only the actions that genuinely need an expanded view (Upload),
// plus the not-yet-built stubs. Everything common is inline above.
const TILES: Tile[] = [
  { key: "upload", label: "Upload image", icon: <IconImage size={22} />, modal: "upload" },
  { key: "graffiti", label: "Graffiti", icon: <IconGraffiti size={22} />, soon: true },
  { key: "gif", label: "GIF gallery", icon: <IconGif size={22} />, soon: true },
  { key: "score", label: "Scoreboard", icon: <IconScore size={22} />, soon: true },
  { key: "timers", label: "Timers", icon: <IconTimer size={22} />, soon: true },
  { key: "albums", label: "Albums", icon: <IconAlbum size={22} />, soon: true },
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

  const device = devices?.find((d) => d.lightEntityId === selected) ?? null;
  const entityId = device?.lightEntityId ?? "";
  const on = device ? isLightOn(hass, entityId) : false;
  const brightness = device ? getBrightnessPct(hass, entityId) : 0;

  const togglePower = async () => {
    if (!device) return;
    try {
      await hass.callService("light", on ? "turn_off" : "turn_on", {
        entity_id: entityId,
      });
    } catch (e) {
      notify("Power failed: " + (e as Error).message, true);
    }
  };

  const setBrightness = async (pct: number) => {
    if (!device) return;
    try {
      await hass.callService("light", "turn_on", {
        entity_id: entityId,
        brightness_pct: pct,
      });
    } catch (e) {
      notify("Brightness failed: " + (e as Error).message, true);
    }
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
              <span className="idot-bright-val">{on ? brightness + "%" : "—"}</span>
            </div>

            <div className="idot-power" onClick={togglePower} role="button" tabIndex={0}>
              <span className="idot-power-label">{on ? "ON" : "OFF"}</span>
              <span className={"idot-switch" + (on ? " on" : "")}>
                <span className="knob" />
              </span>
            </div>
          </div>
        </header>

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
            {devices.length > 1 ? (
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
            ) : (
              <span className="idot-dot" style={{ marginLeft: "auto" }} />
            )}
          </div>

          <div
            className="idot-card idot-status-card power-card"
            onClick={togglePower}
            role="button"
            tabIndex={0}
          >
            <div className={"idot-status-icon" + (on ? " on" : "")}>
              <IconPower />
            </div>
            <div>
              <div className="idot-status-title">{on ? "ON" : "OFF"}</div>
              <div className="idot-status-sub">Tap to turn {on ? "off" : "on"}</div>
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
              onClick={() => !t.soon && t.modal && setModal(t.modal)}
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
      </div>

      {/* Upload modal (needs file picker + size + preview) */}
      {device && modal === "upload" && (
        <UploadModal device={device} onClose={closeModal} notify={notify} />
      )}

      {toast && <div className={"idot-toast" + (toast.err ? " err" : "")}>{toast.msg}</div>}
    </div>
  );
}
