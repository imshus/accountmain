import type { CSSProperties, ReactNode } from "react";
import "./Spinner.css";

/** The design's ring spinner (border track, violet arc). With children it becomes a status line ("Working…"). */
export function Spinner({ size = 16, children }: { size?: number; children?: ReactNode }) {
  const ring = <span className="ui-spinner" style={{ width: size, height: size }} aria-hidden="true" />;
  if (!children) return ring;
  return (
    <span className="ui-spinner-line" role="status">
      {ring}
      {children}
    </span>
  );
}

/** A grey placeholder block while something loads. */
export function Skeleton({ width = "100%", height = 16, radius = 8, style }: { width?: number | string; height?: number | string; radius?: number; style?: CSSProperties }) {
  return <span className="ui-skeleton" style={{ width, height, borderRadius: radius, ...style }} aria-hidden="true" />;
}

/** Loading placeholder for a whole screen (used while a lazy screen's code arrives). */
export function ScreenLoading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="ui-screen-loading">
      <Spinner size={22}>{label}</Spinner>
    </div>
  );
}
