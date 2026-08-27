import { useState } from "react";
import { Modal } from "./Modal";
import { useHass } from "./hass-context";
import { arrayBufferToBase64 } from "./idot";
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
