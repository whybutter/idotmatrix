import { useCallback, useRef, useState } from "react";

export type ActionStatus = "idle" | "busy" | "success" | "error";

/**
 * Wraps an async action (typically a hass.callService call) and exposes a
 * per-control status so buttons can show immediate loading feedback, then a
 * brief success/error flash. Used consistently by every action control so the
 * user always sees that their click registered — important on BLE where the
 * service promise can take several seconds (first power-on triggers connect).
 */
export function useBusyAction(onError?: (msg: string) => void) {
  const [status, setStatus] = useState<ActionStatus>("idle");
  const timer = useRef<number | null>(null);

  const clearTimer = () => {
    if (timer.current !== null) {
      window.clearTimeout(timer.current);
      timer.current = null;
    }
  };

  const run = useCallback(
    async (fn: () => Promise<unknown>): Promise<boolean> => {
      clearTimer();
      setStatus("busy");
      try {
        await fn();
        setStatus("success");
        timer.current = window.setTimeout(() => setStatus("idle"), 1400);
        return true;
      } catch (e) {
        setStatus("error");
        onError?.((e as Error).message || "Action failed");
        timer.current = window.setTimeout(() => setStatus("idle"), 1800);
        return false;
      }
    },
    [onError]
  );

  return { status, run, busy: status === "busy" };
}
