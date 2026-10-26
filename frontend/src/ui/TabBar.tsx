import type { MouseEvent } from "react";
import { goTab, hrefOf, type TabName } from "../router";
import { Icon, type IconName } from "./icons";
import "./TabBar.css";

const TABS: { tab: TabName; label: string; icon: IconName }[] = [
  { tab: "home", label: "Home", icon: "home" },
  { tab: "transactions", label: "Transactions", icon: "swap" },
  { tab: "reports", label: "Reports", icon: "chart" },
];

/** The floating pill tab bar: Home / Transactions / Reports. */
export function TabBar({ active }: { active: TabName }) {
  const go = (event: MouseEvent, tab: TabName) => {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return;
    event.preventDefault();
    goTab(tab);
  };
  return (
    <nav className="ui-tabbar" aria-label="Main">
      {TABS.map(({ tab, label, icon }) => (
        <a
          key={tab}
          href={hrefOf({ name: tab })}
          className={`ui-tab${tab === active ? " is-active" : ""}`}
          aria-current={tab === active ? "page" : undefined}
          onClick={(event) => go(event, tab)}
        >
          <span className="ui-tab__bar" />
          <span className="ui-tab__icon">
            <Icon name={icon} size={20} />
          </span>
          {label}
        </a>
      ))}
    </nav>
  );
}
