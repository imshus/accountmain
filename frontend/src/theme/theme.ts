import { useSyncExternalStore } from "react";

/** Dark is the default; the menu's Dark mode switch picks light, kept per device. */
export type ThemeMode = "dark" | "light";

const KEY = "accountsai.theme";
const listeners = new Set<() => void>();

function read(): ThemeMode {
  try {
    return localStorage.getItem(KEY) === "light" ? "light" : "dark";
  } catch {
    return "dark";
  }
}

let mode: ThemeMode = read();

/** Put the theme on <html> (index.html already does this before the first paint, so there is no flash). */
export function applyTheme(next: ThemeMode = mode): void {
  const root = document.documentElement;
  root.classList.toggle("theme-light", next === "light");
  // The browser chrome / Android status bar follows the page background.
  const bg = getComputedStyle(root).getPropertyValue("--bg").trim();
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", bg);
}

export function setTheme(next: ThemeMode): void {
  mode = next;
  try {
    localStorage.setItem(KEY, next);
  } catch {
    // Not saved: the choice lasts until the app is closed.
  }
  applyTheme(next);
  listeners.forEach((listener) => listener());
}

export function getTheme(): ThemeMode {
  return mode;
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useTheme(): { mode: ThemeMode; setMode: (mode: ThemeMode) => void; toggle: () => void } {
  const current = useSyncExternalStore(subscribe, getTheme);
  return { mode: current, setMode: setTheme, toggle: () => setTheme(current === "dark" ? "light" : "dark") };
}
