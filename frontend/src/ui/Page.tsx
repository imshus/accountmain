import type { ReactNode } from "react";
import type { Route } from "../router";
import { BackHeader } from "./BackHeader";
import { Glow } from "./Glow";
import "./Page.css";

type Props = {
  title: ReactNode;
  /**
   * narrow: phone-width column (entry forms, stock, history, menu screens) · wide: up to 1100px (lists, legacy books
   * and file screens) · full: up to 1280px (big data tables)
   */
  width?: "narrow" | "wide" | "full";
  titleSize?: "lg" | "sm";
  /** Right side of the header. */
  right?: ReactNode;
  onBack?: () => void;
  /** Where Back goes when the screen was opened directly. Default Home. */
  fallback?: Route;
  /** Content gets the side gutter (default). Off for screens that pad themselves. */
  padded?: boolean;
  children: ReactNode;
};

/** A screen reached from somewhere else (not a tab): glow, back header and a centred column; no tab bar. */
export function Page({ title, width = "narrow", titleSize = "lg", right, onBack, fallback, padded = true, children }: Props) {
  return (
    <div className={`ui-page ui-page--${width}`}>
      <Glow />
      <div className="ui-page__col">
        <BackHeader title={title} size={titleSize} right={right} onBack={onBack} fallback={fallback} />
        <main className={`ui-page__main${padded ? " is-padded" : ""}`}>
          {children}
        </main>
      </div>
    </div>
  );
}
