import { useCallback, useEffect, useMemo, useRef, type MouseEvent, type PointerEvent } from "react";

const HOLD_MS = 550;
const SLOP_PX = 10;

/**
 * Press and hold (touch or mouse) calls onHold. A right-click, or Android's own long-press context menu, does too.
 * `consumeHold()` tells the click handler that the press it ends was a hold, so the click is ignored.
 */
export function useLongPress(onHold: () => void) {
  const timer = useRef<number | undefined>(undefined);
  const start = useRef<{ x: number; y: number } | null>(null);
  const held = useRef(false);
  const latest = useRef(onHold);
  latest.current = onHold;

  const stop = useCallback(() => {
    window.clearTimeout(timer.current);
    start.current = null;
  }, []);
  useEffect(() => stop, [stop]);

  const fire = useCallback(() => {
    stop();
    if (held.current) return;
    held.current = true;
    navigator.vibrate?.(12);
    latest.current();
  }, [stop]);

  const handlers = useMemo(
    () => ({
      onPointerDown: (e: PointerEvent) => {
        // Every press starts fresh (a right-click too, so its context menu event counts once).
        held.current = false;
        if (e.button !== 0) return;
        start.current = { x: e.clientX, y: e.clientY };
        window.clearTimeout(timer.current);
        timer.current = window.setTimeout(fire, HOLD_MS);
      },
      onPointerMove: (e: PointerEvent) => {
        // A scroll or drag is not a hold.
        if (start.current && Math.hypot(e.clientX - start.current.x, e.clientY - start.current.y) > SLOP_PX) stop();
      },
      onPointerUp: stop,
      onPointerLeave: stop,
      onPointerCancel: stop,
      onContextMenu: (e: MouseEvent) => {
        e.preventDefault();
        fire();
      },
    }),
    [fire, stop],
  );

  const consumeHold = useCallback(() => {
    const was = held.current;
    held.current = false;
    return was;
  }, []);

  return { handlers, consumeHold };
}
