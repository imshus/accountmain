import { createContext, useContext } from "react";

/** What the app header's buttons do. App.tsx provides it; AppShell and AppHeader read it. */
export type ShellActions = {
  /** Two letters for the avatar (the current company). */
  initials: string;
  openMenu: () => void;
  menuOpen: boolean;
  onBell: () => void;
  onSearch: () => void;
  /** Show the rose dot on the bell. */
  bellDot: boolean;
};

export const ShellContext = createContext<ShellActions>({
  initials: "AI",
  openMenu: () => undefined,
  menuOpen: false,
  onBell: () => undefined,
  onSearch: () => undefined,
  bellDot: false,
});

export const useShell = () => useContext(ShellContext);
