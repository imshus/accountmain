import type { ReactNode } from "react";
import { Icon, type IconName } from "./icons";
import "./Notice.css";

type Tone = "error" | "warning" | "success" | "info";
const ICONS: Record<Tone, IconName> = { error: "alert", warning: "alert", success: "check", info: "info" };

/** A message box: an error from the server, a warning, a saved confirmation. Errors are announced (role="alert"). */
export function Notice({ tone = "info", children, action }: { tone?: Tone; children: ReactNode; action?: ReactNode }) {
  return (
    <div className={`ui-notice ui-notice--${tone}`} role={tone === "error" ? "alert" : "status"}>
      <Icon name={ICONS[tone]} size={16} stroke={2.2} />
      <div className="ui-notice__text">{children}</div>
      {action ? <div className="ui-notice__action">{action}</div> : null}
    </div>
  );
}
