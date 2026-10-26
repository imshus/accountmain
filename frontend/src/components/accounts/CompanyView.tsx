import { useCallback, useEffect, useState } from "react";
import { api } from "../../api";
import { formatDate, formatTimestamp } from "../../format";
import type { AccountsMeta, BookSummary, Company, DatasetSummary, Ledger, Metal, Report } from "../../types";
import { Icon } from "../../ui";
import ReportBody from "../ReportBody";
import AccountsImport from "./AccountsImport";
import AccountsReports from "./AccountsReports";
import GoldPanel from "./GoldPanel";
import LedgersPanel from "./LedgersPanel";
import VoucherEntry from "./VoucherEntry";
import VouchersPanel from "./VouchersPanel";

type Props = {
  company: Company;
  books: BookSummary[];
  datasets: DatasetSummary[];
  onCompanyChange: (company: Company) => void;
  /** Open on this tab (e.g. "gold", "ledgers") instead of the dashboard. */
  initialTab?: string;
};

const TABS = [
  ["dashboard", "Home"],
  ["new", "New entry"],
  ["vouchers", "Entries"],
  ["reports", "Reports"],
  ["gold", "Gold"],
  ["ledgers", "Ledgers"],
  ["more", "More"],
] as const;
type Tab = (typeof TABS)[number][0] | "import" | "audit" | "settings";
const MORE = [
  ["import", "Import from Excel"],
  ["audit", "Audit trail"],
  ["settings", "Settings"],
] as const;

/** One company's double-entry books. */
const TAB_KEYS: string[] = [...TABS.map(([key]) => key), ...MORE.map(([key]) => key)];

export default function CompanyView({ company, books, datasets, onCompanyChange, initialTab }: Props) {
  const [tab, setTab] = useState<Tab>(initialTab && initialTab !== "more" && TAB_KEYS.includes(initialTab) ? (initialTab as Tab) : "dashboard");
  const [meta, setMeta] = useState<AccountsMeta | null>(null);
  const [ledgers, setLedgers] = useState<Ledger[]>([]);
  // Bumped whenever vouchers or ledgers change so open lists and reports reload.
  const [version, setVersion] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.accountsMeta().then(setMeta, (e: Error) => setError(e.message));
  }, []);

  useEffect(() => {
    api.ledgers(company.id).then(setLedgers, (e: Error) => setError(e.message));
  }, [company.id, version]);

  const changed = useCallback(() => setVersion((v) => v + 1), []);
  // The Gold tab appears once the books hold any metal (a jewellery import or a metal entry).
  const metals = (["gold", "silver"] as Metal[]).filter((m) => ledgers.some((l) => l.metal?.[m]));
  const inMore = tab === "more" || MORE.some(([key]) => key === tab);

  return (
    <div className="dataset-view">
      <header className="dataset-header">
        <div>
          <h1>{company.name}</h1>
          <p className="muted small">
            {company.gstin ? `GSTIN ${company.gstin} · state ${company.state_code}` : "No GSTIN set"} · books from{" "}
            {formatDate(company.fy_start)}
            {company.locked_until ? ` · locked up to ${formatDate(company.locked_until)}` : ""}
          </p>
        </div>
      </header>

      <nav className="view-tabs segmented" aria-label="Views">
        {TABS.filter(([key]) => key !== "gold" || metals.length).map(([key, label]) => {
          const active = key === "more" ? inMore : tab === key;
          return (
            <button key={key} className={active ? "active" : ""} onClick={() => setTab(key === "more" ? "import" : key)} aria-current={active ? "page" : undefined}>
              {label}
            </button>
          );
        })}
      </nav>
      {inMore ? (
        <nav className="sub-tabs" aria-label="More">
          {MORE.map(([key, label]) => (
            <button key={key} className={tab === key ? "active" : ""} onClick={() => setTab(key)}>
              {label}
            </button>
          ))}
        </nav>
      ) : null}
      {error ? <div className="callout warning">{error}</div> : null}

      {tab === "dashboard" ? <Dashboard company={company} refreshKey={version} onGo={setTab} /> : null}
      {tab === "new" ? <VoucherEntry company={company} ledgers={ledgers} onSaved={changed} /> : null}
      {tab === "vouchers" ? (
        <VouchersPanel company={company} voucherTypes={meta?.voucher_types ?? []} refreshKey={version} onChanged={changed} />
      ) : null}
      {tab === "reports" ? <AccountsReports company={company} ledgers={ledgers} refreshKey={version} /> : null}
      {tab === "gold" ? <GoldPanel company={company} metals={metals.length ? metals : ["gold"]} refreshKey={version} /> : null}
      {tab === "ledgers" ? <LedgersPanel company={company} ledgers={ledgers} groups={meta?.groups ?? []} onChanged={changed} onCompanyChange={onCompanyChange} /> : null}
      {tab === "import" ? <AccountsImport company={company} books={books} datasets={datasets} ledgers={ledgers} onImported={changed} /> : null}
      {tab === "audit" ? <AuditPanel company={company} refreshKey={version} /> : null}
      {tab === "settings" ? <Settings company={company} onCompanyChange={onCompanyChange} /> : null}
    </div>
  );
}

