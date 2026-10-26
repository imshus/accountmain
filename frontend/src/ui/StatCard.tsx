import type { CSSProperties, ReactNode } from "react";
import "./StatCard.css";

type Props = {
  label: ReactNode;
  value: ReactNode;
  /** Colour of the short bar under the value. */
  tone?: "mint" | "brand" | "rose";
};

/** A Reports total ("Total Spent"): label, value (display face) and a short gradient bar under it. A figure given as
 * text stays on one line, its size fitted to its length (StatCard.css). */
export function StatCard({ label, value, tone = "brand" }: Props) {
  const fit = typeof value === "string" ? ({ "--chars": value.length } as CSSProperties) : undefined;
  return (
    <div className="ui-stat">
      <span className="ui-stat__label">{label}</span>
      <span className="ui-stat__value" style={fit}>
        {value}
      </span>
      <span className={`ui-stat__bar ui-stat__bar--${tone}`} aria-hidden="true" />
    </div>
  );
}
