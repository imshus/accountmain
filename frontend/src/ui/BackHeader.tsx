import type { ReactNode } from "react";
import { back, type Route } from "../router";
import { Icon } from "./icons";
import "./BackHeader.css";

type Props = {
  title: ReactNode;
  /** Default: one screen back (or `fallback` when this screen was opened directly). */
  onBack?: () => void;
  fallback?: Route;
  /** Controls on the right, e.g. the Gold/Silver switch. */
  right?: ReactNode;
  /** lg: 26px title (Sales entry) · sm: 22px title that takes the free width (Stock). */
  size?: "lg" | "sm";
};

/** A sub-screen's header: round back button and the title. */
export function BackHeader({ title, onBack, fallback, right, size = "lg" }: Props) {
  const long = typeof title === "string" && title.length > 22;
  return (
    <header className={`ui-backheader ui-backheader--${size}`}>
      <button type="button" className="ui-backheader__back" onClick={onBack ?? (() => back(fallback))} aria-label="Back">
        <Icon name="back" />
      </button>
      <h1 className={`ui-backheader__title${long ? " is-long" : ""}`} title={long ? (title as string) : undefined} tabIndex={-1}>
        {title}
      </h1>
      {right ? <div className="ui-backheader__right">{right}</div> : null}
    </header>
  );
}
