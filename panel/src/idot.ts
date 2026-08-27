import type {
  Album,
  CatalogGroup,
  CatalogItem,
  CatalogSource,
  GalleryItem,
  Hass,
  HassEntityRegistryEntry,
  IDotDevice,
  RGB,
} from "./types";

export const CLOCK_STYLES = [
  "RGB swipe outline",
  "Christmas tree",
  "Checkers",
  "Color",
  "Hourglass",
  "Alarm clock",
  "Outlines",
  "RGB corners",
];

export const EFFECT_STYLES = [
  "Horizontal rainbow",
  "Random colored pixels",
  "Random white pixels",
  "Vertical rainbow",
  "Diagonal-right rainbow",
  "Diagonal-left rainbow",
  "Random colored pixels (alt)",
];

// Mic rhythm styles: value -> label (style is 1-4).
export const MIC_STYLES: { value: number; label: string }[] = [
  { value: 1, label: "Dancing guy" },
  { value: 2, label: "Heart" },
  { value: 3, label: "Gummy bear" },
  { value: 4, label: "Eyes and mouth" },
];

export const TEXT_MODES = [
  "Static",
  "Scroll left",
  "Scroll right",
  "Scroll up",
  "Scroll down",
  "Fade",
  "Blink",
  "Marquee",
  "Laser",
];

/**
 * Discover iDotMatrix devices via the entity registry.
 * Filters entities to platform === "idotmatrix" and picks the light entity
 * per device. Returns one IDotDevice per distinct device.
 */
export async function discoverDevices(hass: Hass): Promise<IDotDevice[]> {
  let entries: HassEntityRegistryEntry[] = [];
  try {
    entries = await hass.callWS<HassEntityRegistryEntry[]>({
      type: "config/entity_registry/list",
    });
  } catch {
    entries = [];
  }

  const idot = entries.filter((e) => e.platform === "idotmatrix");
  const lights = idot.filter((e) => e.entity_id.startsWith("light."));

  // Fallback: if the registry is unavailable or empty, scan hass.states
  // for any light entity mentioning "idotmatrix"/"dotmatrix".
  let candidates: { entity_id: string; device_id: string | null }[] = lights.map(
    (e) => ({ entity_id: e.entity_id, device_id: e.device_id })
  );

  if (candidates.length === 0) {
    candidates = Object.keys(hass.states)
      .filter(
        (id) =>
          id.startsWith("light.") &&
          /dot.?matrix/i.test(id)
      )
      .map((id) => ({ entity_id: id, device_id: null }));
  }

  return candidates.map((c) => {
    const st = hass.states[c.entity_id];
    const name =
      (st?.attributes?.friendly_name as string) ||
      c.entity_id.replace("light.", "").replace(/_/g, " ");
    return {
      deviceId: c.device_id,
      name,
      lightEntityId: c.entity_id,
    };
  });
}

export function rgbToHex([r, g, b]: RGB): string {
  const h = (n: number) => n.toString(16).padStart(2, "0");
  return `#${h(r)}${h(g)}${h(b)}`;
}

export function hexToRgb(hex: string): RGB {
  const m = hex.replace("#", "");
  return [
    parseInt(m.slice(0, 2), 16) || 0,
    parseInt(m.slice(2, 4), 16) || 0,
    parseInt(m.slice(4, 6), 16) || 0,
  ];
}

/** Encode an ArrayBuffer to base64 without blowing the call stack. */
export function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode.apply(
      null,
      bytes.subarray(i, i + chunk) as unknown as number[]
    );
  }
  return btoa(binary);
}

/* ---------------- Gallery WS API ---------------- */

export async function galleryList(hass: Hass): Promise<GalleryItem[]> {
  const res = await hass.callWS<{ items: GalleryItem[] }>({
    type: "idotmatrix/gallery/list",
  });
  return res?.items ?? [];
}

export async function galleryAdd(
  hass: Hass,
  item: {
    name: string;
    image_data: string;
    size: 16 | 32 | 64;
    is_gif: boolean;
    mime: string;
  }
): Promise<GalleryItem> {
  const res = await hass.callWS<{ item: GalleryItem }>({
    type: "idotmatrix/gallery/add",
    ...item,
  });
  return res.item;
}

export async function galleryDelete(hass: Hass, id: string): Promise<void> {
  await hass.callWS({ type: "idotmatrix/gallery/delete", id });
}

