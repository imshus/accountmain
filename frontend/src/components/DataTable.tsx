import { decimalsOf, formatCell, isIdentifierName } from "../format";
import type { Cell } from "../types";

type Props = {
  columns: string[];
  rows: Cell[][];
  caption?: string;
  /** Columns that hold reference numbers (the sheet profile's "identifier" role); names like Invoice No or HSN are found anyway. */
  identifiers?: ReadonlySet<string>;
};

/** Plain grid for previews and SQL results. Numbers are right-aligned and grouped; reference numbers are not. */
export default function DataTable({ columns, rows, caption, identifiers }: Props) {
  if (rows.length === 0) return <p className="muted small">No rows.</p>;
  // One precision per column, enough for its most precise value (1,250.00 not 1,250; 142.438 not 142.44).
  const decimals = columns.map((_, i) => decimalsOf(rows.map((row) => row[i])));
  // HSN 7113, invoice 100234, mobile 9876543210 and year 2025 are codes, not amounts: no lakh grouping.
  const plain = columns.map((column) => Boolean(identifiers?.has(column)) || isIdentifierName(column));
  return (
    <div className="table-scroll">
      <table className="data-table">
        {caption ? <caption>{caption}</caption> : null}
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column} scope="col">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {row.map((value, colIndex) =>
                plain[colIndex] ? (
                  <td key={colIndex}>{value === null ? "—" : String(value)}</td>
                ) : (
                  <td key={colIndex} className={typeof value === "number" ? "num" : undefined}>
                    {formatCell(value, decimals[colIndex])}
                  </td>
                ),
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
