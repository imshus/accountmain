import { formatCount, formatDate, formatValue } from "../format";
import type { SheetProfile } from "../types";

export default function SummaryCards({ profile }: { profile: SheetProfile }) {
  const { totals, period } = profile.summary;
  return (
    <div className="cards">
      <div className="card stat">
        <span className="stat-label">Rows</span>
        <span className="stat-value">{formatCount(profile.row_count)}</span>
        <span className="muted small">{profile.column_count} columns</span>
      </div>
      {period ? (
        <div className="card stat">
          <span className="stat-label">Period</span>
          <span className="stat-value period">
            {formatDate(period.from)} – {formatDate(period.to)}
          </span>
        </div>
      ) : null}
      {totals.map((card) => {
        // A -0.0 difference shows as 0.00 (not red) next to "Balanced".
        const text = formatValue(card.value, card.format);
        return (
          <div className="card stat" key={card.label}>
            <span className="stat-label">{card.label}</span>
            <span className={`stat-value${text.startsWith("-") ? " negative" : ""}`}>{text}</span>
            {card.hint ? <span className="pill success small-pill">{card.hint}</span> : null}
          </div>
        );
      })}
    </div>
  );
}
