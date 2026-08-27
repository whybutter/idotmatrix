import { useCallback, useEffect, useRef, useState } from "react";
import { useHass } from "./hass-context";
import {
  catalogGroups,
  catalogImageBase64,
  catalogImgUrl,
  catalogList,
  catalogSources,
  galleryAdd,
} from "./idot";
import type {
  CatalogGroup,
  CatalogItem,
  CatalogSource,
  IDotDevice,
} from "./types";
import { Modal } from "./Modal";
import { useBusyAction } from "./useBusyAction";
import { IconImage, IconSpinner } from "./icons";

interface Props {
  device: IDotDevice;
  available: boolean;
  notify: (msg: string, isError?: boolean) => void;
}

const PAGE = 60;

// Per-source attribution shown under the grid.
const ATTRIBUTION: Record<string, string> = {
  heaton: "Catálogo original de la app iDotMatrix",
  openmoji: "Emojis por OpenMoji (CC BY-SA 4.0)",
  poke: "Sprites de Pokémon © Nintendo / Game Freak — uso personal",
};

export function Explore({ device, available, notify }: Props) {
  const hass = useHass();
  const hassRef = useRef(hass);
  hassRef.current = hass;

  const [sources, setSources] = useState<CatalogSource[] | null>(null);
  const [source, setSource] = useState<string | null>(null);
  const [groups, setGroups] = useState<CatalogGroup[] | null>(null);
  const [group, setGroup] = useState<string | null>(null);
  const [items, setItems] = useState<CatalogItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [active, setActive] = useState<CatalogItem | null>(null);

  // Load the source list once (ref-guarded so hass churn can't re-run it).
  const inited = useRef(false);
  useEffect(() => {
    if (inited.current) return;
    inited.current = true;
    catalogSources(hassRef.current)
      .then((s) => {
        setSources(s);
        if (s.length) setSource(s[0].id);
      })
      .catch((e) => {
        setSources([]);
        setError("No se pudieron cargar las fuentes: " + (e as Error).message);
      });
  }, []);

  // Load categories whenever the SOURCE changes (not on hass churn — deps are
  // [source] only, so switching a category never re-triggers this and never
  // resets the selection).
  useEffect(() => {
    if (!source) return;
    let alive = true;
    setGroups(null);
    setGroup(null);
    setItems([]);
    setTotal(0);
    setError(null);
    catalogGroups(hassRef.current, source)
      .then((g) => {
        if (!alive) return;
        setGroups(g);
        if (g.length) setGroup(g[0].id);
      })
      .catch((e) => {
        if (!alive) return;
        setGroups([]);
        setError("No se pudieron cargar las categorías: " + (e as Error).message);
      });
    return () => {
      alive = false;
    };
  }, [source]);

  const loadPage = useCallback(
    async (src: string, grp: string, offset: number, replace: boolean) => {
      setLoading(true);
      setError(null);
      try {
        const res = await catalogList(hassRef.current, src, grp, PAGE, offset);
        setTotal(res.total);
        setItems((prev) => (replace ? res.items : [...prev, ...res.items]));
      } catch (e) {
        setError("No se pudo cargar el catálogo: " + (e as Error).message);
      } finally {
        setLoading(false);
      }
    },
    []
  );

  // Load the first page whenever the group changes.
  useEffect(() => {
    if (!source || !group) return;
    setItems([]);
    setTotal(0);
    loadPage(source, group, 0, true);
  }, [source, group, loadPage]);

  const canLoadMore = items.length < total && !loading;

  return (
    <div className="idot-card idot-section">
      <div className="idot-section-head">
        <div className="idot-section-icon">
          <IconImage size={18} />
        </div>
        <div className="idot-section-title">Explorar</div>
      </div>

      {/* Source selector */}
      {sources && sources.length > 1 && (
        <div className="idot-source-row">
          {sources.map((s) => (
            <button
              key={s.id}
              className={"idot-source-btn" + (source === s.id ? " active" : "")}
              onClick={() => setSource(s.id)}
            >
              {s.name}
            </button>
          ))}
        </div>
      )}

      {/* Category chips */}
      {groups === null ? (
        <div className="idot-gallery-loading">
          <IconSpinner size={22} />
          <span>Cargando categorías…</span>
        </div>
      ) : groups.length === 0 ? (
        <div className="idot-gallery-empty">No hay categorías disponibles.</div>
      ) : (
        <div className="idot-chip-row">
          {groups.map((g) => (
            <button
              key={g.id}
              className={"idot-chip" + (group === g.id ? " active" : "")}
              onClick={() => setGroup(g.id)}
            >
              {g.name}
            </button>
          ))}
        </div>
      )}

      {/* Thumbnail grid */}
      {error && items.length === 0 ? (
        <div className="idot-gallery-empty">{error}</div>
      ) : items.length === 0 && loading ? (
        <div className="idot-gallery-loading">
          <IconSpinner size={26} />
          <span>Cargando…</span>
        </div>
      ) : items.length === 0 ? (
        <div className="idot-gallery-empty">No hay elementos en esta categoría.</div>
      ) : (
        <>
          <div className="idot-catalog-grid">
            {items.map((it) => (
              <button
                key={it.ref}
                className="idot-catalog-thumb"
                onClick={() => setActive(it)}
                title={it.name}
              >
                <img
                  src={source ? catalogImgUrl(source, it.ref) : ""}
                  alt={it.name}
                  loading="lazy"
                />
              </button>
            ))}
          </div>

          {canLoadMore && (
            <button
              className="idot-btn-secondary idot-loadmore"
              onClick={() =>
                source && group && loadPage(source, group, items.length, false)
              }
            >
              Cargar más ({items.length} / {total})
            </button>
          )}
          {loading && items.length > 0 && (
            <div className="idot-gallery-loading" style={{ padding: "16px 0" }}>
              <IconSpinner size={20} />
            </div>
          )}
        </>
      )}

      {source && ATTRIBUTION[source] && (
        <div className="idot-attribution">{ATTRIBUTION[source]}</div>
      )}

      {active && source && (
        <ActionSheet
          source={source}
          item={active}
          device={device}
          available={available}
          notify={notify}
          onClose={() => setActive(null)}
        />
      )}
    </div>
  );
}

