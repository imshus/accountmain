import { decimalsOf, formatCount, formatDate, formatFixed } from "../format";
import type { Cell, ColumnProfile } from "../types";

const KIND_LABEL = { number: "Number", date: "Date", text: "Text" } as const;

type Preview = { columns: string[]; rows: Cell[][] };

/** Places for a number column: as many as its own values have (a Gross Wt column keeps 3: 5,432.105). */
function precision(column: ColumnProfile, preview?: Preview): number {
  const stats = column.stats && "sum" in column.stats ? column.stats : null;
  const index = preview ? preview.columns.indexOf(column.name) : -1;
  const sample = index >= 0 && preview ? preview.rows.map((row) => row[index]) : [];
  return decimalsOf([...sample, stats?.sum, stats?.min, stats?.max]);
}

function details(column: ColumnProfile, decimals: number): string {
  const stats = column.stats;
  if (column.role === "identifier") return "Reference number (not totalled)";
  if (!stats) return "—";
  if ("sum" in stats) {
    // Median and spread are derived figures: at least 2 places even for a whole-number column.
    const derived = Math.max(decimals, 2);
    return `Median ${formatFixed(stats.median, derived)} · Std dev ${formatFixed(stats.std, derived)}${
      stats.negatives ? ` · ${formatCount(stats.negatives)} negative` : ""
    }`;
  }
  if ("span_days" in stats) return `${formatDate(stats.min)} – ${formatDate(stats.max)} (${stats.span_days} days)`;
  return stats.top.map((t) => `${t.value} (${t.count})`).join(", ");
}

export default function ColumnStats({ columns, rowCount, preview }: { columns: ColumnProfile[]; rowCount: number; preview?: Preview }) {
  return (
    <div className="table-scroll">
      <table className="data-table compact">
        <thead>
          <tr>
            <th scope="col">Column</th>
            <th scope="col">Type</th>
            <th scope="col" className="num">Filled</th>
            <th scope="col" className="num">Unique</th>
            <th scope="col" className="num">Sum</th>
            <th scope="col" className="num">Average</th>
            <th scope="col" className="num">Min</th>
            <th scope="col" className="num">Max</th>
            <th scope="col">Details</th>
          </tr>
        </thead>
        <tbody>
          {columns.map((column) => {
            const stats = column.stats && "sum" in column.stats ? column.stats : null;
            // Reference numbers (invoice no, HSN) are not totalled: no sum or average, and min/max as written.
            const reference = column.role === "identifier" ? stats : null;
            const numeric = reference ? null : stats;
            const decimals = numeric ? precision(column, preview) : 0;
            return (
              <tr key={column.name}>
                <td>
                  <span className="col-label">{column.label}</span>
                  <code className="col-name">{column.name}</code>
                </td>
                <td>
                  <span className={`kind kind-${column.kind}`}>{KIND_LABEL[column.kind]}</span>
                </td>
                <td className="num">
                  {formatCount(column.non_null)}
                  {column.nulls ? <span className="muted"> / {formatCount(rowCount)}</span> : null}
                </td>
                <td className="num">{formatCount(column.unique)}</td>
                <td className="num">{numeric ? formatFixed(numeric.sum, decimals) : "—"}</td>
                <td className="num">{numeric ? formatFixed(numeric.mean, Math.max(decimals, 2)) : "—"}</td>
                <td className="num">{numeric ? formatFixed(numeric.min, decimals) : reference ? String(reference.min) : "—"}</td>
                <td className="num">{numeric ? formatFixed(numeric.max, decimals) : reference ? String(reference.max) : "—"}</td>
                <td className="details-cell">{details(column, decimals)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
