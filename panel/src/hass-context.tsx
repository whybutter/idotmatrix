import { createContext, useContext } from "react";
import type { Hass } from "./types";

export const HassContext = createContext<Hass | null>(null);

export function useHass(): Hass {
  const hass = useContext(HassContext);
  if (!hass) {
    throw new Error("useHass must be used within a HassContext provider");
  }
  return hass;
}
