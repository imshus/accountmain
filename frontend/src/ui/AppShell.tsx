import type { ReactNode } from "react";
import type { TabName } from "../router";
import { AppHeader } from "./AppHeader";
import { Glow } from "./Glow";
import { TabBar } from "./TabBar";
import { useKeyboard } from "./useKeyboard";
import "./AppShell.css";

type Props = {
  /** Which tab is lit in the tab bar. */
  tab: TabName;
  /** narrow: a phone-width column (Home, chat, Reports) · wide: up to 1100px on desktop (Transactions). */
  width?: "narrow" | "wide";
  /** The floating ask box (Home): docked above the tab bar; the page keeps room for it. */
  composer?: ReactNode;
  /** Something between the avatar and the bell (rarely needed). */
  headerMiddle?: ReactNode;
  children: ReactNode;
};

/**
 * A tab screen: ambient glow, the header (avatar, bell, search), the content column, the optional composer and the
 * floating tab bar. The window scrolls (not an inner box), so Back restores the scroll position.
 */
export function AppShell({ tab, width = "narrow", composer, headerMiddle, children }: Props) {
  useKeyboard(Boolean(composer));
  return (
    <div className={`ui-shell ui-shell--${width}${composer ? " has-composer" : ""}`}>
      <Glow />
      <div className="ui-shell__col">
        <AppHeader>{headerMiddle}</AppHeader>
        <main className="ui-shell__main">
          {children}
        </main>
      </div>
      {composer ? <div className="ui-shell__dock">{composer}</div> : null}
      <TabBar active={tab} />
    </div>
  );
}
