import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { formatCount, formatTimestamp } from "../format";
import type { AnalysisSpec, BookDetail, Health, RegisterType, Report } from "../types";
import AnalysePanel from "./AnalysePanel";
import ChatPanel from "./ChatPanel";
import ReportBody from "./ReportBody";

type Props = {
  book: BookDetail;
  health: Health | null;
  onBookChange: (book: BookDetail) => void;
  onOpenDataset: (datasetId: number) => void;
};

const PARAMS: Record<string, string[]> = {
  party_ledger: ["party"],
  profit_and_loss: ["opening_stock", "closing_stock"],
  ageing: ["as_of"],
  stock: ["measure"],
};
const PARAM_LABELS: Record<string, string> = {
  party: "Party",
  measure: "Count stock by",
  opening_stock: "Opening stock ₹",
  closing_stock: "Closing stock ₹",
  as_of: "Age as on",
};
const REGISTER_LABEL: Record<RegisterType, string> = { sales: "Sales", purchases: "Purchases", unused: "Not used" };
const KEY_ROLES = [
  ["date", "Date"],
  ["account", "Party"],
  ["taxable", "Taxable value"],
  ["invoice_value", "Invoice value"],
  ["cgst", "CGST"],
  ["sgst", "SGST"],
  ["igst", "IGST"],
  ["item", "Item"],
] as const;

const SUGGESTIONS = [
  "Compare sales and purchases month by month.",
  "Which items did we sell more of than we bought?",
  "What is the net GST payable after input tax credit?",
  "Which customers are also suppliers, and what is the net balance with each?",
  "Which supplier did we buy the most from, and what share of purchases is that?",
];

