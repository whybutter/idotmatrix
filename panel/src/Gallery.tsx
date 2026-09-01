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
import { PixelPreview } from "./PixelPreview";
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
  // Items queued for deletion. One entry = the single-item trash button; many =
  // a multi-select batch. Both go through the same confirm + bulk delete.
  const [confirmDelete, setConfirmDelete] = useState<GalleryItem[] | null>(null);
  const [selecting, setSelecting] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());

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

  const onDeleted = (ids: string[]) => {
    const gone = new Set(ids);
    setItems((prev) => (prev ? prev.filter((i) => !gone.has(i.id)) : prev));
    setSelected((prev) => {
      const next = new Set(prev);
      ids.forEach((id) => next.delete(id));
      return next;
    });
  };

  const toggle = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const exitSelect = () => {
    setSelecting(false);
    setSelected(new Set());
  };

  const allSelected = !!items && items.length > 0 && selected.size === items.length;

  return (
    <div className="idot-card idot-section">
      <div className="idot-gallery-head">
        <div className="idot-section-head" style={{ margin: 0 }}>
          <div className="idot-section-icon">
            <IconImage size={18} />
          </div>
          <div className="idot-section-title">Gallery</div>
        </div>
        <div className="idot-gallery-head-actions">
          {!!items?.length && (
            <button
              className={"idot-select-btn" + (selecting ? " active" : "")}
              onClick={() => (selecting ? exitSelect() : setSelecting(true))}
            >
              {selecting ? "Done" : "Select"}
            </button>
          )}
          <button className="idot-add-btn" onClick={() => setShowAdd(true)}>
            + Add
          </button>
        </div>
      </div>

      {selecting && !!items?.length && (
        <div className="idot-selectbar">
          <label className="idot-selectall">
            <input
              type="checkbox"
              checked={allSelected}
              onChange={() =>
                setSelected(allSelected ? new Set() : new Set(items.map((i) => i.id)))
              }
            />
            <span>{allSelected ? "Clear all" : "Select all"}</span>
          </label>
          <span className="idot-selectcount">{selected.size} selected</span>
          <button
            className="idot-btn idot-btn-danger idot-selectdel"
            disabled={selected.size === 0}
            onClick={() =>
              setConfirmDelete(items.filter((i) => selected.has(i.id)))
            }
          >
            Delete
          </button>
        </div>
      )}

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
              selecting={selecting}
              selected={selected.has(it.id)}
              onToggle={() => toggle(it.id)}
              onRequestDelete={() => setConfirmDelete([it])}
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
          items={confirmDelete}
          notify={notify}
          onClose={() => setConfirmDelete(null)}
          onDeleted={(ids) => {
            onDeleted(ids);
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
  selecting,
  selected,
  onToggle,
  onRequestDelete,
}: {
  item: GalleryItem;
  device: IDotDevice;
  notify: (msg: string, isError?: boolean) => void;
  selecting: boolean;
  selected: boolean;
  onToggle: () => void;
  onRequestDelete: () => void;
}) {
  const hass = useHass();
  const { status, busy, run } = useBusyAction((m) => notify("Send failed: " + m, true));

  const send = () =>
    run(() => gallerySend(hass, device.lightEntityId, item)).then((ok) => {
      if (ok) notify(`Sent: ${item.name}`);
    });

  return (
    <div
      className={
        "idot-thumb" +
        (busy ? " busy" : "") +
        (selecting ? " selecting" : "") +
        (selected ? " selected" : "")
      }
      // In selection mode a tap picks the item instead of sending it, so you
      // can never fire an upload while curating the gallery.
      onClick={selecting ? onToggle : send}
      role="button"
      tabIndex={0}
      title={selecting ? item.name : `Send "${item.name}" to the panel`}
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

        {selecting ? (
          <span className={"idot-thumb-check" + (selected ? " on" : "")}>
            {selected && <CheckIcon />}
          </span>
        ) : (
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
        )}
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
        {previewUrl && (
          <div className="idot-preview-pair">
            <figure>
              <img className="idot-preview-img" src={previewUrl} alt="preview" />
              <figcaption>Original</figcaption>
            </figure>
            <figure>
              <PixelPreview
                src={previewUrl}
                size={size}
                display={140}
              />
              <figcaption>On the panel ({size}x{size})</figcaption>
            </figure>
          </div>
        )}
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
  items,
  notify,
  onClose,
  onDeleted,
}: {
  items: GalleryItem[];
  notify: (msg: string, isError?: boolean) => void;
  onClose: () => void;
  onDeleted: (ids: string[]) => void;
}) {
  const hass = useHass();
  const { busy, run } = useBusyAction((m) => notify("Delete failed: " + m, true));
  const ids = items.map((i) => i.id);
  const many = items.length > 1;

  const del = () =>
    run(async () => {
      // One round trip and one store write for the whole selection.
      await galleryDelete(hass, ids);
      notify(many ? `Deleted ${items.length} images` : "Deleted");
    }).then((ok) => {
      if (ok) onDeleted(ids);
    });

  return (
    <Modal title={many ? `Delete ${items.length} images` : "Delete image"} onClose={onClose}>
      <p className="idot-hint" style={{ marginBottom: 18 }}>
        {many ? (
          <>
            Delete <strong>{items.length} images</strong> from the gallery? This cannot
            be undone.
          </>
        ) : (
          <>
            Delete <strong>{items[0].name}</strong> from the gallery? This cannot be
            undone.
          </>
        )}
      </p>
      <div className="idot-modal-actions">
        <button className="idot-btn-secondary" onClick={onClose} disabled={busy}>
          Cancel
        </button>
        <button className="idot-btn idot-btn-danger" onClick={del} disabled={busy}>
          {busy ? "Deleting…" : "Delete"}
        </button>
      </div>
    </Modal>
  );
}

function CheckIcon() {
  return (
    <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={3} strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 6L9 17l-5-5" />
    </svg>
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
