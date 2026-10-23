import { useCallback, useEffect, useState } from "react";
import { api } from "../../api";
import type { Company, Ledger, Report } from "../../types";
import ReportBody from "../ReportBody";

type Props = {
  company: Company;
  ledgers: Ledger[];
  refreshKey: number;
};

const REPORT_GROUPS: [string, [string, string][]][] = [
  ["Final accounts", [["trial_balance", "Trial balance"], ["profit_and_loss", "Profit & loss"], ["balance_sheet", "Balance sheet"]]],
  ["Books", [["day_book", "Day book"], ["ledger", "Ledger of an account"], ["cash_bank_book", "Cash / bank book"]]],
  ["Customers and suppliers", [["receivables", "Who owes us (receivables)"], ["payables", "Whom we owe (payables)"]]],
  ["GST", [["gstr1", "GSTR-1 (sales)"], ["gstr3b", "GSTR-3B (tax to pay)"]]],
  ["Bank", [["bank_reconciliation", "Bank reconciliation"]]],
];

const PARAMS: Record<string, string[]> = {
  day_book: ["start", "end", "vtype"],
  ledger: ["ledger_id", "start", "end"],
  cash_bank_book: ["ledger_id", "start", "end"],
  trial_balance: ["start", "end"],
  profit_and_loss: ["start", "end", "opening_stock", "closing_stock"],
  balance_sheet: ["as_of", "opening_stock", "closing_stock"],
  receivables: ["as_of"],
  payables: ["as_of"],
  gstr1: ["start", "end"],
  gstr3b: ["start", "end"],
  bank_reconciliation: ["ledger_id", "as_of"],
};
const LABELS: Record<string, string> = {
  start: "From",
  end: "To",
  as_of: "As on",
  vtype: "Voucher type",
  ledger_id: "Ledger",
  opening_stock: "Opening stock ₹ (blank = from books)",
  closing_stock: "Closing stock ₹",
};
const BANK_GROUPS = new Set(["Bank Accounts", "Bank OD A/c"]);
const CASH_BANK_GROUPS = new Set(["Cash-in-Hand", ...BANK_GROUPS]);

function iso(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** Quick periods: GST returns are monthly, the final accounts yearly. */
function periods(fyStart: string): [string, string, string][] {
  const now = new Date();
  const month = (offset: number) => {
    const first = new Date(now.getFullYear(), now.getMonth() + offset, 1);
    return [iso(first), iso(new Date(first.getFullYear(), first.getMonth() + 1, 0))];
  };
  const fy = new Date(`${fyStart}T00:00:00`);
  const fyEnd = new Date(fy.getFullYear() + 1, fy.getMonth(), 0);
  return [
    ["This month", ...month(0)] as [string, string, string],
    ["Last month", ...month(-1)] as [string, string, string],
    ["Books year", iso(fy), iso(fyEnd)],
  ];
}

export default function AccountsReports({ company, ledgers, refreshKey }: Props) {
  const [kind, setKind] = useState("trial_balance");
  const [params, setParams] = useState<Record<string, string>>({});
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const wanted = PARAMS[kind] ?? [];

  const run = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setReport(await api.companyReport(company.id, kind, Object.fromEntries(wanted.map((p) => [p, params[p] ?? ""]))));
    } catch (e) {
      setReport(null);
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [company.id, kind, params, wanted]);

  useEffect(() => {
    void run();
    // Parameter edits wait for the Show button; a new report or new vouchers re-run it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind, refreshKey]);

  const ledgerChoices =
    report?.options.ledgers ??
    ledgers
      .filter((l) => (kind === "bank_reconciliation" ? BANK_GROUPS.has(l.group_name) : kind === "cash_bank_book" ? CASH_BANK_GROUPS.has(l.group_name) : true))
      .map((l) => ({ id: l.id, name: l.name, group: l.group_name }));

  return (
    <section className="panel">
      <label className="field report-choice">
        <span>Report</span>
        <select
          value={kind}
          onChange={(e) => {
            setReport(null);
            setKind(e.target.value);
          }}
        >
          {REPORT_GROUPS.map(([group, items]) => (
            <optgroup key={group} label={group}>
              {items.map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
      </label>
      <form
        className="report-params"
        onSubmit={(e) => {
          e.preventDefault();
          void run();
        }}
      >
        {wanted.map((p) => (
          <label key={p} className={p === "ledger_id" ? "field grow" : "field"}>
            <span>{LABELS[p]}</span>
            {p === "ledger_id" ? (
              <select value={params.ledger_id ?? ""} onChange={(e) => setParams((s) => ({ ...s, ledger_id: e.target.value }))}>
                <option value="">Choose…</option>
                {ledgerChoices.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.name} ({l.group})
                  </option>
                ))}
              </select>
            ) : p === "vtype" ? (
              <select value={params.vtype ?? ""} onChange={(e) => setParams((s) => ({ ...s, vtype: e.target.value }))}>
                <option value="">All</option>
                {(report?.options.voucher_types ?? []).map((t) => (
                  <option key={t}>{t}</option>
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
        {wanted.includes("start") ? (
          <div className="field">
            <span>Quick period</span>
            <div className="sql-actions">
              {periods(company.fy_start).map(([label, start, end]) => (
                <button key={label} type="button" className="button small-button" onClick={() => setParams((s) => ({ ...s, start, end }))}>
                  {label}
                </button>
              ))}
            </div>
          </div>
        ) : null}
        <button className="button primary" type="submit" disabled={loading}>
          {loading ? "Working…" : "Show"}
        </button>
      </form>
      {wanted.includes("start") && !params.start && !params.end ? (
        <p className="muted small">Blank dates mean everything from the day the books begin.</p>
      ) : null}
      {error ? <div className="callout warning">{error}</div> : null}
      {loading && !report ? <p className="muted small">Working…</p> : null}
      {report ? <ReportBody report={report} /> : null}
    </section>
  );
}
