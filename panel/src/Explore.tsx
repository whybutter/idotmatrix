import { useCallback, useEffect, useState } from "react";
import { useHass } from "./hass-context";
import {
  catalogGroups,
  catalogImageBase64,
  catalogImgUrl,
  catalogList,
  galleryAdd,
} from "./idot";
import type { CatalogGroup, CatalogItem, IDotDevice } from "./types";
import { Modal } from "./Modal";
import { useBusyAction } from "./useBusyAction";
import { IconImage, IconSpinner } from "./icons";

interface Props {
  device: IDotDevice;
  available: boolean;
  notify: (msg: string, isError?: boolean) => void;
}

const PAGE = 60;

// Source registry — only OpenMoji today, structured so more can be added later.
const SOURCES = [{ id: "openmoji", name: "OpenMoji" }];

export function Explore({ device, available, notify }: Props) {
  const hass = useHass();
  const [source] = useState("openmoji");
  const [groups, setGroups] = useState<CatalogGroup[] | null>(null);
  const [group, setGroup] = useState<string | null>(null);
  const [items, setItems] = useState<CatalogItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [active, setActive] = useState<CatalogItem | null>(null);

  // Load groups once.
  useEffect(() => {
    let alive = true;
    catalogGroups(hass)
      .then((g) => {
        if (!alive) return;
        setGroups(g);
        if (g.length) setGroup(g[0].id);
      })
      .catch((e) => {
        if (alive) {
          setGroups([]);
          setError("No se pudieron cargar las categorías: " + (e as Error).message);
        }
      });
    return () => {
      alive = false;
    };
  }, [hass]);

  const loadPage = useCallback(
    async (grp: string, offset: number, replace: boolean) => {
      setLoading(true);
      setError(null);
      try {
        const res = await catalogList(hass, grp, PAGE, offset);
        setTotal(res.total);
        setItems((prev) => (replace ? res.items : [...prev, ...res.items]));
      } catch (e) {
        setError("No se pudo cargar el catálogo: " + (e as Error).message);
      } finally {
        setLoading(false);
      }
    },
    [hass]
  );

  // Load first page whenever the group changes.
  useEffect(() => {
    if (!group) return;
    setItems([]);
    setTotal(0);
    loadPage(group, 0, true);
  }, [group, loadPage]);

  const canLoadMore = items.length < total && !loading;

  return (
    <div className="idot-card idot-section">
      <div className="idot-section-head">
        <div className="idot-section-icon">
          <IconImage size={18} />
        </div>
        <div className="idot-section-title">Explorar</div>
      </div>

      {/* Source selector (single source today) */}
      <div className="idot-source-row">
        {SOURCES.map((s) => (
          <button
            key={s.id}
            className={"idot-source-btn" + (source === s.id ? " active" : "")}
            disabled={s.id !== "openmoji"}
          >
            {s.name}
          </button>
        ))}
      </div>

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
                key={it.hexcode}
                className="idot-catalog-thumb"
                onClick={() => setActive(it)}
                title={it.name}
              >
                <img src={catalogImgUrl(it.hexcode)} alt={it.name} loading="lazy" />
              </button>
            ))}
          </div>

          {canLoadMore && (
            <button
              className="idot-btn-secondary idot-loadmore"
              onClick={() => group && loadPage(group, items.length, false)}
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

      <div className="idot-attribution">Emojis por OpenMoji (CC BY-SA 4.0)</div>

      {active && (
        <ActionSheet
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
  item,
  device,
  available,
  notify,
  onClose,
}: {
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
      const b64 = await catalogImageBase64(item.hexcode);
      await hass.callService("idotmatrix", "upload_image", {
        entity_id: device.lightEntityId,
        image_data: b64,
        size,
      });
      notify(`Enviado: ${item.name}`);
    });

  const onSave = () =>
    save.run(async () => {
      const b64 = await catalogImageBase64(item.hexcode);
      await galleryAdd(hass, {
        name: item.name,
        image_data: b64,
        size,
        is_gif: false,
        mime: "image/png",
      });
      notify("Guardado en la galería");
    });

  const busy = send.busy || save.busy;

  return (
    <Modal title={item.name} onClose={onClose}>
      <div className="idot-sheet-preview">
        <img src={catalogImgUrl(item.hexcode)} alt={item.name} />
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
