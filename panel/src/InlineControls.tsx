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
import {
  IconAlert,
  IconCheck,
  IconClock,
  IconColor,
  IconEffect,
  IconMic,
  IconSpinner,
  IconText,
} from "./icons";
import { useBusyAction, type ActionStatus } from "./useBusyAction";

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

function statusClass(status: ActionStatus): string {
  switch (status) {
    case "busy":
      return " st-busy";
    case "success":
      return " st-success";
    case "error":
      return " st-error";
    default:
      return "";
  }
}

/** Small glyph reflecting an action status; used inside buttons. */
function StatusGlyph({ status, idle }: { status: ActionStatus; idle: React.ReactNode }) {
  if (status === "busy")
    return (
      <span className="idot-btn-status">
        <IconSpinner />
      </span>
    );
  if (status === "success")
    return (
      <span className="idot-btn-status">
        <IconCheck />
      </span>
    );
  if (status === "error")
    return (
      <span className="idot-btn-status">
        <IconAlert />
      </span>
    );
  return <>{idle}</>;
}

/* ---------- Inline Color: tap swatch or picker to apply immediately ---------- */
export function InlineColor({ device, notify }: Props) {
  const hass = useHass();
  const [hex, setHex] = useState(() => rgbToHex(getRgbColor(hass, device.lightEntityId)));
  const { busy, run } = useBusyAction((m) => notify("Color failed: " + m, true));
  const [pending, setPending] = useState<string | null>(null);

  const apply = (h: string) => {
    setHex(h);
    setPending(h);
    run(() =>
      hass.callService("light", "turn_on", {
        entity_id: device.lightEntityId,
        rgb_color: hexToRgb(h),
      })
    ).then(() => setPending(null));
  };

  return (
    <div className="idot-card idot-section">
      <SectionHead
        icon={busy ? <IconSpinner size={18} /> : <IconColor size={18} />}
        title="Color"
      />
      <div className="idot-inline-color">
        <input
          type="color"
          className="idot-color-input"
          value={hex}
          disabled={busy}
          onChange={(e) => apply(e.target.value)}
          title="Custom color"
        />
        {PRESET_COLORS.map((c) => (
          <button
            key={c}
            className={
              "idot-swatch" +
              (c.toLowerCase() === hex.toLowerCase() ? " active" : "") +
              (busy && pending === c ? " st-busy" : "")
            }
            style={{ background: c }}
            disabled={busy}
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
  const { status, busy, run } = useBusyAction((m) => notify("Text failed: " + m, true));

  const send = () => {
    if (!text.trim() || busy) return;
    run(() =>
      hass.callService("idotmatrix", "send_text", {
        entity_id: device.lightEntityId,
        text,
        mode: 1,
        speed: 50,
      })
    ).then(() => setText(""));
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
          disabled={busy}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
        />
        <button
          className={"idot-inline-send" + statusClass(status)}
          onClick={send}
          disabled={busy || !text.trim()}
        >
          <StatusGlyph status={status} idle={<>Send</>} />
        </button>
      </div>
    </div>
  );
}

/* ---------- One quick-mode row with its own busy state ---------- */
function QuickRow({
  label,
  icon,
  options,
  value,
  onChange,
  buttonLabel,
  onFire,
}: {
  label: string;
  icon: React.ReactNode;
  options: { value: number; label: string }[];
  value: number;
  onChange: (v: number) => void;
  buttonLabel: string;
  onFire: () => Promise<unknown>;
}) {
  const { status, busy, run } = useBusyAction();
  return (
    <div className="idot-quick">
      <span className="idot-quick-label">
        {icon} {label}
      </span>
      <div className="idot-quick-row">
        <select
          className="idot-select"
          value={value}
          disabled={busy}
          onChange={(e) => onChange(+e.target.value)}
        >
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <button
          className={"idot-quick-go" + statusClass(status)}
          disabled={busy}
          onClick={() => run(onFire)}
        >
          <StatusGlyph status={status} idle={<>{buttonLabel}</>} />
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

  const call = (service: string, data: Record<string, unknown>, ok: string, err: string) =>
    hass
      .callService("idotmatrix", service, { entity_id: device.lightEntityId, ...data })
      .then((r) => {
        notify(ok);
        return r;
      })
      .catch((e) => {
        notify(err + ": " + (e as Error).message, true);
        throw e;
      });

  return (
    <div className="idot-card idot-section">
      <SectionHead icon={<IconEffect size={18} />} title="Quick modes" />
      <div className="idot-quick-grid">
        <QuickRow
          label="Clock"
          icon={<IconClock size={13} />}
          options={CLOCK_STYLES.map((s, i) => ({ value: i, label: s }))}
          value={clock}
          onChange={setClock}
          buttonLabel="Show"
          onFire={() =>
            call("show_clock", { style: clock, show_date: true, hour24: true }, "Clock set", "Clock")
          }
        />
        <QuickRow
          label="Effect"
          icon={<IconEffect size={13} />}
          options={EFFECT_STYLES.map((s, i) => ({ value: i, label: s }))}
          value={effect}
          onChange={setEffect}
          buttonLabel="Show"
          onFire={() => call("show_effect", { style: effect }, "Effect applied", "Effect")}
        />
        <QuickRow
          label="Mic rhythm"
          icon={<IconMic size={13} />}
          options={MIC_STYLES}
          value={mic}
          onChange={setMic}
          buttonLabel="Start"
          onFire={() =>
            call("mic_rhythm", { style: mic, sensitivity: 50 }, "Mic rhythm on", "Mic")
          }
        />
      </div>
    </div>
  );
}