/** A sales register and a purchase register compared and combined. */
export default function BooksView({ book, health, onBookChange, onOpenDataset }: Props) {
  const [view, setView] = useState<"reports" | "analyse" | "chat" | "sheets">("reports");
  // Analyse stays mounted once opened; the AI's analyses open in it.
  const [analyse, setAnalyse] = useState<{ key: number; spec: AnalysisSpec | null } | null>(null);
  const openAnalyse = (spec: AnalysisSpec | null) => {
    setAnalyse((current) => ({ key: (current?.key ?? 0) + (spec ? 1 : 0), spec: spec ?? current?.spec ?? null }));
    setView("analyse");
  };
  const [kind, setKind] = useState<string>("compare");
  const [params, setParams] = useState<Record<string, string>>({});
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const sales = book.sheets.filter((s) => s.register_type === "sales");
  const purchases = book.sheets.filter((s) => s.register_type === "purchases");
  const isReport = view === "reports";
  // Only the latest report request may update the screen (answers can arrive out of order).
  const latest = useRef(0);

  const run = useCallback(async () => {
    if (!(kind in book.reports)) return;
    const id = ++latest.current;
    setLoading(true);
    setError(null);
    try {
      const wanted = PARAMS[kind] ?? [];
      const answer = await api.bookReport(book.id, kind, Object.fromEntries(wanted.map((p) => [p, params[p] ?? ""])));
      if (id === latest.current) setReport(answer);
    } catch (e) {
      if (id !== latest.current) return;
      setReport(null);
      setError((e as Error).message);
    } finally {
      if (id === latest.current) setLoading(false);
    }
  }, [book.id, book.reports, kind, params]);

  useEffect(() => {
    void run();
    // Parameter edits wait for the Show button; switching report or changing sheets re-runs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind, book]);

  async function setRegister(table: string, register: RegisterType) {
    try {
      onBookChange(await api.setBookSheets(book.id, { [table]: register }));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="dataset-view">
      <header className="dataset-header">
        <div>
          <h1>{book.name}</h1>
          <p className="muted small">
            Sales: {sales.map((s) => `${s.filename} › ${s.sheet_name} (${formatCount(s.row_count)})`).join(", ") || "none"} · Purchases:{" "}
            {purchases.map((s) => `${s.filename} › ${s.sheet_name} (${formatCount(s.row_count)})`).join(", ") || "none"} · Created{" "}
            {formatTimestamp(book.created_at)}
          </p>
        </div>
      </header>

      <nav className="view-tabs segmented" aria-label="Views">
        {(
          [
            ["reports", "Reports"],
            ["analyse", "Analyse"],
            ["chat", "Ask AI"],
            ["sheets", "Sheets"],
          ] as const
        ).map(([key, label]) => (
          <button key={key} className={view === key ? "active" : ""} onClick={() => (key === "analyse" ? openAnalyse(null) : setView(key))} aria-current={view === key ? "page" : undefined}>
            {label}
          </button>
        ))}
      </nav>

      {analyse ? (
        <div hidden={view !== "analyse"}>
          <AnalysePanel key={analyse.key} initialSpec={analyse.spec} loadTables={() => api.bookFields(book.id)}
            run={(spec) => api.analyseBook(book.id, spec)} />
        </div>
      ) : null}

      <div hidden={view !== "chat"}>
        <ChatPanel
          onOpenAnalysis={openAnalyse}
          scope={`book-${book.id}`}
          stream={(messages, provider, onEvent, options) => api.bookChatStream(book.id, messages, provider, onEvent, options)}
          subject={book.name}
          tables={[...sales, ...purchases]}
          defaultTable={(sales[0] ?? purchases[0])?.table_name ?? ""}
          suggestionList={SUGGESTIONS}
          health={health}
          runSql={(sql) => api.bookSql(book.id, sql)}
        />
      </div>

      {isReport ? (
        <section className="panel">
          <label className="field report-choice">
            <span>Report</span>
            <select value={kind} onChange={(e) => { setReport(null); setKind(e.target.value); }}>
              {Object.entries(book.reports).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          {(PARAMS[kind] ?? []).length ? (
            <form
              className="report-params"
              onSubmit={(e) => {
                e.preventDefault();
                void run();
              }}
            >
              {(PARAMS[kind] ?? []).map((p) => (
                <label key={p} className="field">
                  <span>{PARAM_LABELS[p]}</span>
                  {p === "party" ? (
                    <select value={params.party ?? ""} onChange={(e) => setParams((s) => ({ ...s, party: e.target.value }))}>
                      <option value="">Choose a party…</option>
                      {report?.options.parties?.map((name) => (
                        <option key={name} value={name}>
                          {name}
                        </option>
                      ))}
                    </select>
                  ) : p === "measure" ? (
                    <select value={params.measure ?? ""} onChange={(e) => setParams((s) => ({ ...s, measure: e.target.value }))}>
                      <option value="">Automatic</option>
                      {report?.options.measures?.map((m) => (
                        <option key={m.name} value={m.name}>
                          {m.label}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type={p.endsWith("stock") ? "number" : "date"}
                      step={p.endsWith("stock") ? "0.01" : undefined}
                      value={params[p] ?? ""}
                      onChange={(e) => setParams((s) => ({ ...s, [p]: e.target.value }))}
                    />
                  )}
                </label>
              ))}
              <button className="button primary" type="submit" disabled={loading}>
                {loading ? "Working…" : "Show"}
              </button>
            </form>
          ) : null}
          {error ? <div className="callout warning">{error}</div> : null}
          {loading && !report ? <p className="muted small">Working…</p> : null}
          {report ? <ReportBody report={report} /> : null}
        </section>
      ) : null}

      {view === "sheets" ? (
        <section className="panel">
          <h2>Sheets in this set</h2>
          <p className="muted small">
            Mark each sheet as sales or purchases. The reports read the columns below; if one is wrong or missing, open the file and
            fix it under Reports → Column roles.
          </p>
          {error ? <div className="callout warning">{error}</div> : null}
          <div className="table-scroll">
            <table className="data-table compact">
              <thead>
                <tr>
                  <th>File › sheet</th>
                  <th className="num">Rows</th>
                  <th>Used as</th>
                  {KEY_ROLES.map(([, label]) => (
                    <th key={label}>{label}</th>
                  ))}
                  <th />
                </tr>
              </thead>
              <tbody>
                {book.sheets.map((s) => (
                  <tr key={s.table_name}>
                    <td>
                      {s.filename} › {s.sheet_name}
                    </td>
                    <td className="num">{formatCount(s.row_count)}</td>
                    <td>
                      <select value={s.register_type} onChange={(e) => void setRegister(s.table_name, e.target.value as RegisterType)}>
                        {(Object.keys(REGISTER_LABEL) as RegisterType[]).map((r) => (
                          <option key={r} value={r}>
                            {REGISTER_LABEL[r]}
                          </option>
                        ))}
                      </select>
                    </td>
                    {KEY_ROLES.map(([role]) => (
                      <td key={role} className={s.mapping[role] ? undefined : "muted"}>
                        {s.mapping[role] ?? "—"}
                      </td>
                    ))}
                    <td>
                      <button className="button small-button" onClick={() => onOpenDataset(s.dataset_id)}>
                        Open file
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </div>
  );
}