/* ---------- Tap action sheet: size + send/save ---------- */
function ActionSheet({
  source,
  item,
  device,
  available,
  notify,
  onClose,
}: {
  source: string;
  item: CatalogItem;
  device: IDotDevice;
  available: boolean;
  notify: (msg: string, isError?: boolean) => void;
  onClose: () => void;
}) {
  const hass = useHass();
  const [size, setSize] = useState<16 | 32 | 64>(32);
  const send = useBusyAction((m) => notify("Enviar falló: " + m, true));
  const save = useBusyAction((m) => notify("Guardar falló: " + m, true));

  const onSend = () =>
    send.run(async () => {
      const b64 = await catalogImageBase64(source, item.ref);
      await hass.callService(
        "idotmatrix",
        item.is_gif ? "upload_gif" : "upload_image",
        {
          entity_id: device.lightEntityId,
          image_data: b64,
          size,
        }
      );
      notify(`Enviado: ${item.name}`);
    });

  const onSave = () =>
    save.run(async () => {
      const b64 = await catalogImageBase64(source, item.ref);
      await galleryAdd(hass, {
        name: item.name,
        image_data: b64,
        size,
        is_gif: item.is_gif,
        mime: item.is_gif ? "image/gif" : "image/png",
      });
      notify("Guardado en la galería");
    });

  const busy = send.busy || save.busy;

  return (
    <Modal title={item.name} onClose={onClose}>
      <div className="idot-sheet-preview">
        <img src={catalogImgUrl(source, item.ref)} alt={item.name} />
      </div>

      <div className="idot-field">
        <label>Tamaño del panel</label>
        <div className="idot-size-toggle">
          {([16, 32, 64] as const).map((s) => (
            <button
              key={s}
              className={"idot-size-btn" + (size === s ? " active" : "")}
              onClick={() => setSize(s)}
              disabled={busy}
            >
              {s}×{s}
            </button>
          ))}
        </div>
      </div>

      <div className="idot-modal-actions">
        <button
          className={"idot-btn-secondary" + (save.status === "success" ? " st-success" : "")}
          onClick={onSave}
          disabled={busy}
        >
          {save.busy ? (
            <span className="idot-btn-status">
              <IconSpinner /> &nbsp;Guardando…
            </span>
          ) : (
            "Guardar en galería"
          )}
        </button>
        <button
          className={
            "idot-btn" +
            (send.status === "success" ? " st-success" : send.status === "error" ? " st-error" : "")
          }
          onClick={onSend}
          disabled={busy || !available}
          title={!available ? "El panel no está disponible" : ""}
        >
          {send.busy ? (
            <span className="idot-btn-status">
              <IconSpinner /> &nbsp;Enviando…
            </span>
          ) : (
            "Enviar al panel"
          )}
        </button>
      </div>
      {!available && (
        <p className="idot-hint" style={{ marginTop: 12, marginBottom: 0 }}>
          El panel no está disponible — solo puedes guardar en la galería.
        </p>
      )}
    </Modal>
  );
}
