import { useLayoutEffect, useRef, useSyncExternalStore } from "react";
import { App as NativeApp } from "@capacitor/app";
import { isApp } from "./api";

/**
 * A tiny router over the URL hash (#/entry/sale), so every screen has an address, the browser's back button
 * works, and the Android back button walks back through screens (the WebView's own history is used).
 * The hash form also survives a reload in the APK and behind nginx without server rewrites.
 */

export type EntryKind = "sale" | "purchase";
export type MetalKind = "receipt" | "issue";
export type StockMetal = "gold" | "silver";
export type RegisterKind = "sales" | "purchases";

export type Route =
  | { name: "home"; chat?: string } // chat: open this saved conversation
  | { name: "history" }
  | { name: "entry"; kind: EntryKind }
  | { name: "register"; kind: RegisterKind } // the Sales / Purchase bills with their totals
  | { name: "stock"; metal?: StockMetal }
  | { name: "transactions"; search?: boolean } // search: open with the search box focused
  | { name: "reports" }
  | { name: "masters" }
  | { name: "dashboard"; tab?: string } // the full company books (CompanyView); tab = one of its tabs
  | { name: "metal"; kind: MetalKind }
  | { name: "new-company" };

export type RouteName = Route["name"];
/** The three screens of the floating tab bar. */
export type TabName = "home" | "transactions" | "reports";

const ENTRY_KINDS: EntryKind[] = ["sale", "purchase"];
const REGISTER_KINDS: RegisterKind[] = ["sales", "purchases"];
const METAL_KINDS: MetalKind[] = ["receipt", "issue"];
const METALS: StockMetal[] = ["gold", "silver"];
const pick = <T extends string>(list: T[], value: string | null | undefined): T | undefined =>
  list.find((item) => item === value);

