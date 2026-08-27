// Minimal Home Assistant typings — only what this panel uses.

export interface HassEntityState {
  entity_id: string;
  state: string;
  attributes: Record<string, any>;
  last_changed?: string;
  last_updated?: string;
}

export interface HassEntityRegistryEntry {
  entity_id: string;
  device_id: string | null;
  platform: string;
  name?: string | null;
  original_name?: string | null;
}

export interface HassDeviceRegistryEntry {
  id: string;
  name?: string | null;
  name_by_user?: string | null;
  manufacturer?: string | null;
  model?: string | null;
}

export interface Hass {
  states: Record<string, HassEntityState>;
  themes?: any;
  language?: string;
  callService: (
    domain: string,
    service: string,
    data?: Record<string, any>
  ) => Promise<unknown>;
  callWS: <T = any>(msg: Record<string, any>) => Promise<T>;
}

export interface PanelConfig {
  narrow?: boolean;
  panel?: any;
  route?: any;
}

export type RGB = [number, number, number];

export interface IDotDevice {
  deviceId: string | null;
  name: string;
  lightEntityId: string;
}

export interface GalleryItem {
  id: string;
  name: string;
  image_data: string; // base64 of original file bytes
  mime: string; // e.g. "image/png", "image/gif"
  size: 16 | 32 | 64;
  is_gif: boolean;
  created: string;
}

export interface Album {
  id: string;
  name: string;
  item_ids: string[];
  interval: number; // seconds between images
}

export interface CatalogGroup {
  id: string;
  name: string;
}

export interface CatalogItem {
  hexcode: string;
  name: string;
}
