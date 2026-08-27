import { useCallback, useEffect, useMemo, useState } from "react";
import { useHass } from "./hass-context";
import {
  albumsDelete,
  albumsList,
  albumsPlay,
  albumsSave,
  albumsStop,
  dataUrl,
  galleryList,
} from "./idot";
import type { Album, GalleryItem, IDotDevice } from "./types";
import { Modal } from "./Modal";
import { useBusyAction } from "./useBusyAction";
import { IconAlbum, IconSpinner } from "./icons";

interface Props {
  device: IDotDevice;
  available: boolean;
  notify: (msg: string, isError?: boolean) => void;
}

const DEFAULT_INTERVAL = 10;
const MIN_INTERVAL = 3;
const MAX_INTERVAL = 120;

export function Albums({ device, available, notify }: Props) {
  const hass = useHass();
  const [albums, setAlbums] = useState<Album[] | null>(null);
  const [playingId, setPlayingId] = useState<string | null>(null);
  const [gallery, setGallery] = useState<GalleryItem[]>([]);
  const [editing, setEditing] = useState<Album | "new" | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<Album | null>(null);

  const galleryById = useMemo(() => {
    const m: Record<string, GalleryItem> = {};
    for (const g of gallery) m[g.id] = g;
    return m;
  }, [gallery]);

  const refresh = useCallback(async () => {
    try {
      const [a, g] = await Promise.all([
        albumsList(hass, device.lightEntityId),
        galleryList(hass),
      ]);
      setAlbums(a.albums);
      setPlayingId(a.playingAlbumId);
      setGallery(g);
    } catch (e) {
      notify("No se pudieron cargar los álbumes: " + (e as Error).message, true);
      setAlbums([]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hass, device.lightEntityId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <div className="idot-card idot-section">
      <div className="idot-gallery-head">
        <div className="idot-section-head" style={{ margin: 0 }}>
          <div className="idot-section-icon">
            <IconAlbum size={18} />
          </div>
          <div className="idot-section-title">Álbumes</div>
        </div>
        <button
          className="idot-add-btn"
          onClick={() => setEditing("new")}
          disabled={gallery.length === 0 && albums !== null && albums.length === 0}
          title={gallery.length === 0 ? "Primero añade imágenes en la Galería" : ""}
        >
          + Nuevo álbum
        </button>
      </div>

      {albums === null ? (
        <div className="idot-gallery-loading">
          <IconSpinner size={26} />
          <span>Cargando álbumes…</span>
        </div>
      ) : albums.length === 0 ? (
        <div className="idot-gallery-empty">
          {gallery.length === 0 ? (
            <>Aún no hay álbumes. Primero añade imágenes en la Galería, luego crea un álbum.</>
          ) : (
            <>Aún no hay álbumes — crea uno con "+ Nuevo álbum".</>
          )}
        </div>
      ) : (
        <div className="idot-album-list">
          {albums.map((al) => (
            <AlbumCard
              key={al.id}
              album={al}
              entityId={device.lightEntityId}
              gallery={galleryById}
              playing={al.id === playingId}
              available={available}
              notify={notify}
              onChanged={refresh}
              onEdit={() => setEditing(al)}
              onRequestDelete={() => setConfirmDelete(al)}
            />
          ))}
        </div>
      )}

      {editing && (
        <EditModal
          album={editing === "new" ? null : editing}
          gallery={gallery}
          notify={notify}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            refresh();
          }}
        />
      )}

      {confirmDelete && (
        <DeleteModal
          album={confirmDelete}
          notify={notify}
          onClose={() => setConfirmDelete(null)}
          onDeleted={() => {
            setConfirmDelete(null);
            refresh();
          }}
        />
      )}
    </div>
  );
}

/* ---------- One album card ---------- */
function AlbumCard({
  album,
  entityId,
  gallery,
  playing,
  available,
  notify,
  onChanged,
  onEdit,
  onRequestDelete,
}: {
  album: Album;
  entityId: string;
  gallery: Record<string, GalleryItem>;
  playing: boolean;
  available: boolean;
  notify: (msg: string, isError?: boolean) => void;
  onChanged: () => void;
  onEdit: () => void;
  onRequestDelete: () => void;
}) {
  const hass = useHass();
  const play = useBusyAction((m) => notify("Reproducir falló: " + m, true));
  const stop = useBusyAction((m) => notify("Detener falló: " + m, true));

  const thumbs = album.item_ids
    .map((id) => gallery[id])
    .filter(Boolean)
    .slice(0, 5);

  const onPlay = () =>
    play.run(() => albumsPlay(hass, album.id, entityId)).then((ok) => {
      if (ok) {
        notify(`Reproduciendo "${album.name}"`);
        onChanged();
      }
    });

  return (
    <div className={"idot-album-card" + (playing ? " playing" : "")}>
      <div className="idot-album-info">
        <div className="idot-album-title-row">
          <div className="idot-album-name">{album.name}</div>
          {playing && <span className="idot-album-badge">Reproduciendo</span>}
        </div>
        <div className="idot-album-meta">
          {album.item_ids.length} imagen{album.item_ids.length === 1 ? "" : "es"} · cada{" "}
          {album.interval}s
        </div>
        <div className="idot-album-thumbs">
          {thumbs.map((g) => (
            <img key={g.id} className="idot-album-thumb" src={dataUrl(g)} alt={g.name} />
          ))}
          {album.item_ids.length > thumbs.length && (
            <span className="idot-album-more">+{album.item_ids.length - thumbs.length}</span>
          )}
          {thumbs.length === 0 && <span className="idot-album-empty">Sin imágenes</span>}
        </div>
      </div>

      <div className="idot-album-actions">
        {playing ? (
          <button
            className={"idot-quick-go st-danger" + (stop.busy ? " st-busy" : "")}
            onClick={() =>
              stop.run(() => albumsStop(hass, entityId)).then((ok) => ok && onChanged())
            }
            disabled={stop.busy}
          >
            {stop.busy ? <IconSpinner /> : "Detener"}
          </button>
        ) : (
          <button
            className={"idot-quick-go" + (play.busy ? " st-busy" : "")}
            onClick={onPlay}
            disabled={play.busy || !available || album.item_ids.length === 0}
            title={!available ? "El panel no está disponible" : ""}
          >
            {play.busy ? <IconSpinner /> : "Reproducir"}
          </button>
        )}
        <button className="idot-icon-btn" onClick={onEdit} title="Editar">
          <EditIcon />
        </button>
        <button className="idot-icon-btn danger" onClick={onRequestDelete} title="Eliminar">
          <TrashIcon />
        </button>
      </div>
    </div>
  );
}

/* ---------- Create / edit modal ---------- */
function EditModal({
  album,
  gallery,
  notify,
  onClose,
  onSaved,
}: {
  album: Album | null;
  gallery: GalleryItem[];
  notify: (msg: string, isError?: boolean) => void;
  onClose: () => void;
  onSaved: () => void;
}) {
  const hass = useHass();
  const [name, setName] = useState(album?.name ?? "");
  const [interval, setInterval] = useState(album?.interval ?? DEFAULT_INTERVAL);
  // Preserve selection order; start from the album's existing ordering.
  const [selected, setSelected] = useState<string[]>(album?.item_ids ?? []);
  const { busy, run } = useBusyAction((m) => notify("Guardar falló: " + m, true));

  const toggle = (id: string) =>
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );

  const save = () => {
    if (!name.trim() || selected.length === 0) return;
    run(async () => {
      await albumsSave(hass, {
        album_id: album?.id,
        name: name.trim(),
        item_ids: selected,
        interval,
      });
      notify(album ? "Álbum actualizado" : "Álbum creado");
    }).then((ok) => ok && onSaved());
  };

  return (
    <Modal title={album ? "Editar álbum" : "Nuevo álbum"} onClose={onClose}>
      <div className="idot-field">
        <label>Nombre</label>
        <input
          className="idot-input"
          placeholder="Nombre del álbum"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </div>

      <div className="idot-field">
        <label>Intervalo: {interval}s</label>
        <input
          type="range"
          className="idot-slider"
          min={MIN_INTERVAL}
          max={MAX_INTERVAL}
          value={interval}
          onChange={(e) => setInterval(+e.target.value)}
        />
      </div>

      <div className="idot-field">
        <label>
          Imágenes ({selected.length} seleccionada{selected.length === 1 ? "" : "s"})
        </label>
        {gallery.length === 0 ? (
          <p className="idot-hint">
            No hay imágenes en la Galería. Añade algunas primero.
          </p>
        ) : (
          <div className="idot-select-grid">
            {gallery.map((g) => {
              const idx = selected.indexOf(g.id);
              const on = idx >= 0;
              return (
                <button
                  key={g.id}
                  className={"idot-select-thumb" + (on ? " on" : "")}
                  onClick={() => toggle(g.id)}
                  title={g.name}
                >
                  <img src={dataUrl(g)} alt={g.name} />
                  {on && <span className="idot-select-order">{idx + 1}</span>}
                </button>
              );
            })}
          </div>
        )}
      </div>

      <button
        className={"idot-btn" + (busy ? " st-busy" : "")}
        onClick={save}
        disabled={busy || !name.trim() || selected.length === 0}
      >
        {busy ? (
          <span className="idot-btn-status">
            <IconSpinner /> &nbsp;Guardando…
          </span>
        ) : album ? (
          "Guardar cambios"
        ) : (
          "Crear álbum"
        )}
      </button>
    </Modal>
  );
}

