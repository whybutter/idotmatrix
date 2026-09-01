import { useCallback, useEffect, useState } from "react";
import { useHass } from "./hass-context";
import {
  arrayBufferToBase64,
  dataUrl,
  galleryAdd,
  galleryDelete,
  galleryList,
  gallerySend,
} from "./idot";
import type { GalleryItem, IDotDevice } from "./types";
import { Modal } from "./Modal";
import { useBusyAction } from "./useBusyAction";
import { IconAlert, IconCheck, IconImage, IconSpinner } from "./icons";

interface Props {
  device: IDotDevice;
  notify: (msg: string, isError?: boolean) => void;
}

export function Gallery({ device, notify }: Props) {
  const hass = useHass();
  const [items, setItems] = useState<GalleryItem[] | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<GalleryItem | null>(null);

  const refresh = useCallback(async () => {
    try {
      const list = await galleryList(hass);
      setItems(list);
    } catch (e) {
      notify("Could not load the gallery: " + (e as Error).message, true);
      setItems([]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hass]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const onDeleted = (id: string) =>
    setItems((prev) => (prev ? prev.filter((i) => i.id !== id) : prev));

  return (
    <div className="idot-card idot-section">
      <div className="idot-gallery-head">
        <div className="idot-section-head" style={{ margin: 0 }}>
          <div className="idot-section-icon">
            <IconImage size={18} />
          </div>
          <div className="idot-section-title">Gallery</div>
        </div>
        <button className="idot-add-btn" onClick={() => setShowAdd(true)}>
          + Add
        </button>
      </div>

      {items === null ? (
        <div className="idot-gallery-loading">
          <IconSpinner size={26} />
          <span>Loading gallery…</span>
        </div>
      ) : items.length === 0 ? (
        <div className="idot-gallery-empty">
          No images yet — upload one from your computer.
        </div>
      ) : (
        <div className="idot-gallery-grid">
          {items.map((it) => (
            <GalleryThumb
              key={it.id}
              item={it}
              device={device}
              notify={notify}
              onRequestDelete={() => setConfirmDelete(it)}
            />
          ))}
        </div>
      )}

      {showAdd && (
        <AddModal
          notify={notify}
          onClose={() => setShowAdd(false)}
          onAdded={() => {
            setShowAdd(false);
            refresh();
          }}
        />
      )}

      {confirmDelete && (
        <DeleteModal
          item={confirmDelete}
          notify={notify}
          onClose={() => setConfirmDelete(null)}
          onDeleted={(id) => {
            onDeleted(id);
            setConfirmDelete(null);
          }}
        />
      )}
    </div>
  );
}

/* ---------- Single thumbnail: tap to send, trash to delete ---------- */
function GalleryThumb({
  item,
  device,
  notify,
  onRequestDelete,
}: {
  item: GalleryItem;
  device: IDotDevice;
  notify: (msg: string, isError?: boolean) => void;
  onRequestDelete: () => void;
}) {
  const hass = useHass();
  const { status, busy, run } = useBusyAction((m) => notify("Send failed: " + m, true));

  const send = () =>
    run(() => gallerySend(hass, device.lightEntityId, item)).then((ok) => {
      if (ok) notify(`Enviado: ${item.name}`);
    });

  return (
    <div
      className={"idot-thumb" + (busy ? " busy" : "")}
      onClick={send}
      role="button"
      tabIndex={0}
      title={`Enviar "${item.name}" al panel`}
    >
      <div className="idot-thumb-img-wrap">
        <img className="idot-thumb-img" src={dataUrl(item)} alt={item.name} />
        {item.is_gif && <span className="idot-thumb-badge">GIF</span>}
        <span className="idot-thumb-size">{item.size}</span>

        {/* Status overlay */}
        {status !== "idle" && (
          <div className={"idot-thumb-overlay st-" + status}>
            {status === "busy" && <IconSpinner size={22} />}
            {status === "success" && <IconCheck size={22} />}
            {status === "error" && <IconAlert size={22} />}
          </div>
        )}

        <button
          className="idot-thumb-del"
          title="Delete"
          onClick={(e) => {
            e.stopPropagation();
            onRequestDelete();
          }}
        >
          <TrashIcon />
        </button>
      </div>
      <div className="idot-thumb-name">{item.name}</div>
    </div>
  );
}

/* ---------- Add-to-gallery modal ---------- */
function AddModal({
  notify,
  onClose,
  onAdded,
}: {
  notify: (msg: string, isError?: boolean) => void;
  onClose: () => void;
  onAdded: () => void;
}) {
  const hass = useHass();
  const [size, setSize] = useState<16 | 32 | 64>(32);
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const { busy, run } = useBusyAction((m) => notify("Save failed: " + m, true));

  const pick = (f: File | null) => {
    setFile(f);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(f ? URL.createObjectURL(f) : null);
    if (f && !name) setName(f.name.replace(/\.[^.]+$/, ""));
  };

  const save = () => {
    if (!file) return;
    run(async () => {
      const buf = await file.arrayBuffer();
      const b64 = arrayBufferToBase64(buf);
      const isGif = /gif$/i.test(file.type) || /\.gif$/i.test(file.name);
      await galleryAdd(hass, {
        name: name.trim() || file.name,
        image_data: b64,
        size,
        is_gif: isGif,
        mime: file.type || (isGif ? "image/gif" : "image/png"),
      });
      notify("Saved to gallery");
    }).then((ok) => {
      if (ok) onAdded();
    });
  };

  return (
    <Modal title="Add to gallery" onClose={onClose}>
      <div className="idot-field">
        <label>Image / GIF from your computer</label>
        <label className="idot-file-drop">
          {file ? file.name : "Choose a file (PNG, JPG, GIF)"}
          <input
            type="file"
            accept="image/*"
            style={{ display: "none" }}
            onChange={(e) => pick(e.target.files?.[0] ?? null)}
          />
        </label>
        {previewUrl && <img className="idot-preview-img" src={previewUrl} alt="preview" />}
      </div>

      <div className="idot-field">
        <label>Name</label>
        <input
          className="idot-input"
          placeholder="Name for the gallery"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </div>

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

      <button
        className={"idot-btn" + (busy ? " st-busy" : "")}
        onClick={save}
        disabled={busy || !file}
      >
        {busy ? (
          <span className="idot-btn-status">
            <IconSpinner /> &nbsp;Saving…
          </span>
        ) : (
          "Save to gallery"
        )}
      </button>
    </Modal>
  );
}

/* ---------- Delete confirmation ---------- */
function DeleteModal({
  item,
  notify,
  onClose,
  onDeleted,
}: {
  item: GalleryItem;
  notify: (msg: string, isError?: boolean) => void;
  onClose: () => void;
  onDeleted: (id: string) => void;
}) {
  const hass = useHass();
  const { busy, run } = useBusyAction((m) => notify("Delete failed: " + m, true));

  const del = () =>
    run(async () => {
      await galleryDelete(hass, item.id);
      notify("Deleted");
    }).then((ok) => {
      if (ok) onDeleted(item.id);
    });

  return (
    <Modal title="Delete image" onClose={onClose}>
      <p className="idot-hint" style={{ marginBottom: 18 }}>
        Delete <strong>{item.name}</strong> from the gallery? This cannot be undone.
      </p>
      <div className="idot-modal-actions">
        <button className="idot-btn-secondary" onClick={onClose} disabled={busy}>
          Cancelar
        </button>
        <button className="idot-btn idot-btn-danger" onClick={del} disabled={busy}>
          {busy ? "Deleting…" : "Delete"}
        </button>
      </div>
    </Modal>
  );
}

function TrashIcon() {
  return (
    <svg
      width={15}
      height={15}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M4 7h16M9 7V5h6v2M6 7l1 13h10l1-13" />
    </svg>
  );
}
