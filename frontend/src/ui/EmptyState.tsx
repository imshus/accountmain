import type { ReactNode } from "react";
import { Icon, type IconName } from "./icons";
import "./EmptyState.css";

type Props = {
  icon?: IconName;
  title: ReactNode;
  children?: ReactNode;
  /** A button or two. */
  action?: ReactNode;
};

/** Nothing to show yet: an icon in a tinted circle, a title, a line of help and an action. */
export function EmptyState({ icon = "info", title, children, action }: Props) {
  return (
    <div className="ui-empty">
      <span className="ui-empty__icon">
        <Icon name={icon} size={24} />
      </span>
      <p className="ui-empty__title">{title}</p>
      {children ? <div className="ui-empty__text">{children}</div> : null}
      {action ? <div className="ui-empty__action">{action}</div> : null}
    </div>
  );
}
