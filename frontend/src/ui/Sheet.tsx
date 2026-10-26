import { useId, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Icon } from "./icons";
import { useOverlay } from "./useOverlay";
import "./Sheet.css";

type Props = {
  open: boolean;
  onClose: () => void;
  /** Heading of the sheet (also its accessible name). */
  title: string;
  /** A line under the title. */
  description?: ReactNode;
  children?: ReactNode;
  /** Buttons along the bottom (e.g. <Button>Cancel</Button><Button variant="danger">Delete</Button>). */
  actions?: ReactNode;
};

/**
 * A modal sheet: slides up from the bottom on phones, a centred dialog on wide windows. Rendered only while open,
 * into <body>, above the drawer.
 */
export function Sheet({ open, onClose, title, description, children, actions }: Props) {
  const panel = useRef<HTMLDivElement>(null);
  const titleId = useId();
  useOverlay(open, onClose, panel);
  if (!open) return null;
  return createPortal(
    <div className="ui-sheet">
      <div className="ui-sheet__backdrop" onClick={onClose} aria-hidden="true" />
      <div ref={panel} className="ui-sheet__panel" role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1}>
        <span className="ui-sheet__grip" aria-hidden="true" />
        <div className="ui-sheet__head">
          <h2 id={titleId} className="ui-sheet__title">
            {title}
          </h2>
          <button type="button" className="ui-sheet__close" onClick={onClose} aria-label="Close">
            <Icon name="close" size={17} stroke={2.2} />
          </button>
        </div>
        {description ? <p className="ui-sheet__desc">{description}</p> : null}
        {children ? <div className="ui-sheet__body">{children}</div> : null}
        {actions ? <div className="ui-sheet__actions">{actions}</div> : null}
      </div>
    </div>,
    document.body,
  );
}