/** Send a stored gallery item to the panel via the existing upload service. */
export async function gallerySend(
  hass: Hass,
  entityId: string,
  item: GalleryItem
): Promise<void> {
  await hass.callService("idotmatrix", item.is_gif ? "upload_gif" : "upload_image", {
    entity_id: entityId,
    image_data: item.image_data,
    size: item.size,
  });
}

export function dataUrl(item: GalleryItem): string {
  return `data:${item.mime};base64,${item.image_data}`;
}

/* ---------------- Albums WS API ---------------- */

export async function albumsList(
  hass: Hass,
  entityId: string
): Promise<{ albums: Album[]; playingAlbumId: string | null }> {
  const res = await hass.callWS<{ albums: Album[]; playing_album_id: string | null }>({
    type: "idotmatrix/albums/list",
    entity_id: entityId,
  });
  return { albums: res?.albums ?? [], playingAlbumId: res?.playing_album_id ?? null };
}

export async function albumsSave(
  hass: Hass,
  data: { album_id?: string; name: string; item_ids: string[]; interval: number }
): Promise<Album> {
  const res = await hass.callWS<{ album: Album }>({
    type: "idotmatrix/albums/save",
    ...data,
  });
  return res.album;
}

export async function albumsDelete(hass: Hass, albumId: string): Promise<void> {
  await hass.callWS({ type: "idotmatrix/albums/delete", album_id: albumId });
}

export async function albumsPlay(
  hass: Hass,
  albumId: string,
  entityId: string
): Promise<void> {
  await hass.callWS({ type: "idotmatrix/albums/play", album_id: albumId, entity_id: entityId });
}

export async function albumsStop(hass: Hass, entityId: string): Promise<void> {
  await hass.callWS({ type: "idotmatrix/albums/stop", entity_id: entityId });
}

/* ---------------- Online catalog (Explorar) ---------------- */

export async function catalogSources(hass: Hass): Promise<CatalogSource[]> {
  const res = await hass.callWS<{ sources: CatalogSource[] }>({
    type: "idotmatrix/catalog/sources",
  });
  return res?.sources ?? [];
}

export async function catalogGroups(
  hass: Hass,
  source: string
): Promise<CatalogGroup[]> {
  const res = await hass.callWS<{ groups: CatalogGroup[] }>({
    type: "idotmatrix/catalog/groups",
    source,
  });
  return res?.groups ?? [];
}

export async function catalogList(
  hass: Hass,
  source: string,
  group: string,
  limit = 60,
  offset = 0
): Promise<{ items: CatalogItem[]; total: number }> {
  const res = await hass.callWS<{ items: CatalogItem[]; total: number }>({
    type: "idotmatrix/catalog/list",
    source,
    group,
    limit,
    offset,
  });
  return { items: res?.items ?? [], total: res?.total ?? 0 };
}

/** Same-origin HA-served image URL (PNG or GIF) for a catalog item. */
export function catalogImgUrl(source: string, ref: string): string {
  return `/api/idotmatrix/catalog/img/${source}/${encodeURIComponent(ref)}`;
}

/** Fetch a catalog image and return raw base64 (no data-URL prefix). */
export async function catalogImageBase64(
  source: string,
  ref: string
): Promise<string> {
  const res = await fetch(catalogImgUrl(source, ref));
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const buf = await res.arrayBuffer();
  return arrayBufferToBase64(buf);
}

export function isLightOn(hass: Hass, entityId: string): boolean {
  return hass.states[entityId]?.state === "on";
}

/**
 * A device is "available" once its light entity exists and its state is not
 * "unavailable"/"unknown" — i.e. HA reports the BLE panel as reachable.
 */
export function isAvailable(hass: Hass, entityId: string): boolean {
  const s = hass.states[entityId]?.state;
  return s === "on" || s === "off";
}

export function getBrightnessPct(hass: Hass, entityId: string): number {
  const b = hass.states[entityId]?.attributes?.brightness;
  if (typeof b !== "number") return 100;
  return Math.round((b / 255) * 100);
}

export function getRgbColor(hass: Hass, entityId: string): RGB {
  const c = hass.states[entityId]?.attributes?.rgb_color;
  if (Array.isArray(c) && c.length === 3) return c as RGB;
  return [124, 77, 255];
}