function Dashboard({ company, refreshKey, onGo }: { company: Company; refreshKey: number; onGo: (tab: Tab) => void }) {
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.companyReport(company.id, "dashboard", {}).then(setReport, (e: Error) => setError(e.message));
  }, [company.id, refreshKey]);

  return (
    <section className="panel">
      {error ? <div className="callout warning">{error}</div> : null}
      {report ? <ReportBody report={report} /> : !error ? <p className="muted small">Working…</p> : null}
      <div className="sql-actions">
        <button className="button primary" onClick={() => onGo("new")}>
          + New entry
        </button>
        <button className="button" onClick={() => onGo("import")}>
          Import from Excel
        </button>
        <button className="button" onClick={() => onGo("reports")}>
          Reports
        </button>
      </div>
    </section>
  );
}

type AuditRow = Awaited<ReturnType<typeof api.audit>>[number];

function AuditPanel({ company, refreshKey }: { company: Company; refreshKey: number }) {
  const [rows, setRows] = useState<AuditRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.audit(company.id).then(setRows, (e: Error) => setError(e.message));
  }, [company.id, refreshKey]);

  return (
    <section className="panel">
      <h2>Audit trail</h2>
      <p className="muted small">Every change is logged with its time and before/after values. The log cannot be edited.</p>
      {error ? <div className="callout warning">{error}</div> : null}
      {rows ? (
        <div className="table-scroll">
          <table className="data-table compact">
            <thead>
              <tr>
                <th>When</th>
                <th>Action</th>
                <th>What</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td>{formatTimestamp(r.at)}</td>
                  <td>{r.action}</td>
                  <td>
                    {r.entity}
                    {r.entity_id ? ` #${r.entity_id}` : ""}
                  </td>
                  <td>
                    {r.before_json || r.after_json ? (
                      <details>
                        <summary className="small">{describe(r)}</summary>
                        {r.before_json ? <pre className="json-block">Before: {pretty(r.before_json)}</pre> : null}
                        {r.after_json ? <pre className="json-block">After: {pretty(r.after_json)}</pre> : null}
                      </details>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}

function pretty(json: string): string {
  try {
    return JSON.stringify(JSON.parse(json), null, 1);
  } catch {
    return json;
  }
}

function describe(row: AuditRow): string {
  try {
    // A cancel logs only {"cancelled": true} as "after", so name the voucher from "before".
    const data = { ...JSON.parse(row.before_json ?? "{}"), ...JSON.parse(row.after_json ?? "{}") } as Record<string, unknown>;
    const bits = [data.vtype, data.number, data.name, data.date].filter((x) => typeof x === "string");
    return bits.length ? bits.join(" ") : "Show values";
  } catch {
    return "Show values";
  }
}

function Settings({ company, onCompanyChange }: { company: Company; onCompanyChange: (company: Company) => void }) {
  const [name, setName] = useState(company.name);
  const [gstin, setGstin] = useState(company.gstin ?? "");
  const [lock, setLock] = useState(company.locked_until ?? "");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function save(body: Parameters<typeof api.updateCompany>[1], done: string) {
    setError(null);
    setMessage(null);
    try {
      onCompanyChange(await api.updateCompany(company.id, body));
      setMessage(done);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <section className="panel">
      <h2>Company</h2>
      <div className="report-params">
        <label className="field grow">
          <span>Name</span>
          <input value={name} onChange={(e) => setName(e.target.value)} maxLength={200} />
        </label>
        <label className="field">
          <span>GSTIN</span>
          <input value={gstin} onChange={(e) => setGstin(e.target.value.toUpperCase())} maxLength={15} />
        </label>
        <button className="button primary" onClick={() => void save({ name, gstin: gstin || undefined }, "Saved.")} disabled={!name.trim()}>
          Save
        </button>
      </div>
      <h2>Lock the books</h2>
      <p className="muted small">
        After filing a return or closing a period, lock it: vouchers dated on or before this day can no longer be added, changed or
        cancelled.
      </p>
      <div className="report-params">
        <label className="field">
          <span>Locked up to</span>
          <input type="date" value={lock} onChange={(e) => setLock(e.target.value)} />
        </label>
        <button className="button primary" disabled={!lock} onClick={() => void save({ locked_until: lock }, `Books locked up to ${formatDate(lock)}.`)}>
          Lock
        </button>
        {company.locked_until ? (
          <button className="button" onClick={() => { setLock(""); void save({ locked_until: null }, "Lock removed."); }}>
            Remove lock
          </button>
        ) : null}
      </div>
      {error ? <div className="callout warning">{error}</div> : null}
      {message ? <p className="verify verified"><Icon name="check" size={14} stroke={2.2} /> {message}</p> : null}
    </section>
  );
}
