import { formatValue } from "../format";
import type { SummaryTable } from "../types";

/** Monthly / category summaries from the backend. A "share" column is drawn as a bar. */
export default function SummaryTableView({ table }: { table: SummaryTable }) {
  return (
    <div className="table-scroll">
      <table className="data-table compact">
        <thead>
          <tr>
            {table.columns.map((column) => (
              <th key={column.key} scope="col" className={column.format === "text" ? undefined : "num"}>
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.rows.map((row, index) => (
            <tr key={index}>
              {table.columns.map((column) => {
                const value = row[column.key];
                if (column.format === "percent" && typeof value === "number") {
                  return (
                    <td key={column.key} className="num share-cell">
                      <span className="share-bar" style={{ width: `${Math.round(value * 100)}%` }} />
                      <span className="share-value">{formatValue(value, "percent")}</span>
                    </td>
                  );
                }
                const text = formatValue(value, column.format);
                const negative = typeof value === "number" && text.startsWith("-");
                return (
                  <td
                    key={column.key}
                    className={[column.format === "text" ? "" : "num", negative ? "negative" : ""].join(" ").trim() || undefined}
                  >
                    {text}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
