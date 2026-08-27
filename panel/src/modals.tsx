import { useState } from "react";
import { Modal } from "./Modal";
import { useHass } from "./hass-context";
import {
  CLOCK_STYLES,
  EFFECT_STYLES,
  TEXT_MODES,
  arrayBufferToBase64,
  getRgbColor,
  hexToRgb,
  rgbToHex,
} from "./idot";
import type { IDotDevice } from "./types";

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

interface BaseProps {
  device: IDotDevice;
  onClose: () => void;
  notify: (msg: string, isError?: boolean) => void;
}

/* ---------------- Color ---------------- */
export function ColorModal({ device, onClose, notify }: BaseProps) {
  const hass = useHass();
  const [hex, setHex] = useState(() => rgbToHex(getRgbColor(hass, device.lightEntityId)));
  const [busy, setBusy] = useState(false);

  const apply = async () => {
    setBusy(true);
    try {
      await hass.callService("light", "turn_on", {
        entity_id: device.lightEntityId,
        rgb_color: hexToRgb(hex),
      });
      notify("Color applied");
      onClose();
    } catch (e) {
      notify("Failed: " + (e as Error).message, true);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title="Color" onClose={onClose}>
      <div className="idot-field">
        <label>Pick a color</label>
        <div className="idot-color-row">
          <input
            type="color"
            className="idot-color-input"
            value={hex}
            onChange={(e) => setHex(e.target.value)}
          />
          <div className="idot-swatches">
            {PRESET_COLORS.map((c) => (
              <button
                key={c}
                className="idot-swatch"
                style={{ background: c }}
                onClick={() => setHex(c)}
                aria-label={c}
              />
            ))}
          </div>
        </div>
      </div>
      <button className="idot-btn" onClick={apply} disabled={busy}>
        {busy ? "Applying…" : "Apply color"}
      </button>
    </Modal>
  );
}

/* ---------------- Text ---------------- */
export function TextModal({ device, onClose, notify }: BaseProps) {
  const hass = useHass();
  const [text, setText] = useState("");
  const [mode, setMode] = useState(1);
  const [speed, setSpeed] = useState(50);
  const [hex, setHex] = useState("#ffffff");
  const [busy, setBusy] = useState(false);

  const send = async () => {
    if (!text.trim()) return;
    setBusy(true);
    try {
      await hass.callService("idotmatrix", "send_text", {
        entity_id: device.lightEntityId,
        text,
        mode,
        speed,
        rgb_color: hexToRgb(hex),
      });
      notify("Text sent");
      onClose();
    } catch (e) {
      notify("Failed: " + (e as Error).message, true);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title="Text" onClose={onClose}>
      <div className="idot-field">
        <label>Message</label>
        <textarea
          className="idot-textarea"
          placeholder="Enter text to display…"
          value={text}
          maxLength={500}
          onChange={(e) => setText(e.target.value)}
        />
      </div>
      <div className="idot-field">
        <label>Animation</label>
        <select className="idot-select" value={mode} onChange={(e) => setMode(+e.target.value)}>
          {TEXT_MODES.map((m, i) => (
            <option key={i} value={i}>
              {m}
            </option>
          ))}
        </select>
      </div>
      <div className="idot-field">
        <label>Speed: {speed}</label>
        <input
          type="range"
          className="idot-slider"
          min={0}
          max={100}
          value={speed}
          onChange={(e) => setSpeed(+e.target.value)}
        />
      </div>
      <div className="idot-field">
        <label>Text color</label>
        <div className="idot-color-row">
          <input
            type="color"
            className="idot-color-input"
            value={hex}
            onChange={(e) => setHex(e.target.value)}
          />
          <div className="idot-swatches">
            {PRESET_COLORS.map((c) => (
              <button
                key={c}
                className="idot-swatch"
                style={{ background: c }}
                onClick={() => setHex(c)}
              />
            ))}
          </div>
        </div>
      </div>
      <button className="idot-btn" onClick={send} disabled={busy || !text.trim()}>
        {busy ? "Sending…" : "Send text"}
      </button>
    </Modal>
  );
}

/* ---------------- Upload image ---------------- */
export function UploadModal({ device, onClose, notify }: BaseProps) {
  const hass = useHass();
  const [size, setSize] = useState<16 | 32 | 64>(32);
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const pick = (f: File | null) => {
    setFile(f);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(f ? URL.createObjectURL(f) : null);
  };

  const upload = async () => {
    if (!file) return;
    setBusy(true);
    try {
      const buf = await file.arrayBuffer();
      const b64 = arrayBufferToBase64(buf);
      const isGif = /gif$/i.test(file.type) || /\.gif$/i.test(file.name);
      await hass.callService("idotmatrix", isGif ? "upload_gif" : "upload_image", {
        entity_id: device.lightEntityId,
        size,
        image_data: b64,
      });
      notify(isGif ? "GIF uploaded" : "Image uploaded");
      onClose();
    } catch (e) {
      notify("Failed: " + (e as Error).message, true);
    } finally {
      setBusy(false);
    }
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
      <button className="idot-btn" onClick={upload} disabled={busy || !file}>
        {busy ? "Uploading…" : "Upload to panel"}
      </button>
    </Modal>
  );
}

/* ---------------- Clock ---------------- */
export function ClockModal({ device, onClose, notify }: BaseProps) {
  const hass = useHass();
  const [style, setStyle] = useState(0);
  const [showDate, setShowDate] = useState(true);
  const [hour24, setHour24] = useState(true);
  const [hex, setHex] = useState("#7c4dff");
  const [busy, setBusy] = useState(false);

  const apply = async () => {
    setBusy(true);
    try {
      await hass.callService("idotmatrix", "show_clock", {
        entity_id: device.lightEntityId,
        style,
        show_date: showDate,
        hour24,
        rgb_color: hexToRgb(hex),
      });
      notify("Clock set");
      onClose();
    } catch (e) {
      notify("Failed: " + (e as Error).message, true);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title="Clock" onClose={onClose}>
      <div className="idot-field">
        <label>Style</label>
        <select className="idot-select" value={style} onChange={(e) => setStyle(+e.target.value)}>
          {CLOCK_STYLES.map((s, i) => (
            <option key={i} value={i}>
              {s}
            </option>
          ))}
        </select>
      </div>
      <div className="idot-checkbox-row">
        <input id="c24" type="checkbox" checked={hour24} onChange={(e) => setHour24(e.target.checked)} />
        <label htmlFor="c24">24-hour format</label>
      </div>
      <div className="idot-checkbox-row">
        <input id="cdate" type="checkbox" checked={showDate} onChange={(e) => setShowDate(e.target.checked)} />
        <label htmlFor="cdate">Show date</label>
      </div>
      <div className="idot-field">
        <label>Color</label>
        <div className="idot-color-row">
          <input
            type="color"
            className="idot-color-input"
            value={hex}
            onChange={(e) => setHex(e.target.value)}
          />
          <div className="idot-swatches">
            {PRESET_COLORS.map((c) => (
              <button key={c} className="idot-swatch" style={{ background: c }} onClick={() => setHex(c)} />
            ))}
          </div>
        </div>
      </div>
      <button className="idot-btn" onClick={apply} disabled={busy}>
        {busy ? "Applying…" : "Show clock"}
      </button>
    </Modal>
  );
}

/* ---------------- Effect ---------------- */
export function EffectModal({ device, onClose, notify }: BaseProps) {
  const hass = useHass();
  const [style, setStyle] = useState(0);
  const [busy, setBusy] = useState(false);

  const apply = async () => {
    setBusy(true);
    try {
      await hass.callService("idotmatrix", "show_effect", {
        entity_id: device.lightEntityId,
        style,
      });
      notify("Effect applied");
      onClose();
    } catch (e) {
      notify("Failed: " + (e as Error).message, true);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title="Effect" onClose={onClose}>
      <div className="idot-field">
        <label>Effect style</label>
        <select className="idot-select" value={style} onChange={(e) => setStyle(+e.target.value)}>
          {EFFECT_STYLES.map((s, i) => (
            <option key={i} value={i}>
              {s}
            </option>
          ))}
        </select>
      </div>
      <p className="idot-hint">Built-in animated effects rendered on the panel.</p>
      <button className="idot-btn" onClick={apply} disabled={busy}>
        {busy ? "Applying…" : "Show effect"}
      </button>
    </Modal>
  );
}