/* ---------- Delete confirm ---------- */
function DeleteModal({
  album,
  notify,
  onClose,
  onDeleted,
}: {
  album: Album;
  notify: (msg: string, isError?: boolean) => void;
  onClose: () => void;
  onDeleted: () => void;
}) {
  const hass = useHass();
  const { busy, run } = useBusyAction((m) => notify("Eliminar falló: " + m, true));

  const del = () =>
    run(async () => {
      await albumsDelete(hass, album.id);
      notify("Álbum eliminado");
    }).then((ok) => ok && onDeleted());

  return (
    <Modal title="Eliminar álbum" onClose={onClose}>
      <p className="idot-hint" style={{ marginBottom: 18 }}>
        ¿Eliminar el álbum <strong>{album.name}</strong>? Las imágenes de la galería no se
        borran.
      </p>
      <div className="idot-modal-actions">
        <button className="idot-btn-secondary" onClick={onClose} disabled={busy}>
          Cancelar
        </button>
        <button className="idot-btn idot-btn-danger" onClick={del} disabled={busy}>
          {busy ? "Eliminando…" : "Eliminar"}
        </button>
      </div>
    </Modal>
  );
}

function EditIcon() {
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
      <path d="M4 20h4L18 10l-4-4L4 16v4zM14 6l4 4" />
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