/** "#/entry/sale?x=1" -> the route; anything unknown is Home. */
export function parseHash(hash: string): Route {
  const [path, search = ""] = hash.replace(/^#\/?/, "").split("?");
  const parts = path.split("/").filter(Boolean).map(decodeURIComponent);
  const query = new URLSearchParams(search);
  switch (parts[0]) {
    case "chat":
      return parts[1] ? { name: "home", chat: parts[1] } : { name: "home" };
    case "history":
      return { name: "history" };
    case "entry":
      return { name: "entry", kind: pick(ENTRY_KINDS, parts[1]) ?? "sale" };
    case "register":
      return { name: "register", kind: pick(REGISTER_KINDS, parts[1]) ?? "sales" };
    case "stock": {
      const metal = pick(METALS, query.get("metal"));
      return metal ? { name: "stock", metal } : { name: "stock" };
    }
    case "transactions":
      return query.get("search") ? { name: "transactions", search: true } : { name: "transactions" };
    case "reports":
      return { name: "reports" };
    case "masters":
      return { name: "masters" };
    case "dashboard":
      return query.get("tab") ? { name: "dashboard", tab: query.get("tab")! } : { name: "dashboard" };
    case "metal":
      return { name: "metal", kind: pick(METAL_KINDS, parts[1]) ?? "receipt" };
    case "new-company":
      return { name: "new-company" };
    default:
      return { name: "home" };
  }
}

/** The address of a route, for <a href> and the history entry. */
export function hrefOf(route: Route): string {
  const q = (params: Record<string, string | undefined>) => {
    const query = new URLSearchParams(Object.entries(params).filter((e): e is [string, string] => Boolean(e[1]))).toString();
    return query ? `?${query}` : "";
  };
  switch (route.name) {
    case "home":
      return route.chat ? `#/chat/${encodeURIComponent(route.chat)}` : "#/";
    case "entry":
      return `#/entry/${route.kind}`;
    case "register":
      return `#/register/${route.kind}`;
    case "stock":
      return `#/stock${q({ metal: route.metal })}`;
    case "transactions":
      return `#/transactions${q({ search: route.search ? "1" : undefined })}`;
    case "dashboard":
      return `#/dashboard${q({ tab: route.tab })}`;
    case "metal":
      return `#/metal/${route.kind}`;
    default:
      return `#/${route.name}`;
  }
}

// ── the store ──────────────────────────────────────────────────────────────────────────────────

type Entry = { route: Route; idx: number; key: string; pop: boolean };
type HistoryState = { idx: number; key: string };

const newKey = () => Math.random().toString(36).slice(2, 10);
/** Routes of the entries of this session, by history index (for "is the previous screen Home?"). */
const stack: Route[] = [];
const scrollTops = new Map<string, number>();
const listeners = new Set<() => void>();

function start(): Entry {
  const state = history.state as HistoryState | null;
  const idx = typeof state?.idx === "number" ? state.idx : 0;
  const key = typeof state?.key === "string" ? state.key : newKey();
  if (state?.idx !== idx || state?.key !== key) history.replaceState({ ...(history.state ?? {}), idx, key }, "");
  const route = parseHash(location.hash);
  stack[idx] = route;
  return { route, idx, key, pop: false };
}

let current: Entry = start();
if ("scrollRestoration" in history) history.scrollRestoration = "manual";

function emit(next: Entry) {
  current = next;
  stack[next.idx] = next.route;
  stack.length = next.idx + 1;
  listeners.forEach((listener) => listener());
}

window.addEventListener("popstate", () => {
  const state = history.state as HistoryState | null;
  const idx = typeof state?.idx === "number" ? state.idx : 0;
  const key = typeof state?.key === "string" ? state.key : newKey();
  if (state?.key !== key) history.replaceState({ ...(history.state ?? {}), idx, key }, "");
  scrollTops.set(current.key, window.scrollY);
  current = { route: parseHash(location.hash), idx, key, pop: true };
  stack[idx] = current.route;
  listeners.forEach((listener) => listener());
});

/** Go to a screen. `replace` swaps the current history entry instead of adding one. */
export function navigate(route: Route, options: { replace?: boolean } = {}): void {
  const href = hrefOf(route);
  scrollTops.set(current.key, window.scrollY);
  const key = newKey();
  if (options.replace) {
    history.replaceState({ idx: current.idx, key }, "", href);
    emit({ route, idx: current.idx, key, pop: false });
  } else {
    const idx = current.idx + 1;
    history.pushState({ idx, key }, "", href);
    emit({ route, idx, key, pop: false });
  }
}

/** Back one screen; when this screen was opened directly (nothing to go back to), go to `fallback` instead. */
export function back(fallback: Route = { name: "home" }): void {
  if (current.idx > 0) history.back();
  else navigate(fallback, { replace: true });
}

/** Home's start page: no conversation open. */
const isStart = (route: Route | undefined) => route?.name === "home" && !route.chat;

/**
 * The tab bar. Home is always the start page with a new, empty conversation (the one on screen stays in History): it
 * goes back to this session's latest start page, so Back from there does not return to the chat or the tab. Home <->
 * a tab never piles up history, so Back from Transactions/Reports lands on Home.
 */
export function goTab(tab: TabName): void {
  const here = current.route;
  if (tab === "home" ? isStart(here) : here.name === tab) {
    window.scrollTo({ top: 0, behavior: "smooth" });
    return;
  }
  if (tab === "home") {
    let start = current.idx - 1;
    while (start >= 0 && !isStart(stack[start])) start--;
    if (start >= 0) history.go(start - current.idx);
    else navigate({ name: "home" }, { replace: true });
    return;
  }
  navigate({ name: tab }, { replace: here.name === "transactions" || here.name === "reports" });
}

export function getRoute(): Route {
  return current.route;
}

/** The current screen was reached with Back (browser, Android or back()), not opened afresh. */
export function cameBack(): boolean {
  return current.pop;
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

const getEntry = () => current;

/** The current screen; re-renders on every navigation. */
export function useRoute(): Route {
  return useSyncExternalStore(subscribe, getEntry).route;
}

/**
 * Call once, in the component that renders the screens: after a navigation the window starts at the top, and after
 * Back it returns to where it was (tried for a moment, while a lazy screen loads its content).
 */
export function useScrollRestoration(): void {
  const entry = useSyncExternalStore(subscribe, getEntry);
  useLayoutEffect(() => {
    const target = entry.pop ? (scrollTops.get(entry.key) ?? 0) : 0;
    let tries = 0;
    let frame = 0;
    const apply = () => {
      window.scrollTo(0, target);
      if (Math.abs(window.scrollY - target) > 2 && tries++ < 30) frame = requestAnimationFrame(apply);
    };
    apply();
    return () => cancelAnimationFrame(frame);
  }, [entry]);
}

// ── Android back button ─────────────────────────────────────────────────────────────────────────

/** Open overlays (drawer, sheets) register here so the hardware back button closes them first. */
const backHandlers: (() => void)[] = [];

/** While `active`, the Android back button calls `onBack` instead of leaving the screen. Use from overlays. */
export function useBackHandler(active: boolean, onBack: () => void): void {
  const latest = useRef(onBack);
  latest.current = onBack;
  useLayoutEffect(() => {
    if (!active) return;
    const handler = () => latest.current();
    backHandlers.push(handler);
    return () => {
      const at = backHandlers.lastIndexOf(handler);
      if (at >= 0) backHandlers.splice(at, 1);
    };
  }, [active]);
}

if (isApp) {
  void NativeApp.addListener("backButton", () => {
    const overlay = backHandlers.at(-1);
    if (overlay) overlay();
    else if (current.idx > 0) history.back();
    else if (current.route.name !== "home") navigate({ name: "home" }, { replace: true });
    else void NativeApp.exitApp();
  });
}
