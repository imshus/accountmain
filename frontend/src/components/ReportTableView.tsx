import { memo, useMemo, useState, type ReactNode } from "react";
import { isApp } from "../api";
import { decimalsOf, formatCount, formatValue } from "../format";
import type { Cell, ReportFormat, ReportTable } from "../types";

type Props = {
  table: ReportTable;
  /** Optional editor for "group" cells (trial balance account groups). */
  renderGroup?: (row: Record<string, unknown>) => ReactNode;
};

function csvCell(value: unknown): string {
  const text = value === null || value === undefined ? "" : String(value);
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

const BOM = "﻿"; // lets Excel open the CSV as UTF-8 (₹, names in Hindi)

/** Download a report table as CSV (amounts unformatted, so Excel can add them up).
 *  In the Android app, where downloads are not possible, the file goes to the share sheet instead. */
export async function downloadCsv(table: ReportTable, filename: string) {
  const lines = [table.columns.map((c) => csvCell(c.label)).join(",")];
  for (const row of [...table.rows, ...(table.total ? [table.total] : [])]) {
    lines.push(table.columns.map((c) => csvCell(row[c.key])).join(","));
  }
  if (isApp) {
    const [{ Directory, Encoding, Filesystem }, { Share }] = await Promise.all([import("@capacitor/filesystem"), import("@capacitor/share")]);
    const name = filename.replace(/[\\/:*?"<>|]+/g, "-");
    const file = await Filesystem.writeFile({ path: name, data: BOM + lines.join("\r\n"), directory: Directory.Cache, encoding: Encoding.UTF8 });
    await Share.share({ title: name, url: file.uri, dialogTitle: "Save or send the CSV" });
    return;
  }
  const url = URL.createObjectURL(new Blob(["﻿" + lines.join("\r\n")], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

/** Rows drawn at a time: a whole-sheet ledger can have tens of thousands, which freezes the phone. */
export const ROW_PAGE = 300;

/** How many rows of `rows` to draw; starts again at one page whenever a new list arrives. */
export function useRowLimit(rows: readonly unknown[]) {
  const [state, setState] = useState({ rows, limit: ROW_PAGE });
  let limit = state.limit;
  if (state.rows !== rows) {
    limit = ROW_PAGE;
    setState({ rows, limit });
  }
  return [limit, () => setState((s) => ({ ...s, limit: s.limit + ROW_PAGE }))] as const;
}

/** "Showing 300 of 30,000 rows · Show 300 more" under a table that is not fully drawn (the CSV has every row). */
export function MoreRows({ shown, total, onMore }: { shown: number; total: number; onMore: () => void }) {
  if (shown >= total) return null;
  return (
    <div className="more-rows">
      <span className="muted small">
        Showing {formatCount(shown)} of {formatCount(total)} rows · Download CSV has all of them
      </span>
      <button type="button" className="button small-button" onClick={onMore}>
        Show {formatCount(Math.min(ROW_PAGE, total - shown))} more
      </button>
    </div>
  );
}

function ReportTableView({ table, renderGroup }: Props) {
  const [limit, showMore] = useRowLimit(table.rows);
  const rows = table.rows.length > limit ? table.rows.slice(0, limit) : table.rows;
  // One precision per "number" column (weights keep 3 decimals, quantities what they have), from every row.
  const decimals = useMemo(() => {
    const out: Record<string, number> = {};
    for (const c of table.columns) {
      if (c.format === "number") out[c.key] = decimalsOf([...table.rows.map((r) => r[c.key]), table.total?.[c.key]]);
    }
    return out;
  }, [table]);
  const cell = (value: Cell | undefined, format: ReportFormat, key: string) =>
    value === undefined || value === null ? "" : formatValue(value, format, decimals[key]);
  return (
    <>
      <div className="table-scroll report-table">
        <table className="data-table compact">
          <thead>
            <tr>
              {table.columns.map((c) => (
                <th key={c.key} scope="col" className={c.format === "text" || c.format === "group" || c.format === "date" ? undefined : "num"}>
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={index} className={row._kind ? `row-${row._kind}` : undefined}>
                {table.columns.map((c) => {
                  const value = row[c.key];
                  if (c.format === "group" && renderGroup) return <td key={c.key}>{renderGroup(row)}</td>;
                  const numeric = typeof value === "number";
                  const text = cell(value, c.format, c.key);
                  // Red only when the shown figure is negative (not for -0.001 that shows as 0.00).
                  const negative = numeric && text.startsWith("-") && c.format !== "drcr" && c.format !== "weight_drcr";
                  return (
                    <td key={c.key} className={[numeric ? "num" : "", negative ? "negative" : ""].join(" ").trim() || undefined}>
                      {text}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
          {table.total ? (
            <tfoot>
              <tr className="row-total">
                {table.columns.map((c) => {
                  const value = table.total?.[c.key];
                  return (
                    <td key={c.key} className={typeof value === "number" ? "num" : undefined}>
                      {cell(value, c.format, c.key)}
                    </td>
                  );
                })}
              </tr>
            </tfoot>
          ) : null}
        </table>
      </div>
      <MoreRows shown={rows.length} total={table.rows.length} onMore={showMore} />
    </>
  );
}

// Memoised: typing in a report's From/To/stock fields must not redraw an unchanged table.
export default memo(ReportTableView);
