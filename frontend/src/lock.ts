import { useSyncExternalStore } from "react";

/**
 * The menu's Logout. The app has no accounts (the backend has no login), so logging out locks the app on this device
 * until "Log in" is tapped; nothing is deleted. Kept on the device so the app stays locked after a restart.
 */
const KEY = "accountsai.loggedOut";
const listeners = new Set<() => void>();

function read(): boolean {
  try {
    return localStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}

let loggedOut = read();

function set(next: boolean) {
  loggedOut = next;
  try {
    if (next) localStorage.setItem(KEY, "1");
    else localStorage.removeItem(KEY);
  } catch {
    // Storage blocked: locked until the app restarts.
  }
  listeners.forEach((listener) => listener());
}

export const logOut = () => set(true);
export const logIn = () => set(false);

export function useLoggedOut(): boolean {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => loggedOut,
  );
}
