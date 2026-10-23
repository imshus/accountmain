import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { decimalsOf, formatCell, formatCount, isIdentifierName } from "../format";
import type { DatasetDetail, RowsPage, Sheet } from "../types";

type Props = {
  dataset: DatasetDetail;
  sheet: Sheet;
  onSheetChanged: (sheet: Sheet) => void;
};

const PAGE = 50;

/** Browse, search, add and delete entries. Totals and reports are recalculated after every change. */
export default function EntriesPanel({ dataset, sheet, onSheetChanged }: Props) {
  const [page, setPage] = useState<RowsPage | null>(null);
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [adding, setAdding] = useState(false);
  const [busy, setBusy] = useState(false);
  const columns = sheet.profile.columns;
  const table = sheet.table_name;
  // Only the latest page request may update the screen (two quick clicks on Next can answer out of order).
  const latest = useRef(0);

  const load = useCallback(async () => {
    const id = ++latest.current;
    try {
      const answer = await api.rows(dataset.id, table, offset, PAGE, query);
      if (id !== latest.current) return;
      setPage(answer);
      setError(null);
    } catch (e) {
      if (id === latest.current) setError((e as Error).message);
    }
  }, [dataset.id, table, offset, query]);

  useEffect(() => {
    void load();
  }, [load, sheet.row_count]);

  async function addEntry() {
    setBusy(true);
    setError(null);
    try {
      onSheetChanged(await api.addRow(dataset.id, table, draft));
      setDraft({});
      setAdding(false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function deleteEntry(rowid: number) {
    if (!window.confirm("Delete this entry? Totals and reports will be recalculated.")) return;
    setBusy(true);
    try {
      onSheetChanged(await api.deleteRow(dataset.id, table, rowid));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const labels = Object.fromEntries(columns.map((c) => [c.name, c.label]));
  const shownColumns = page ? page.columns.slice(1) : [];

  const columnDecimals = (page?.rows[0] ?? []).slice(1).map((_, i) => decimalsOf(page!.rows.map((row) => row[i + 1])));
  // Invoice no, HSN, mobile, year…: shown as written, without lakh grouping.
  const identifiers = new Set(columns.filter((c) => c.role === "identifier" || isIdentifierName(c.name) || isIdentifierName(c.label)).map((c) => c.name));

  return (
    <section className="panel">
      <div className="panel-heading">
        <h2>Entries</h2>
        <div className="toolbar">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setOffset(0);
              setQuery(search.trim());
            }}
          >
            <input className="search" type="search" placeholder="Search entries…" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Search entries" />
          </form>
          <button className="button primary small-button" onClick={() => setAdding((v) => !v)}>
            {adding ? "Cancel" : "+ Add entry"}
          </button>
        </div>
      </div>

      {adding ? (
        <form
          className="entry-form"
          onSubmit={(e) => {
            e.preventDefault();
            void addEntry();
          }}
        >
          {columns.map((c) => (
            <label key={c.name} className="field">
              <span>{c.label}</span>
              <input
                type={c.kind === "date" ? "date" : "text"}
                inputMode={c.kind === "number" ? "decimal" : undefined}
                placeholder={c.kind === "number" ? "e.g. 1,250.00 or (500)" : ""}
                value={draft[c.name] ?? ""}
                onChange={(e) => setDraft((d) => ({ ...d, [c.name]: e.target.value }))}
              />
            </label>
          ))}
          <div className="entry-actions">
            <button className="button primary" type="submit" disabled={busy}>
              {busy ? "Saving…" : "Save entry"}
            </button>
            <span className="muted small">Amounts accept 1,23,456.78, (500) for minus, and "Dr"/"Cr".</span>
          </div>
        </form>
      ) : null}

      {error ? <div className="callout warning">{error}</div> : null}

      {page ? (
        <>
          <p className="muted small">
            {query ? `${formatCount(page.total)} entries match "${query}"` : `${formatCount(page.total)} entries`}
            {page.rows.length > 0 ? ` · showing ${formatCount(page.offset + 1)}–${formatCount(page.offset + page.rows.length)}` : ""}
          </p>
          {page.rows.length ? (
            <div className="table-scroll">
              {/* One precision per column, enough for its most precise value on this page. */}
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col" aria-label="Delete" />
                    {shownColumns.map((c) => (
                      <th key={c} scope="col">
                        {labels[c] ?? c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {page.rows.map((row) => (
                    <tr key={String(row[0])}>
                      <td>
                        <button className="icon-button" onClick={() => void deleteEntry(Number(row[0]))} disabled={busy} aria-label="Delete entry" title="Delete entry">
                          ×
                        </button>
                      </td>
                      {row.slice(1).map((value, i) =>
                        identifiers.has(shownColumns[i]) ? (
                          <td key={i}>{value === null ? "—" : String(value)}</td>
                        ) : (
                          <td key={i} className={typeof value === "number" ? "num" : undefined}>
                            {formatCell(value, columnDecimals[i])}
                          </td>
                        ),
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="muted small">No entries.</p>
          )}
          <div className="pager">
            <button className="button small-button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>
              ← Previous
            </button>
            <button className="button small-button" disabled={offset + PAGE >= page.total} onClick={() => setOffset(offset + PAGE)}>
              Next →
            </button>
          </div>
        </>
      ) : null}
    </section>
  );
}
