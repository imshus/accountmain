import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../api";
import type { Company, Metal, Report } from "../../types";
import ReportBody from "../ReportBody";

type Props = {
  company: Company;
  metals: Metal[];
  refreshKey: number;
};

const VIEWS = [
  ["metal_balances", "Who owes metal"],
  ["metal_ledger", "Party metal account"],
  ["stock_grams", "Stock in grams"],
] as const;
type View = (typeof VIEWS)[number][0];

/** Jewellers' metal books: fine-weight balances of every party, one party's metal account, stock in grams. */
export default function GoldPanel({ company, metals, refreshKey }: Props) {
  const [view, setView] = useState<View>("metal_balances");
  const [metal, setMetal] = useState<Metal>(metals[0] ?? "gold");
  const [ledger, setLedger] = useState("");
  const [rate, setRate] = useState("");
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  // Only the latest request may show its answer, so party A's slower account never appears under party B.
  const latest = useRef(0);

  const run = useCallback(async (nextView: View, nextLedger: string) => {
    const id = ++latest.current;
    setError(null);
    setLoading(true);
    try {
      const params: Record<string, string> = { metal };
      if (nextView === "metal_ledger") params.ledger_id = nextLedger;
      if (nextView === "metal_balances") params.rate = rate;
      const next = await api.companyReport(company.id, nextView, params);
      if (id === latest.current) setReport(next);
    } catch (e) {
      if (id !== latest.current) return;
      setReport(null);
      setError((e as Error).message);
    } finally {
      if (id === latest.current) setLoading(false);
    }
  }, [company.id, metal, rate]);

  useEffect(() => {
    void run(view, ledger);
    // The rate waits for the Show button.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, metal, refreshKey]);

  return (
    <section className="panel">
      <div className="panel-heading">
        <div className="segmented" role="tablist">
          {VIEWS.map(([key, label]) => (
            <button key={key} role="tab" aria-selected={view === key} className={view === key ? "active" : ""} onClick={() => { setReport(null); setView(key); }}>
              {label}
            </button>
          ))}
        </div>
        {metals.length > 1 ? (
          <select value={metal} onChange={(e) => setMetal(e.target.value as Metal)} aria-label="Metal">
            {metals.map((m) => (
              <option key={m} value={m}>
                {m === "gold" ? "Gold" : "Silver"}
              </option>
            ))}
          </select>
        ) : null}
      </div>
      {view === "metal_balances" ? (
        <form className="report-params" onSubmit={(e) => { e.preventDefault(); void run(view, ledger); }}>
          <label className="field">
            <span>Value at rate ₹ per g fine (optional)</span>
            <input inputMode="decimal" value={rate} onChange={(e) => setRate(e.target.value)} />
          </label>
          <button className="button" type="submit">
            Show
          </button>
        </form>
      ) : null}
      {view === "metal_ledger" ? (
        <div className="report-params">
          <label className="field grow">
            <span>Party</span>
            <select value={ledger} onChange={(e) => { setLedger(e.target.value); void run(view, e.target.value); }}>
              <option value="">Choose…</option>
              {report?.options.ledgers?.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.name}
                </option>
              ))}
            </select>
          </label>
        </div>
      ) : null}
      {error ? <div className="callout warning">{error}</div> : null}
      {report && loading ? <p className="muted small" role="status">Working…</p> : null}
      {report ? <ReportBody report={report} /> : !error ? <p className="muted small">Working…</p> : null}
    </section>
  );
}
