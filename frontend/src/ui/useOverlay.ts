import { useEffect, useRef, type RefObject } from "react";
import { useBackHandler } from "../router";

/** Open overlays, innermost last: only the top one handles keys (a sheet opened from the drawer). */
const open: object[] = [];

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Shared behaviour of the drawer and sheets while open: focus moves in and is kept inside (Tab wraps), Escape and the
 * Android back button close, and focus returns to whatever opened it. The page behind should be made inert by the caller.
 */
export function useOverlay(isOpen: boolean, onClose: () => void, panel: RefObject<HTMLElement | null>): void {
  const opener = useRef<HTMLElement | null>(null);
  // Callers pass inline arrows: keep the latest without re-running the effect (which would move focus again).
  const close = useRef(onClose);
  close.current = onClose;
  useBackHandler(isOpen, onClose);

  useEffect(() => {
    if (!isOpen) return;
    const token = {};
    open.push(token);
    opener.current = document.activeElement as HTMLElement | null;
    const node = panel.current;
    // After the opening frame, so the slide-in has started and the element is focusable.
    const frame = requestAnimationFrame(() => {
      const target = node?.querySelector<HTMLElement>("[data-autofocus]") ?? node?.querySelector<HTMLElement>(FOCUSABLE) ?? node;
      target?.focus({ preventScroll: true });
    });
    const onKey = (event: KeyboardEvent) => {
      if (open[open.length - 1] !== token) return;
      if (event.key === "Escape") {
        event.stopPropagation();
        close.current();
        return;
      }
      if (event.key !== "Tab" || !node) return;
      const items = [...node.querySelectorAll<HTMLElement>(FOCUSABLE)].filter((el) => el.offsetParent !== null);
      if (!items.length) {
        event.preventDefault();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && (document.activeElement === first || !node.contains(document.activeElement))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey, true);
    return () => {
      cancelAnimationFrame(frame);
      open.splice(open.indexOf(token), 1);
      document.removeEventListener("keydown", onKey, true);
      const back = opener.current;
      if (back && document.contains(back)) back.focus({ preventScroll: true });
    };
  }, [isOpen, panel]);
}
