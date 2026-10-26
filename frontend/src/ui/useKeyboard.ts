import { useEffect } from "react";

// The page counts as "keyboard open" when it is this much shorter than its tallest height at the same width.
const KEYBOARD_MIN = 150;

/**
 * The phone keyboard resizes the page (the app's window shrinks). Keep what was at the bottom of the page in view, so
 * the chat moves up with the ask box instead of sliding under it, and mark <html data-keyboard="open"> so the tab bar
 * can step aside while the person types. Tallest heights are kept per width, so turning the phone is not a keyboard.
 */
export function useKeyboard(enabled: boolean) {
  useEffect(() => {
    if (!enabled) return;
    const root = document.documentElement;
    const tallest = new Map<number, number>();
    let last = window.innerHeight;

    const onResize = () => {
      const height = window.innerHeight;
      const width = window.innerWidth;
      tallest.set(width, Math.max(tallest.get(width) ?? 0, height));
      const shrink = last - height;
      // At the end of the page before the change (when the page grows, the browser has already pulled it to the end).
      const pinned = window.scrollY + Math.max(last, height) >= document.documentElement.scrollHeight - 24;
      last = height;
      if (shrink > 0 && !pinned) window.scrollBy(0, shrink); // the line at the bottom stays at the bottom
      const open = (tallest.get(width) ?? height) - height > KEYBOARD_MIN;
      if (open) root.dataset.keyboard = "open";
      else delete root.dataset.keyboard;
      // The page's bottom room changes with the tab bar: stay on the latest message (reading scrollHeight lays it out).
      if (pinned) window.scrollTo(0, document.documentElement.scrollHeight);
    };

    tallest.set(window.innerWidth, last);
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      delete root.dataset.keyboard;
    };
  }, [enabled]);
}
