import { useState } from "react";
import { useHass } from "./hass-context";
import {
  CLOCK_STYLES,
  EFFECT_STYLES,
  MIC_STYLES,
  getRgbColor,
  hexToRgb,
  rgbToHex,
} from "./idot";
import type { IDotDevice } from "./types";
import { IconClock, IconColor, IconEffect, IconMic, IconText } from "./icons";

const PRESET_COLORS = [
  "#ff3b30",
  "#ff9500",
  "#ffe000",
  "#34c759",
  "#0a84ff",
  "#bf5af2",
  "#ff2d92",
  "#ffffff",
];

interface Props {
  device: IDotDevice;
  notify: (msg: string, isError?: boolean) => void;
}

function SectionHead({ icon, title }: { icon: React.ReactNode; title: string }) {
  return (
    <div className="idot-section-head">
      <div className="idot-section-icon">{icon}</div>
      <div className="idot-section-title">{title}</div>
    </div>
  );
}

/* ---------- Inline Color: tap swatch or picker to apply immediately ---------- */
export function InlineColor({ device, notify }: Props) {
  const hass = useHass();
  const [hex, setHex] = useState(() => rgbToHex(getRgbColor(hass, device.lightEntityId)));

  const apply = async (h: string) => {
    setHex(h);
    try {
      await hass.callService("light", "turn_on", {
        entity_id: device.lightEntityId,
        rgb_color: hexToRgb(h),
      });
      notify("Color set");
    } catch (e) {
      notify("Failed: " + (e as Error).message, true);
    }
  };

  return (
    <div className="idot-card idot-section">
      <SectionHead icon={<IconColor size={18} />} title="Color" />
      <div className="idot-inline-color">
        <input
          type="color"
          className="idot-color-input"
          value={hex}
          onChange={(e) => apply(e.target.value)}
          title="Custom color"
        />
        {PRESET_COLORS.map((c) => (
          <button
            key={c}
            className={"idot-swatch" + (c.toLowerCase() === hex.toLowerCase() ? " active" : "")}
            style={{ background: c }}
            onClick={() => apply(c)}
            aria-label={c}
          />
        ))}
      </div>
    </div>
  );
}

/* ---------- Inline Text: input + send ---------- */
export function InlineText({ device, notify }: Props) {
  const hass = useHass();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);

  const send = async () => {
    if (!text.trim()) return;
    setBusy(true);
    try {
      await hass.callService("idotmatrix", "send_text", {
        entity_id: device.lightEntityId,
        text,
        mode: 1,
        speed: 50,
      });
      notify("Text sent");
      setText("");
    } catch (e) {
      notify("Failed: " + (e as Error).message, true);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="idot-card idot-section">
      <SectionHead icon={<IconText size={18} />} title="Text" />
      <div className="idot-inline-text">
        <input
          className="idot-input"
          placeholder="Type a message to display…"
          value={text}
          maxLength={500}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
        />
        <button className="idot-inline-send" onClick={send} disabled={busy || !text.trim()}>
          {busy ? "…" : "Send"}
        </button>
      </div>
    </div>
  );
}

/* ---------- Inline Quick Modes: Clock / Effect / Mic ---------- */
export function InlineModes({ device, notify }: Props) {
  const hass = useHass();
  const [clock, setClock] = useState(0);
  const [effect, setEffect] = useState(0);
  const [mic, setMic] = useState(1);

  const call = async (service: string, data: Record<string, unknown>, ok: string) => {
    try {
      await hass.callService("idotmatrix", service, {
        entity_id: device.lightEntityId,
        ...data,
      });
      notify(ok);
    } catch (e) {
      notify("Failed: " + (e as Error).message, true);
    }
  };

  return (
    <div className="idot-card idot-section">
      <SectionHead icon={<IconEffect size={18} />} title="Quick modes" />
      <div className="idot-quick-grid">
        <div className="idot-quick">
          <span className="idot-quick-label">
            <IconClock size={13} /> Clock
          </span>
          <div className="idot-quick-row">
            <select
              className="idot-select"
              value={clock}
              onChange={(e) => setClock(+e.target.value)}
            >
              {CLOCK_STYLES.map((s, i) => (
                <option key={i} value={i}>
                  {s}
                </option>
              ))}
            </select>
            <button
              className="idot-quick-go"
              onClick={() =>
                call("show_clock", { style: clock, show_date: true, hour24: true }, "Clock set")
              }
            >
              Show
            </button>
          </div>
        </div>

        <div className="idot-quick">
          <span className="idot-quick-label">
            <IconEffect size={13} /> Effect
          </span>
          <div className="idot-quick-row">
            <select
              className="idot-select"
              value={effect}
              onChange={(e) => setEffect(+e.target.value)}
            >
              {EFFECT_STYLES.map((s, i) => (
                <option key={i} value={i}>
                  {s}
                </option>
              ))}
            </select>
            <button
              className="idot-quick-go"
              onClick={() => call("show_effect", { style: effect }, "Effect applied")}
            >
              Show
            </button>
          </div>
        </div>

        <div className="idot-quick">
          <span className="idot-quick-label">
            <IconMic size={13} /> Mic rhythm
          </span>
          <div className="idot-quick-row">
            <select className="idot-select" value={mic} onChange={(e) => setMic(+e.target.value)}>
              {MIC_STYLES.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
            <button
              className="idot-quick-go"
              onClick={() => call("mic_rhythm", { style: mic, sensitivity: 50 }, "Mic rhythm on")}
            >
              Start
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
