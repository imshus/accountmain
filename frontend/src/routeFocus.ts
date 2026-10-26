import { useEffect, useRef } from "react";
import { hrefOf, type Route } from "./router";

/** Focus is lost: on the page itself, or on something that left the page or is hidden now (Home's tab bar). */
function focusLost(): boolean {
  const el = document.activeElement;
  return !el || el === document.body || !el.isConnected || Boolean(el.closest("[hidden], [inert]"));
}

/** The new screen's title (or its main area), skipping Home while it is hidden. */
function screenTarget(): HTMLElement | null {
  for (const el of document.querySelectorAll<HTMLElement>(".app-screens h1, .app-screens main")) {
    if (el.closest("[hidden]") || el.getClientRects().length === 0) continue;
    return el;
  }
  return null;
}

/**
 * After a navigation, a keyboard or screen-reader user lands on the new screen's title instead of at the top of the
 * document: the title is focused (and so read out) when focus would otherwise be lost. A screen or overlay that
 * takes focus itself (a search box, a sheet) keeps it. Lazy screens are waited for, for up to about a second.
 */
export function useRouteFocus(route: Route): void {
  const href = hrefOf(route);
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    let frame = 0;
    let tries = 0;
    const attempt = () => {
      if (!focusLost()) return;
      const target = screenTarget();
      if (target) {
        if (!target.hasAttribute("tabindex")) target.setAttribute("tabindex", "-1");
        target.focus({ preventScroll: true });
        return;
      }
      if (tries++ < 60) frame = requestAnimationFrame(attempt);
    };
    frame = requestAnimationFrame(attempt);
    return () => cancelAnimationFrame(frame);
  }, [href]);
}
