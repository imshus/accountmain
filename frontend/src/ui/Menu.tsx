import type { ReactNode } from "react";
import { Icon, type IconName } from "./icons";
import "./Menu.css";

/** A floating menu card (the composer's attach menu). Children are <MenuItem>s. */
export function Menu({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="ui-menu" role="menu" aria-label={label}>
      {children}
    </div>
  );
}

type ItemProps = {
  icon: IconName;
  title: string;
  /** The small line under the title, e.g. "Excel / CSV file". */
  sub?: string;
  /** A tag after the title, e.g. "SOON". */
  badge?: string;
  onSelect: () => void;
  disabled?: boolean;
  /** Highlighted (the suggested choice). */
  highlight?: boolean;
};

export function MenuItem({ icon, title, sub, badge, onSelect, disabled, highlight }: ItemProps) {
  return (
    <button type="button" role="menuitem" className={`ui-menu__item${highlight ? " is-hl" : ""}`} onClick={onSelect} aria-disabled={disabled || undefined}>
      <span className="ui-menu__icon">
        <Icon name={icon} />
      </span>
      <span className="ui-menu__text">
        <strong>
          {title}
          {badge ? <span className="ui-menu__badge">{badge}</span> : null}
        </strong>
        {sub ? <small>{sub}</small> : null}
      </span>
    </button>
  );
}
