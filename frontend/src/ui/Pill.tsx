import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Icon, type IconName } from "./icons";
import "./Pill.css";

type PillProps = ButtonHTMLAttributes<HTMLButtonElement> & { icon?: IconName };

/** A Home quick-action pill (big, raised, rounded). Put them in <PillRow>. */
export function Pill({ icon, className, children, type = "button", ...rest }: PillProps) {
  return (
    <button type={type} className={`ui-pill${className ? ` ${className}` : ""}`} {...rest}>
      {icon ? <Icon name={icon} size={17} /> : null}
      {children}
    </button>
  );
}

/** Pills in a row (wraps when they do not fit). */
export function PillRow({ children, label }: { children: ReactNode; label?: string }) {
  return (
    <div className="ui-pills" role={label ? "group" : undefined} aria-label={label}>
      {children}
    </div>
  );
}

type ChipProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, "onClick"> & { pressed: boolean; onClick: () => void };

/** A filter chip (All / Sales / Purchases / Gold). Pressed = filled with ink. Put them in <ChipGroup>. */
export function Chip({ pressed, className, children, type = "button", ...rest }: ChipProps) {
  return (
    <button type={type} className={`ui-chip${className ? ` ${className}` : ""}`} aria-pressed={pressed} {...rest}>
      {children}
    </button>
  );
}

export function ChipGroup({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="ui-chips" role="group" aria-label={label}>
      {children}
    </div>
  );
}

/** A small tag: SOON (amber), CANCELLED (rose), 22K (gold), Verified (mint), or neutral. */
export function Badge({ tone = "neutral", children }: { tone?: "amber" | "rose" | "gold" | "mint" | "brand" | "neutral"; children: ReactNode }) {
  return <span className={`ui-badge ui-badge--${tone}`}>{children}</span>;
}
