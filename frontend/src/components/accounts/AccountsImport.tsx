import { useEffect, useState } from "react";
import { api } from "../../api";
import { formatCount } from "../../format";
import type { BookSummary, Company, DatasetDetail, DatasetSummary, ImportResult, Ledger } from "../../types";

type Props = {
  company: Company;
  books: BookSummary[];
  datasets: DatasetSummary[];
  ledgers: Ledger[];
  onImported: () => void;
};

/** Turn uploaded Excel registers into vouchers, and load bank statements for reconciliation. */
export default function AccountsImport({ company, books, datasets, ledgers, onImported }: Props) {
  const [result, setResult] = useState<{ title: string; data: ImportResult } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(title: string, job: () => Promise<ImportResult>) {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult({ title, data: await job() });
      onImported();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel">
      <h2>Import from Excel</h2>
      <p className="muted small">
        Each register row becomes one voucher: sales rows post Dr customer, Cr Sales and Output GST; purchase rows post Dr Purchase and
        Input GST, Cr supplier. Customers and suppliers are created as ledgers with their GSTIN. Rows already imported are skipped, so
        importing the same sheet twice is safe. Upload files first with “+ Upload Excel”.
      </p>
      <div className="import-grid">
        <BookImport books={books} busy={busy} onRun={(id, name) => void run(`Imported "${name}"`, () => api.importBook(company.id, id))} />
        <SheetImport
          title="One register sheet"
          hint="A single sales or purchase register you uploaded."
          datasets={datasets}
          busy={busy}
          extra={(value, set) => (
            <label className="field">
              <span>It is a</span>
              <select value={value} onChange={(e) => set(e.target.value)}>
                <option value="sales">Sales register</option>
                <option value="purchases">Purchase register</option>
              </select>
            </label>
          )}
          defaultExtra="sales"
          onRun={(datasetId, table, label, register) =>
            void run(`Imported ${label}`, () => api.importRegister(company.id, datasetId, table, register as "sales" | "purchases"))
          }
        />
        <SheetImport
          title="Bank statement"
          hint="Statement lines are stored for bank reconciliation; they do not post vouchers."
          datasets={datasets}
          busy={busy}
          extra={(value, set) => (
            <label className="field">
              <span>Bank ledger</span>
              <select value={value} onChange={(e) => set(e.target.value)}>
                <option value="">Choose…</option>
                {ledgers
                  .filter((l) => l.group_name === "Bank Accounts" || l.group_name === "Bank OD A/c")
                  .map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.name}
                    </option>
                  ))}
              </select>
            </label>
          )}
          defaultExtra=""
          needsExtra
          onRun={(datasetId, table, label, bankId) =>
            void run(`Loaded statement ${label}`, () => api.importBank(company.id, datasetId, table, Number(bankId)))
          }
        />
      </div>
      {!ledgers.some((l) => l.group_name === "Bank Accounts" || l.group_name === "Bank OD A/c") ? (
        <p className="muted small">To load a bank statement, first create your bank account as a ledger under “Bank Accounts”.</p>
      ) : null}
      {busy ? <p className="muted small">Importing…</p> : null}
      {error ? <div className="callout warning">{error}</div> : null}
      {result ? (
        <div className="callout">
          <strong>{result.title}:</strong> {formatCount(result.data.created)} created, {formatCount(result.data.skipped)} skipped (already
          imported).
          {result.data.notes.length ? (
            <ul className="tight-list">
              {result.data.notes.map((n, i) => (
                <li key={i}>{n}</li>
              ))}
            </ul>
          ) : null}
          {result.data.problems.length ? (
            <>
              <p className="warning-text">{formatCount(result.data.problems.length)} row(s) need attention:</p>
              <ul className="tight-list">
                {result.data.problems.slice(0, 100).map((p, i) => (
                  <li key={i}>{p}</li>
                ))}
              </ul>
            </>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function BookImport({ books, busy, onRun }: { books: BookSummary[]; busy: boolean; onRun: (id: number, name: string) => void }) {
  const [id, setId] = useState("");
  const book = books.find((b) => String(b.id) === id);
  return (
    <div className="import-card">
      <h3>Sales + purchases set</h3>
      <p className="muted small">Both registers of a set you uploaded together.</p>
      {books.length ? (
        <>
          <label className="field">
            <span>Set</span>
            <select value={id} onChange={(e) => setId(e.target.value)}>
              <option value="">Choose…</option>
              {books.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </label>
          <button className="button primary" disabled={!book || busy} onClick={() => book && onRun(book.id, book.name)}>
            Import set
          </button>
        </>
      ) : (
        <p className="muted small">No sets yet. Upload with “+ Upload Excel” → Sales + Purchases.</p>
      )}
    </div>
  );
}

function SheetImport({ title, hint, datasets, busy, extra, defaultExtra, needsExtra, onRun }: {
  title: string;
  hint: string;
  datasets: DatasetSummary[];
  busy: boolean;
  extra: (value: string, set: (v: string) => void) => React.ReactNode;
  defaultExtra: string;
  needsExtra?: boolean;
  onRun: (datasetId: number, table: string, label: string, extra: string) => void;
}) {
  const [datasetId, setDatasetId] = useState("");
  const [detail, setDetail] = useState<DatasetDetail | null>(null);
  const [table, setTable] = useState("");
  const [extraValue, setExtraValue] = useState(defaultExtra);

  useEffect(() => {
    setDetail(null);
    setTable("");
    if (!datasetId) return;
    let live = true;
    api.dataset(Number(datasetId)).then(
      (d) => {
        if (!live) return;
        setDetail(d);
        setTable(d.sheets[0]?.table_name ?? "");
      },
      () => undefined,
    );
    return () => {
      live = false;
    };
  }, [datasetId]);

  const sheet = detail?.sheets.find((s) => s.table_name === table);
  return (
    <div className="import-card">
      <h3>{title}</h3>
      <p className="muted small">{hint}</p>
      <label className="field">
        <span>File</span>
        <select value={datasetId} onChange={(e) => setDatasetId(e.target.value)}>
          <option value="">Choose…</option>
          {datasets.map((d) => (
            <option key={d.id} value={d.id}>
              {d.filename}
            </option>
          ))}
        </select>
      </label>
      {detail && detail.sheets.length > 1 ? (
        <label className="field">
          <span>Sheet</span>
          <select value={table} onChange={(e) => setTable(e.target.value)}>
            {detail.sheets.map((s) => (
              <option key={s.table_name} value={s.table_name}>
                {s.sheet_name} ({formatCount(s.row_count)} rows)
              </option>
            ))}
          </select>
        </label>
      ) : null}
      {extra(extraValue, setExtraValue)}
      <button
        className="button primary"
        disabled={!sheet || busy || (needsExtra && !extraValue)}
        onClick={() => sheet && detail && onRun(detail.id, sheet.table_name, `${detail.filename} › ${sheet.sheet_name}`, extraValue)}
      >
        Import
      </button>
    </div>
  );
}
