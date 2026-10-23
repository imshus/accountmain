import { useEffect, useMemo, useState } from "react";
import { api } from "../../api";
import { formatDate, formatValue } from "../../format";
import type { AccountsMeta, Company, Ledger } from "../../types";

type Props = {
  company: Company;
  ledgers: Ledger[];
  groups: AccountsMeta["groups"];
  onChanged: () => void;
  /** Called with the saved company after the books-start date changes. */
  onCompanyChange?: (company: Company) => void;
};

const EMPTY = { name: "", group: "Sundry Debtors", opening: "", side: "Dr", gstin: "", state: "", credit_days: "", gold: "", goldSide: "Dr" };
// Ledgers that can hold metal: parties (metal owed) and stock (metal in hand).
const METAL_GROUPS = new Set(["Sundry Debtors", "Sundry Creditors", "Stock-in-Hand"]);
const GSTIN_LIKE = /^[0-9]{2}[0-9A-Z]{13}$/;

/** Chart of accounts: ledgers under the 28 standard groups, with opening and current balances. */
export default function LedgersPanel({ company, ledgers, groups, onChanged, onCompanyChange }: Props) {
  const [form, setForm] = useState(EMPTY);
  const [states, setStates] = useState<AccountsMeta["states"]>([]);
  const [booksFrom, setBooksFrom] = useState(company.fy_start);
  const [savedBooksFrom, setSavedBooksFrom] = useState(company.fy_start);
  const [editing, setEditing] = useState<number | null>(null);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const isParty = form.group === "Sundry Debtors" || form.group === "Sundry Creditors";
  const holdsMetal = METAL_GROUPS.has(form.group);
  const showGold = ledgers.some((l) => l.metal?.gold);
  // Income and expense ledgers have no opening balance (an old one is still shown so it can be cleared).
  const plGroup = ["income", "expense"].includes(groups.find((g) => g.name === form.group)?.nature ?? "");
  // A GSTIN's first two digits are the party's state, so the State list is only needed without one.
  const gstinState = GSTIN_LIKE.test(form.gstin) ? form.gstin.slice(0, 2) : "";
  const stateName = useMemo(() => new Map(states.map((s) => [s.code, s.name])), [states]);

  useEffect(() => {
    api.accountsMeta().then((m) => setStates(m.states ?? []), () => setStates([]));
  }, []);

  useEffect(() => {
    setBooksFrom(company.fy_start);
    setSavedBooksFrom(company.fy_start);
  }, [company.fy_start]);

  const grouped = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    const list = needle ? ledgers.filter((l) => l.name.toLowerCase().includes(needle) || l.group_name.toLowerCase().includes(needle)) : ledgers;
    const byGroup = new Map<string, Ledger[]>();
    for (const l of list) byGroup.set(l.group_name, [...(byGroup.get(l.group_name) ?? []), l]);
    return [...byGroup.entries()];
  }, [ledgers, filter]);

  const totals = useMemo(
    () => ledgers.reduce((t, l) => ({ opening: t.opening + l.opening_paise, closing: t.closing + l.closing_paise }), { opening: 0, closing: 0 }),
    [ledgers],
  );

  function edit(ledger: Ledger) {
    setEditing(ledger.id);
    setMessage(null);
    setForm({
      name: ledger.name,
      group: ledger.group_name,
      opening: ledger.opening_paise ? (Math.abs(ledger.opening_paise) / 100).toFixed(2) : "",
      side: ledger.opening_paise < 0 ? "Cr" : "Dr",
      gstin: ledger.gstin ?? "",
      state: ledger.state_code ?? "",
      credit_days: ledger.credit_days == null ? "" : String(ledger.credit_days),
      gold: ledger.metal?.gold?.opening_mg ? (Math.abs(ledger.metal.gold.opening_mg) / 1000).toFixed(3) : "",
      goldSide: (ledger.metal?.gold?.opening_mg ?? 0) < 0 ? "Cr" : "Dr",
    });
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      const amount = form.opening.replace(/[₹,\s]/g, "");
      const saved = await api.saveLedger(company.id, editing, {
        name: form.name,
        group: form.group,
        opening: amount ? `${form.side === "Cr" ? "-" : ""}${amount}` : "0",
        gstin: form.gstin || undefined,
        state_code: isParty ? gstinState || form.state || null : null,
        credit_days: form.credit_days ? Number(form.credit_days) : null,
        ...(holdsMetal ? { opening_gold: form.gold.trim() ? `${form.goldSide === "Cr" ? "-" : ""}${form.gold.replace(/[,\s]/g, "")}` : "0" } : {}),
      });
      setMessage(`${editing ? "Updated" : "Created"} ${saved.name} under ${saved.group_name}.`);
      setForm({ ...EMPTY, group: form.group });
      setEditing(null);
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function changeBooksFrom() {
    setError(null);
    setMessage(null);
    try {
      const saved = await api.updateCompany(company.id, { fy_start: booksFrom });
      setSavedBooksFrom(saved.fy_start);
      setMessage(`Books now begin on ${formatDate(saved.fy_start)}. Opening balances are as on that day.`);
      onCompanyChange?.(saved);
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <section className="panel">
      <h2>{editing ? "Edit ledger" : "New ledger"}</h2>
      <form className="report-params" onSubmit={(e) => void save(e)}>
        <label className="field grow">
          <span>Name</span>
          <input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} required maxLength={200} />
        </label>
        <label className="field">
          <span>Under group</span>
          <select value={form.group} onChange={(e) => setForm((f) => ({ ...f, group: e.target.value }))}>
            {groups.map((g) => (
              <option key={g.name} value={g.name}>
                {g.parent ? `${g.name} (${g.parent})` : g.name}
              </option>
            ))}
          </select>
        </label>
        {plGroup && !form.opening ? null : (
          <>
            <label className="field">
              <span>Opening balance ₹</span>
              <input inputMode="decimal" value={form.opening} onChange={(e) => setForm((f) => ({ ...f, opening: e.target.value }))} placeholder="0.00" />
            </label>
            <label className="field">
              <span>Dr / Cr</span>
              <select value={form.side} onChange={(e) => setForm((f) => ({ ...f, side: e.target.value }))}>
                <option>Dr</option>
                <option>Cr</option>
              </select>
            </label>
          </>
        )}
        {holdsMetal ? (
          <>
            <label className="field">
              <span>Opening gold (fine g)</span>
              <input inputMode="decimal" value={form.gold} onChange={(e) => setForm((f) => ({ ...f, gold: e.target.value }))} placeholder="0.000" />
            </label>
            <label className="field">
              <span>Dr / Cr</span>
              <select value={form.goldSide} onChange={(e) => setForm((f) => ({ ...f, goldSide: e.target.value }))}>
                <option value="Dr">{form.group === "Stock-in-Hand" ? "Dr (in hand)" : "Dr (owes us)"}</option>
                <option value="Cr">Cr (we owe)</option>
              </select>
            </label>
          </>
        ) : null}
        {isParty ? (
          <>
            <label className="field">
              <span>GSTIN</span>
              <input value={form.gstin} onChange={(e) => setForm((f) => ({ ...f, gstin: e.target.value.toUpperCase() }))} maxLength={15} />
            </label>
            <label className="field">
              <span>State (place of supply)</span>
              <select
                value={gstinState || form.state}
                disabled={Boolean(gstinState)}
                title={gstinState ? "Taken from the GSTIN" : "Needed for customers without a GSTIN: another state means IGST"}
                onChange={(e) => setForm((f) => ({ ...f, state: e.target.value }))}
              >
                <option value="">{company.state_code ? "Same as ours" : "Not set"}</option>
                {gstinState && !stateName.has(gstinState) ? <option value={gstinState}>{gstinState}</option> : null}
                {states.map((s) => (
                  <option key={s.code} value={s.code}>
                    {s.code} {s.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Credit days</span>
              <input type="number" min={0} max={365} value={form.credit_days} onChange={(e) => setForm((f) => ({ ...f, credit_days: e.target.value }))} />
            </label>
          </>
        ) : null}
        <button className="button primary" type="submit">
          {editing ? "Save changes" : "Create ledger"}
        </button>
        {editing ? (
          <button className="button" type="button" onClick={() => { setEditing(null); setForm(EMPTY); }}>
            Cancel
          </button>
        ) : null}
      </form>
      <p className="muted small">
        Assets normally have a Dr opening; liabilities and capital Cr. Income and expense ledgers have no opening: they start every
        financial year at zero, and earlier years' profit is carried to Capital. A party's state (from its GSTIN, or the State you
        choose when it has none) decides CGST+SGST (same state as you) or IGST (other state) on invoices.
      </p>
      {error ? <div className="callout warning">{error}</div> : null}
      {message ? <p className="verify verified">✓ {message}</p> : null}

      <h2>Books begin from</h2>
      <p className="muted small">
        Opening balances are as on this day, and no voucher can be dated earlier. It can be changed only while the company has no
        vouchers (for example, before importing a register of an earlier year).
      </p>
      <div className="report-params">
        <label className="field">
          <span>Books begin from</span>
          <input type="date" value={booksFrom} onChange={(e) => setBooksFrom(e.target.value)} required />
        </label>
        <button className="button" type="button" disabled={!booksFrom || booksFrom === savedBooksFrom} onClick={() => void changeBooksFrom()}>
          Change date
        </button>
      </div>

      <div className="report-head">
        <h2>Ledgers ({ledgers.length})</h2>
        <input className="search-input" placeholder="Filter ledgers…" value={filter} onChange={(e) => setFilter(e.target.value)} />
      </div>
      {totals.opening !== 0 ? (
        <div className="callout warning">
          Opening balances differ by {formatValue(totals.opening / 100, "drcr")}. Total Dr openings must equal total Cr openings; the
          trial balance shows the gap as "Difference in opening balances".
        </div>
      ) : null}
      <div className="table-scroll">
        <table className="data-table compact">
          <thead>
            <tr>
              <th>Ledger</th>
              <th>GSTIN / state</th>
              <th className="num">Credit days</th>
              <th className="num">Opening</th>
              <th className="num">Closing</th>
              {showGold ? <th className="num">Gold (fine)</th> : null}
              <th />
            </tr>
          </thead>
          <tbody>
            {grouped.map(([group, list]) => (
              <GroupRows
              key={group}
              group={group}
              nature={groups.find((g) => g.name === group)?.nature}
              list={list}
              onEdit={edit}
              showGold={showGold}
              stateName={stateName}
            />
            ))}
          </tbody>
          <tfoot>
            <tr className="row-total">
              <td colSpan={3}>Total (should be nil)</td>
              <td className="num">{formatValue(totals.opening / 100, "drcr")}</td>
              <td className="num">{formatValue(totals.closing / 100, "drcr")}</td>
              {showGold ? <td /> : null}
              <td />
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  );
}

function GroupRows({ group, nature, list, onEdit, showGold, stateName }: {
  group: string;
  nature?: string;
  list: Ledger[];
  onEdit: (l: Ledger) => void;
  showGold: boolean;
  stateName: Map<string, string>;
}) {
  return (
    <>
      <tr className="row-heading">
        <td colSpan={showGold ? 7 : 6}>
          {group} {nature ? <span className="muted small">· {nature}</span> : null}
        </td>
      </tr>
      {list.map((l) => (
        <tr key={l.id}>
          <td>{l.name}</td>
          <td>{l.gstin ?? (l.state_code ? `${l.state_code} ${stateName.get(l.state_code) ?? ""}`.trim() : "")}</td>
          <td className="num">{l.credit_days ?? ""}</td>
          <td className="num">{l.opening_paise ? formatValue(l.opening_paise / 100, "drcr") : ""}</td>
          <td className="num">{l.closing_paise ? formatValue(l.closing_paise / 100, "drcr") : "—"}</td>
          {showGold ? <td className="num">{l.metal?.gold?.closing_mg ? formatValue(l.metal.gold.closing_mg / 1000, "weight_drcr") : ""}</td> : null}
          <td>
            <button className="button small-button" onClick={() => onEdit(l)}>
              Edit
            </button>
          </td>
        </tr>
      ))}
    </>
  );
}
