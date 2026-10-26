import type { ReactNode } from "react";
import { Avatar } from "./Avatar";
import { IconButton } from "./Button";
import { useShell } from "./shellContext";
import "./AppHeader.css";

/** The tab screens' header: company avatar (opens the menu) on the left, bell and search on the right. */
export function AppHeader({ children }: { children?: ReactNode }) {
  const { initials, openMenu, menuOpen, onBell, onSearch, bellDot } = useShell();
  return (
    <header className="ui-appheader">
      <Avatar initials={initials} onClick={openMenu} label="Open menu" expanded={menuOpen} />
      {children ? <div className="ui-appheader__middle">{children}</div> : null}
      <div className="ui-appheader__actions">
        <IconButton icon="bell" label="Notifications" onClick={onBell} dot={bellDot} />
        <IconButton icon="search" label="Search entries" onClick={onSearch} />
      </div>
    </header>
  );
}
