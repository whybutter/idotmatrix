import { useState } from "react";
import { Modal } from "./Modal";
import { useHass } from "./hass-context";
import { arrayBufferToBase64 } from "./idot";
import { useBusyAction } from "./useBusyAction";
import { IconSpinner } from "./icons";
import type { IDotDevice } from "./types";

interface BaseProps {
  device: IDotDevice;
  onClose: () => void;
  notify: (msg: string, isError?: boolean) => void;
}

/* ---------------- Upload image / GIF ----------------
 * Kept as a modal because it genuinely needs a file picker, a size
 * selector and a preview — more than a one-tap inline control. */
export function UploadModal({ device, onClose, notify }: BaseProps) {
  const hass = useHass();
  const [size, setSize] = useState<16 | 32 | 64>(32);
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const { busy, run } = useBusyAction((m) => notify("Upload failed: " + m, true));

  const pick = (f: File | null) => {
    setFile(f);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(f ? URL.createObjectURL(f) : null);
  };

  const upload = () => {
    if (!file) return;
    run(async () => {
      const buf = await file.arrayBuffer();
      const b64 = arrayBufferToBase64(buf);
      const isGif = /gif$/i.test(file.type) || /\.gif$/i.test(file.name);
      await hass.callService("idotmatrix", isGif ? "upload_gif" : "upload_image", {
        entity_id: device.lightEntityId,
        size,
        image_data: b64,
      });
      notify(isGif ? "GIF uploaded" : "Image uploaded");
    }).then((ok) => {
      if (ok) onClose();
    });
  };

  return (
    <Modal title="Upload image" onClose={onClose}>
      <div className="idot-field">
        <label>Panel size</label>
        <div className="idot-size-toggle">
          {([16, 32, 64] as const).map((s) => (
            <button
              key={s}
              className={"idot-size-btn" + (size === s ? " active" : "")}
              onClick={() => setSize(s)}
            >
              {s}×{s}
            </button>
          ))}
        </div>
      </div>
      <div className="idot-field">
        <label>Image / GIF from your computer</label>
        <label className="idot-file-drop">
          {file ? file.name : "Click to choose a file (PNG, JPG, GIF)"}
          <input
            type="file"
            accept="image/*"
            style={{ display: "none" }}
            onChange={(e) => pick(e.target.files?.[0] ?? null)}
          />
        </label>
        {previewUrl && <img className="idot-preview-img" src={previewUrl} alt="preview" />}
      </div>
      <button
        className={"idot-btn" + (busy ? " st-busy" : "")}
        onClick={upload}
        disabled={busy || !file}
      >
        {busy ? (
          <span className="idot-btn-status">
            <IconSpinner /> &nbsp;Uploading…
          </span>
        ) : (
          "Upload to panel"
        )}
      </button>
    </Modal>
  );
}

/* ---------------- Scoreboard ----------------
 * Two counters; both travel in every frame, so we always send {count1, count2}
 * together on any change. */
export function ScoreboardModal({
  device,
  onClose,
  notify,
  available,
}: BaseProps & { available: boolean }) {
  const hass = useHass();
  const [c1, setC1] = useState(0);
  const [c2, setC2] = useState(0);
  const { status, busy, run } = useBusyAction((m) => notify("Scoreboard failed: " + m, true));

  const send = (n1: number, n2: number) => {
    const a = clamp(n1);
    const b = clamp(n2);
    setC1(a);
    setC2(b);
    if (!available) return;
    run(() =>
      hass.callService("idotmatrix", "scoreboard", {
        entity_id: device.lightEntityId,
        count1: a,
        count2: b,
      })
    );
  };

  return (
    <Modal title="Scoreboard" onClose={onClose}>
      {!available && (
        <p className="idot-hint">Panel is unavailable — connect it to send.</p>
      )}
      <div className="idot-score-row">
        <Counter color="#0a84ff" label="Home" value={c1} onChange={(v) => send(v, c2)} disabled={busy} />
        <div className="idot-score-sep">:</div>
        <Counter color="#ff453a" label="Away" value={c2} onChange={(v) => send(c1, v)} disabled={busy} />
      </div>
      <div className="idot-modal-actions" style={{ marginTop: 6 }}>
        <button className="idot-btn-secondary" onClick={() => send(0, 0)} disabled={busy}>
          Reset (0 : 0)
        </button>
        <button
          className={"idot-btn" + statusFlash(status)}
          onClick={() => send(c1, c2)}
          disabled={busy || !available}
        >
          {busy ? (
            <span className="idot-btn-status">
              <IconSpinner /> &nbsp;Sending…
            </span>
          ) : (
            "Send scoreboard"
          )}
        </button>
      </div>
    </Modal>
  );
}

