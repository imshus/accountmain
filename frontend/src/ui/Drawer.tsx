import { useRef, type ReactNode } from "react";
import { useOverlay } from "./useOverlay";
import "./Drawer.css";

type Props = {
  open: boolean;
  onClose: () => void;
  /** Accessible name of the panel, e.g. "Menu". */
  label: string;
  children: ReactNode;
};

/** The left side sheet (the menu). Stays mounted so it can slide; inert and hidden from screen readers while closed. */
export function Drawer({ open, onClose, label, children }: Props) {
  const panel = useRef<HTMLElement>(null);
  useOverlay(open, onClose, panel);
  return (
    <div className={`ui-drawer${open ? " is-open" : ""}`} inert={!open} aria-hidden={!open}>
      <div className="ui-drawer__backdrop" onClick={onClose} aria-hidden="true" />
      <aside ref={panel} className="ui-drawer__panel" role="dialog" aria-modal="true" aria-label={label} tabIndex={-1}>
        {children}
      </aside>
    </div>
  );
}
