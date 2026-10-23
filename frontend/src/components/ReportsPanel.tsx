import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { api } from "../api";
import { formatValue } from "../format";
import type { DatasetDetail, GstNet, Report, Setup, Sheet } from "../types";
import ReportBody from "./ReportBody";

type Props = { dataset: DatasetDetail; sheet: Sheet };

const PARAMS: Record<string, string[]> = {
  ledger: ["account", "start", "end"],
  day_book: ["start", "end"],
  profit_and_loss: ["opening_stock", "closing_stock"],
  balance_sheet: ["opening_stock", "closing_stock"],
  ageing: ["as_of"],
};

// The trial balance's label for accounts with no group; choosing it saves "" (clears the override).
const UNCLASSIFIED = "Unclassified";

const PARAM_LABELS: Record<string, string> = {
  account: "Account",
  start: "From",
  end: "To",
  opening_stock: "Opening stock ₹",
  closing_stock: "Closing stock ₹",
  as_of: "Age as on",
};

export default function ReportsPanel({ dataset, sheet }: Props) {
  const [setup, setSetup] = useState<Setup | null>(null);
  const [kind, setKind] = useState("ledger");
  const [params, setParams] = useState<Record<string, string>>({});
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [showRoles, setShowRoles] = useState(false);
  const [roleDraft, setRoleDraft] = useState<Record<string, string>>({});
  const table = sheet.table_name;
  // Only the latest report request may update the screen (a slow ledger must not replace a later trial balance).
  const latest = useRef(0);
  // Parameters are read when a report runs, so typing in them does not make a new run (or a new group editor).
  const paramsRef = useRef(params);
  useEffect(() => {
    paramsRef.current = params;
  }, [params]);
  // The classification the server last confirmed, and group changes not yet sent (see setGroup).
  const classification = useRef<Record<string, string>>({});
  const unsent = useRef<Record<string, string>>({});
  const saving = useRef<Promise<void>>(Promise.resolve());

  const applySetup = useCallback((result: Setup) => {
    classification.current = result.classification;
    setSetup(result);
  }, []);

  useEffect(() => {
    let cancelled = false;
    api.setup(dataset.id, table).then(
      (result) => {
        if (cancelled) return;
        applySetup(result);
        setRoleDraft(result.mapping);
      },
      (e: Error) => !cancelled && setError(e.message),
    );
    return () => {
      cancelled = true;
    };
  }, [dataset.id, table, applySetup]);

  const run = useCallback(async () => {
    const id = ++latest.current;
    setLoading(true);
    setError(null);
    try {
      const wanted = PARAMS[kind] ?? [];
      const answer = await api.report(dataset.id, table, kind, Object.fromEntries(wanted.map((p) => [p, paramsRef.current[p] ?? ""])));
      if (id === latest.current) setReport(answer);
    } catch (e) {
      if (id !== latest.current) return;
      setReport(null);
      setError((e as Error).message);
    } finally {
      if (id === latest.current) setLoading(false);
    }
  }, [dataset.id, table, kind]);
  // A queued group save re-runs whatever report is chosen by the time it finishes.
  const runRef = useRef(run);
  useEffect(() => {
    runRef.current = run;
  }, [run]);

  useEffect(() => {
    void run();
    // Re-run when the report type or sheet changes; parameter edits wait for the button.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind, table, sheet.row_count]);

  async function saveRoles() {
    try {
      const result = await api.saveSetup(dataset.id, table, { mapping: roleDraft });
      applySetup(result);
      setShowRoles(false);
      await run();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  // The server replaces the whole classification map, so saves go one at a time, each built on the
  // last confirmed map plus every change picked since: two quick changes both survive. "" clears an override.
  const setGroup = useCallback(
    (account: string, group: string) => {
      unsent.current = { ...unsent.current, [account]: group };
      saving.current = saving.current.then(async () => {
        const changes = unsent.current;
        if (!Object.keys(changes).length) return; // already sent with an earlier save
        unsent.current = {};
        try {
          applySetup(await api.saveSetup(dataset.id, table, { classification: { ...classification.current, ...changes } }));
          await runRef.current();
        } catch (e) {
          setError((e as Error).message);
        }
      });
    },
    [dataset.id, table, applySetup],
  );

  const groups = kind === "trial_balance" ? setup?.groups : undefined;
  const renderGroup = useCallback(
    (row: Record<string, unknown>): ReactNode => {
      const unclassified = row.source === "unclassified" || row.group === UNCLASSIFIED;
      return (
        <select
          className={`group-select${unclassified ? " unclassified" : ""}`}
          value={unclassified ? "" : String(row.group ?? "")}
          onChange={(e) => setGroup(String(row.account), e.target.value)}
          title={`Grouped by: ${row.source}`}
          aria-label={`Group of ${String(row.account)}`}
        >
          <option value="">Automatic / Unclassified</option>
          {(groups ?? []).map((g) => (
            <option key={g} value={g}>
              {g}
            </option>
          ))}
        </select>
      );
    },
    [groups, setGroup],
  );

  const columns = sheet.profile.columns.filter((c) => c.non_null > 0);

  return (
    <section className="panel">
      <div className="panel-heading">
        <h2>Accounting reports</h2>
        <button className="button small-button" onClick={() => setShowRoles((v) => !v)} disabled={!setup}>
          {showRoles ? "Close column roles" : "Column roles"}
        </button>
      </div>

      {showRoles && setup ? (
        <div className="roles-editor">
          <p className="muted small">
            Tell the reports which column holds what. Detected automatically; change any that are wrong. Leave a role empty if
            the sheet has no such column.
          </p>
          <div className="roles-grid">
            {Object.entries(setup.roles).map(([role, label]) => (
              <label key={role} className="field">
                <span>{label}</span>
                <select value={roleDraft[role] ?? ""} onChange={(e) => setRoleDraft((d) => ({ ...d, [role]: e.target.value }))}>
                  <option value="">—</option>
                  {columns.map((c) => (
                    <option key={c.name} value={c.name}>
                      {c.label}
                    </option>
                  ))}
                </select>
              </label>
            ))}
          </div>
          <div className="sql-actions">
            <button className="button primary" onClick={() => void saveRoles()}>
              Save roles
            </button>
            <button className="button" onClick={() => setRoleDraft(setup.detected)}>
              Use detected
            </button>
          </div>
        </div>
      ) : null}

      <div className="report-picker" role="tablist">
        {Object.entries(setup?.reports ?? { ledger: "Ledger" }).map(([key, label]) => (
          <button
            key={key}
            role="tab"
            aria-selected={kind === key}
            className={`chip${kind === key ? " chip-active" : ""}`}
            onClick={() => {
              if (key === kind) return;
              setReport(null); // never show one report under another report's name while loading
              setKind(key);
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {(PARAMS[kind] ?? []).length > 0 ? (
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
              {p === "account" ? (
                <select value={params.account ?? ""} onChange={(e) => setParams((s) => ({ ...s, account: e.target.value }))}>
                  <option value="">All entries</option>
                  {(report?.options.accounts ?? []).map((a) => (
                    <option key={a} value={a}>
                      {a}
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

      {report ? (
        <ReportBody report={report} renderGroup={groups ? renderGroup : undefined}>
          {kind === "gst" ? <GstNetPayable dataset={dataset} sheet={sheet} /> : null}
        </ReportBody>
      ) : null}
    </section>
  );
}

function GstNetPayable({ dataset, sheet }: { dataset: DatasetDetail; sheet: Sheet }) {
  const [sales, setSales] = useState(sheet.table_name);
  const [purchases, setPurchases] = useState("");
  const [result, setResult] = useState<GstNet | null>(null);
  const [error, setError] = useState<string | null>(null);
  const heads = ["igst", "cgst", "sgst", "cess"];

  async function calculate() {
    setError(null);
    try {
      setResult(await api.gstNet(dataset.id, sales, purchases));
    } catch (e) {
      setResult(null);
      setError((e as Error).message);
    }
  }

  return (
    <div className="report-section">
      <h4>Net GST payable (output tax − input tax credit)</h4>
      <div className="report-params">
        <label className="field">
          <span>Sales register (output tax)</span>
          <select value={sales} onChange={(e) => setSales(e.target.value)}>
            {dataset.sheets.map((s) => (
              <option key={s.table_name} value={s.table_name}>
                {s.sheet_name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Purchase register (input credit)</span>
          <select value={purchases} onChange={(e) => setPurchases(e.target.value)}>
            <option value="">None</option>
            {dataset.sheets.map((s) => (
              <option key={s.table_name} value={s.table_name}>
                {s.sheet_name}
              </option>
            ))}
          </select>
        </label>
        <button className="button primary" onClick={() => void calculate()}>
          Calculate
        </button>
      </div>
      {error ? <div className="callout warning">{error}</div> : null}
      {result ? (
        <>
          <div className="table-scroll">
            <table className="data-table compact">
              <thead>
                <tr>
                  <th>Head</th>
                  <th className="num">Output tax</th>
                  <th className="num">Input credit</th>
                  <th className="num">Cash payable (₹, rounded)</th>
                  <th className="num">Credit carried forward</th>
                </tr>
              </thead>
              <tbody>
                {heads.map((h) => (
                  <tr key={h}>
                    <td>{h.toUpperCase()}</td>
                    <td className="num">{formatValue(result.output_tax[h], "money")}</td>
                    <td className="num">{formatValue(result.input_credit[h], "money")}</td>
                    <td className="num">{formatValue(result.cash_payable[h], "money")}</td>
                    <td className="num">{formatValue(result.credit_carried_forward[h], "money")}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="row-total">
                  <td>Total cash payable</td>
                  <td />
                  <td />
                  <td className="num">{formatValue(result.total_cash_payable, "money")}</td>
                  <td />
                </tr>
              </tfoot>
            </table>
          </div>
          <p className="muted small">
            Credit is used in the legal order (Rule 88A): IGST credit first, CGST and SGST credit never cross; cash per head is
            rounded to the rupee (Section 170). {result.steps.length ? `Steps: ${result.steps.join("; ")}.` : ""}
          </p>
        </>
      ) : null}
    </div>
  );
}