function clamp(n: number): number {
  if (Number.isNaN(n)) return 0;
  return Math.max(0, Math.min(999, Math.round(n)));
}

function statusFlash(status: string): string {
  if (status === "success") return " st-success";
  if (status === "error") return " st-error";
  if (status === "busy") return " st-busy";
  return "";
}

function Counter({
  color,
  label,
  value,
  onChange,
  disabled,
}: {
  color: string;
  label: string;
  value: number;
  onChange: (v: number) => void;
  disabled: boolean;
}) {
  return (
    <div className="idot-counter">
      <div className="idot-counter-label">{label}</div>
      <div className="idot-counter-display" style={{ color }}>
        {value}
      </div>
      <div className="idot-counter-btns">
        <button className="idot-counter-btn" onClick={() => onChange(value - 1)} disabled={disabled}>
          −
        </button>
        <input
          className="idot-counter-input"
          type="number"
          min={0}
          max={999}
          value={value}
          disabled={disabled}
          onChange={(e) => onChange(clamp(+e.target.value))}
        />
        <button className="idot-counter-btn" onClick={() => onChange(value + 1)} disabled={disabled}>
          +
        </button>
      </div>
    </div>
  );
}

/* ---------------- Timers: chronograph + countdown ---------------- */
export function TimersModal({
  device,
  onClose,
  notify,
  available,
}: BaseProps & { available: boolean }) {
  const hass = useHass();
  const chrono = useBusyAction((m) => notify("Stopwatch failed: " + m, true));
  const count = useBusyAction((m) => notify("Countdown failed: " + m, true));
  const [min, setMin] = useState(1);
  const [sec, setSec] = useState(0);

  const chronoAction = (action: "start" | "pause" | "resume" | "reset") =>
    chrono.run(() =>
      hass.callService("idotmatrix", "chronograph", {
        entity_id: device.lightEntityId,
        action,
      })
    );

  const countAction = (action: "start" | "pause" | "restart" | "stop") =>
    count.run(() =>
      hass.callService("idotmatrix", "countdown", {
        entity_id: device.lightEntityId,
        action,
        minutes: min,
        seconds: sec,
      })
    );

  const clampM = (n: number) => Math.max(0, Math.min(59, Number.isNaN(n) ? 0 : Math.round(n)));

  return (
    <Modal title="Timers" onClose={onClose}>
      {!available && (
        <p className="idot-hint">Panel is unavailable — connect it to send.</p>
      )}

      {/* Chronograph */}
      <div className="idot-timer-block">
        <div className="idot-timer-title">
          Stopwatch {chrono.busy && <IconSpinner size={14} />}
        </div>
        <div className="idot-timer-btns">
          <button className="idot-quick-go" onClick={() => chronoAction("start")} disabled={chrono.busy || !available}>
            Start
          </button>
          <button className="idot-quick-go" onClick={() => chronoAction("pause")} disabled={chrono.busy || !available}>
            Pause
          </button>
          <button className="idot-quick-go" onClick={() => chronoAction("resume")} disabled={chrono.busy || !available}>
            Resume
          </button>
          <button className="idot-quick-go st-danger" onClick={() => chronoAction("reset")} disabled={chrono.busy || !available}>
            Reset
          </button>
        </div>
      </div>

      {/* Countdown */}
      <div className="idot-timer-block">
        <div className="idot-timer-title">
          Countdown {count.busy && <IconSpinner size={14} />}
        </div>
        <div className="idot-timer-inputs">
          <div className="idot-timer-field">
            <label>Min</label>
            <input
              className="idot-input"
              type="number"
              min={0}
              max={59}
              value={min}
              onChange={(e) => setMin(clampM(+e.target.value))}
            />
          </div>
          <div className="idot-timer-colon">:</div>
          <div className="idot-timer-field">
            <label>Sec</label>
            <input
              className="idot-input"
              type="number"
              min={0}
              max={59}
              value={sec}
              onChange={(e) => setSec(clampM(+e.target.value))}
            />
          </div>
        </div>
        <div className="idot-timer-btns">
          <button className="idot-quick-go" onClick={() => countAction("start")} disabled={count.busy || !available}>
            Start
          </button>
          <button className="idot-quick-go" onClick={() => countAction("pause")} disabled={count.busy || !available}>
            Pause
          </button>
          <button className="idot-quick-go" onClick={() => countAction("restart")} disabled={count.busy || !available}>
            Restart
          </button>
          <button className="idot-quick-go st-danger" onClick={() => countAction("stop")} disabled={count.busy || !available}>
            Stop
          </button>
        </div>
      </div>
    </Modal>
  );
}
