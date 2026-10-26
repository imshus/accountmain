import { useEffect, useLayoutEffect, useState, type RefObject } from "react";

const NEAR = 120;

function nearBottom(): boolean {
  const doc = document.documentElement;
  return doc.scrollHeight - window.scrollY - window.innerHeight < NEAR;
}

function toBottom() {
  window.scrollTo(0, document.documentElement.scrollHeight);
}

/**
 * The window scrolls (not an inner box), so the chat follows a growing answer by scrolling the window, unless the
 * person scrolled up to read. Nothing happens while the chat is hidden (Home behind another screen, a file's other
 * view), so another screen's scroll position is never touched.
 */
export function useFollow(enabled: boolean, anchor: RefObject<HTMLElement | null>, content: unknown, conversation: string | null) {
  const [stuck, setStuck] = useState(true);
  const visible = () => enabled && Boolean(anchor.current?.offsetParent);

  useEffect(() => {
    if (!enabled) return;
    const onScroll = () => setStuck(nearBottom());
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [enabled]);

  useLayoutEffect(() => {
    if (stuck && visible()) toBottom();
  }, [content, stuck]);

  // Another conversation opened: start at its latest answer (after the router has put a new screen at the top).
  useEffect(() => {
    setStuck(true);
    if (!conversation) return;
    const frame = requestAnimationFrame(() => {
      if (visible()) toBottom();
    });
    return () => cancelAnimationFrame(frame);
  }, [conversation]);

  return {
    stuck,
    jump: () => {
      setStuck(true);
      window.scrollTo({ top: document.documentElement.scrollHeight, behavior: "smooth" });
    },
  };
}
